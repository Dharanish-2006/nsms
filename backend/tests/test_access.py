import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.alerts.models import Threshold
from apps.plants.models import Gateway, GatewayAssignment, Machine, Plant

from .conftest import client_for, make_user, push

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


def test_admin_creates_gateway_key_is_shown_once(admin_client, gateway):
    r = admin_client.post("/api/gateways", {"name": "North mill", "plant": "Plant 9"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["apiKey"].startswith("gw_") and body["apiKeyPrefix"] == body["apiKey"][:11]
    assert Plant.objects.filter(name="Plant 9").exists()
    again = admin_client.get(f"/api/gateways/{body['id']}").json()
    assert "apiKey" not in again  # only the hash is stored
    # the new key authenticates a gateway
    r = admin_client.post("/api/ingest", {"readings": [{"meterId": "1", "kw": 1}]}, format="json", HTTP_X_GATEWAY_KEY=body["apiKey"])
    assert r.status_code == 202  # accepted request, meter simply unknown


def test_rotating_a_key_invalidates_the_old_one(admin_client, anon, gateway, machines):
    old = gateway.raw_key
    r = admin_client.post(f"/api/gateways/{gateway.pk}/rotate-key")
    assert r.status_code == 200
    new = r.json()["apiKey"]
    reading = [{"meterId": "1", "kw": 5}]
    assert push(anon, gateway, reading, key=old).status_code == 401
    assert push(anon, gateway, reading, key=new).status_code == 202


def test_users_see_only_their_assigned_gateways(admin_client, operator, other_user, gateway, second_gateway, machines):
    now = timezone.now()
    push(admin_client, gateway, [{"meterId": "1", "ts": int(now.timestamp() * 1000), "kw": 20}])

    # Nothing assigned yet: nothing visible
    mine = client_for(operator)
    assert ids(mine.get("/api/machines")) == []
    assert mine.get("/api/plants").json() == []

    # Admin assigns Gateway A to the operator
    r = admin_client.post(f"/api/gateways/{gateway.pk}/users", {"userId": operator.pk}, format="json")
    assert r.status_code == 201
    assert ids(mine.get("/api/machines")) == ["sheller-1", "sortex-1", "whitener-2"]
    assert mine.get("/api/plants").json() == ["Plant 1"]
    assert ids(mine.get("/api/machines?plant=Plant 2")) == []
    assert ids(client_for(other_user).get("/api/machines")) == []

    # The admin sees everything
    assert len(admin_client.get("/api/machines").json()["machines"]) == 4

    # A machine of an unassigned gateway is invisible by id as well
    assert mine.get("/api/machines/huller-9/trend").status_code == 404
    assert mine.get("/api/machines/sheller-1/trend?hours=1").status_code == 200

    # Unassigning takes access away again
    assert admin_client.delete(f"/api/gateways/{gateway.pk}/users/{operator.pk}").status_code == 204
    assert ids(mine.get("/api/machines")) == []


def test_replace_assignments_in_one_call(admin_client, operator, other_user, gateway, machines, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        r = admin_client.put(f"/api/gateways/{gateway.pk}/users", {"userIds": [operator.pk, other_user.pk]}, format="json")
    assert r.status_code == 200 and {u["username"] for u in r.json()} == {"asha", "ravi"}
    r = admin_client.put(f"/api/gateways/{gateway.pk}/users", {"userIds": [other_user.pk]}, format="json")
    assert {u["username"] for u in r.json()} == {"ravi"}
    assert GatewayAssignment.objects.filter(gateway=gateway).count() == 1
    assert GatewayAssignment.objects.get().assigned_by.username == "boss"
    listing = admin_client.get(f"/api/gateways?userId={other_user.pk}").json()
    assert [g["name"] for g in listing] == ["Gateway A"] and listing[0]["users"][0]["username"] == "ravi"


def test_only_approved_users_can_be_assigned(admin_client, gateway):
    pending = make_user("pending-one", status="pending")
    r = admin_client.post(f"/api/gateways/{gateway.pk}/users", {"userId": pending.pk}, format="json")
    assert r.status_code == 422
    assert admin_client.post(f"/api/gateways/{gateway.pk}/users", {"userId": 99999}, format="json").status_code == 422
    assert admin_client.post(f"/api/gateways/{gateway.pk}/users", {}, format="json").status_code == 422


def test_regular_users_cannot_manage_gateways_or_see_keys(user_client, operator, gateway, machines):
    assert user_client.post("/api/gateways", {"name": "x", "plant": "y"}, format="json").status_code == 403
    assert user_client.post(f"/api/gateways/{gateway.pk}/users", {"userId": operator.pk}, format="json").status_code == 403
    assert user_client.put(f"/api/gateways/{gateway.pk}/users", {"userIds": [operator.pk]}, format="json").status_code == 403
    assert user_client.post(f"/api/gateways/{gateway.pk}/rotate-key").status_code == 403
    assert user_client.delete(f"/api/gateways/{gateway.pk}").status_code == 403
    assert user_client.post("/api/machines", {}, format="json").status_code == 403

    GatewayAssignment.objects.create(gateway=gateway, user=operator)
    listing = user_client.get("/api/gateways").json()
    assert len(listing) == 1
    assert "apiKeyPrefix" not in listing[0] and "users" not in listing[0]  # nothing administrative
    assert user_client.get(f"/api/gateways/{uuid.uuid4()}").status_code == 404


def test_alerts_are_scoped_like_machines(admin_client, operator, gateway, second_gateway, machines, pf_threshold):
    now = int(timezone.now().timestamp() * 1000)
    push(admin_client, gateway, [{"meterId": "3", "ts": now, "kw": 15, "pf": 0.7}])
    push(admin_client, second_gateway, [{"meterId": "1", "ts": now, "kw": 15, "pf": 0.7}])
    assert len(admin_client.get("/api/alerts").json()) == 2
    GatewayAssignment.objects.create(gateway=second_gateway, user=operator)
    mine = client_for(operator).get("/api/alerts").json()
    assert [a["machineId"] for a in mine] == ["huller-9"]


def test_gateway_with_machines_cannot_be_deleted(admin_client, gateway, machines):
    r = admin_client.delete(f"/api/gateways/{gateway.pk}")
    assert r.status_code == 409 and r.json()["code"] == "has_machines"


def test_admin_manages_machines(admin_client, gateway):
    body = {"name": "Whitener 3", "type": "whitener", "ratedKw": 22, "gatewayId": str(gateway.pk), "meterId": "7"}
    r = admin_client.post("/api/machines", body, format="json")
    assert r.status_code == 201 and r.json()["id"] == "whitener-3" and r.json()["on"] is False
    assert r.json()["updatedAt"] == 0  # never reported: the UI shows it as unknown
    assert admin_client.post("/api/machines", {**body, "name": "Other"}, format="json").status_code == 409  # same meter
    assert admin_client.post("/api/machines", {**body, "meterId": "8", "id": "usage"}, format="json").status_code == 409
    r = admin_client.put("/api/machines/whitener-3", {"name": "Whitener Three"}, format="json")
    assert r.status_code == 200 and r.json()["name"] == "Whitener Three"
    assert admin_client.delete("/api/machines/whitener-3").status_code == 204


# --- thresholds & phones ----------------------------------------------------
def test_threshold_validation_and_permissions(admin_client, user_client, machines):
    ok = {"param": "powerFactor", "machineId": "all", "warning": 0.9, "critical": 0.8}
    assert user_client.post("/api/thresholds", ok, format="json").status_code == 403
    assert user_client.get("/api/thresholds").status_code == 200
    assert admin_client.post("/api/thresholds", {"param": "powerFactor", "machineId": "all"}, format="json").status_code == 422
    r = admin_client.post("/api/thresholds", {**ok, "warning": 0.8, "critical": 0.9}, format="json")
    assert r.status_code == 422 and "critical" in r.json()["message"].lower()
    assert admin_client.post("/api/thresholds", {**ok, "warning": 1.5}, format="json").status_code == 422
    assert admin_client.post("/api/thresholds", {**ok, "machineId": "nope"}, format="json").status_code == 422

    created = admin_client.post("/api/thresholds", ok, format="json").json()
    assert created["machineId"] == "all" and created["id"]
    assert admin_client.post("/api/thresholds", ok, format="json").status_code == 409  # duplicate
    only_critical = {"param": "powerFactor", "machineId": "sheller-1", "warning": None, "critical": 0.7}
    assert admin_client.post("/api/thresholds", only_critical, format="json").status_code == 201
    r = admin_client.put(f"/api/thresholds/{created['id']}", {**ok, "warning": 0.95}, format="json")
    assert r.status_code == 200 and r.json()["warning"] == 0.95
    assert admin_client.delete(f"/api/thresholds/{created['id']}").status_code == 204
    assert Threshold.objects.count() == 1


def test_phone_numbers(admin_client, user_client):
    assert user_client.post("/api/phones", {"digits": "9000000001"}, format="json").status_code == 403
    assert admin_client.post("/api/phones", {"digits": "12345"}, format="json").status_code == 422
    r = admin_client.post("/api/phones", {"digits": "9000000001", "label": "Primary contact"}, format="json")
    assert r.status_code == 201 and r.json()["digits"] == "9000000001"
    assert admin_client.post("/api/phones", {"digits": "9000000001"}, format="json").status_code == 409
    other = admin_client.post("/api/phones", {"digits": "9000000002"}, format="json").json()
    assert admin_client.put(f"/api/phones/{other['id']}", {"digits": "9000000001", "label": "x"}, format="json").status_code == 409
    assert admin_client.put(f"/api/phones/{other['id']}", {"digits": "9000000003", "label": "x"}, format="json").status_code == 200
    assert len(user_client.get("/api/phones").json()) == 2  # any signed-in user may read
    assert admin_client.delete(f"/api/phones/{other['id']}").status_code == 204
