import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import hash_secret


LIVE_STATUSES = ("assigned", "connected")


class Plant(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Gateway(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    plant = models.ForeignKey(Plant, on_delete=models.PROTECT, related_name="gateways")
    enabled = models.BooleanField(default=True)
    serial_number = models.CharField(max_length=64, unique=True, null=True, blank=True)
    verified = models.BooleanField(default=True)
    api_key_prefix = models.CharField(max_length=16, editable=False)
    api_key_hash = models.CharField(max_length=64, unique=True, editable=False)
    last_seen_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_ip = models.GenericIPAddressField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["plant__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.plant})"

    def rotate_key(self):
        raw = "gw_" + secrets.token_urlsafe(32)
        self.api_key_prefix = raw[:11]
        self.api_key_hash = hash_secret(raw)
        return raw

    def save(self, *args, **kwargs):
        if not self.api_key_hash:
            self._first_key = self.rotate_key()
        super().save(*args, **kwargs)

    @property
    def online(self):
        return bool(
            self.last_seen_at
            and (timezone.now() - self.last_seen_at).total_seconds() <= settings.STALE_AFTER_SEC
        )

    @property
    def availability(self):
        return "assigned" if self.assignments.filter(status__in=LIVE_STATUSES).exists() else "available"


class GatewayAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned"
        CONNECTED = "connected"
        DISCONNECTED = "disconnected"

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gateway_assignments")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ASSIGNED)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    connected_at = models.DateTimeField(null=True, blank=True)
    disconnected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    disconnected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_at", "-pk"]
        constraints = [
            # The database itself refuses a second live record for one gateway, even if two
            # admins click at the same moment.
            models.UniqueConstraint(
                fields=["gateway"],
                condition=models.Q(status__in=["assigned", "connected"]),
                name="one_live_assignment_per_gateway",
            )
        ]


class ConnectionPeriod(models.Model):
    assignment = models.ForeignKey(GatewayAssignment, on_delete=models.CASCADE, related_name="periods")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["start"]


class Machine(models.Model):
    class Type(models.TextChoices):
        SHELLER = "sheller"
        WHITENER = "whitener"
        SORTEX = "sortex"

    id = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=Type.choices)
    rated_kw = models.FloatField(default=0)
    gateway = models.ForeignKey(Gateway, on_delete=models.PROTECT, related_name="machines")
    meter_id = models.CharField(max_length=32)
    on_threshold_kw = models.FloatField(default=0.5)
    position = models.PositiveSmallIntegerField(default=0)
    configured = models.BooleanField(default=True)

    class Meta:
        ordering = ["gateway__plant__name", "position", "name"]
        constraints = [
            models.UniqueConstraint(fields=["gateway", "meter_id"], name="unique_meter_per_gateway")
        ]

    def __str__(self):
        return self.name

    @property
    def plant_name(self):
        return self.gateway.plant.name
