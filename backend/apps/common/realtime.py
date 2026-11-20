"""Publishing to dashboards over Channels groups.

Groups:
  gw.<gateway>   machines on one gateway (the owner connected to it)
  user.<id>      messages for one user (access changed, sign-out)
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

def gateway_group(gateway_id):
    return f"gw.{gateway_id}"


def user_group(user_id):
    return f"user.{user_id}"


def group_send(groups, message):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        for group in groups:
            async_to_sync(layer.group_send)(group, message)
    except Exception:  # noqa: BLE001 
        logger.exception("Realtime publish failed")


def notify_user_access_changed(user_id):
    group_send([user_group(user_id)], {"type": "access.changed"})
