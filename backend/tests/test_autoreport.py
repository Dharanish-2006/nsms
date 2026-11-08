"""Automatic report emails."""

import csv
import io
from datetime import date, datetime, timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.alerts.autoreport import current_period, last_finished_period, send_due_reports
from apps.alerts.models import NotificationSettings
from apps.plants.models import ConnectionPeriod
from apps.telemetry.models import HourlyReport

from .conftest import connect

pytestmark = pytest.mark.django_db


def at(y, m, d, hour):
    return timezone.make_aware(datetime(y, m, d, hour, 0))


def test_periods():
    # Sun 8 Nov 2026
    today = date(2026, 11, 8)
    assert last_finished_period("day", today).key == "2026-11-07"
    w = last_finished_period("week", today)  # last full Mon-Sun: 26 Oct - 1 Nov
    assert (w.key, w.start.date(), (w.end - timedelta(seconds=1)).date()) == ("2026-W44", date(2026, 10, 26), date(2026, 11, 1))
    m = last_finished_period("month", today)
    assert (m.key, m.start.date(), m.end.date()) == ("2026-10", date(2026, 10, 1), date(2026, 11, 1))
    assert last_finished_period("month", date(2026, 1, 15)).key == "2025-12"  # across the year
    assert current_period("week", today).key == "2026-W45" and current_period("month", today).key == "2026-11"


def hours(machine, day, kwh):
    HourlyReport.objects.create(
        machine=machine, hour=at(day.year, day.month, day.day, 10), kwh=kwh, run_kwh=kwh, run_seconds=3600,
        samples=10, sum_kw=100, max_kw=12, max_current=20, pf_samples=10, sum_pf=9,
    )  # fmt: skip


@pytest.fixture
def prefs(operator, gateway, machines):
    connect(operator, gateway)
    ConnectionPeriod.objects.update(start=at(2026, 10, 1, 0))
    return NotificationSettings.objects.create(owner=operator, auto_reports=True, report_frequency="day")


def now_at(day, hour):
    return at(day.year, day.month, day.day, hour)


def test_sends_yesterdays_report_once_with_csv(prefs, operator, machines):
    hours(machines["sheller-1"], date(2026, 11, 7), 40)
    assert send_due_reports(now_at(date(2026, 11, 8), 7)) == 1
    msg = mail.outbox[0]
    assert msg.to == [operator.email] and "07 Nov 2026" in msg.subject and "40.0 kWh" in msg.body
    name, content, kind = msg.attachments[0]
    assert name == "rice-mill-report-2026-11-07.csv" and kind == "text/csv"
    rows = {r["Machine"]: r for r in csv.DictReader(io.StringIO(content))}
    assert list(rows["Sheller"]) [:3] == ["Machine", "Plant", "Motor (HP)"]
    assert rows["Sheller"]["Plant"] == "Plant 1" and float(rows["Sheller"]["Energy (kWh)"]) == 40
    assert rows["Sheller"]["Motor (HP)"] == "48.3"  # 36 kW rating, shown in HP

    assert send_due_reports(now_at(date(2026, 11, 8), 9)) == 0  # same period: not again
    assert len(mail.outbox) == 1
    assert send_due_reports(now_at(date(2026, 11, 9), 7)) == 1  # next day: next report
    assert "2026-11-08" in mail.outbox[1].attachments[0][0]


@override_settings(AUTO_REPORT_HOUR=6)
def test_waits_for_the_configured_hour(prefs):
    assert send_due_reports(now_at(date(2026, 11, 8), 5)) == 0
    assert send_due_reports(now_at(date(2026, 11, 8), 5), ignore_hour=True) == 1


def test_off_means_nothing_is_sent(prefs):
    NotificationSettings.objects.update(auto_reports=False)
    assert send_due_reports(now_at(date(2026, 11, 8), 8)) == 0 and mail.outbox == []


def test_weekly_and_monthly(prefs):
    NotificationSettings.objects.update(report_frequency="week")
    assert send_due_reports(now_at(date(2026, 11, 8), 8)) == 1 and "2026-W44" in mail.outbox[-1].attachments[0][0]
    NotificationSettings.objects.update(report_frequency="month", last_report_key="")
    assert send_due_reports(now_at(date(2026, 11, 8), 8)) == 1 and "2026-10" in mail.outbox[-1].attachments[0][0]


def test_only_the_owners_connected_hours_are_reported(prefs, operator, machines):
    hours(machines["sheller-1"], date(2026, 11, 7), 40)
    ConnectionPeriod.objects.update(start=at(2026, 11, 7, 12))  # connected after the 10:00 hour
    send_due_reports(now_at(date(2026, 11, 8), 8))
    rows = {r["Machine"]: r for r in csv.DictReader(io.StringIO(mail.outbox[0].attachments[0][1]))}
    assert float(rows["Sheller"]["Energy (kWh)"]) == 0
    assert "Total energy used: 0 kWh" in mail.outbox[0].body


def test_failed_send_is_retried_next_run(prefs, monkeypatch):
    from django.core.mail import EmailMessage

    def boom(self, *a, **k):
        raise OSError("smtp down")

    monkeypatch.setattr(EmailMessage, "send", boom)
    assert send_due_reports(now_at(date(2026, 11, 8), 8)) == 0
    assert NotificationSettings.objects.get().last_report_key == ""  # not marked as sent
    monkeypatch.undo()
    assert send_due_reports(now_at(date(2026, 11, 8), 9)) == 1


def test_owner_with_nothing_connected_gets_no_empty_report(operator):
    NotificationSettings.objects.create(owner=operator, auto_reports=True)
    assert send_due_reports(now_at(date(2026, 11, 8), 8)) == 0 and mail.outbox == []


def test_turning_it_on_starts_with_the_next_period(owner_client, operator):
    r = owner_client.put("/api/settings/notifications", {"alertsEnabled": True, "autoReports": True, "reportFrequency": "week"}, format="json")
    assert r.status_code == 200
    key = NotificationSettings.objects.get(owner=operator).last_report_key
    assert key == current_period("week").key  # not a report for a period that has already ended
    # saving again with no change leaves it alone
    owner_client.put("/api/settings/notifications", {"alertsEnabled": False, "autoReports": True, "reportFrequency": "week"}, format="json")
    assert NotificationSettings.objects.get(owner=operator).last_report_key == key
