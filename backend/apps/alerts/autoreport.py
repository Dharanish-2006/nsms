import csv
import io
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.plants.access import accessible_machines
from apps.telemetry.reports import owner_report_rows

from .models import NotificationSettings

logger = logging.getLogger(__name__)

HEADER = [
    "Machine", "Plant", "Motor (HP)", "Energy (kWh)", "Running energy (kWh)", "Reactive (kVArh)",
    "Apparent (kVAh)", "Run time (h)", "Average kW", "Peak kW", "Average power factor", "Peak current (A)",
]  # fmt: skip


@dataclass(frozen=True)
class Period:
    key: str
    label: str
    start: datetime
    end: datetime


def _midnight(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _period_for(freq, first_day, last_day):
    start, end = _midnight(first_day), _midnight(last_day + timedelta(days=1))
    if freq == "day":
        return Period(first_day.isoformat(), first_day.strftime("%d %b %Y"), start, end)
    if freq == "week":
        year, week, _ = first_day.isocalendar()
        label = f"{first_day.strftime('%d %b')} to {last_day.strftime('%d %b %Y')}"
        return Period(f"{year}-W{week:02d}", label, start, end)
    return Period(first_day.strftime("%Y-%m"), first_day.strftime("%B %Y"), start, end)


def last_finished_period(freq, today=None):
    today = today or timezone.localdate()
    if freq == "day":
        d = today - timedelta(days=1)
        return _period_for(freq, d, d)
    if freq == "week":
        monday = today - timedelta(days=today.weekday())
        return _period_for(freq, monday - timedelta(days=7), monday - timedelta(days=1))
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return _period_for(freq, last_prev.replace(day=1), last_prev)


def current_period(freq, today=None):
    today = today or timezone.localdate()
    if freq == "day":
        return _period_for(freq, today, today)
    if freq == "week":
        monday = today - timedelta(days=today.weekday())
        return _period_for(freq, monday, monday + timedelta(days=6))
    first = today.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return _period_for(freq, first, nxt - timedelta(days=1))


def build_csv(rows):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(HEADER)
    for r in rows:
        w.writerow(
            [
                r["machineName"], r["plant"], "" if r["motorHp"] is None else r["motorHp"], r["kwh"],
                r["runKwh"], r["kvarh"], r["kvah"], round(r["runSeconds"] / 3600, 2), r["avgKw"], r["maxKw"],
                "" if r["avgPf"] is None else r["avgPf"], r["maxCurrent"],
            ]
        )  # fmt: skip
    return out.getvalue()


def send_report(owner, period):
    machines = list(accessible_machines(owner))
    rows = owner_report_rows(owner, period.start, period.end, machines)
    total = round(sum(r["kwh"] for r in rows), 2)
    body = (
        f"Hello {owner.full_name or owner.username},\n\n"
        f"Your Rice Mill Monitor report for {period.label} is attached.\n"
        f"Total energy used: {total} kWh across {len(rows)} machine(s).\n\n"
        "You can switch automatic reports off in Settings."
    )
    message = EmailMessage(f"Rice Mill report: {period.label}", body, None, [owner.email])
    message.attach(f"rice-mill-report-{period.key}.csv", build_csv(rows), "text/csv")
    message.send()
    return total


def send_due_reports(now=None, ignore_hour=False, only_user=None):
    now = timezone.localtime(now or timezone.now())
    if not ignore_hour and now.hour < settings.AUTO_REPORT_HOUR:
        return 0
    sent = 0
    qs = NotificationSettings.objects.filter(auto_reports=True, owner__is_active=True, owner__status="active", owner__role="user")
    if only_user is not None:
        qs = qs.filter(owner=only_user)
    for prefs in qs.select_related("owner"):
        owner = prefs.owner
        period = last_finished_period(prefs.report_frequency, now.date())
        if prefs.last_report_key == period.key or not owner.email:
            continue
        if not accessible_machines(owner).exists():
            NotificationSettings.objects.filter(pk=prefs.pk).update(last_report_key=period.key)
            continue
        try:
            send_report(owner, period)
        except Exception:  # noqa: BLE001 
            logger.exception("Could not send the automatic report to user %s", owner.pk)
            continue
        NotificationSettings.objects.filter(pk=prefs.pk).update(last_report_key=period.key)
        sent += 1
    return sent
