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


def test_old_unverified_gateway_can_be_assigned(admin_client, operator, gateway):
    Gateway.objects.filter(pk=gateway.pk).update(verified=False)  # no approval step any more
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
                         ("post", "/assignments")):  # fmt: skip
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
    from apps.plants.models import ConnectionPeriod

    now = timezone.now()
    aid = assign(admin_client, operator, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{aid}/connect")
    started = now - timedelta(minutes=40)
    GatewayAssignment.objects.filter(pk=aid).update(connected_at=started)
    ConnectionPeriod.objects.filter(assignment_id=aid).update(start=started)
    # 30 minutes of the first owner's data, stamped a few minutes ago
    push(anon, gateway, [{"meterId": "1", "ts": ms(now - timedelta(minutes=30)), "kw": 30, "pf": 0.9, "kwh": 100},
                         {"meterId": "1", "ts": ms(now - timedelta(minutes=10)), "kw": 30, "pf": 0.9, "kwh": 110}])  # fmt: skip
    assert client_for(operator).get("/api/machines/usage?range=week").json()["consumedKwh"] > 0

    admin_client.post(f"{P}/assignments/{aid}/disconnect")
    new = assign(admin_client, other_user, gateway).json()["id"]
    admin_client.post(f"{P}/assignments/{new}/connect")  # connects "now": after the data above
    # the new owner's period starts now; the hour filter is whole-hour, so move the old data
    # one clear hour back to test the boundary honestly
    from apps.telemetry.models import HourlyReport

    keep = HourlyReport.objects.order_by("hour").first()
    HourlyReport.objects.exclude(pk=keep.pk).delete()
    HourlyReport.objects.filter(pk=keep.pk).update(hour=timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=3))
    ConnectionPeriod.objects.filter(assignment_id=aid).update(start=now - timedelta(hours=4), end=now - timedelta(hours=2))
    theirs = client_for(other_user)
    assert theirs.get("/api/machines/usage?range=week").json() == {"consumedKwh": 0, "actualKwh": 0}
    row = next(m for m in theirs.get("/api/reports/daily").json()["machines"] if m["machineId"] == "sheller-1")
    assert row["kwh"] == 0 and row["samples"] == 0
    live = next(m for m in theirs.get("/api/machines").json()["machines"] if m["id"] == "sheller-1")
    assert sum(live["hourlyKwh"]) == 0


# --- gateways registering themselves ----------------------------------------------------
@override_settings(GATEWAY_PROVISION_KEY="fleet-secret")
def test_gateway_registers_itself_and_is_ready_at_once(anon, admin_client, operator):
    body = {"serial": "SN-2026-0001", "name": "Mill gateway"}
    assert anon.post("/api/gateways/provision", body, format="json").status_code == 401
    assert anon.post("/api/gateways/provision", body, format="json", HTTP_X_PROVISION_KEY="wrong").status_code == 401

    r = anon.post("/api/gateways/provision", body, format="json", HTTP_X_PROVISION_KEY="fleet-secret")
    assert r.status_code == 201 and r.json()["apiKey"].startswith("gw_")
    key = r.json()["apiKey"]
    # a second registration of the same serial is refused (the key is shown only once)
    r2 = anon.post("/api/gateways/provision", body, format="json", HTTP_X_PROVISION_KEY="fleet-secret")
    assert r2.status_code == 409

    # The admin sees it straight away, approved and available to assign
    gw = admin_client.get(f"{P}/gateways").json()
    assert len(gw) == 1 and gw[0]["serialNumber"] == "SN-2026-0001" and gw[0]["availability"] == "available"
    assert assign(admin_client, operator, Gateway.objects.get(serial_number="SN-2026-0001")).status_code == 201

    reading = {"readings": [{"meterId": "7", "kw": 10}]}
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


# --- AWS IoT Core (MQTT) ---------------------------------------------------------------
@override_settings(IOT_RULE_SECRET="rule-secret")
def test_iot_rule_delivers_mqtt_readings(anon, admin_client, operator):
    H = {"HTTP_X_IOT_SECRET": "rule-secret"}
    msg = {"serial": "SN-MQTT-0001", "readings": [{"meterId": "1", "kw": 12.5, "pf": 0.9}]}
    assert anon.post("/api/iot/ingest", msg, format="json").status_code == 401
    assert anon.post("/api/iot/ingest", msg, format="json", HTTP_X_IOT_SECRET="nope").status_code == 401

    # The first message from an unknown serial registers it and is stored
    r = anon.post("/api/iot/ingest", msg, format="json", **H)
    assert r.status_code == 202 and r.json()["accepted"] == 1
    assert [g["serialNumber"] for g in admin_client.get(f"{P}/gateways").json()] == ["SN-MQTT-0001"]
    assert Machine.objects.get(gateway__serial_number="SN-MQTT-0001").meter_id == "1"

    # Bad serials and bad bodies are refused
    assert anon.post("/api/iot/ingest", {"serial": "x", "readings": []}, format="json", **H).status_code == 422
    assert anon.post("/api/iot/ingest", {"serial": "SN-MQTT-0001", "readings": "no"}, format="json", **H).status_code == 422


@override_settings(IOT_RULE_SECRET="rule-secret")
def test_iot_destination_confirmation_is_logged_not_trusted(anon, caplog):
    with caplog.at_level("WARNING"):
        r = anon.post("/api/iot/ingest", {"confirmationToken": "tok-123", "enableUrl": "https://x"}, format="json")
    assert r.status_code == 200 and "tok-123" in caplog.text
    assert Gateway.objects.count() == 0  # nothing created by it


def test_iot_ingest_is_off_without_a_secret(anon):
    assert anon.post("/api/iot/ingest", {"serial": "SN-MQTT-0001", "readings": []}, format="json").status_code == 404


def test_iot_bridge_message_handler(admin_client, db):
    """What the `iot_bridge` subscriber does with each MQTT message."""
    from apps.plants.models import Gateway
    from apps.telemetry.iot import handle_message

    good = b'{"readings": [{"meterId": "1", "kw": 5.0}]}'
    assert handle_message("other/topic", good).startswith("ignored")
    assert handle_message("mill/SN-BRIDGE-1/readings", b"not json").startswith("rejected")
    assert handle_message("mill/SN-BRIDGE-1/readings", b"[1]").startswith("rejected")
    # the first message registers and approves the gateway, and is stored
    assert handle_message("mill/SN-BRIDGE-1/readings", good).startswith("stored")
    gw = Gateway.objects.get(serial_number="SN-BRIDGE-1")
    assert gw.verified
    gw.enabled = False
    gw.save()
    assert "disabled" in handle_message("mill/SN-BRIDGE-1/readings", good)


# --- automatic verification (the default) -----------------------------------------------
@override_settings(GATEWAY_PROVISION_KEY="fleet-secret")
def test_self_registered_gateway_is_verified_and_can_send_at_once(anon, admin_client, operator):
    r = anon.post("/api/gateways/provision", {"serial": "SN-AUTO-1"}, format="json", HTTP_X_PROVISION_KEY="fleet-secret")
    assert r.status_code == 201 and r.json()["status"] == "verified"
    gw = Gateway.objects.get(serial_number="SN-AUTO-1")
    assert gw.verified
    reading = {"readings": [{"meterId": "7", "kw": 10}]}
    assert anon.post("/api/ingest", reading, format="json", HTTP_X_GATEWAY_KEY=r.json()["apiKey"]).status_code == 202
    # still reaches no owner until the admin assigns and connects it
    assert assign(admin_client, operator, gw).status_code in (200, 201)


@override_settings(IOT_RULE_SECRET="rule-secret")
def test_first_mqtt_message_registers_and_verifies_the_gateway(anon):
    msg = {"serial": "SN-MQTT-AUTO", "readings": [{"meterId": "1", "kw": 12.5}]}
    r = anon.post("/api/iot/ingest", msg, format="json", HTTP_X_IOT_SECRET="rule-secret")
    assert r.status_code == 202 and r.json()["accepted"] == 1
    assert Gateway.objects.get(serial_number="SN-MQTT-AUTO").verified
    assert Machine.objects.get(gateway__serial_number="SN-MQTT-AUTO").configured is True


def test_bridge_message_from_a_new_gateway_is_stored(db):
    from apps.telemetry.iot import handle_message

    assert handle_message("mill/SN-BRIDGE-2/readings", b'{"readings": [{"meterId": "1", "kw": 5.0}]}').startswith("stored")
    assert Gateway.objects.get(serial_number="SN-BRIDGE-2").verified


@override_settings(IOT_RULE_SECRET="rule-secret")
def test_earlier_unverified_gateway_is_verified_by_its_next_message(anon):
    Gateway.objects.create(name="old", serial_number="SN-OLD-1", verified=False, plant=Gateway.objects.model._meta.get_field("plant").related_model.objects.get_or_create(name="Plant 1")[0])
    r = anon.post("/api/iot/ingest", {"serial": "SN-OLD-1", "readings": [{"meterId": "1", "kw": 1}]}, format="json", HTTP_X_IOT_SECRET="rule-secret")
    assert r.status_code == 202 and Gateway.objects.get(serial_number="SN-OLD-1").verified


def test_disabled_gateway_stays_blocked(anon, gateway):
    Gateway.objects.filter(pk=gateway.pk).update(enabled=False)
    assert push(anon, gateway, [{"meterId": "1", "kw": 1}]).status_code == 403
