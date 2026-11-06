from datetime import timedelta

import pytest
from django.db.models import Sum
from django.utils import timezone

from apps.alerts.models import Alert, PhoneNumber, Threshold
from apps.common import sms
from apps.telemetry.models import HourlyReport, MachineState, Reading

from .conftest import push

pytestmark = pytest.mark.django_db


def ms(dt):
    return int(dt.timestamp() * 1000)


def reading(meter, t, kw=20.0, pf=0.93, kwh=None, **extra):
    body = {"meterId": meter, "ts": ms(t), "kw": kw, "pf": pf}
    if kwh is not None:
        body["kwh"] = kwh
    body.update(extra)
    return body


def machine_json(client, machine_id):
    machines = client.get("/api/machines").json()["machines"]
    return next(m for m in machines if m["id"] == machine_id)


def test_gateway_key_is_required(anon, gateway, machines):
    now = timezone.now()
    r = push(anon, gateway, [reading("1", now)], key="gw_wrong")
    assert r.status_code == 401 and r.json()["code"] == "invalid_gateway_key"
    assert anon.post("/api/ingest", {"readings": []}, format="json").status_code == 401


def test_disabled_gateway_is_refused(anon, gateway, machines):
    gateway.enabled = False
    gateway.save()
    assert push(anon, gateway, [reading("1", timezone.now())]).status_code == 403


def test_ingest_updates_live_state_and_report(anon, admin_client, gateway, machines, pf_threshold):
    t0 = timezone.now() - timedelta(minutes=10)
    r = push(anon, gateway, [
        reading("1", t0, kw=20, kwh=1000.0),
        reading("1", t0 + timedelta(seconds=60), kw=24, kwh=1000.4, current=38.5),
        reading("1", t0 + timedelta(seconds=120), kw=26, kwh=1000.85),
    ])
    assert r.status_code == 202 and r.json()["accepted"] == 3

    m = machine_json(admin_client, "sheller-1")
    assert m["on"] is True
    assert m["kw"] == 26 and m["pf"] == 0.93
    assert m["totalKwh"] == 1000.85
    assert m["runSec"] == 120 and m["todaySec"] == 120
    assert m["runKwh"] == pytest.approx(0.85)
    assert m["loadFactor"] == pytest.approx(26 / 36 * 100, abs=0.1)
    assert m["avgPfRun"] == 0.93
    assert m["runStart"] == ms(t0) and m["lastStop"] is None
    assert sum(m["hourlyKwh"]) == pytest.approx(0.85, abs=0.01)
    assert len(m["hourlyKwh"]) == 24 and len(m["hourOn"]) == 24

    # consolidated hourly report (one row, maybe two if the batch straddles an IST hour)
    totals = HourlyReport.objects.filter(machine_id="sheller-1").aggregate(k=Sum("kwh"), s=Sum("run_seconds"))
    assert totals["k"] == pytest.approx(0.85) and totals["s"] == 120


def test_serverTime_and_updatedAt_use_the_servers_clock(anon, admin_client, gateway, machines):
    # a gateway whose clock is 4 minutes behind still looks live
    push(anon, gateway, [reading("1", timezone.now() - timedelta(minutes=4))])
    body = admin_client.get("/api/machines").json()
    m = next(x for x in body["machines"] if x["id"] == "sheller-1")
    assert 0 <= body["serverTime"] - m["updatedAt"] < 5000


def test_off_machine_reports_zeroes_and_stop_time(anon, admin_client, gateway, machines):
    t0 = timezone.now() - timedelta(minutes=5)
    push(anon, gateway, [reading("1", t0, kw=20), reading("1", t0 + timedelta(seconds=30), kw=0.0, pf=0)])
    m = machine_json(admin_client, "sheller-1")
    assert m["on"] is False
    assert (m["kw"], m["pf"], m["kva"], m["current"], m["loadFactor"], m["runKwh"], m["runSec"]) == (0,) * 7
    assert m["avgPfRun"] is None and m["runStart"] is None
    assert m["lastStop"] == ms(t0 + timedelta(seconds=30))
    assert m["todaySec"] == 30  # it ran for the first 30 s interval


def test_duplicate_and_late_samples_do_not_double_count(anon, admin_client, gateway, machines):
    t0 = timezone.now() - timedelta(minutes=5)
    batch = [reading("1", t0, kwh=10.0), reading("1", t0 + timedelta(seconds=60), kwh=10.5)]
    push(anon, gateway, batch)
    push(anon, gateway, batch)  # gateway retried the same batch
    push(anon, gateway, [reading("1", t0 - timedelta(seconds=30), kwh=9.0)])  # arrives late
    m = machine_json(admin_client, "sheller-1")
    assert m["totalKwh"] == 10.5 and m["runSec"] == 60
    assert HourlyReport.objects.filter(machine_id="sheller-1").aggregate(k=Sum("kwh"))["k"] == pytest.approx(0.5)


def test_energy_falls_back_to_integrating_power_without_counters(anon, admin_client, gateway, machines):
    t0 = timezone.now() - timedelta(minutes=5)
    push(anon, gateway, [reading("1", t0, kw=36), reading("1", t0 + timedelta(seconds=100), kw=36)])
    m = machine_json(admin_client, "sheller-1")
    assert m["runKwh"] == pytest.approx(36 * 100 / 3600, abs=0.01)


def test_counter_glitch_is_ignored(anon, admin_client, gateway, machines):
    t0 = timezone.now() - timedelta(minutes=5)
    push(anon, gateway, [
        reading("1", t0, kw=20, kwh=100.0),
        reading("1", t0 + timedelta(seconds=60), kw=20, kwh=5000.0),  # absurd jump for one minute
    ])
    m = machine_json(admin_client, "sheller-1")
    assert m["runKwh"] == pytest.approx(20 / 60, abs=0.01)  # integrated, not the glitch


def test_bad_readings_are_rejected_individually(anon, gateway, machines):
    now = timezone.now()
    r = push(anon, gateway, [
        reading("1", now),
        {"meterId": "1", "ts": ms(now), "kw": "abc"},
        {"meterId": "1", "ts": ms(now + timedelta(hours=2)), "kw": 5},
        {"meterId": "1", "ts": ms(now), "kw": 5, "pf": 1.7},
        reading("99", now),  # not a registered meter
    ])
    body = r.json()
    # `accepted` counts readings stored for registered meters; unknown meters are listed apart
    assert r.status_code == 202 and body["accepted"] == 1
    assert [x["index"] for x in body["rejected"]] == [1, 2, 3]
    assert body["unknownMeters"] == ["99"]


def test_request_with_nothing_valid_is_422(anon, gateway, machines):
    r = push(anon, gateway, [{"meterId": "1", "kw": "x"}])
    assert r.status_code == 422 and r.json()["rejected"][0]["index"] == 0


def test_single_reading_body_and_second_timestamps_are_accepted(anon, admin_client, gateway, machines):
    now = timezone.now()
    r = anon.post("/api/ingest", {"meterId": "1", "ts": int(now.timestamp()), "kw": 12}, format="json", HTTP_X_GATEWAY_KEY=gateway.raw_key)
    assert r.status_code == 202
    assert machine_json(admin_client, "sheller-1")["kw"] == 12


def test_derived_values_are_filled_in(anon, admin_client, gateway, machines):
    push(anon, gateway, [{"meterId": "1", "ts": ms(timezone.now()), "kw": 30, "kva": 40}])
    m = machine_json(admin_client, "sheller-1")
    assert m["pf"] == 0.75 and m["kva"] == 40 and m["kvar"] == pytest.approx(26.46, abs=0.01) and m["current"] > 0


def test_raw_samples_are_thinned_but_state_changes_are_kept(anon, gateway, machines, settings):
    settings.RAW_SAMPLE_INTERVAL_SEC = 15
    t0 = timezone.now() - timedelta(minutes=5)
    push(anon, gateway, [reading("1", t0 + timedelta(seconds=s)) for s in range(0, 30, 2)])
    assert Reading.objects.filter(machine_id="sheller-1").count() == 2  # t0 and t0+16s
    push(anon, gateway, [reading("1", t0 + timedelta(seconds=31), kw=0.0, pf=0)])  # stops: always kept
    assert Reading.objects.filter(machine_id="sheller-1").count() == 3


# --- alerts -----------------------------------------------------------------
def test_low_power_factor_raises_critical_alert_and_sends_sms(anon, admin_client, gateway, machines, pf_threshold):
    PhoneNumber.objects.create(digits="9000000001", label="Primary")
    now = timezone.now()
    push(anon, gateway, [reading("3", now, kw=15, pf=0.79)])
    alerts = admin_client.get("/api/alerts?plant=Plant 1").json()
    assert len(alerts) == 1
    a = alerts[0]
    assert (a["machineId"], a["param"], a["severity"], a["status"]) == ("whitener-2", "powerFactor", "critical", "active")
    assert a["reading"] == 0.79 and a["limit"] == 0.8 and a["plant"] == "Plant 1" and a["recoveredAt"] is None
    assert len(sms.outbox) == 1 and sms.outbox[0][0] == "9000000001" and "CRITICAL" in sms.outbox[0][1]

    # a second batch does not text again
    push(anon, gateway, [reading("3", now + timedelta(seconds=5), kw=15, pf=0.78)])
    assert len(sms.outbox) == 1


def test_warning_then_escalation_then_recovery(anon, admin_client, gateway, machines, pf_threshold):
    PhoneNumber.objects.create(digits="9000000001")
    t = timezone.now() - timedelta(minutes=1)
    push(anon, gateway, [reading("1", t, pf=0.85)])
    assert admin_client.get("/api/alerts").json()[0]["severity"] == "warning"
    assert len(sms.outbox) == 1

    push(anon, gateway, [reading("1", t + timedelta(seconds=5), pf=0.75)])
    assert admin_client.get("/api/alerts").json()[0]["severity"] == "critical"
    assert len(sms.outbox) == 2  # escalation texts again

    push(anon, gateway, [reading("1", t + timedelta(seconds=10), pf=0.95)])
    a = admin_client.get("/api/alerts").json()[0]
    assert a["status"] == "recovered" and a["recoveredAt"] is not None
    assert len(sms.outbox) == 2  # recovery is not texted


def test_off_machines_and_sortex_never_alert(anon, admin_client, gateway, machines, pf_threshold):
    now = timezone.now()
    push(anon, gateway, [reading("1", now, kw=0.0, pf=0.1), reading("4", now, kw=12, pf=0.5)])
    assert admin_client.get("/api/alerts").json() == []


def test_machine_going_off_recovers_its_alert(anon, admin_client, gateway, machines, pf_threshold):
    t = timezone.now() - timedelta(minutes=1)
    push(anon, gateway, [reading("3", t, pf=0.7)])
    push(anon, gateway, [reading("3", t + timedelta(seconds=10), kw=0.0, pf=0)])
    assert admin_client.get("/api/alerts").json()[0]["status"] == "recovered"


def test_machine_specific_threshold_overrides_all(anon, admin_client, gateway, machines, pf_threshold):
    Threshold.objects.create(param="powerFactor", machine=machines["whitener-2"], warning=0.7, critical=0.6)
    push(anon, gateway, [reading("3", timezone.now(), pf=0.75)])  # below "all" (0.8) but above its own 0.7
    assert admin_client.get("/api/alerts").json() == []


def test_changing_thresholds_reevaluates_immediately(anon, admin_client, gateway, machines, django_capture_on_commit_callbacks):
    push(anon, gateway, [reading("3", timezone.now(), pf=0.85)])
    assert admin_client.get("/api/alerts").json() == []
    with django_capture_on_commit_callbacks(execute=True):
        r = admin_client.post("/api/thresholds", {"param": "powerFactor", "machineId": "all", "warning": 0.9, "critical": 0.8}, format="json")
    assert r.status_code == 201
    assert admin_client.get("/api/alerts").json()[0]["severity"] == "warning"


def test_sms_cooldown_suppresses_flapping(anon, gateway, machines, pf_threshold):
    PhoneNumber.objects.create(digits="9000000001")
    t = timezone.now() - timedelta(minutes=2)
    for i, pf in enumerate([0.7, 0.95, 0.7, 0.95, 0.7]):  # flaps across the limit
        push(anon, gateway, [reading("3", t + timedelta(seconds=10 * i), pf=pf)])
    assert len(sms.outbox) == 1
    assert Alert.objects.get().status == "active"


def test_state_row_is_created_per_machine(anon, gateway, machines):
    push(anon, gateway, [reading("1", timezone.now())])
    assert MachineState.objects.filter(machine_id="sheller-1").exists()
    assert not MachineState.objects.filter(machine_id="whitener-2").exists()


def test_hovering_at_a_limit_does_not_text_repeatedly(anon, gateway, machines, pf_threshold):
    PhoneNumber.objects.create(digits="9000000001")
    t = timezone.now() - timedelta(minutes=2)
    # critical -> warning -> critical -> warning -> critical, all within the cool-down
    for i, pf in enumerate([0.78, 0.82, 0.78, 0.82, 0.78]):
        push(anon, gateway, [reading("3", t + timedelta(seconds=10 * i), pf=pf)])
    assert len(sms.outbox) == 1
