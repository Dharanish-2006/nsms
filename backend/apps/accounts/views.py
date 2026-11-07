from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.common.errors import ApiError
from apps.common.realtime import notify_user_access_changed

from . import otp
from .models import AuthToken, User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    OtpSendSerializer,
    OtpVerifySerializer,
    RegisterSerializer,
    user_json,
)

LOGIN_FAIL_LIMIT = 10
LOGIN_FAIL_WINDOW = 15 * 60


class PublicView(APIView):
    """Sign-in, register and OTP: no token needed, and rate limited."""

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


class LoginView(PublicView):
    throttle_scope = "login"

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        username, password = s.validated_data["username"], s.validated_data["password"]

        # Per-account lockout on top of the per-IP throttle, against distributed guessing.
        fail_key = f"login-fail:{username.lower()}"
        if cache.get(fail_key, 0) >= LOGIN_FAIL_LIMIT:
            raise ApiError(
                "Too many failed attempts. Please wait 15 minutes.", 429, "too_many_attempts"
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            try:
                cache.incr(fail_key)
            except ValueError:
                cache.set(fail_key, 1, LOGIN_FAIL_WINDOW)
            raise ApiError("Wrong username or password.", 401, "invalid_credentials")
        cache.delete(fail_key)

        if user.status == User.Status.REJECTED:
            reason = f" Reason: {user.rejection_reason}" if user.rejection_reason else ""
            raise ApiError("Your registration request was not approved." + reason, 403, "rejected")
        if user.status != User.Status.ACTIVE:
            raise ApiError(
                "Your account is waiting for administrator approval.", 403, "pending_approval"
            )
        raw, token = AuthToken.issue(user)
        return Response({"token": raw, "user": user_json(user)})


class OtpSendView(PublicView):
    throttle_scope = "otp"

    def post(self, request):
        s = OtpSendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        otp.send_code(s.validated_data["channel"], s.validated_data["target"])
        return Response(status=204)


class OtpVerifyView(PublicView):
    throttle_scope = "otp"

    def post(self, request):
        s = OtpVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        token = otp.verify_code(d["channel"], d["target"], d["code"])
        return Response({"token": token})


class RegisterView(PublicView):
    throttle_scope = "register"

    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        email = otp.normalise_target("email", d["email"])
        mobile = otp.normalise_target("phone", d["mobile"]) if d.get("mobile") else ""

        try:
            with transaction.atomic():
                # Conflicts first, so a taken username does not burn the verification codes.
                if User.objects.filter(username__iexact=d["username"]).exists():
                    raise ApiError("That username is already taken.", 409, "username_taken")
                if User.objects.filter(email__iexact=email).exists():
                    raise ApiError("An account with that email already exists.", 409, "email_taken")

                email_proof = otp.proof_for("email", email, d["emailToken"])
                if email_proof is None:
                    raise ApiError("Verify your email address first.", 400, "otp_required")
                phone_proof = None
                if mobile:
                    phone_proof = otp.proof_for("phone", mobile, d.get("phoneToken"))
                    if phone_proof is None:
                        raise ApiError("Verify your mobile number first.", 400, "otp_required")

                user = User(
                    username=d["username"],
                    email=email,
                    full_name=d["fullName"].strip(),
                    mobile=mobile,
                    role=User.Role.USER,  # asking for "admin" is only a request
                    requested_role=d["role"],
                    status=User.Status.PENDING,
                )
                user.set_password(d["password"])
                user.save()
                email_proof.delete()
                if phone_proof:
                    phone_proof.delete()
        except IntegrityError:
            raise ApiError("That username or email is already taken.", 409, "conflict") from None
        return Response({"ok": True, "status": "pending"}, status=201)


class ProfileSerializer(serializers.Serializer):
    """The only profile fields a person may edit. Email and phone need verifying, so not here."""

    fullName = serializers.CharField(max_length=150)


class MeView(APIView):
    def get(self, request):
        return Response(user_json(request.user))

    def patch(self, request):
        s = ProfileSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        request.user.full_name = s.validated_data["fullName"].strip()
        request.user.save(update_fields=["full_name"])
        return Response(user_json(request.user))

    put = patch


class LogoutView(APIView):
    def post(self, request):
        request.auth.delete()
        notify_user_access_changed(request.user.pk)  # closes this user's open dashboards
        return Response(status=204)


class ChangePasswordView(APIView):
    def post(self, request):
        s = ChangePasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(s.validated_data["currentPassword"]):
            raise ApiError("Current password is incorrect.", 400, "wrong_password")
        try:
            validate_password(s.validated_data["newPassword"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"newPassword": list(exc.messages)}) from None
        user.set_password(s.validated_data["newPassword"])
        user.save(update_fields=["password"])
        # Sign the account out everywhere else.
        AuthToken.objects.filter(user=user).exclude(pk=request.auth.pk).delete()
        return Response(status=204)
