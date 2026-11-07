"""Alert evaluation. Runs on the server for every batch the gateway sends, so alerts
fire (and SMS goes out) even when nobody has the dashboard open.

Rules (docs/API.md):
  * power factor alerts when BELOW its limit; skipped while the machine is off and
    never raised for sortex machines (no power factor)
  * critical wins over warning
  * a machine-specific threshold overrides the "all machines" one for that parameter
"""

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.plants.access import connected_owner
from apps.plants.models import Machine

from .models import Alert, Threshold

RANK = {"": 0, "warning": 1, "critical": 2}


@dataclass
class AlertEvent:
    kind: str  # raised | escalated | deescalated | recovered
    alert: Alert
    notify: bool = False  # send an SMS for this event


def _reading(param, machine, state):
    """Current value of `param`, or None when it cannot be judged (off, no data...)."""
    if param == "powerFactor":
        if machine.type == Machine.Type.SORTEX or state is None or not state.on:
            return None
        return state.pf if state.pf else None
    return None


def _severity(threshold, value):
    """(severity, limit) for a "below the limit is bad" parameter."""
    if threshold.critical is not None and value < threshold.critical:
        return Alert.Severity.CRITICAL, threshold.critical
    if threshold.warning is not None and value < threshold.warning:
        return Alert.Severity.WARNING, threshold.warning
    return None, None


def _applicable_thresholds(machine):
    """{param: Threshold} with machine-specific rows beating the "all" row.

    Only the limits of the owner connected to the machine's gateway count; with nobody
    connected there is nobody to alert, so nothing applies."""
    chosen = {}
    owner_id = connected_owner(machine.gateway_id)
    if owner_id is None:
        return chosen
    rows = Threshold.objects.filter(Q(machine=machine) | Q(machine__isnull=True), owner_id=owner_id)
    for th in sorted(rows, key=lambda t: t.machine_id is None):  # specific first
        chosen.setdefault(th.param, th)
    return chosen


def evaluate_machine(machine, state, now=None):
    """Bring the machine's alerts in line with its latest reading. Returns AlertEvents."""
    now = now or timezone.now()
    cooldown = timedelta(minutes=settings.ALERT_SMS_COOLDOWN_MIN)
    existing = {a.threshold_id: a for a in Alert.objects.filter(machine=machine)}
    events = []
    live_thresholds = set()

    for param, th in _applicable_thresholds(machine).items():
        live_thresholds.add(th.pk)
        value = _reading(param, machine, state)
        severity, limit = _severity(th, value) if value is not None else (None, None)
        alert = existing.get(th.pk)

        if severity is None:
            if alert and alert.status == Alert.Status.ACTIVE:
                alert.status = Alert.Status.RECOVERED
                alert.recovered_at = now
                alert.save(update_fields=["status", "recovered_at"])
                events.append(AlertEvent("recovered", alert))
            continue

        if alert is None:
            alert = Alert.objects.create(
                threshold=th, machine=machine, param=param, severity=severity,
                reading=value, limit_value=limit, since=now,
                notified_at=now, notified_severity=severity,
            )
            events.append(AlertEvent("raised", alert, notify=True))
        elif alert.status == Alert.Status.RECOVERED:
            quiet = (
                alert.notified_at
                and now - alert.notified_at < cooldown
                and RANK[severity] <= RANK[alert.notified_severity]
            )
            alert.status = Alert.Status.ACTIVE
            alert.severity, alert.reading, alert.limit_value = severity, value, limit
            alert.since, alert.recovered_at = now, None
            if not quiet:
                alert.notified_at, alert.notified_severity = now, severity
            alert.save()
            events.append(AlertEvent("raised", alert, notify=not quiet))
        else:
            old = alert.severity
            changed = severity != old
            drifted = abs(alert.reading - value) >= 0.01
            if changed or drifted or alert.limit_value != limit:
                alert.severity, alert.reading, alert.limit_value = severity, value, limit
                escalated = changed and RANK[severity] > RANK[old]
                notify = False
                if escalated:
                    # Text again only for something worse than what was already sent inside the
                    # cool-down, so a value hovering at a limit does not flood phones.
                    recent = alert.notified_at and now - alert.notified_at < cooldown
                    notify = not (recent and RANK[severity] <= RANK[alert.notified_severity])
                    if notify:
                        alert.notified_at, alert.notified_severity = now, severity
                alert.save()
                if changed:
                    events.append(AlertEvent("escalated" if escalated else "deescalated", alert, notify=notify))

    # Alerts of thresholds that no longer apply to this machine (overridden) recover.
    for threshold_id, alert in existing.items():
        if threshold_id not in live_thresholds and alert.status == Alert.Status.ACTIVE:
            alert.status = Alert.Status.RECOVERED
            alert.recovered_at = now
            alert.save(update_fields=["status", "recovered_at"])
            events.append(AlertEvent("recovered", alert))
    return events


def _reevaluate(states):
    events = []
    for state in states.select_related("machine__gateway__plant"):
        events.extend(evaluate_machine(state.machine, state))
    return events


def reevaluate_gateway(gateway_id):
    """Ownership of a gateway changed: re-judge its machines (and recover alerts that no longer apply)."""
    from apps.telemetry.models import MachineState

    return _reevaluate(MachineState.objects.filter(machine__gateway_id=gateway_id))


def reevaluate_owner(user):
    """After an owner changes their limits: re-judge the machines they are connected to."""
    from apps.telemetry.models import MachineState

    return _reevaluate(
        MachineState.objects.filter(
            machine__gateway__assignments__user=user,
            machine__gateway__assignments__status="connected",
        )
    )
