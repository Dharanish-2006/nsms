from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.common.errors import ApiError
from apps.common.permissions import AdminWritesMixin, IsAdminRole
from apps.common.realtime import notify_user_access_changed
from apps.common.timeutil import to_ms

from .access import accessible_gateways, accessible_plants
from .models import Gateway, GatewayAssignment, Plant


class PlantListView(APIView):
    def get(self, request):
        return Response([p.name for p in accessible_plants(request.user)])


def gateway_json(gateway, *, admin, api_key=None):
    data = {
        "id": str(gateway.pk),
        "name": gateway.name,
        "plant": gateway.plant.name,
        "enabled": gateway.enabled,
        "online": gateway.online,
        "lastSeenAt": to_ms(gateway.last_seen_at),
        "machineCount": getattr(gateway, "machine_count", None),
    }
    if admin:
        data["apiKeyPrefix"] = gateway.api_key_prefix
        data["users"] = [
            {"id": str(u.pk), "username": u.username, "fullName": u.full_name}
            for u in gateway.users.all()
        ]
    if api_key:
        data["apiKey"] = api_key  # only ever returned once
    return data


class GatewaySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    plant = serializers.CharField(max_length=100)
    enabled = serializers.BooleanField(default=True)


def _listing(user):
    return (
        accessible_gateways(user)
        .annotate(machine_count=Count("machines", distinct=True))
        .prefetch_related("users")
        .distinct()
    )




class GatewayListView(AdminWritesMixin, APIView):
    def get(self, request):
        qs = _listing(request.user)
        user_id = request.query_params.get("userId")
        if user_id and request.user.role == "admin":
            qs = qs.filter(assignments__user_id=user_id)
        admin = request.user.role == "admin"
        return Response([gateway_json(g, admin=admin) for g in qs])

    def post(self, request):
        s = GatewaySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        plant, _ = Plant.objects.get_or_create(name=d["plant"].strip())
        gateway = Gateway(name=d["name"].strip(), plant=plant, enabled=d["enabled"])
        gateway.save()
        raw_key = gateway._first_key  # set by Gateway.save(); shown once, never stored
        gateway = _listing(request.user).get(pk=gateway.pk)
        return Response(gateway_json(gateway, admin=True, api_key=raw_key), status=201)


class GatewayDetailView(AdminWritesMixin, APIView):
    def _get(self, request, pk):
        return get_object_or_404(_listing(request.user), pk=pk)

    def get(self, request, pk):
        return Response(gateway_json(self._get(request, pk), admin=request.user.role == "admin"))

    def put(self, request, pk):
        gateway = self._get(request, pk)
        s = GatewaySerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if "name" in d:
            gateway.name = d["name"].strip()
        if "plant" in d:
            gateway.plant, _ = Plant.objects.get_or_create(name=d["plant"].strip())
        if "enabled" in d:
            gateway.enabled = d["enabled"]
        gateway.save()
        return Response(gateway_json(self._get(request, pk), admin=True))

    patch = put

    def delete(self, request, pk):
        gateway = self._get(request, pk)
        if gateway.machines.exists():
            raise ApiError(
                "Remove or move this gateway's machines first.", 409, "has_machines"
            )
        gateway.delete()
        return Response(status=204)


class GatewayRotateKeyView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        gateway = get_object_or_404(Gateway, pk=pk)
        raw = gateway.rotate_key()
        gateway.save(update_fields=["api_key_prefix", "api_key_hash"])
        gateway = _listing(request.user).get(pk=pk)
        return Response(gateway_json(gateway, admin=True, api_key=raw))


class GatewayUsersView(APIView):
    """Admin: who is this gateway assigned to?

    GET  -> the assigned users
    PUT  {userIds: [...]}  replace the whole set
    POST {userId}          add one user
    """

    permission_classes = [IsAdminRole]

    @staticmethod
    def _users_json(gateway):
        return [
            {"id": str(u.pk), "username": u.username, "fullName": u.full_name}
            for u in gateway.users.order_by("username")
        ]

    @staticmethod
    def _active_users(ids):
        users = list(User.objects.filter(pk__in=ids, status=User.Status.ACTIVE))
        if len(users) != len(set(ids)):
            raise ApiError(
                "Every user must exist and be approved before a gateway can be assigned.",
                422,
                "validation",
            )
        return users

    def get(self, request, pk):
        return Response(self._users_json(get_object_or_404(Gateway, pk=pk)))

    def post(self, request, pk):
        gateway = get_object_or_404(Gateway, pk=pk)
        user_id = request.data.get("userId") if isinstance(request.data, dict) else None
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            raise ApiError("userId is required.", 422, "validation") from None
        (user,) = self._active_users([user_id])
        _, created = GatewayAssignment.objects.get_or_create(
            gateway=gateway, user=user, defaults={"assigned_by": request.user}
        )
        if created:
            notify_user_access_changed(user.pk)
        return Response(self._users_json(gateway), status=201 if created else 200)

    @transaction.atomic
    def put(self, request, pk):
        gateway = get_object_or_404(Gateway, pk=pk)
        ids = request.data.get("userIds") if isinstance(request.data, dict) else None
        if not isinstance(ids, list):
            raise ApiError("userIds must be a list.", 422, "validation")
        try:
            wanted = {int(i) for i in ids}
        except (TypeError, ValueError):
            raise ApiError("userIds must be a list of user ids.", 422, "validation") from None
        users = self._active_users(wanted)

        current = set(gateway.assignments.values_list("user_id", flat=True))
        gateway.assignments.exclude(user_id__in=wanted).delete()
        for user in users:
            GatewayAssignment.objects.get_or_create(
                gateway=gateway, user=user, defaults={"assigned_by": request.user}
            )
        changed = current ^ wanted
        transaction.on_commit(lambda: [notify_user_access_changed(uid) for uid in changed])
        return Response(self._users_json(gateway))


class GatewayUserDetailView(APIView):
    permission_classes = [IsAdminRole]

    def delete(self, request, pk, user_id):
        deleted, _ = GatewayAssignment.objects.filter(gateway_id=pk, user_id=user_id).delete()
        if not deleted:
            raise ApiError("That user is not assigned to this gateway.", 404, "not_found")
        notify_user_access_changed(user_id)
        return Response(status=204)
