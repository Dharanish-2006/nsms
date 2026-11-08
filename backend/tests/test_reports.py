from datetime import timedelta

import pytest
from django.db.models import F
from django.utils import timezone

from apps.telemetry.consolidate import consolidate_day
from apps.telemetry.models import DailyReport
from apps.telemetry.management.commands.run_maintenance import run_once
from apps.telemetry.models import Reading

from .conftest import push

pytestmark = pytest.mark.django_db


def ms(dt):
    return int(dt.timestamp() * 1000)


def feed(anon, gateway, meter="1", start=None, minutes=10, kw=24.0, pf=0.9, kwh0=500.0):
    """One reading per minute with a consistent kWh counter."""
    start = start or timezone.now() - timedelta(minutes=minutes + 1)
    rows = [
        {"meterId": meter, "ts": ms(start + timedelta(minutes=i)), "kw": kw, "pf": pf,
         "kwh": kwh0 + kw * i / 60}
        for i in range(minutes + 1)
    ]  # fmt: skip
    assert push(anon, gateway, rows).status_code == 202
    return kw * minutes / 60  # kWh covered


def test_usage_sums_consumed_and_running_energy(anon, owner_client, gateway, machines):
    expected = feed(anon, gateway)
    r = owner_client.get("/api/machines/usage?range=week")
    assert r.status_code == 200
    assert r.json()["consumedKwh"] == pytest.approx(expected, abs=0.1)
    assert r.json()["actualKwh"] == pytest.approx(expected, abs=0.1)
    assert owner_client.get("/api/machines/usage?range=month&plant=Plant 1").json()["consumedKwh"] > 0
    assert owner_client.get("/api/machines/usage?range=month&plant=Nowhere").json() == {"consumedKwh": 0, "actualKwh": 0}
    r = owner_client.get("/api/machines/usage?range=year")
    assert r.status_code == 422 and r.json()["code"] == "validation"


def test_idle_draw_counts_as_consumed_but_not_actual(anon, owner_client, gateway, machines):
    t = timezone.now() - timedelta(minutes=10)
    rows = []
    for i in range(11):  # machine "off" (flag) but the meter still counts a little standby energy
        rows.append({"meterId": "1", "ts": ms(t + timedelta(minutes=i)), "kw": 0.3, "on": False, "kwh": 10 + 0.3 * i / 60})
    push(anon, gateway, rows)
    body = owner_client.get("/api/machines/usage?range=week").json()
    assert body["consumedKwh"] > 0 and body["actualKwh"] == 0


def test_trend_returns_oldest_first_buckets(anon, owner_client, gateway, machines):
    feed(anon, gateway, minutes=30, pf=0.91)
    r = owner_client.get("/api/machines/sheller-1/trend?hours=1")
    assert r.status_code == 200
    points = r.json()
    assert len(points) >= 2
    assert [p["t"] for p in points] == sorted(p["t"] for p in points)
    assert set(points[0]) == {"t", "pf", "current", "kw"}
    assert points[0]["pf"] == pytest.approx(0.91, abs=0.001) and points[0]["kw"] == pytest.approx(24, abs=0.01)
    assert owner_client.get("/api/machines/sheller-1/trend?hours=0").status_code == 422
    assert owner_client.get("/api/machines/sheller-1/trend?hours=999").status_code == 422
    assert owner_client.get("/api/machines/nope/trend").status_code == 404


def test_daily_report_is_consolidated_into_the_database(anon, owner_client, gateway, machines):
    expected = feed(anon, gateway, kw=30, pf=0.92)
    r = owner_client.get("/api/reports/daily")
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == timezone.localdate().isoformat()
    row = next(m for m in body["machines"] if m["machineId"] == "sheller-1")
    assert row["kwh"] == pytest.approx(expected, abs=0.1)
    assert row["avgPf"] == pytest.approx(0.92, abs=0.001)
    assert row["maxKw"] == 30 and row["runSeconds"] == 600
    idle = next(m for m in body["machines"] if m["machineId"] == "whitener-2")
    assert idle["kwh"] == 0 and idle["avgPf"] is None

    # The nightly roll-up stored for operations is idempotent
    consolidate_day(timezone.localdate())
    consolidate_day(timezone.localdate())
    assert DailyReport.objects.filter(machine_id="sheller-1", date=timezone.localdate()).count() == 1

    assert owner_client.get("/api/reports/daily?date=2999-01-01").status_code == 422
    assert owner_client.get("/api/reports/daily?date=garbage").status_code == 422


def test_maintenance_prunes_old_raw_readings_but_keeps_reports(anon, gateway, machines, settings):
    settings.RAW_RETENTION_DAYS = 7
    feed(anon, gateway)
    Reading.objects.update(ts=F("ts") - timedelta(days=30))
    rows, pruned, _ = run_once()
    assert pruned > 0 and Reading.objects.count() == 0
    assert DailyReport.objects.filter(machine_id="sheller-1").exists()
