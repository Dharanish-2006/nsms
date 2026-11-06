"""Publishing to dashboards over Channels groups.

Groups:
  admin          every machine (admins)
  gw.<gateway>   machines on one gateway (users it is assigned to)
  user.<id>      messages for one user (access changed, sign-out)
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

ADMIN_GROUP = "admin"


def gateway_group(gateway_id):
    return f"gw.{gateway_id}"


def user_group(user_id):
    return f"user.{user_id}"


def group_send(groups, message):
    """Best effort: a realtime failure must never fail ingestion or an API call."""
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        for group in groups:
            async_to_sync(layer.group_send)(group, message)
    except Exception:  # noqa: BLE001 - e.g. Redis briefly unreachable
        logger.exception("Realtime publish failed")


def notify_user_access_changed(user_id):
    """Tell a user's open dashboards to re-check what they may see."""
    group_send([user_group(user_id)], {"type": "access.changed"})
