from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.plants.models import Machine


class Threshold(models.Model):
    """Limits for one parameter, for every machine ("all") or a single machine."""

    class Param(models.TextChoices):
        POWER_FACTOR = "powerFactor"

    # Each plant owner sets their own limits. (Rows with no owner are ignored.)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="thresholds")
    param = models.CharField(max_length=20, choices=Param.choices)
    machine = models.ForeignKey(Machine, null=True, blank=True, on_delete=models.CASCADE, related_name="thresholds")
    warning = models.FloatField(null=True, blank=True)
    critical = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.param} {self.machine_id or 'all'}"


class PhoneNumber(models.Model):
    """Numbers that receive an SMS when an alert is raised."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="phone_numbers")
    digits = models.CharField(max_length=10)  # Indian mobile, no country code
    label = models.CharField(max_length=60, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "digits"], name="unique_phone_per_owner")]

    def __str__(self):
        return f"{self.label or 'Contact'} {self.digits}"


class Alert(models.Model):
    """One row per (threshold, machine): re-raised in place, so the API `key` stays stable."""

    class Severity(models.TextChoices):
        WARNING = "warning"
        CRITICAL = "critical"

    class Status(models.TextChoices):
        ACTIVE = "active"
        RECOVERED = "recovered"

    threshold = models.ForeignKey(Threshold, on_delete=models.CASCADE, related_name="alerts")
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="alerts")
    param = models.CharField(max_length=20)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    reading = models.FloatField()
    limit_value = models.FloatField()
    since = models.DateTimeField(default=timezone.now)
    recovered_at = models.DateTimeField(null=True, blank=True)
    # SMS bookkeeping (cool-down so a flapping machine does not spam phones)
    notified_at = models.DateTimeField(null=True, blank=True)
    notified_severity = models.CharField(max_length=10, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["threshold", "machine"], name="unique_alert_per_threshold_machine")]
        indexes = [models.Index(fields=["status", "-since"])]

    @property
    def key(self):
        return f"t{self.threshold_id}:{self.machine_id}"


class NotificationSettings(models.Model):
    """A plant owner's notification choices (docs/API.md: /settings/notifications)."""

    class Frequency(models.TextChoices):
        DAY = "day"
        WEEK = "week"
        MONTH = "month"

    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_settings")
    alerts_enabled = models.BooleanField(default=True)
    auto_reports = models.BooleanField(default=False)
    report_frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.DAY)
    # The period (e.g. "2026-11-07", "2026-W45", "2026-10") whose report was last emailed.
    # Stops the same report going out twice.
    last_report_key = models.CharField(max_length=20, blank=True)
