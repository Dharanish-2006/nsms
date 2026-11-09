"""The Admin Portal API (Smart Mill Admin Requirements).

Five screens: Dashboard, User Approval, Gateway Assignment, Connections, Profile (the profile
is /auth/me). Nothing here exposes machine readings, alerts or reports: those belong to the
plant owners. Every rule is enforced here on the server, and every action is audited.
"""

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AdminAuditLog, User
from apps.common.errors import ApiError
from apps.common.permissions import IsAdminRole
from apps.common.realtime import notify_user_access_changed
from apps.common.timeutil import to_ms
from apps.plants import services
from apps.plants.models import LIVE_STATUSES, Gateway, GatewayAssignment, Machine

PAGE = 200  # most rows returned by a list


class AdminView(APIView):
    permission_classes = [IsAdminRole]


def _person(u):
    return None if u is None else {"id": str(u.pk), "username": u.username, "fullName": u.full_name}


def user_row(u):
    return {
        "id": str(u.pk),
        "username": u.username,
        "fullName": u.full_name,
        "email": u.email,
        "mobile": u.mobile,
        "status": u.status,  # pending | active (approved) | rejected
        "registeredAt": to_ms(u.date_joined),
        "decidedAt": to_ms(u.decided_at),
        "decidedBy": _person(u.decided_by),
        "rejectionReason": u.rejection_reason,
    }


def gateway_row(g, live=None, api_key=None):
    """`live` is the gateway's assigned/connected record, if any."""
    data = {
        "id": str(g.pk),
        "name": g.name,
        "serialNumber": g.serial_number,
        "verified": g.verified,
        "enabled": g.enabled,
        "availability": "assigned" if live else "available",
        "online": g.online,
        "lastSeenAt": to_ms(g.last_seen_at),
        "registeredAt": to_ms(g.created_at),
        "apiKeyPrefix": g.api_key_prefix,
        "assignmentId": live.pk if live else None,
        "assignedTo": _person(live.user) if live else None,
        "connection": live.status if live else None,
        "machineCount": g.machines.count(),
        "unconfiguredMachines": g.machines.filter(configured=False).count(),
    }
    if api_key:
        data["apiKey"] = api_key  # shown once
    return data


def assignment_row(a):
    return {
        "id": a.pk,
        "user": _person(a.user),
        "gateway": {"id": str(a.gateway_id), "name": a.gateway.name, "serialNumber": a.gateway.serial_number},
        "status": a.status,  # assigned | connected | disconnected
        "assignedAt": to_ms(a.assigned_at),
        "assignedBy": _person(a.assigned_by),
        "connectedAt": to_ms(a.connected_at),
        "connectedBy": _person(a.connected_by),
        "disconnectedAt": to_ms(a.disconnected_at),
        "disconnectedBy": _person(a.disconnected_by),
    }


def _live_by_gateway():
    rows = GatewayAssignment.objects.filter(status__in=LIVE_STATUSES).select_related("user")
    return {a.gateway_id: a for a in rows}


def _assignments():
    return GatewayAssignment.objects.select_related("user", "gateway", "assigned_by", "connected_by", "disconnected_by")


def _remarks(request):
    value = request.data.get("remarks", "") if isinstance(request.data, dict) else ""
    return value.strip()[:300] if isinstance(value, str) else ""


# --- Screen 1: Dashboard ---------------------------------------------------------------
class DashboardView(AdminView):
    def get(self, request):
        owners = User.objects.filter(role=User.Role.USER)
        live = _live_by_gateway()
        gateways = list(Gateway.objects.order_by("name"))
        return Response(
            {
                "pendingUsers": owners.filter(status=User.Status.PENDING).count(),
                "approvedUsers": owners.filter(status=User.Status.ACTIVE).count(),
                "registeredGateways": len(gateways),
                "unverifiedGateways": sum(1 for g in gateways if not g.verified),
                "activeConnections": GatewayAssignment.objects.filter(status=GatewayAssignment.Status.CONNECTED).count(),
                "availableGateways": sum(1 for g in gateways if g.verified and g.pk not in live),
                "assignedGateways": len(live),
                "machinesNeedingSetup": Machine.objects.filter(configured=False).count(),
                "gateways": [gateway_row(g, live.get(g.pk)) for g in gateways],
            }
        )


# --- Screen 2: User Approval -----------------------------------------------------------
class UserListView(AdminView):
    """?status=pending|active|rejected  &q=search (name, username, email)"""

    def get(self, request):
        users = User.objects.filter(role=User.Role.USER).select_related("decided_by").order_by("-date_joined", "-pk")
        status = request.query_params.get("status")
        if status:
            if status not in User.Status.values:
                raise ApiError("Unknown status.", 422, "validation")
            users = users.filter(status=status)
        q = request.query_params.get("q", "").strip()
        if q:
            users = users.filter(
                Q(username__icontains=q) | Q(full_name__icontains=q) | Q(email__icontains=q)
            )
        return Response([user_row(u) for u in users[:PAGE]])


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


def _decide(request, pk, *, approve):
    with transaction.atomic():
        user = get_object_or_404(User.objects.select_for_update(), pk=pk, role=User.Role.USER)
        if user.status != User.Status.PENDING:
            raise ApiError("This request has already been decided.", 409, "already_decided")
        reason = ""
        if not approve:
            s = RejectSerializer(data=request.data)
            s.is_valid(raise_exception=True)
            reason = s.validated_data["reason"].strip()
        user.status = User.Status.ACTIVE if approve else User.Status.REJECTED
        user.decided_at, user.decided_by, user.rejection_reason = timezone.now(), request.user, reason
        user.save(update_fields=["status", "decided_at", "decided_by", "rejection_reason"])
        AdminAuditLog.record(
            request.user,
            AdminAuditLog.Action.USER_APPROVED if approve else AdminAuditLog.Action.USER_REJECTED,
            "user", user.pk, reason,
        )  # fmt: skip
    return user


class UserApproveView(AdminView):
    def post(self, request, pk):
        return Response(user_row(_decide(request, pk, approve=True)))


class UserRejectView(AdminView):
    def post(self, request, pk):
        return Response(user_row(_decide(request, pk, approve=False)))


# --- Screen 3: Gateway Assignment (gateways list) ---------------------------------------
class GatewayListView(AdminView):
    """?availability=available|assigned  &verified=true|false  &q=search (name, serial)"""

    def get(self, request):
        gateways = Gateway.objects.order_by("name")
        q = request.query_params.get("q", "").strip()
        if q:
            gateways = gateways.filter(Q(name__icontains=q) | Q(serial_number__icontains=q))
        verified = request.query_params.get("verified")
        if verified in ("true", "false"):
            gateways = gateways.filter(verified=verified == "true")
        live = _live_by_gateway()
        rows = [gateway_row(g, live.get(g.pk)) for g in gateways[:PAGE]]
        availability = request.query_params.get("availability")
        if availability in ("available", "assigned"):
            rows = [r for r in rows if r["availability"] == availability]
        return Response(rows)


class GatewayVerifyView(AdminView):
    """Confirm that a gateway which registered itself is the box that was installed."""

    @transaction.atomic
    def post(self, request, pk):
        gateway = get_object_or_404(Gateway.objects.select_for_update(), pk=pk)
        if gateway.verified:
            raise ApiError("Already verified.", 409, "already_verified")
        gateway.verified = True
        gateway.save(update_fields=["verified"])
        AdminAuditLog.record(request.user, AdminAuditLog.Action.GATEWAY_VERIFIED, "gateway", gateway.pk, _remarks(request))
        return Response(gateway_row(gateway, _live_by_gateway().get(gateway.pk)))


class GatewayRotateKeyView(AdminView):
    """Issue a new gateway key (a replaced or reset device). The old key stops working at once."""

    @transaction.atomic
    def post(self, request, pk):
        gateway = get_object_or_404(Gateway.objects.select_for_update(), pk=pk)
        raw = gateway.rotate_key()
        gateway.save(update_fields=["api_key_prefix", "api_key_hash"])
        AdminAuditLog.record(request.user, AdminAuditLog.Action.GATEWAY_KEY_ROTATED, "gateway", gateway.pk, _remarks(request))
        return Response(gateway_row(gateway, _live_by_gateway().get(gateway.pk), api_key=raw))


# --- Screens 3 and 4: assignments and connections --------------------------------------
class AssignSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    gatewayId = serializers.UUIDField()


class AssignmentListView(AdminView):
    """GET ?status=  &userId=  &gatewayId=  &q=   (current and previous records)
    POST {userId, gatewayId}   assign an available gateway to an approved user"""

    def get(self, request):
        qs = _assignments()
        status = request.query_params.get("status")
        if status:
            if status not in GatewayAssignment.Status.values:
                raise ApiError("Unknown status.", 422, "validation")
            qs = qs.filter(status=status)
        for param, field in (("userId", "user_id"), ("gatewayId", "gateway_id")):
            value = request.query_params.get(param)
            if value:
                try:
                    qs = qs.filter(**{field: value})
                except (ValueError, TypeError, Exception):  # noqa: BLE001 - malformed id
                    raise ApiError(f"{param} is not valid.", 422, "validation") from None
        q = request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(user__username__icontains=q) | Q(user__full_name__icontains=q)
                | Q(gateway__name__icontains=q) | Q(gateway__serial_number__icontains=q)
            )  # fmt: skip
        return Response([assignment_row(a) for a in qs[:PAGE]])

    def post(self, request):
        s = AssignSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        a = services.assign(request.user, s.validated_data["userId"], s.validated_data["gatewayId"], _remarks(request))
        return Response(assignment_row(_assignments().get(pk=a.pk)), status=201)


class AssignmentConnectView(AdminView):
    def post(self, request, pk):
        a = services.connect(request.user, pk, _remarks(request))
        return Response(assignment_row(_assignments().get(pk=a.pk)))


class AssignmentDisconnectView(AdminView):
    def post(self, request, pk):
        a = services.disconnect(request.user, pk, _remarks(request))
        return Response(assignment_row(_assignments().get(pk=a.pk)))


# --- Audit log -------------------------------------------------------------------------
class AuditLogView(AdminView):
    """?action=  &limit=  (newest first)"""

    def get(self, request):
        qs = AdminAuditLog.objects.all()
        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)
        try:
            limit = min(int(request.query_params.get("limit", 100)), 500)
        except ValueError:
            limit = 100
        return Response(
            [
                {
                    "id": e.pk,
                    "admin": e.admin_username,
                    "action": e.action,
                    "targetType": e.target_type,
                    "targetId": e.target_id,
                    "remarks": e.remarks,
                    "timestamp": to_ms(e.timestamp),
                }
                for e in qs[:limit]
            ]
        )


# --- Naming machines -------------------------------------------------------------------
def machine_row(m):
    """Configuration only. No readings: those belong to the plant owner."""
    state = getattr(m, "state", None)
    return {
        "id": m.pk,
        "meterId": m.meter_id,
        "name": m.name,
        "type": m.type,
        "ratedKw": m.rated_kw,
        "configured": m.configured,
        "lastSeenAt": to_ms(state.received_at) if state else None,
    }


class GatewayMachinesView(AdminView):
    """The machines (meters) a gateway has reported, so the admin can name them."""

    def get(self, request, pk):
        gateway = get_object_or_404(Gateway, pk=pk)
        machines = gateway.machines.select_related("state").order_by("configured", "position", "meter_id")
        return Response({"gateway": gateway_row(gateway, _live_by_gateway().get(gateway.pk)), "machines": [machine_row(m) for m in machines]})


class MachineConfigureSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(Machine.Type.values)
    ratedKw = serializers.FloatField(min_value=0, max_value=100000, required=False)


class MachineConfigureView(AdminView):
    """Name a machine and set its type (and optionally its rating). It then becomes visible to the
    owner connected to its gateway."""

    @transaction.atomic
    def put(self, request, pk):
        from apps.alerts.dispatch import dispatch
        from apps.alerts.engine import reevaluate_gateway
        from apps.telemetry.publish import publish_machine_change

        machine = get_object_or_404(Machine.objects.select_for_update().select_related("gateway"), pk=pk)
        s = MachineConfigureSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        name = d["name"].strip()
        if not name:
            raise ApiError("Enter a machine name.", 422, "validation")
        if Machine.objects.filter(gateway=machine.gateway, name__iexact=name).exclude(pk=machine.pk).exists():
            raise ApiError("Another machine on this gateway already has that name.", 409, "name_in_use")
        before = f"{machine.name} ({machine.type})" if machine.configured else f"unnamed meter {machine.meter_id}"
        machine.name, machine.type, machine.configured = name, d["type"], True
        if "ratedKw" in d:
            machine.rated_kw = d["ratedKw"]
        machine.save()
        AdminAuditLog.record(
            request.user, AdminAuditLog.Action.MACHINE_CONFIGURED, "machine", machine.pk,
            f"{before} -> {name} ({machine.type}); gateway {machine.gateway.serial_number or machine.gateway.name}",
        )  # fmt: skip
        transaction.on_commit(lambda: (publish_machine_change(machine), dispatch(reevaluate_gateway(machine.gateway_id))))
        machine = Machine.objects.select_related("state").get(pk=machine.pk)
        return Response(machine_row(machine))
