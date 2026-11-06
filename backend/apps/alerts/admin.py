from django.contrib import admin

from .models import Alert, PhoneNumber, Threshold


@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    list_display = ["param", "machine", "warning", "critical"]


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ["label", "digits"]


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ["machine", "param", "severity", "status", "reading", "since", "recovered_at"]
    list_filter = ["status", "severity"]
