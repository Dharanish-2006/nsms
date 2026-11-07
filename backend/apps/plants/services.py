"""The admin's gateway operations. Every rule here is enforced on the server and every
change is written to the audit log inside the same transaction."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.models import AdminAuditLog, User
from apps.common.errors import ApiError
from apps.common.realtime import gateway_group, group_send, notify_user_access_changed

from .models import LIVE_STATUSES, ConnectionPeriod, Gateway, GatewayAssignment

Action = AdminAuditLog.Action
Status = GatewayAssignment.Status


def _announce(gateway_id, user_id):
    """After commit: re-judge alerts for the gateway's machines and refresh open dashboards."""
    from apps.alerts import engine
    from apps.alerts.dispatch import dispatch

    events = engine.reevaluate_gateway(gateway_id)
    dispatch(events)
    notify_user_access_changed(user_id)
    group_send([gateway_group(gateway_id)], {"type": "alerts.refresh"})


def _after_commit(gateway_id, user_id):
    transaction.on_commit(lambda: _announce(gateway_id, user_id))


def _live_exists(gateway, exclude=None):
    qs = GatewayAssignment.objects.filter(gateway=gateway, status__in=LIVE_STATUSES)
    if exclude is not None:
        qs = qs.exclude(pk=exclude)
    return qs.exists()


@transaction.atomic
def assign(admin, user_id, gateway_id, remarks=""):
    gateway = get_object_or_404(Gateway.objects.select_for_update(), pk=gateway_id)
    user = get_object_or_404(User.objects.select_for_update(), pk=user_id)
    if user.role != User.Role.USER or user.status != User.Status.ACTIVE:
        raise ApiError("Only approved users can be assigned a gateway.", 409, "user_not_approved")
    if not gateway.verified:
        raise ApiError("Verify this gateway before assigning it.", 409, "gateway_not_verified")
    if _live_exists(gateway):
        raise ApiError("This gateway is already assigned. Disconnect it first.", 409, "gateway_in_use")
    try:
        with transaction.atomic():
            a = GatewayAssignment.objects.create(gateway=gateway, user=user, assigned_by=admin)
    except IntegrityError:  # two admins at once: the database constraint decides
        raise ApiError("This gateway is already assigned. Disconnect it first.", 409, "gateway_in_use") from None
    AdminAuditLog.record(admin, Action.GATEWAY_ASSIGNED, "assignment", a.pk, remarks or f"{gateway} -> {user.username}")
    return a


@transaction.atomic
def connect(admin, assignment_id, remarks=""):
    a = get_object_or_404(GatewayAssignment.objects.select_for_update(), pk=assignment_id)
    gateway = Gateway.objects.select_for_update().get(pk=a.gateway_id)
    if a.status == Status.CONNECTED:
        raise ApiError("Already connected.", 409, "already_connected")
    user = User.objects.get(pk=a.user_id)
    if user.status != User.Status.ACTIVE:
        raise ApiError("Only approved users can be connected.", 409, "user_not_approved")
    if not gateway.verified:
        raise ApiError("Verify this gateway before connecting it.", 409, "gateway_not_verified")
    if _live_exists(gateway, exclude=a.pk):
        raise ApiError("Another user holds this gateway.", 409, "gateway_in_use")
    now = timezone.now()
    a.status, a.connected_at, a.connected_by = Status.CONNECTED, now, admin
    a.disconnected_at = a.disconnected_by = None
    try:
        with transaction.atomic():
            a.save()
    except IntegrityError:
        raise ApiError("Another user holds this gateway.", 409, "gateway_in_use") from None
    ConnectionPeriod.objects.create(assignment=a, start=now)
    AdminAuditLog.record(admin, Action.GATEWAY_CONNECTED, "assignment", a.pk, remarks)
    _after_commit(a.gateway_id, a.user_id)
    return a


@transaction.atomic
def disconnect(admin, assignment_id, remarks=""):
    a = get_object_or_404(GatewayAssignment.objects.select_for_update(), pk=assignment_id)
    if a.status == Status.DISCONNECTED:
        raise ApiError("Already disconnected.", 409, "already_disconnected")
    now = timezone.now()
    a.status, a.disconnected_at, a.disconnected_by = Status.DISCONNECTED, now, admin
    a.save()
    a.periods.filter(end__isnull=True).update(end=now)
    AdminAuditLog.record(admin, Action.GATEWAY_DISCONNECTED, "assignment", a.pk, remarks)
    _after_commit(a.gateway_id, a.user_id)
    return a
