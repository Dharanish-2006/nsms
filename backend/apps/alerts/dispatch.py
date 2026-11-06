"""Deliver alert events: push to open dashboards and text the configured numbers."""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from apps.common.realtime import ADMIN_GROUP, gateway_group, group_send
from apps.common.sms import send_sms

from .models import PhoneNumber
from .serializers import alert_json

logger = logging.getLogger(__name__)

_sms_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="alert-sms")


def _message(alert):
    label = {"powerFactor": "power factor"}.get(alert.param, alert.param)
    return (
        f"{alert.severity.upper()} alert: {alert.machine.name} ({alert.machine.gateway.plant.name}) "
        f"{label} is {alert.reading:.2f}, below the {alert.limit_value:.2f} limit."
    )


def _send_all(numbers, text):
    for digits in numbers:
        try:
            send_sms(digits, text)
        except Exception:  # noqa: BLE001 - one bad number must not block the rest
            logger.exception("SMS to %s failed", digits)


def dispatch(events):
    """Call after the transaction that produced `events` has committed."""
    if not events:
        return
    numbers = None
    for event in events:
        alert = event.alert
        groups = [ADMIN_GROUP, gateway_group(alert.machine.gateway_id)]
        group_send(groups, {"type": "alert.event", "kind": event.kind, "alert": alert_json(alert)})

        if event.notify:
            if numbers is None:  # read in this thread; the worker never touches the database
                numbers = list(PhoneNumber.objects.values_list("digits", flat=True))
            if numbers:
                text = _message(alert)
                if settings.ALERT_SMS_ASYNC:
                    _sms_pool.submit(_send_all, numbers, text)
                else:
                    _send_all(numbers, text)


def refresh_all_dashboards():
    """Thresholds changed: ask every open dashboard to reload its alerts."""
    from apps.plants.models import Gateway

    groups = [ADMIN_GROUP] + [gateway_group(pk) for pk in Gateway.objects.values_list("pk", flat=True)]
    group_send(groups, {"type": "alerts.refresh"})
