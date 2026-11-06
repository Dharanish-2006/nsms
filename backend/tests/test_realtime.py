"""The WebSocket dashboard feed: data pushed by a gateway reaches open dashboards."""

import asyncio
from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from apps.plants.models import GatewayAssignment
from config.asgi import application

from .conftest import client_for, make_user, push, token_for

pytestmark = pytest.mark.django_db(transaction=True)

ORIGIN = [(b"origin", b"http://testserver")]


async def api(user):
    """A signed-in REST client (building it touches the database)."""
    return await database_sync_to_async(client_for)(user)


async def connect(user=None, token=None):
    ws = WebsocketCommunicator(application, "/api/live/", headers=ORIGIN)
    ok, _ = await ws.connect()
    assert ok
    token = token or await database_sync_to_async(token_for)(user)
    await ws.send_json_to({"type": "auth", "token": token})
    return ws


def reading(meter, kw=20.0, pf=0.93, t=None):
    t = t or timezone.now()
    return {"meterId": meter, "ts": int(t.timestamp() * 1000), "kw": kw, "pf": pf}


async def test_admin_gets_snapshot_then_live_updates(admin, gateway, machines):
    ws = await connect(admin)
    snap = await ws.receive_json_from()
    assert snap["type"] == "snapshot" and len(snap["machines"]) == 3 and snap["alerts"] == []
    assert snap["serverTime"] > 0

    gateway_client = await api(admin)  # any client may post; the key authenticates it
    r = await database_sync_to_async(push)(gateway_client, gateway, [reading("1", kw=31.5)])
    assert r.status_code == 202

    msg = await ws.receive_json_from(timeout=3)
    assert msg["type"] == "machines"
    machine = msg["machines"][0]
    assert machine["id"] == "sheller-1" and machine["kw"] == 31.5 and machine["on"] is True
    await ws.disconnect()


async def test_assigned_user_gets_updates_unassigned_user_does_not(admin, operator, other_user, gateway, machines):
    await database_sync_to_async(GatewayAssignment.objects.create)(gateway=gateway, user=operator)
    mine, theirs = await connect(operator), await connect(other_user)
    assert len((await mine.receive_json_from())["machines"]) == 3
    assert (await theirs.receive_json_from())["machines"] == []

    await database_sync_to_async(push)(await api(admin), gateway, [reading("1", kw=12)])
    assert (await mine.receive_json_from(timeout=3))["machines"][0]["kw"] == 12
    assert await theirs.receive_nothing(timeout=0.5)
    await mine.disconnect()
    await theirs.disconnect()


async def test_new_assignment_reaches_open_dashboard(admin, operator, gateway, machines):
    ws = await connect(operator)
    assert (await ws.receive_json_from())["machines"] == []

    r = await database_sync_to_async((await api(admin)).post)(
        f"/api/gateways/{gateway.pk}/users", {"userId": operator.pk}, format="json"
    )
    assert r.status_code == 201
    snap = await ws.receive_json_from(timeout=3)  # access changed -> fresh snapshot
    assert snap["type"] == "snapshot" and len(snap["machines"]) == 3

    await database_sync_to_async(push)(await api(admin), gateway, [reading("1", kw=9)])
    assert (await ws.receive_json_from(timeout=3))["machines"][0]["kw"] == 9
    await ws.disconnect()


async def test_alert_is_pushed_live(admin, gateway, machines, pf_threshold):
    ws = await connect(admin)
    await ws.receive_json_from()
    await database_sync_to_async(push)(await api(admin), gateway, [reading("3", kw=15, pf=0.7)])
    kinds = {}
    for _ in range(2):
        msg = await ws.receive_json_from(timeout=3)
        kinds[msg["type"]] = msg
    assert kinds["alert"]["kind"] == "raised" and kinds["alert"]["alert"]["severity"] == "critical"
    assert kinds["alert"]["alert"]["machineId"] == "whitener-2"
    await ws.disconnect()


async def test_bad_token_is_closed_with_4401(db):
    ws = WebsocketCommunicator(application, "/api/live/", headers=ORIGIN)
    await ws.connect()
    await ws.send_json_to({"type": "auth", "token": "nonsense"})
    assert (await ws.receive_json_from())["code"] == "unauthenticated"
    out = await ws.receive_output()
    assert out["type"] == "websocket.close" and out["code"] == 4401


async def test_messages_before_auth_are_refused(db):
    ws = WebsocketCommunicator(application, "/api/live/", headers=ORIGIN)
    await ws.connect()
    await ws.send_json_to({"type": "ping"})
    out = await ws.receive_output()
    assert out["type"] == "websocket.close" and out["code"] == 4401


async def test_signing_out_closes_the_socket(admin, gateway, machines):
    raw = await database_sync_to_async(token_for)(admin)
    ws = await connect(token=raw)
    await ws.receive_json_from()
    client = await database_sync_to_async(lambda: __import__("rest_framework.test", fromlist=["x"]).APIClient())()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
    await database_sync_to_async(client.post)("/api/auth/logout")
    msgs = []
    while True:
        out = await ws.receive_output(timeout=3)
        msgs.append(out)
        if out["type"] == "websocket.close":
            break
    assert msgs[-1]["code"] == 4401


async def test_origin_must_be_allowed(db):
    ws = WebsocketCommunicator(application, "/api/live/", headers=[(b"origin", b"http://evil.example")])
    ok, _ = await ws.connect()
    assert not ok
