"""Realtime dashboard feed: WebSocket at /api/live/.

Protocol (JSON text frames)
  client -> {"type":"auth","token":"<bearer token>"}   first message, within 10 s
  server -> {"type":"snapshot","serverTime",ms,"machines":[machine],"alerts":[alert]}
  server -> {"type":"machines","serverTime":ms,"machines":[machine]}   whenever data arrives
  server -> {"type":"alert","kind":"raised|escalated|deescalated|recovered","alert":{...}}
  server -> {"type":"alerts","alerts":[alert]}        after thresholds change
  client -> {"type":"ping"}  (every ~30 s)  server -> {"type":"pong"}

The token goes in a message rather than the URL so it never lands in access logs.
A plant owner only receives the machines of gateways they are connected to; admins get none.
Close code 4401 means "not signed in" (bad, expired or revoked token).
"""

import asyncio
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from apps.accounts.authentication import InvalidToken, authenticate_token
from apps.alerts.views import alerts_for
from apps.common.realtime import gateway_group, user_group
from apps.common.timeutil import to_ms
from apps.plants.access import accessible_gateway_ids, accessible_machines

from .payloads import build_payloads

AUTH_TIMEOUT_SEC = 10
REVALIDATE_EVERY_SEC = 60
CLOSE_UNAUTHENTICATED = 4401


def _groups_for(user):
    groups = {user_group(user.pk)}
    groups.update(gateway_group(pk) for pk in accessible_gateway_ids(user))  # none for admins
    return groups


def _snapshot(user):
    now = timezone.now()
    machines = accessible_machines(user).select_related("state")
    return {
        "type": "snapshot",
        "serverTime": to_ms(now),
        "machines": build_payloads(machines, now),
        "alerts": alerts_for(user),
    }


class LiveConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = None
        self.raw_token = None
        self.joined = set()
        self.checked_at = 0.0
        await self.accept()
        self._deadline = asyncio.create_task(self._auth_deadline())

    async def _auth_deadline(self):
        await asyncio.sleep(AUTH_TIMEOUT_SEC)
        if self.user is None:
            await self.close(code=CLOSE_UNAUTHENTICATED)

    async def disconnect(self, code):
        self._deadline.cancel()
        for group in self.joined:
            await self.channel_layer.group_discard(group, self.channel_name)
        self.joined = set()

    async def receive_json(self, content, **kwargs):
        kind = content.get("type") if isinstance(content, dict) else None
        if kind == "auth":
            await self._sign_in(content.get("token"))
        elif self.user is None:
            await self.close(code=CLOSE_UNAUTHENTICATED)
        elif kind == "ping":
            if time.monotonic() - self.checked_at > REVALIDATE_EVERY_SEC and not await self._still_valid():
                return
            await self.send_json({"type": "pong"})

    # -- access ---------------------------------------------------------------
    async def _still_valid(self):
        """Re-check the token (sign-out, expiry, account removed). Closes the socket if not."""
        try:
            self.user, _ = await database_sync_to_async(authenticate_token)(self.raw_token)
        except InvalidToken:
            await self.send_json({"type": "error", "code": "unauthenticated"})
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return False
        self.checked_at = time.monotonic()
        return True

    async def _sync_groups(self):
        wanted = await database_sync_to_async(_groups_for)(self.user)
        for group in self.joined - wanted:
            await self.channel_layer.group_discard(group, self.channel_name)
        for group in wanted - self.joined:
            await self.channel_layer.group_add(group, self.channel_name)
        self.joined = wanted

    async def _sign_in(self, raw_token):
        try:
            self.user, _ = await database_sync_to_async(authenticate_token)(raw_token)
        except InvalidToken:
            await self.send_json({"type": "error", "code": "unauthenticated"})
            await self.close(code=CLOSE_UNAUTHENTICATED)
            return
        self.raw_token = raw_token
        self.checked_at = time.monotonic()
        await self._sync_groups()
        await self.send_json(await database_sync_to_async(_snapshot)(self.user))

    # -- events from the channel layer ----------------------------------------
    async def machines_update(self, event):
        if self.user:
            await self.send_json(
                {"type": "machines", "serverTime": event["serverTime"], "machines": event["machines"]}
            )

    async def alert_event(self, event):
        if self.user:
            await self.send_json({"type": "alert", "kind": event["kind"], "alert": event["alert"]})

    async def alerts_refresh(self, event):
        if self.user:
            alerts = await database_sync_to_async(alerts_for)(self.user)
            await self.send_json({"type": "alerts", "alerts": alerts})

    async def access_changed(self, event):
        """Assignments changed, the user signed out or was removed: re-check everything."""
        if self.user and await self._still_valid():
            await self._sync_groups()
            await self.send_json(await database_sync_to_async(_snapshot)(self.user))
