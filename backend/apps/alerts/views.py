from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import AdminWritesMixin
from apps.plants.access import accessible_machines

from . import engine
from .dispatch import dispatch, refresh_all_dashboards
from .models import Alert, PhoneNumber, Threshold
from .serializers import (
    PhoneSerializer,
    ThresholdSerializer,
    alert_json,
    phone_json,
    threshold_json,
)

RECOVERED_KEPT = 100  # most recent recovered alerts returned


def alerts_for(user, plant=None):
    """Alerts the user may see: active first (critical, then newest), then recovered."""
    machines = accessible_machines(user)
    if plant:
        machines = machines.filter(gateway__plant__name=plant)
    qs = Alert.objects.filter(machine__in=machines).select_related("machine__gateway__plant")
    active = qs.filter(status=Alert.Status.ACTIVE).annotate(
        sev=Case(When(severity="critical", then=Value(0)), default=Value(1), output_field=IntegerField())
    ).order_by("sev", "-since")
    recovered = qs.filter(status=Alert.Status.RECOVERED).order_by("-recovered_at")[:RECOVERED_KEPT]
    return [alert_json(a) for a in [*active, *recovered]]


class AlertListView(APIView):
    def get(self, request):
        return Response(alerts_for(request.user, request.query_params.get("plant")))




def _after_threshold_change():
    """Re-judge every machine against the new limits, then tell dashboards."""
    events = engine.reevaluate_all()
    transaction.on_commit(lambda: (dispatch(events), refresh_all_dashboards()))


class ThresholdListView(AdminWritesMixin, APIView):
    def get(self, request):
        return Response([threshold_json(t) for t in Threshold.objects.order_by("pk")])

    @transaction.atomic
    def post(self, request):
        s = ThresholdSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        s.check_unique(d)
        t = Threshold.objects.create(
            param=d["param"], machine=d["machine"], warning=d["warning"], critical=d["critical"]
        )
        _after_threshold_change()
        return Response(threshold_json(t), status=201)


class ThresholdDetailView(AdminWritesMixin, APIView):
    @transaction.atomic
    def put(self, request, pk):
        t = get_object_or_404(Threshold, pk=pk)
        s = ThresholdSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        s.check_unique(d, exclude_pk=t.pk)
        t.param, t.machine, t.warning, t.critical = d["param"], d["machine"], d["warning"], d["critical"]
        t.save()
        _after_threshold_change()
        return Response(threshold_json(t))

    @transaction.atomic
    def delete(self, request, pk):
        get_object_or_404(Threshold, pk=pk).delete()  # cascades its alerts
        _after_threshold_change()
        return Response(status=204)


class PhoneListView(AdminWritesMixin, APIView):
    def get(self, request):
        return Response([phone_json(p) for p in PhoneNumber.objects.order_by("pk")])

    def post(self, request):
        s = PhoneSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.check_unique(s.validated_data["digits"])
        p = PhoneNumber.objects.create(**s.validated_data)
        return Response(phone_json(p), status=201)


class PhoneDetailView(AdminWritesMixin, APIView):
    def put(self, request, pk):
        p = get_object_or_404(PhoneNumber, pk=pk)
        s = PhoneSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.check_unique(s.validated_data["digits"], exclude_pk=p.pk)
        p.digits, p.label = s.validated_data["digits"], s.validated_data["label"]
        p.save()
        return Response(phone_json(p))

    def delete(self, request, pk):
        get_object_or_404(PhoneNumber, pk=pk).delete()
        return Response(status=204)
