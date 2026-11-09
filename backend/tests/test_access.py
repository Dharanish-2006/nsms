"""Plant owners see only what they are connected to; thresholds, phones and settings are theirs."""

import pytest
from django.utils import timezone

from apps.alerts.models import Threshold
from apps.plants.models import Gateway, Machine, Plant

from .conftest import client_for, connect, push

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_gateway():
    plant = Plant.objects.create(name="Plant 2")
    gw = Gateway(name="Gateway B", plant=plant)
    gw.save()
    gw.raw_key = gw._first_key
    Machine.objects.create(id="huller-9", name="Huller", type="sheller", rated_kw=30, gateway=gw, meter_id="1")
    return gw


def ids(response):
    return sorted(m["id"] for m in response.json()["machines"])


def test_owner_sees_only_connected_gateways(anon, operator, other_user, gateway, second_gateway, machines):
    now = timezone.now()
    push(anon, gateway, [{"meterId": "1", "ts": int(now.timestamp() * 1000), "kw": 20}])

    mine = client_for(operator)
    assert ids(mine.get("/api/machines")) == []  # nothing connected yet
    assert mine.get("/api/plants").json() == []

    connect(operator, gateway)
    assert ids(mine.get("/api/machines")) == ["sheller-1", "sortex-1", "whitener-2"]
    assert mine.get("/api/plants").json() == ["Plant 1"]
    assert ids(mine.get("/api/machines?plant=Plant 2")) == []
    assert ids(client_for(other_user).get("/api/machines")) == []

    # A machine on someone else's gateway is invisible by id as well
    assert mine.get("/api/machines/huller-9/trend").status_code == 404
    assert mine.get("/api/machines/sheller-1/trend?hours=1").status_code == 200
    assert mine.put("/api/machines/huller-9", {"ratedKw": 1}, format="json").status_code == 404


def test_assigned_but_not_connected_sees_nothing(operator, gateway, machines):
    from apps.plants.models import GatewayAssignment

    GatewayAssignment.objects.create(gateway=gateway, user=operator)  # status: assigned
    assert ids(client_for(operator).get("/api/machines")) == []


def test_admin_has_no_access_to_monitoring_data(admin_client, anon, gateway, machines, operator):
    connect(operator, gateway)
    push(anon, gateway, [{"meterId": "1", "kw": 20}])
    for path in ("/api/machines", "/api/machines/usage?range=week", "/api/machines/sheller-1/trend",
                 "/api/alerts", "/api/reports/daily", "/api/thresholds", "/api/phones",
                 "/api/settings/notifications", "/api/plants"):  # fmt: skip
        assert admin_client.get(path).status_code == 403, path


def test_alerts_are_scoped_to_the_connected_owner(anon, operator, other_user, gateway, second_gateway, machines, pf_threshold):
    now = int(timezone.now().timestamp() * 1000)
    connect(operator, gateway)
    connect(other_user, second_gateway)
    Threshold.objects.create(owner=other_user, param="powerFactor", machine=None, warning=0.9, critical=0.8)
    push(anon, gateway, [{"meterId": "3", "ts": now, "kw": 15, "pf": 0.7}])
    push(anon, second_gateway, [{"meterId": "1", "ts": now, "kw": 15, "pf": 0.7}])
    assert [a["machineId"] for a in client_for(operator).get("/api/alerts").json()] == ["whitener-2"]
    assert [a["machineId"] for a in client_for(other_user).get("/api/alerts").json()] == ["huller-9"]


# --- machines: the owner edits their own -----------------------------------------------
def test_owner_edits_machine_rating_but_not_name_or_wiring(owner_client, gateway, machines):
    r = owner_client.put("/api/machines/sheller-1", {"ratedKw": 37.285, "name": "Sheller One", "type": "sortex"}, format="json")
    assert r.status_code == 200 and r.json()["ratedKw"] == 37.285
    assert r.json()["name"] == "Sheller" and r.json()["type"] == "sheller"  # the admin names machines
    r = owner_client.put("/api/machines/sheller-1", {"meterId": "9", "gatewayId": "x"}, format="json")
    assert r.status_code == 200 and Machine.objects.get(pk="sheller-1").meter_id == "1"  # ignored
    assert owner_client.put("/api/machines/sheller-1", {"ratedKw": -1}, format="json").status_code == 422
    assert owner_client.post("/api/machines", {}, format="json").status_code == 405
    assert owner_client.delete("/api/machines/sheller-1").status_code == 405


# --- thresholds & phones: per owner ----------------------------------------------------
def test_threshold_validation_and_ownership(owner_client, other_user, machines):
    ok = {"param": "powerFactor", "machineId": "all", "warning": 0.9, "critical": 0.8}
    assert owner_client.post("/api/thresholds", {"param": "powerFactor", "machineId": "all"}, format="json").status_code == 422
    r = owner_client.post("/api/thresholds", {**ok, "warning": 0.8, "critical": 0.9}, format="json")
    assert r.status_code == 422 and "critical" in r.json()["message"].lower()
    assert owner_client.post("/api/thresholds", {**ok, "warning": 1.5}, format="json").status_code == 422
    assert owner_client.post("/api/thresholds", {**ok, "machineId": "nope"}, format="json").status_code == 422

    created = owner_client.post("/api/thresholds", ok, format="json").json()
    assert owner_client.post("/api/thresholds", ok, format="json").status_code == 409  # duplicate
    only_critical = {"param": "powerFactor", "machineId": "sheller-1", "warning": None, "critical": 0.7}
    assert owner_client.post("/api/thresholds", only_critical, format="json").status_code == 201
    r = owner_client.put(f"/api/thresholds/{created['id']}", {**ok, "warning": 0.95}, format="json")
    assert r.status_code == 200 and r.json()["warning"] == 0.95

    # Another owner can neither see nor touch it
    theirs = client_for(other_user)
    assert theirs.get("/api/thresholds").json() == []
    assert theirs.put(f"/api/thresholds/{created['id']}", ok, format="json").status_code == 404
    assert theirs.delete(f"/api/thresholds/{created['id']}").status_code == 404

    assert owner_client.delete(f"/api/thresholds/{created['id']}").status_code == 204
    assert Threshold.objects.count() == 1


def test_phone_numbers_are_per_owner(owner_client, other_user):
    assert owner_client.post("/api/phones", {"digits": "12345"}, format="json").status_code == 422
    r = owner_client.post("/api/phones", {"digits": "9000000001", "label": "Primary contact"}, format="json")
    assert r.status_code == 201 and r.json()["digits"] == "9000000001"
    assert owner_client.post("/api/phones", {"digits": "9000000001"}, format="json").status_code == 409
    other = owner_client.post("/api/phones", {"digits": "9000000002"}, format="json").json()
    assert owner_client.put(f"/api/phones/{other['id']}", {"digits": "9000000001", "label": "x"}, format="json").status_code == 409
    assert owner_client.put(f"/api/phones/{other['id']}", {"digits": "9000000003", "label": "x"}, format="json").status_code == 200

    theirs = client_for(other_user)
    assert theirs.get("/api/phones").json() == []
    assert theirs.post("/api/phones", {"digits": "9000000001"}, format="json").status_code == 201  # same number, own list
    assert theirs.delete(f"/api/phones/{other['id']}").status_code == 404
    assert owner_client.delete(f"/api/phones/{other['id']}").status_code == 204


def test_notification_settings_and_alerts_off_means_no_sms(anon, owner_client, operator, gateway, machines, pf_threshold):
    from apps.common import sms

    assert owner_client.get("/api/settings/notifications").json() == {
        "alertsEnabled": True, "autoReports": False, "reportFrequency": "day",
    }  # fmt: skip
    r = owner_client.put("/api/settings/notifications", {"alertsEnabled": False, "autoReports": True, "reportFrequency": "week"}, format="json")
    assert r.status_code == 200 and r.json()["reportFrequency"] == "week"
    assert owner_client.put("/api/settings/notifications", {"alertsEnabled": True, "autoReports": True, "reportFrequency": "year"}, format="json").status_code == 422

    owner_client.post("/api/phones", {"digits": "9000000001"}, format="json")
    push(anon, gateway, [{"meterId": "3", "kw": 15, "pf": 0.7}])
    assert len(owner_client.get("/api/alerts").json()) == 1  # still raised...
    assert sms.outbox == []  # ...but not texted
