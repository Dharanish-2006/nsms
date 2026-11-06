from datetime import date as date_cls, timedelta
from math import ceil

from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from apps.accounts.models import hash_secret
from apps.alerts.models import Alert
from apps.common.errors import ApiError
from apps.common.permissions import AdminWritesMixin
from apps.common.timeutil import local_day_start, to_ms
from apps.plants.access import accessible_machines
from apps.plants.models import Gateway, Machine

from .consolidate import consolidate_day
from .ingest import ingest
from .models import DailyReport, HourlyReport, Reading
from .payloads import build_payloads
from .publish import publish_ingest

RESERVED_MACHINE_IDS = {"usage"}  # would collide with /machines/usage
RANGE_DAYS = {"week": 7, "month": 30}
TREND_MAX_HOURS = 72
TREND_MAX_POINTS = 360


def health(request):
    """Load balancer / uptime check."""
    from django.http import JsonResponse

    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok"})


# --- Gateway ingestion ------------------------------------------------------
class IngestView(APIView):
    """POST /api/ingest: the endpoint the industrial gateway (or an AWS IoT Core rule /
    API Gateway in front of it) pushes readings to. Authenticated by `X-Gateway-Key`."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        key = request.headers.get("X-Gateway-Key", "").strip()
        gateway = Gateway.objects.select_related("plant").filter(api_key_hash=hash_secret(key)).first() if key else None
        if gateway is None:
            raise ApiError("Invalid gateway key.", 401, "invalid_gateway_key")
        if not gateway.enabled:
            raise ApiError("This gateway is disabled.", 403, "gateway_disabled")

        result = ingest(gateway, request.data, ip=BaseThrottle().get_ident(request) or None)
        publish_ingest(gateway, result)

        body = {
            "accepted": result.accepted,
            "rejected": result.rejected,
            "unknownMeters": result.unknown_meters,
        }
        # Nothing usable at all: tell the gateway plainly (4xx = do not retry this data).
        if result.accepted == 0 and result.rejected:
            return Response({"message": "No valid readings in the request.", "code": "validation", **body}, status=422)
        return Response(body, status=202)


# --- Machines ---------------------------------------------------------------
class MachineSerializer(serializers.Serializer):
    id = serializers.SlugField(max_length=64, required=False)
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(Machine.Type.values)
    ratedKw = serializers.FloatField(min_value=0, required=False, default=0)
    gatewayId = serializers.UUIDField()
    meterId = serializers.CharField(max_length=32)
    onThresholdKw = serializers.FloatField(min_value=0, required=False, default=0.5)
    position = serializers.IntegerField(min_value=0, max_value=1000, required=False, default=0)


def _one_payload(machine_id):
    machine = Machine.objects.select_related("gateway__plant", "state").get(pk=machine_id)
    return build_payloads([machine])[0]


def _unique_id(name):
    base = slugify(name)[:55] or "machine"
    candidate, n = base, 1
    while candidate in RESERVED_MACHINE_IDS or Machine.objects.filter(pk=candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


class MachineListView(AdminWritesMixin, APIView):
    def get(self, request):
        machines = accessible_machines(request.user).select_related("state")
        plant = request.query_params.get("plant")
        if plant:
            machines = machines.filter(gateway__plant__name=plant)
        now = timezone.now()
        return Response({"serverTime": to_ms(now), "machines": build_payloads(machines, now)})

    def post(self, request):
        """Admin: register a machine on a gateway."""
        s = MachineSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        gateway = get_object_or_404(Gateway, pk=d["gatewayId"])
        machine_id = d.get("id") or _unique_id(d["name"])
        if machine_id in RESERVED_MACHINE_IDS or Machine.objects.filter(pk=machine_id).exists():
            raise ApiError("A machine with that id already exists.", 409, "duplicate")
        try:
            with transaction.atomic():
                Machine.objects.create(
                    id=machine_id, name=d["name"].strip(), type=d["type"], rated_kw=d["ratedKw"],
                    gateway=gateway, meter_id=d["meterId"].strip(), on_threshold_kw=d["onThresholdKw"],
                    position=d["position"],
                )  # fmt: skip
        except IntegrityError:
            raise ApiError("That meter is already registered on this gateway.", 409, "meter_in_use") from None
        return Response(_one_payload(machine_id), status=201)


class MachineDetailView(AdminWritesMixin, APIView):
    def put(self, request, pk):
        machine = get_object_or_404(Machine, pk=pk)
        s = MachineSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "gatewayId" in d:
            machine.gateway = get_object_or_404(Gateway, pk=d["gatewayId"])
        for src, dst in (
            ("name", "name"), ("type", "type"), ("ratedKw", "rated_kw"), ("meterId", "meter_id"),
            ("onThresholdKw", "on_threshold_kw"), ("position", "position"),
        ):  # fmt: skip
            if src in d:
                setattr(machine, dst, d[src])
        try:
            with transaction.atomic():
                machine.save()
        except IntegrityError:
            raise ApiError("That meter is already registered on this gateway.", 409, "meter_in_use") from None
        return Response(_one_payload(machine.pk))

    patch = put

    def delete(self, request, pk):
        get_object_or_404(Machine, pk=pk).delete()  # cascades readings and reports
        return Response(status=204)


class UsageView(APIView):
    """Plant totals over the last 7 / 30 IST days (today included).

    consumedKwh = all energy metered; actualKwh = the part used while machines were running.
    """

    def get(self, request):
        days = RANGE_DAYS.get(request.query_params.get("range"))
        if not days:
            raise ApiError("Unknown range.", 422, "validation")
        machines = accessible_machines(request.user)
        plant = request.query_params.get("plant")
        if plant:
            machines = machines.filter(gateway__plant__name=plant)
        start = local_day_start(timezone.now(), days - 1)
        totals = HourlyReport.objects.filter(machine__in=machines.values("pk"), hour__gte=start).aggregate(
            consumed=Sum("kwh"), actual=Sum("run_kwh")
        )
        return Response(
            {"consumedKwh": round(totals["consumed"] or 0, 1), "actualKwh": round(totals["actual"] or 0, 1)}
        )


class TrendView(APIView):
    """[{t, pf, current, kw}] oldest first, averaged into at most ~360 buckets."""

    def get(self, request, pk):
        machine = get_object_or_404(accessible_machines(request.user), pk=pk)
        try:
            hours = int(request.query_params.get("hours", 6))
        except ValueError:
            hours = 0
        if not 1 <= hours <= TREND_MAX_HOURS:
            raise ApiError(f"hours must be between 1 and {TREND_MAX_HOURS}.", 422, "validation")

        bucket = max(settings.RAW_SAMPLE_INTERVAL_SEC, ceil(hours * 3600 / TREND_MAX_POINTS))
        since = timezone.now() - timedelta(hours=hours)

        buckets = {}
        rows = Reading.objects.filter(machine=machine, ts__gte=since).order_by("ts").values_list(
            "ts", "kw", "pf", "current", "on"
        )
        for ts, kw, pf, current, on in rows.iterator():
            b = buckets.setdefault(int(ts.timestamp() // bucket), [0, 0.0, 0.0, 0, 0.0])
            b[0] += 1
            b[1] += kw
            b[2] += current
            if on and pf:
                b[3] += 1
                b[4] += pf
        return Response(
            [
                {
                    "t": key * bucket * 1000,
                    "pf": round(pf_sum / pf_n, 3) if pf_n else 0,
                    "current": round(cur_sum / n, 2),
                    "kw": round(kw_sum / n, 2),
                }
                for key, (n, kw_sum, cur_sum, pf_n, pf_sum) in sorted(buckets.items())
            ]
        )


# --- Reports ----------------------------------------------------------------
class DailyReportView(APIView):
    """GET /api/reports/daily?plant=&date=YYYY-MM-DD : the consolidated report (default: today, IST)."""

    def get(self, request):
        today = timezone.localdate()
        raw = request.query_params.get("date")
        try:
            day = date_cls.fromisoformat(raw) if raw else today
        except ValueError:
            raise ApiError("date must look like 2026-11-06.", 422, "validation") from None
        if day > today:
            raise ApiError("That date is in the future.", 422, "validation")

        machines = accessible_machines(request.user)
        plant = request.query_params.get("plant")
        if plant:
            machines = machines.filter(gateway__plant__name=plant)
        machines = list(machines)
        ids = [m.pk for m in machines]

        have = set(DailyReport.objects.filter(date=day, machine_id__in=ids).values_list("machine_id", flat=True))
        # Today is still changing, and past days are built the first time they are asked for.
        missing = ids if day == today else [i for i in ids if i not in have]
        if missing:
            consolidate_day(day, missing)
        reports = {r.machine_id: r for r in DailyReport.objects.filter(date=day, machine_id__in=ids)}
        active = {}
        for machine_id in Alert.objects.filter(machine_id__in=ids, status=Alert.Status.ACTIVE).values_list("machine_id", flat=True):
            active[machine_id] = active.get(machine_id, 0) + 1

        rows = []
        for m in machines:
            r = reports.get(m.pk)
            rows.append(
                {
                    "machineId": m.pk,
                    "machineName": m.name,
                    "plant": m.gateway.plant.name,
                    "kwh": round(r.kwh, 2) if r else 0,
                    "runKwh": round(r.run_kwh, 2) if r else 0,
                    "kvarh": round(r.kvarh, 2) if r else 0,
                    "kvah": round(r.kvah, 2) if r else 0,
                    "runSeconds": int(r.run_seconds) if r else 0,
                    "avgKw": round(r.avg_kw, 2) if r else 0,
                    "maxKw": round(r.max_kw, 2) if r else 0,
                    "avgPf": round(r.avg_pf, 3) if r and r.avg_pf is not None else None,
                    "maxCurrent": round(r.max_current, 2) if r else 0,
                    "samples": r.samples if r else 0,
                    "activeAlerts": active.get(m.pk, 0),
                }
            )
        return Response(
            {
                "date": day.isoformat(),
                "plant": plant or None,
                "totalKwh": round(sum(r["kwh"] for r in rows), 2),
                "machines": rows,
            }
        )
