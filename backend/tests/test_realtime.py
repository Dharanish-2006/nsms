"""The WebSocket dashboard feed: data pushed by a gateway reaches open dashboards."""

import asyncio
from datetime import timedelta

import pytest
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from config.asgi import application

from .conftest import client_for, connect as connect_owner, make_user, push, token_for

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


async def test_owner_gets_snapshot_then_live_updates(operator, gateway, machines):
    await database_sync_to_async(connect_owner)(operator, gateway)
    ws = await connect(operator)
    snap = await ws.receive_json_from()
    assert snap["type"] == "snapshot" and len(snap["machines"]) == 3 and snap["alerts"] == []
    assert snap["serverTime"] > 0

    gateway_client = await api(operator)  # any client may post; the key authenticates it
    r = await database_sync_to_async(push)(gateway_client, gateway, [reading("1", kw=31.5)])
    assert r.status_code == 202

    msg = await ws.receive_json_from(timeout=3)
    assert msg["type"] == "machines"
    machine = msg["machines"][0]
    assert machine["id"] == "sheller-1" and machine["kw"] == 31.5 and machine["on"] is True
    await ws.disconnect()


async def test_connected_owner_gets_updates_others_do_not(admin, operator, other_user, gateway, machines):
    await database_sync_to_async(connect_owner)(operator, gateway)
    mine, theirs, boss = await connect(operator), await connect(other_user), await connect(admin)
    assert len((await mine.receive_json_from())["machines"]) == 3
    assert (await theirs.receive_json_from())["machines"] == []
    assert (await boss.receive_json_from())["machines"] == []  # admins get no machine data

    await database_sync_to_async(push)(await api(admin), gateway, [reading("1", kw=12)])
    assert (await mine.receive_json_from(timeout=3))["machines"][0]["kw"] == 12
    assert await theirs.receive_nothing(timeout=0.5)
    assert await boss.receive_nothing(timeout=0.5)
    for ws in (mine, theirs, boss):
        await ws.disconnect()


async def test_connecting_reaches_open_dashboard(admin, operator, gateway, machines):
    ws = await connect(operator)
    assert (await ws.receive_json_from())["machines"] == []

    admin_api = await api(admin)
    post = database_sync_to_async(admin_api.post)
    r = await post("/api/admin-portal/assignments", {"userId": operator.pk, "gatewayId": str(gateway.pk)}, format="json")
    assert r.status_code == 201
    # Assigned only reserves the gateway: still nothing to see
    assert await ws.receive_nothing(timeout=0.5)

    aid = r.json()["id"]
    r = await post(f"/api/admin-portal/assignments/{aid}/connect")
    assert r.status_code == 200
    snap = await ws.receive_json_from(timeout=3)  # access changed -> fresh snapshot
    assert snap["type"] == "snapshot" and len(snap["machines"]) == 3

    await database_sync_to_async(push)(await api(admin), gateway, [reading("1", kw=9)])
    assert (await ws.receive_json_from(timeout=3))["machines"][0]["kw"] == 9

    r = await post(f"/api/admin-portal/assignments/{aid}/disconnect")
    assert r.status_code == 200
    snap = await ws.receive_json_from(timeout=3)
    assert snap["machines"] == []  # access taken away at once
    await ws.disconnect()


async def test_alert_is_pushed_live(operator, gateway, machines, pf_threshold):
    await database_sync_to_async(connect_owner)(operator, gateway)
    ws = await connect(operator)
    await ws.receive_json_from()
    await database_sync_to_async(push)(await api(operator), gateway, [reading("3", kw=15, pf=0.7)])
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
