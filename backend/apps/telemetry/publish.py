from django.utils import timezone

from apps.alerts.dispatch import dispatch
from apps.common.realtime import gateway_group, group_send
from apps.common.timeutil import to_ms
from apps.plants.models import Machine

from .payloads import build_payloads


def publish_ingest(gateway, result):
    dispatch(result.events)
    if not result.machine_ids:
        return
    now = timezone.now()
    machines = Machine.objects.filter(pk__in=result.machine_ids, configured=True).select_related("gateway__plant", "state")
    group_send(
        [gateway_group(gateway.pk)],
        {"type": "machines.update", "serverTime": to_ms(now), "machines": build_payloads(machines, now)},
    )


def publish_machine_change(machine):
    now = timezone.now()
    machines = Machine.objects.filter(pk=machine.pk, configured=True).select_related("gateway__plant", "state")
    group_send(
        [gateway_group(machine.gateway_id)],
        {"type": "machines.update", "serverTime": to_ms(now), "machines": build_payloads(machines, now)},
    )
