import hmac
import logging
import re
from datetime import date as date_cls, timedelta
from math import ceil

from django.conf import settings
from django.db import connection
from django.db.models import Max, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView

from apps.accounts.models import hash_secret
from apps.alerts.models import Alert
from apps.common.errors import ApiError
from apps.common.permissions import IsPlantOwner
from apps.common.timeutil import local_day_start, to_ms
from apps.plants.access import accessible_machines, window_q
from apps.plants.models import Gateway, Machine
from apps.plants.services import register_unverified

from .consolidate import day_bounds
from .ingest import ingest
from .models import HourlyReport, Reading
from .payloads import build_payloads
from .publish import publish_ingest, publish_machine_change

logger = logging.getLogger(__name__)
SERIAL_RE = re.compile(r"^[A-Za-z0-9._-]{4,64}$")
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
def _store(gateway, data, request):
    """Shared by the HTTPS and the AWS IoT paths: store, publish live, and answer."""
    result = ingest(gateway, data, ip=BaseThrottle().get_ident(request) or None)
    publish_ingest(gateway, result)
    body = {"accepted": result.accepted, "rejected": result.rejected, "unknownMeters": result.unknown_meters}
    # Nothing usable at all: tell the sender plainly (4xx = do not retry this data).
    if result.accepted == 0 and result.rejected:
        return Response({"message": "No valid readings in the request.", "code": "validation", **body}, status=422)
    return Response(body, status=202)


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
        if not gateway.verified:
            raise ApiError("This gateway is waiting for the administrator to verify it.", 403, "gateway_not_verified")

        return _store(gateway, request.data, request)


class IotIngestView(APIView):
    """POST /api/iot/ingest: where an AWS IoT Core rule delivers what gateways publish over MQTT.

    The gateway publishes to `mill/<serial>/readings`; IoT Core authenticates it with its own
    certificate and its policy only lets it publish under its own serial, so the rule can trust
    the topic. The rule forwards `{"serial": topic(2), "readings": [...]}` with the shared secret
    in `X-IoT-Secret`. A serial we have not seen is registered as an unverified gateway, exactly
    like self-registration over HTTPS. See docs/AWS-IOT.md.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        expected = settings.IOT_RULE_SECRET
        if not expected:
            raise ApiError("AWS IoT ingest is turned off.", 404, "not_found")
        body = request.data if isinstance(request.data, dict) else {}

        # AWS asks the endpoint to confirm itself once, before a rule may use it. That request
        # carries no secret; log the token so the operator can confirm it with the AWS CLI.
        token = body.get("confirmationToken")
        if token and "readings" not in body:
            logger.warning("AWS IoT destination confirmation token: %s", token)
            return Response({"status": "confirmation-logged"})

        given = request.headers.get("X-IoT-Secret", "")
        if not hmac.compare_digest(given.encode(), expected.encode()):
            raise ApiError("Invalid IoT rule secret.", 401, "invalid_iot_secret")

        serial = body.get("serial")
        if not isinstance(serial, str) or not SERIAL_RE.match(serial):
            raise ApiError("A valid gateway serial is required.", 422, "validation")
        gateway, created = register_unverified(serial)
        if created:
            logger.info("Gateway %s registered itself over MQTT; waiting for verification.", serial)
        if not gateway.enabled:
            raise ApiError("This gateway is disabled.", 403, "gateway_disabled")
        if not gateway.verified:
            raise ApiError("This gateway is waiting for the administrator to verify it.", 403, "gateway_not_verified")
        return _store(gateway, {"readings": body.get("readings")}, request)


# --- Machines ---------------------------------------------------------------
class MachineEditSerializer(serializers.Serializer):
    """What a plant owner may change about their machine. Wiring (gateway, meter) is not theirs."""

    name = serializers.CharField(max_length=100, required=False)
    type = serializers.ChoiceField(Machine.Type.values, required=False)
    ratedKw = serializers.FloatField(min_value=0, max_value=100000, required=False)
    onThresholdKw = serializers.FloatField(min_value=0, required=False)


class MachineListView(APIView):
    permission_classes = [IsPlantOwner]

    def get(self, request):
        machines = accessible_machines(request.user).select_related("state")
        plant = request.query_params.get("plant")
        if plant:
            machines = machines.filter(gateway__plant__name=plant)
        now = timezone.now()
        return Response({"serverTime": to_ms(now), "machines": build_payloads(machines, now)})


class MachineDetailView(APIView):
    permission_classes = [IsPlantOwner]

    def put(self, request, pk):
        machine = get_object_or_404(accessible_machines(request.user), pk=pk)
        s = MachineEditSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        for src, dst in (("name", "name"), ("type", "type"), ("ratedKw", "rated_kw"), ("onThresholdKw", "on_threshold_kw")):
            if src in d:
                setattr(machine, dst, d[src])
        machine.save()
        machine = Machine.objects.select_related("gateway__plant", "state").get(pk=machine.pk)
        payload = build_payloads([machine])[0]
        publish_machine_change(machine)
        return Response(payload)

    patch = put


class UsageView(APIView):
    permission_classes = [IsPlantOwner]

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
        totals = HourlyReport.objects.filter(
            window_q(request.user), machine__in=machines.values("pk"), hour__gte=start
        ).aggregate(
            consumed=Sum("kwh"), actual=Sum("run_kwh")
        )
        return Response(
            {"consumedKwh": round(totals["consumed"] or 0, 1), "actualKwh": round(totals["actual"] or 0, 1)}
        )


class TrendView(APIView):
    permission_classes = [IsPlantOwner]

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
        rows = Reading.objects.filter(
            window_q(request.user, gateway_field="machine__gateway", time_field="ts", pad=timedelta(0)),
            machine=machine, ts__gte=since,
        ).order_by("ts").values_list(
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
    permission_classes = [IsPlantOwner]

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

        # Built from the hourly rows inside this owner's connection periods, so a previous
        # owner's hours on the same gateway never show up in their report.
        start, end = day_bounds(day)
        agg = (
            HourlyReport.objects.filter(window_q(request.user), machine_id__in=ids, hour__gte=start, hour__lt=end)
            .values("machine_id")
            .annotate(
                kwh=Sum("kwh"), run_kwh=Sum("run_kwh"), kvarh=Sum("kvarh"), kvah=Sum("kvah"),
                run_seconds=Sum("run_seconds"), samples=Sum("samples"), sum_kw=Sum("sum_kw"),
                max_kw=Max("max_kw"), max_current=Max("max_current"),
                pf_samples=Sum("pf_samples"), sum_pf=Sum("sum_pf"),
            )
        )  # fmt: skip
        reports = {r["machine_id"]: r for r in agg}
        active = {}
        for machine_id in Alert.objects.filter(machine_id__in=ids, status=Alert.Status.ACTIVE).values_list("machine_id", flat=True):
            active[machine_id] = active.get(machine_id, 0) + 1

        rows = []
        for m in machines:
            r = reports.get(m.pk)
            n = (r["samples"] or 0) if r else 0
            rows.append(
                {
                    "machineId": m.pk,
                    "machineName": m.name,
                    "plant": m.gateway.plant.name,
                    "kwh": round(r["kwh"] or 0, 2) if r else 0,
                    "runKwh": round(r["run_kwh"] or 0, 2) if r else 0,
                    "kvarh": round(r["kvarh"] or 0, 2) if r else 0,
                    "kvah": round(r["kvah"] or 0, 2) if r else 0,
                    "runSeconds": int(r["run_seconds"] or 0) if r else 0,
                    "avgKw": round(r["sum_kw"] / n, 2) if r and n else 0,
                    "maxKw": round(r["max_kw"] or 0, 2) if r else 0,
                    "avgPf": round(r["sum_pf"] / r["pf_samples"], 3) if r and r["pf_samples"] else None,
                    "maxCurrent": round(r["max_current"] or 0, 2) if r else 0,
                    "samples": n,
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
