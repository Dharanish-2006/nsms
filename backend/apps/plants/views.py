import hmac

from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.common.permissions import IsPlantOwner

from .access import accessible_plants
from .services import register_unverified


class PlantListView(APIView):
    permission_classes = [IsPlantOwner]

    def get(self, request):
        return Response([p.name for p in accessible_plants(request.user)])


class ProvisionSerializer(serializers.Serializer):
    serial = serializers.RegexField(r"^[A-Za-z0-9._-]{4,64}$", error_messages={"invalid": "Serial number looks wrong."})
    name = serializers.CharField(max_length=100, required=False, allow_blank=True)


class GatewayProvisionView(APIView):
    """POST /api/gateways/provision: a freshly installed gateway registers itself.

    The gateway is configured with this server's address and a provisioning key
    (`GATEWAY_PROVISION_KEY`, sent as `X-Provision-Key`). The first call with a new serial
    number creates the gateway as *unverified* and returns its own API key, once. The admin
    then sees it in the portal and verifies it; until then it cannot send data.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "provision"

    def post(self, request):
        expected = settings.GATEWAY_PROVISION_KEY
        if not expected:
            raise ApiError("Gateway self-registration is turned off.", 404, "not_found")
        given = request.headers.get("X-Provision-Key", "")
        if not hmac.compare_digest(given.encode(), expected.encode()):
            raise ApiError("Invalid provisioning key.", 401, "invalid_provision_key")

        s = ProvisionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        serial = s.validated_data["serial"]
        gateway, created = register_unverified(serial, s.validated_data.get("name", ""))
        if not created:
            raise ApiError(
                "This gateway is already registered. Ask the administrator for a new key.", 409, "already_registered"
            )
        return Response(
            {"gatewayId": str(gateway.pk), "apiKey": gateway._first_key, "status": "verified" if gateway.verified else "awaiting_verification"},
            status=201,
        )
