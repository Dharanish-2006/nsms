import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("status", User.Status.ACTIVE)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin"
        USER = "user"

    class Status(models.TextChoices):
        ACTIVE = "active"
        PENDING = "pending"
        REJECTED = "rejected"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    mobile = models.CharField(max_length=10, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    requested_role = models.CharField(max_length=10, choices=Role.choices, default=Role.USER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    rejection_reason = models.CharField(max_length=300, blank=True)

    objects = UserManager()

    def __str__(self):
        return self.username

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN


def hash_secret(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class AuthToken(models.Model):
    key_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    last_used_at = models.DateTimeField(default=timezone.now)

    @classmethod
    def issue(cls, user):
        raw = secrets.token_urlsafe(32)
        token = cls.objects.create(
            key_hash=hash_secret(raw),
            user=user,
            expires_at=timezone.now() + timedelta(hours=settings.AUTH_TOKEN_TTL_HOURS),
        )
        return raw, token


class OtpChallenge(models.Model):
    channel = models.CharField(max_length=10)
    target = models.CharField(max_length=254)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["channel", "target", "created_at"])]


class OtpProof(models.Model):
    channel = models.CharField(max_length=10)
    target = models.CharField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()


class AdminAuditLog(models.Model):
    class Action(models.TextChoices):
        USER_APPROVED = "user_approved"
        USER_REJECTED = "user_rejected"
        GATEWAY_VERIFIED = "gateway_verified"
        GATEWAY_KEY_ROTATED = "gateway_key_rotated"
        GATEWAY_ASSIGNED = "gateway_assigned"
        GATEWAY_CONNECTED = "gateway_connected"
        GATEWAY_DISCONNECTED = "gateway_disconnected"
        MACHINE_CONFIGURED = "machine_configured"

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="audit_entries"
    )
    admin_username = models.CharField(max_length=150)
    action = models.CharField(max_length=30, choices=Action.choices)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=64)
    remarks = models.CharField(max_length=300, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-timestamp", "-pk"]

    @classmethod
    def record(cls, admin, action, target_type, target_id, remarks=""):
        return cls.objects.create(
            admin=admin, admin_username=admin.username, action=action,
            target_type=target_type, target_id=str(target_id), remarks=remarks[:300],
        )  # fmt: skip
