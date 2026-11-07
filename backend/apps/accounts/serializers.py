from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


def user_json(user):
    """The `user` object of docs/API.md. Never includes anything secret."""
    return {
        "id": str(user.pk),
        "username": user.username,
        "fullName": user.full_name,
        "email": user.email,
        "mobile": user.mobile,
        "role": user.role,
        "status": user.status,
        "requestedRole": user.requested_role,
    }


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class OtpSendSerializer(serializers.Serializer):
    channel = serializers.ChoiceField(["email", "phone"])
    target = serializers.CharField(max_length=254)


class OtpVerifySerializer(OtpSendSerializer):
    code = serializers.CharField(max_length=12)


class RegisterSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=150)
    username = serializers.RegexField(
        r"^[A-Za-z0-9_.-]{3,30}$",
        error_messages={"invalid": "Use 3-30 letters, numbers, dots, dashes or underscores."},
    )
    email = serializers.EmailField(max_length=254)
    emailToken = serializers.CharField(max_length=200)
    mobile = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    phoneToken = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(max_length=256, trim_whitespace=False)
    role = serializers.ChoiceField(["admin", "user"], default="user")

    def validate(self, attrs):
        candidate = User(
            username=attrs["username"], email=attrs["email"], full_name=attrs["fullName"]
        )
        try:
            validate_password(attrs["password"], candidate)
        except Exception as exc:  # DjangoValidationError
            raise serializers.ValidationError({"password": list(getattr(exc, "messages", [str(exc)]))}) from None
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(max_length=256, trim_whitespace=False)
    newPassword = serializers.CharField(max_length=256, trim_whitespace=False)
