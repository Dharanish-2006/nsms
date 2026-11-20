import logging
import re

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.common.permissions import IsAdminRole
from apps.common.timeutil import to_ms

from .models import Enquiry

logger = logging.getLogger(__name__)


def clean_mobile(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise serializers.ValidationError("Enter a valid 10-digit mobile number.")
    return digits


class EnquirySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    mobile = serializers.CharField(max_length=20)
    requirement = serializers.CharField(max_length=2000)
    website = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_name(self, v):
        v = " ".join(v.split())
        if not v:
            raise serializers.ValidationError("Enter your name.")
        return v

    def validate_mobile(self, v):
        return clean_mobile(v)

    def validate_requirement(self, v):
        v = v.strip()
        if len(v) < 5:
            raise serializers.ValidationError("Please describe your requirement.")
        return v


def notify_team(enquiry):
    to = [e.strip() for e in settings.ENQUIRY_NOTIFY_EMAIL.split(",") if e.strip()]
    if not to:
        return False
    body = (
        f"New enquiry from the Smart Milling page\n\n"
        f"Name: {enquiry.name}\nMobile: {enquiry.mobile}\n\nRequirement:\n{enquiry.requirement}\n"
    )
    try:
        send_mail(f"New enquiry: {enquiry.name}", body, None, to)
        return True
    except Exception:  # noqa: BLE001 
        logger.exception("Could not email enquiry %s", enquiry.pk)
        return False


class ContactView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact"

    def post(self, request):
        s = EnquirySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if d["website"]:
            return Response({"ok": True}, status=201)
        enquiry = Enquiry.objects.create(name=d["name"], mobile=d["mobile"], requirement=d["requirement"])
        if notify_team(enquiry):
            Enquiry.objects.filter(pk=enquiry.pk).update(emailed=True)
        return Response({"ok": True}, status=201)


def enquiry_row(e):
    return {
        "id": e.pk,
        "name": e.name,
        "mobile": e.mobile,
        "requirement": e.requirement,
        "status": e.status,
        "emailed": e.emailed,
        "createdAt": to_ms(e.created_at),
        "handledAt": to_ms(e.handled_at),
        "handledBy": e.handled_by.username if e.handled_by_id else None,
    }


class EnquiryListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        rows = Enquiry.objects.select_related("handled_by")
        status = request.query_params.get("status")
        if status:
            if status not in Enquiry.Status.values:
                raise ApiError("Unknown status.", 422, "validation")
            rows = rows.filter(status=status)
        return Response([enquiry_row(e) for e in rows[:200]])


class StatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Enquiry.Status.choices)


class EnquiryUpdateView(APIView):
    permission_classes = [IsAdminRole]

    def put(self, request, pk):
        s = StatusSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        e = get_object_or_404(Enquiry, pk=pk)
        e.status = s.validated_data["status"]
        e.handled_at = None if e.status == Enquiry.Status.NEW else timezone.now()
        e.handled_by = None if e.status == Enquiry.Status.NEW else request.user
        e.save(update_fields=["status", "handled_at", "handled_by"])
        return Response(enquiry_row(e))
