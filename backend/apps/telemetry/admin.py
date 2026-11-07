from django.contrib import admin

from .models import DailyReport, HourlyReport, MachineState, Reading


@admin.register(MachineState)
class MachineStateAdmin(admin.ModelAdmin):
    list_display = ["machine", "on", "kw", "pf", "last_ts", "received_at"]
    readonly_fields = [f.name for f in MachineState._meta.fields]


@admin.register(HourlyReport)
class HourlyReportAdmin(admin.ModelAdmin):
    list_display = ["machine", "hour", "kwh", "run_kwh", "run_seconds", "samples"]
    list_filter = ["machine"]
    date_hierarchy = "hour"


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ["machine", "date", "kwh", "run_kwh", "run_seconds", "avg_pf"]
    list_filter = ["machine"]
    date_hierarchy = "date"


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ["machine", "ts", "on", "kw", "pf", "current"]
    list_filter = ["machine"]
    date_hierarchy = "ts"
