"""Machines a gateway reports on its own appear for the owner at once; the owner names them."""

from apps.plants.models import Machine

from .conftest import push

P = "/api/admin-portal"


def _first_data(anon, gateway):
    Machine.objects.filter(gateway=gateway).delete()
    r = push(anon, gateway, [{"meterId": "1", "kw": 20, "pf": 0.7}, {"meterId": "2", "kw": 5}])
    assert r.status_code == 202
    return Machine.objects.filter(gateway=gateway).order_by("meter_id")


def test_new_meters_are_visible_to_the_owner_with_a_default_name(anon, owner_client, gateway):
    _first_data(anon, gateway)
    seen = owner_client.get("/api/machines").json()["machines"]
    assert sorted(m["name"] for m in seen) == ["Meter 1", "Meter 2"]


def test_owner_renames_a_machine(anon, owner_client, gateway):
    m1, m2 = _first_data(anon, gateway)
    r = owner_client.put(f"/api/machines/{m1.pk}", {"name": "Sheller 1", "type": "sheller"}, format="json")
    assert r.status_code == 200 and r.json()["name"] == "Sheller 1"
    live = {m["id"]: m for m in owner_client.get("/api/machines").json()["machines"]}
    assert live[m1.pk]["name"] == "Sheller 1"
    dup = owner_client.put(f"/api/machines/{m2.pk}", {"name": "sheller 1"}, format="json")
    assert dup.status_code == 409 and dup.json()["code"] == "name_in_use"


def test_admin_cannot_rename_machines_but_can_list_them(anon, admin_client, gateway):
    m1, _ = _first_data(anon, gateway)
    assert admin_client.put(f"{P}/machines/{m1.pk}", {"name": "X", "type": "sheller"}, format="json").status_code in (404, 405)
    listing = admin_client.get(f"{P}/gateways/{gateway.pk}/machines").json()
    assert [x["meterId"] for x in listing["machines"]] == ["1", "2"]
    assert "kw" not in listing["machines"][0]  # no readings
