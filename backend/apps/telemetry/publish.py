"""Push fresh machine data (and alert changes) to open dashboards."""

from django.utils import timezone

from apps.alerts.dispatch import dispatch
from apps.common.realtime import ADMIN_GROUP, gateway_group, group_send
from apps.common.timeutil import to_ms
from apps.plants.models import Machine

from .payloads import build_payloads


def publish_ingest(gateway, result):
    """Call AFTER the ingest transaction committed, so readers never see half a batch."""
    dispatch(result.events)
    if not result.machine_ids:
        return
    now = timezone.now()
    machines = Machine.objects.filter(pk__in=result.machine_ids).select_related("gateway__plant", "state")
    group_send(
        [ADMIN_GROUP, gateway_group(gateway.pk)],
        {"type": "machines.update", "serverTime": to_ms(now), "machines": build_payloads(machines, now)},
    )
