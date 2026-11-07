"""Deliver alert events: push to open dashboards and text the configured numbers."""

import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings

from apps.common.realtime import gateway_group, group_send
from apps.common.sms import send_sms

from .models import NotificationSettings, PhoneNumber
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


def _numbers_for(owner_id):
    """The owner's SMS numbers, or none if they switched alerts off."""
    prefs = NotificationSettings.objects.filter(owner_id=owner_id).first()
    if prefs is not None and not prefs.alerts_enabled:
        return []
    return list(PhoneNumber.objects.filter(owner_id=owner_id).values_list("digits", flat=True))


def dispatch(events):
    """Call after the transaction that produced `events` has committed."""
    if not events:
        return
    numbers_by_gateway = {}
    for event in events:
        alert = event.alert
        gateway_id = alert.machine.gateway_id
        group_send([gateway_group(gateway_id)], {"type": "alert.event", "kind": event.kind, "alert": alert_json(alert)})

        if event.notify:
            if gateway_id not in numbers_by_gateway:  # read here; the worker never touches the database
                owner_id = alert.threshold.owner_id  # the limits that fired belong to the owner to text
                numbers_by_gateway[gateway_id] = _numbers_for(owner_id)
            numbers = numbers_by_gateway[gateway_id]
            if numbers:
                text = _message(alert)
                if settings.ALERT_SMS_ASYNC:
                    _sms_pool.submit(_send_all, numbers, text)
                else:
                    _send_all(numbers, text)


def refresh_all_dashboards(user):
    """Limits changed: ask this owner's open dashboards to reload their alerts."""
    from apps.plants.access import accessible_gateway_ids

    group_send([gateway_group(pk) for pk in accessible_gateway_ids(user)], {"type": "alerts.refresh"})
