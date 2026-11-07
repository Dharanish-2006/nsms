"""Who may see what.

Monitoring data belongs to plant owners. A plant owner sees a gateway (and so its machines,
alerts and plant) only while their assignment to it is "connected". Admins run the system
(approvals, assignments, connections); they do not see machine data, so every function here
returns nothing for them.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import ConnectionPeriod, Gateway, GatewayAssignment, Machine, Plant

CONNECTED = GatewayAssignment.Status.CONNECTED


def _is_owner(user):
    return user.role == "user" and user.status == "active"


def accessible_gateways(user):
    qs = Gateway.objects.select_related("plant")
    if not _is_owner(user):
        return qs.none()
    return qs.filter(assignments__user=user, assignments__status=CONNECTED)


def accessible_machines(user):
    qs = Machine.objects.select_related("gateway__plant")
    if not _is_owner(user):
        return qs.none()
    return qs.filter(gateway__assignments__user=user, gateway__assignments__status=CONNECTED)


def accessible_plants(user):
    if not _is_owner(user):
        return Plant.objects.none()
    return Plant.objects.filter(
        gateways__assignments__user=user, gateways__assignments__status=CONNECTED
    ).distinct()


def accessible_gateway_ids(user):
    return list(accessible_gateways(user).values_list("pk", flat=True))


def connected_owner(gateway_id):
    """The user connected to this gateway right now, or None."""
    return (
        GatewayAssignment.objects.filter(gateway_id=gateway_id, status=CONNECTED)
        .select_related("user")
        .values_list("user", flat=True)
        .first()
    )


# --- Reports only cover the time an owner was connected -----------------------------------
_HOUR = timedelta(hours=1)


def window_q(user, *, gateway_field="machine__gateway", time_field="hour", pad=_HOUR):
    """A filter for rows (hourly reports, readings) that fall inside this user's connection
    periods. `pad` widens the start so an hour that was only partly connected still counts
    (hourly rows are stamped with their start). A Q that matches nothing if there are none."""
    now = timezone.now()
    q = Q(pk__in=[])
    periods = ConnectionPeriod.objects.filter(assignment__user=user).select_related("assignment")
    for p in periods:
        cond = Q(**{f"{gateway_field}_id": p.assignment.gateway_id, f"{time_field}__gt": p.start - pad})
        if p.end is not None:
            cond &= Q(**{f"{time_field}__lt": p.end})
        q |= cond
    return q


def current_period_starts(gateway_ids):
    """{gateway_id: when the current owner connected} for gateways with an open period."""
    rows = ConnectionPeriod.objects.filter(
        end__isnull=True, assignment__gateway_id__in=list(gateway_ids)
    ).values_list("assignment__gateway_id", "start")
    return dict(rows)
