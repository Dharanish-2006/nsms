"""Admin Portal rules: approvals, assignments, connections, the audit log, self-registering gateways."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import AdminAuditLog, User
from apps.plants.models import Gateway, GatewayAssignment, Machine

from .conftest import client_for, make_user, push

pytestmark = pytest.mark.django_db
P = "/api/admin-portal"


def assign(client, user, gateway):
    return client.post(f"{P}/assignments", {"userId": user.pk, "gatewayId": str(gateway.pk)}, format="json")


def ms(t):
    return int(t.timestamp() * 1000)


# --- user approval ----------------------------------------------------------------------
def test_approve_and_reject_pending_requests(admin_client, admin):
    a, b = make_user("pend-a", status="pending"), make_user("pend-b", status="pending")
    r = admin_client.post(f"{P}/users/{a.pk}/approve")
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["decidedBy"]["username"] == "boss"
    r = admin_client.post(f"{P}/users/{b.pk}/reject", {"reason": "Unknown company"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["rejectionReason"] == "Unknown company"
    # decided once: a rejected request stops here
    assert admin_client.post(f"{P}/users/{b.pk}/approve").status_code == 409
    assert admin_client.post(f"{P}/users/{a.pk}/reject").status_code == 409
    assert admin_client.post(f"{P}/users/99999/approve").status_code == 404
    assert [e.action for e in AdminAuditLog.objects.order_by("pk")] == ["user_approved", "user_rejected"]
    assert AdminAuditLog.objects.get(action="user_rejected").remarks == "Unknown company"


def test_user_lists_filter_and_search(admin_client):
    make_user("pend-a", status="pending", )
    User.objects.filter(username="pend-a").update(status="pending")
    make_user("ok-one", status="active")
    make_user("no-one", status="rejected")
    names = lambda q: sorted(u["username"] for u in admin_client.get(f"{P}/users{q}").json())  # noqa: E731
    assert names("?status=pending") == ["pend-a"]
    assert names("?status=active") == ["ok-one"]
    assert names("?status=rejected") == ["no-one"]
    assert names("?q=ok-") == ["ok-one"]
    assert "boss" not in names("")  # admins are not in the owner lists
    assert admin_client.get(f"{P}/users?status=bogus").status_code == 422


# --- assignment rules -------------------------------------------------------------------
def test_only_approved_users_can_be_assigned(admin_client, gateway):
    for status in ("pending", "rejected"):
        user = make_user(f"u-{status}", status=status)
        r = assign(admin_client, user, gateway)
        assert r.status_code == 409 and r.json()["code"] == "user_not_approved"
    assert assign(admin_client, make_user("boss2", role="admin"), gateway).status_code == 409
    assert assign(admin_client, type("U", (), {"pk": 99999}), gateway).status_code == 404
    assert GatewayAssignment.objects.count() == 0


def test_gateway_has_one_live_user_and_a_user_may_have_many(admin_client, operator, other_user, gateway, second_gateway):
    a = assign(admin_client, operator, gateway)
    assert a.status_code == 201 and a.json()["status"] == "assigned"
    # reserved: nobody else can take it, not even the same user twice
    for who in (other_user, operator):
        r = assign(admin_client, who, gateway)
        assert r.status_code == 409 and r.json()["code"] == "gateway_in_use"
    # one user, several gateways
    assert assign(admin_client, operator, second_gateway).status_code == 201
    assert GatewayAssignment.objects.filter(user=operator).count() == 2


def test_database_refuses_two_live_records_for_one_gateway(operator, other_user, gateway):
    GatewayAssignment.objects.create(gateway=gateway, user=operator)
    with pytest.raises(IntegrityError), transaction.atomic():
        GatewayAssignment.objects.create(gateway=gateway, user=other_user, status="connected")
    # history rows are fine
    GatewayAssignment.objects.create(gateway=gateway, user=other_user, status="disconnected")


def test_unverified_gateway_cannot_be_assigned(admin_client, operator, gateway):
    Gateway.objects.filter(pk=gateway.pk).update(verified=False)
    r = assign(admin_client, operator, gateway)
    assert r.status_code == 409 and r.json()["code"] == "gateway_not_verified"
    assert admin_client.post(f"{P}/gateways/{gateway.pk}/verify").status_code == 200
    assert admin_client.post(f"{P}/gateways/{gateway.pk}/verify").status_code == 409
    assert assign(admin_client, operator, gateway).status_code == 201


# --- connect / disconnect ---------------------------------------------------------------
def test_connection_lifecycle_and_history(admin_client, operator, other_user, gateway, machines, anon):
    aid = assign(admin_client, operator, gateway).json()["id"]
    mine = client_for(operator)
    assert mine.get("/api/machines").json()["machines"] == []  # reserved, not connected

    r = admin_client.post(f"{P}/assignments/{aid}/connect", {"remarks": "visit done"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "connected" and r.json()["connectedBy"]["username"] == "boss"
    assert admin_client.post(f"{P}/assignments/{aid}/connect").status_code == 409
    assert len(mine.get("/api/machines").json()["machines"]) == 3

    r = admin_client.post(f"{P}/assignments/{aid}/disconnect")
    assert r.status_code == 200 and r.json()["status"] == "disconnected" and r.json()["disconnectedAt"]
    assert admin_client.post(f"{P}/assignments/{aid}/disconnect").status_code == 409
    assert mine.get("/api/machines").json()["machines"] == []

    # the gateway is free again; the old record stays as history
    gw = next(g for g in admin_client.get(f"{P}/gateways").json() if g["id"] == str(gateway.pk))
    assert gw["availability"] == "available"
    second = assign(admin_client, other_user, gateway)
    assert second.status_code == 201
    history = admin_client.get(f"{P}/assignments?gatewayId={gateway.pk}").json()
    assert [h["status"] for h in history] == ["assigned", "disconnected"]
    assert history[1]["user"]["username"] == "asha" and history[1]["connectedAt"] and history[1]["disconnectedAt"]
    assert GatewayAssignment.objects.count() == 2  # nothing erased


def test_reconnecting_the_same_assignment(admin_client, operator, other_user, gateway, machines):
    aid = assign(admin_client, operator, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{aid}/connect")
    admin_client.post(f"{P}/assignments/{aid}/disconnect")
    assert admin_client.post(f"{P}/assignments/{aid}/connect").status_code == 200  # free: fine
    admin_client.post(f"{P}/assignments/{aid}/disconnect")

    other = assign(admin_client, other_user, gateway).json()["id"]  # someone else takes it
    r = admin_client.post(f"{P}/assignments/{aid}/connect")
    assert r.status_code == 409 and r.json()["code"] == "gateway_in_use"
    assert admin_client.post(f"{P}/assignments/{other}/connect").status_code == 200


def test_user_who_loses_approval_cannot_be_connected(admin_client, operator, gateway):
    aid = assign(admin_client, operator, gateway).json()["id"]
    User.objects.filter(pk=operator.pk).update(status="rejected")
    assert admin_client.post(f"{P}/assignments/{aid}/connect").status_code == 409


def test_every_action_is_audited(admin_client, operator, gateway):
    aid = assign(admin_client, operator, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{aid}/connect")
    admin_client.post(f"{P}/assignments/{aid}/disconnect", {"remarks": "contract ended"}, format="json")
    log = admin_client.get(f"{P}/audit-log").json()
    assert [e["action"] for e in log] == ["gateway_disconnected", "gateway_connected", "gateway_assigned"]
    assert all(e["admin"] == "boss" and e["timestamp"] for e in log)
    assert log[0]["remarks"] == "contract ended" and log[0]["targetId"] == str(aid)
    assert admin_client.get(f"{P}/audit-log?action=gateway_assigned").json()[0]["targetType"] == "assignment"


def test_failed_actions_leave_no_audit_entry(admin_client, operator, other_user, gateway):
    assign(admin_client, operator, gateway)
    before = AdminAuditLog.objects.count()
    assign(admin_client, other_user, gateway)  # refused
    assert AdminAuditLog.objects.count() == before


def test_only_admins_reach_the_portal(user_client, anon, operator, gateway):
    for method, path in (("get", "/dashboard"), ("get", "/gateways"), ("get", "/assignments"), ("get", "/audit-log"),
                         ("post", "/assignments"), ("post", f"/gateways/{gateway.pk}/verify")):  # fmt: skip
        assert getattr(user_client, method)(P + path).status_code == 403, path
        assert getattr(anon, method)(P + path).status_code == 401, path


# --- dashboard --------------------------------------------------------------------------
def test_dashboard_counts(admin_client, operator, other_user, gateway, second_gateway):
    make_user("waiting", status="pending")
    aid = assign(admin_client, operator, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{aid}/connect")
    d = admin_client.get(f"{P}/dashboard").json()
    assert d["pendingUsers"] == 1 and d["approvedUsers"] == 2  # asha, ravi
    assert d["registeredGateways"] == 2 and d["activeConnections"] == 1
    assert d["availableGateways"] == 1 and d["assignedGateways"] == 1
    by_name = {g["name"]: g for g in d["gateways"]}
    assert by_name["Gateway A"]["availability"] == "assigned" and by_name["Gateway A"]["assignedTo"]["username"] == "asha"
    assert by_name["Gateway B"]["availability"] == "available"
    assert "machines" not in d  # no monitoring data


# --- the previous owner's data stays theirs ---------------------------------------------
def test_new_owner_does_not_see_the_previous_owners_hours(admin_client, anon, operator, other_user, gateway, machines):
    day = timezone.localtime().replace(hour=1, minute=0, second=0, microsecond=0)
    # Only meaningful if "now" is later than 01:00 IST; the data is stamped in the past
    if timezone.now() - day < timedelta(hours=3):
        pytest.skip("needs a few hours of today to have passed")
    aid = assign(admin_client, operator, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{aid}/connect")
    GatewayAssignment.objects.filter(pk=aid).update(connected_at=day - timedelta(hours=2))
    from apps.plants.models import ConnectionPeriod

    ConnectionPeriod.objects.filter(assignment_id=aid).update(start=day - timedelta(hours=2))
    t = day + timedelta(minutes=10)
    push(anon, gateway, [{"meterId": "1", "ts": ms(t), "kw": 30, "pf": 0.9, "kwh": 100},
                         {"meterId": "1", "ts": ms(t + timedelta(minutes=10)), "kw": 30, "pf": 0.9, "kwh": 105}])  # fmt: skip
    assert client_for(operator).get("/api/machines/usage?range=week").json()["consumedKwh"] > 0

    admin_client.post(f"{P}/assignments/{aid}/disconnect")
    new = assign(admin_client, other_user, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{new}/connect")  # connects "now": after the data above
    theirs = client_for(other_user)
    assert theirs.get("/api/machines/usage?range=week").json() == {"consumedKwh": 0, "actualKwh": 0}
    row = next(m for m in theirs.get("/api/reports/daily").json()["machines"] if m["machineId"] == "sheller-1")
    assert row["kwh"] == 0 and row["samples"] == 0
    live = next(m for m in theirs.get("/api/machines").json()["machines"] if m["id"] == "sheller-1")
    assert sum(live["hourlyKwh"]) == 0


# --- gateways registering themselves ----------------------------------------------------
@override_settings(GATEWAY_PROVISION_KEY="fleet-secret")
def test_gateway_registers_itself_then_waits_for_verification(anon, admin_client, operator):
    body = {"serial": "SN-2026-0001", "name": "Mill gateway"}
    assert anon.post("/api/gateways/provision", body, format="json").status_code == 401
    assert anon.post("/api/gateways/provision", body, format="json", HTTP_X_PROVISION_KEY="wrong").status_code == 401

    r = anon.post("/api/gateways/provision", body, format="json", HTTP_X_PROVISION_KEY="fleet-secret")
    assert r.status_code == 201 and r.json()["apiKey"].startswith("gw_")
    key = r.json()["apiKey"]
    # a second registration of the same serial is refused (the key is shown only once)
    r2 = anon.post("/api/gateways/provision", body, format="json", HTTP_X_PROVISION_KEY="fleet-secret")
    assert r2.status_code == 409

    # The admin sees it straight away, unverified, and cannot assign it yet
    gw = admin_client.get(f"{P}/gateways?verified=false").json()
    assert len(gw) == 1 and gw[0]["serialNumber"] == "SN-2026-0001" and gw[0]["availability"] == "available"
    assert assign(admin_client, operator, Gateway.objects.get(serial_number="SN-2026-0001")).status_code == 409

    # It may not send data until verified
    reading = {"readings": [{"meterId": "7", "kw": 10}]}
    r = anon.post("/api/ingest", reading, format="json", HTTP_X_GATEWAY_KEY=key)
    assert r.status_code == 403 and r.json()["code"] == "gateway_not_verified"

    assert admin_client.post(f"{P}/gateways/{gw[0]['id']}/verify").status_code == 200
    r = anon.post("/api/ingest", reading, format="json", HTTP_X_GATEWAY_KEY=key)
    assert r.status_code == 202 and r.json()["accepted"] == 1
    machine = Machine.objects.get(gateway__serial_number="SN-2026-0001")
    assert machine.meter_id == "7" and machine.name == "Meter 7"  # the owner renames it later


def test_provisioning_is_off_without_a_key(anon):
    r = anon.post("/api/gateways/provision", {"serial": "SN-2026-0002"}, format="json", HTTP_X_PROVISION_KEY="anything")
    assert r.status_code == 404


@override_settings(GATEWAY_PROVISION_KEY="fleet-secret", MAX_AUTO_MACHINES_PER_GATEWAY=2)
def test_a_faulty_gateway_cannot_flood_us_with_machines(anon, gateway):
    readings = [{"meterId": str(i), "kw": 5} for i in range(10, 16)]
    r = push(anon, gateway, readings)
    assert r.status_code == 202 and r.json()["accepted"] == 2 and len(r.json()["unknownMeters"]) == 4


def test_rotating_a_key_is_audited_and_works(admin_client, anon, gateway, machines):
    old = gateway.raw_key
    r = admin_client.post(f"{P}/gateways/{gateway.pk}/rotate-key")
    assert r.status_code == 200 and r.json()["apiKey"].startswith("gw_")
    assert push(anon, gateway, [{"meterId": "1", "kw": 5}], key=old).status_code == 401
    assert push(anon, gateway, [{"meterId": "1", "kw": 5}], key=r.json()["apiKey"]).status_code == 202
    assert AdminAuditLog.objects.filter(action="gateway_key_rotated").count() == 1
    assert "apiKey" not in admin_client.get(f"{P}/gateways").json()[0]  # shown once only
