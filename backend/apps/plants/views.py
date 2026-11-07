import hmac

from django.conf import settings
from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.common.permissions import IsPlantOwner

from .access import accessible_plants
from .models import Gateway, Plant


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
        if Gateway.objects.filter(serial_number__iexact=serial).exists():
            raise ApiError(
                "This gateway is already registered. Ask the administrator for a new key.",
                409,
                "already_registered",
            )
        plant, _ = Plant.objects.get_or_create(name=settings.DEFAULT_PLANT_NAME)
        gateway = Gateway(
            name=s.validated_data.get("name", "").strip() or serial,
            plant=plant,
            serial_number=serial,
            verified=False,
        )
        try:
            gateway.save()
        except IntegrityError:
            raise ApiError("This gateway is already registered.", 409, "already_registered") from None
        return Response(
            {"gatewayId": str(gateway.pk), "apiKey": gateway._first_key, "status": "awaiting_verification"},
            status=201,
        )
