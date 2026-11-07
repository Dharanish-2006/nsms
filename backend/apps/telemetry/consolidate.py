"""Roll the hourly reports up into one DailyReport row per machine per IST day.

Safe to run as often as you like: each run recomputes the day from the hourly rows.
"""

from datetime import datetime, time, timedelta

from django.db.models import Max, Sum
from django.utils import timezone

from .models import DailyReport, HourlyReport


def day_bounds(day):
    start = timezone.make_aware(datetime.combine(day, time.min))
    return start, start + timedelta(days=1)


def consolidate_day(day, machine_ids=None):
    """(Re)build the DailyReport rows of one IST date. Returns the number of rows written."""
    start, end = day_bounds(day)
    rows = HourlyReport.objects.filter(hour__gte=start, hour__lt=end)
    if machine_ids is not None:
        rows = rows.filter(machine_id__in=list(machine_ids))
    totals = rows.values("machine_id").annotate(
        kwh=Sum("kwh"), run_kwh=Sum("run_kwh"), kvarh=Sum("kvarh"), kvah=Sum("kvah"),
        run_seconds=Sum("run_seconds"), samples=Sum("samples"), sum_kw=Sum("sum_kw"),
        max_kw=Max("max_kw"), max_current=Max("max_current"),
        pf_samples=Sum("pf_samples"), sum_pf=Sum("sum_pf"),
    )  # fmt: skip
    written = 0
    for t in totals:
        samples = t["samples"] or 0
        DailyReport.objects.update_or_create(
            machine_id=t["machine_id"],
            date=day,
            defaults={
                "kwh": t["kwh"] or 0,
                "run_kwh": t["run_kwh"] or 0,
                "kvarh": t["kvarh"] or 0,
                "kvah": t["kvah"] or 0,
                "run_seconds": t["run_seconds"] or 0,
                "samples": samples,
                "avg_kw": (t["sum_kw"] or 0) / samples if samples else 0,
                "max_kw": t["max_kw"] or 0,
                "max_current": t["max_current"] or 0,
                "avg_pf": (t["sum_pf"] / t["pf_samples"]) if t["pf_samples"] else None,
            },
        )
        written += 1
    return written
