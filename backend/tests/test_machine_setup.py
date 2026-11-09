"""Machines a gateway reports on its own stay hidden from owners until an admin names them."""

import pytest

from apps.accounts.models import AdminAuditLog
from apps.plants.models import Machine

from .conftest import connect, push

P = "/api/admin-portal"


@pytest.fixture
def auto_gateway(gateway):
    """A connected gateway with no machines yet: the first message creates them."""
    return gateway


def _first_data(anon, gateway):
    Machine.objects.filter(gateway=gateway).delete()
    r = push(anon, gateway, [{"meterId": "1", "kw": 20, "pf": 0.7}, {"meterId": "2", "kw": 5}])
    assert r.status_code == 202
    return Machine.objects.filter(gateway=gateway).order_by("meter_id")


def test_new_meters_are_hidden_from_the_owner_until_named(anon, owner_client, auto_gateway):
    machines = _first_data(anon, auto_gateway)
    assert [m.configured for m in machines] == [False, False]
    assert owner_client.get("/api/machines").json()["machines"] == []
    assert owner_client.get("/api/alerts").json() == []  # no alert for a machine they cannot see


def test_admin_names_a_machine_and_the_owner_then_sees_it(anon, admin_client, owner_client, auto_gateway):
    m1, _ = _first_data(anon, auto_gateway)
    listing = admin_client.get(f"{P}/gateways/{auto_gateway.pk}/machines").json()
    assert [(x["meterId"], x["configured"]) for x in listing["machines"]] == [("1", False), ("2", False)]
    assert set(listing["machines"][0]) == {"id", "meterId", "name", "type", "ratedKw", "configured", "lastSeenAt"}  # no readings

    r = admin_client.put(f"{P}/machines/{m1.pk}", {"name": "Sheller 1", "type": "sheller", "ratedKw": 22.4}, format="json")
    assert r.status_code == 200 and r.json()["configured"] is True and r.json()["name"] == "Sheller 1"

    seen = owner_client.get("/api/machines").json()["machines"]
    assert [m["name"] for m in seen] == ["Sheller 1"]  # Meter 2 is still hidden
    audit = AdminAuditLog.objects.get(action="machine_configured")
    assert audit.target_id == m1.pk and "Sheller 1" in audit.remarks

    # the pending count shows on the dashboard and on the gateway row
    assert admin_client.get(f"{P}/dashboard").json()["machinesNeedingSetup"] == 1
    assert admin_client.get(f"{P}/gateways").json()[0]["unconfiguredMachines"] == 1


def test_naming_rules(anon, admin_client, owner_client, auto_gateway):
    m1, m2 = _first_data(anon, auto_gateway)
    ok = {"name": "Whitener 1", "type": "whitener"}
    assert admin_client.put(f"{P}/machines/{m1.pk}", ok, format="json").status_code == 200
    r = admin_client.put(f"{P}/machines/{m2.pk}", {**ok, "name": "whitener 1"}, format="json")
    assert r.status_code == 409 and r.json()["code"] == "name_in_use"
    assert admin_client.put(f"{P}/machines/{m2.pk}", {"name": "  ", "type": "sheller"}, format="json").status_code == 422
    assert admin_client.put(f"{P}/machines/{m2.pk}", {"name": "X", "type": "boiler"}, format="json").status_code == 422
    assert admin_client.put(f"{P}/machines/nope", ok, format="json").status_code == 404
    # owners and visitors cannot use the admin endpoints
    assert owner_client.put(f"{P}/machines/{m1.pk}", ok, format="json").status_code == 403
    assert owner_client.get(f"{P}/gateways/{auto_gateway.pk}/machines").status_code == 403
    assert anon.put(f"{P}/machines/{m1.pk}", ok, format="json").status_code in (401, 403)


def test_data_sent_before_naming_is_kept(anon, admin_client, owner_client, auto_gateway):
    m1, _ = _first_data(anon, auto_gateway)
    push(anon, auto_gateway, [{"meterId": "1", "kw": 21}])
    admin_client.put(f"{P}/machines/{m1.pk}", {"name": "Sheller 1", "type": "sheller"}, format="json")
    live = owner_client.get("/api/machines").json()["machines"][0]
    assert live["kw"] == 21 and live["name"] == "Sheller 1"
