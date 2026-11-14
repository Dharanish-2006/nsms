from django.conf import settings
from django.db import models


class Enquiry(models.Model):
    """A message sent from the public Contact form. Kept even if the team email fails."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=10)  # 10-digit Indian mobile, digits only
    requirement = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    emailed = models.BooleanField(default=False)  # the team was notified by email
    created_at = models.DateTimeField(auto_now_add=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.name} ({self.mobile})"
