"""Shared by both ways MQTT data reaches us: the AWS IoT Rule (HTTPS) and the `iot_bridge` subscriber."""

import json
import logging
import re

from apps.common.errors import ApiError
from apps.plants.services import ensure_verified, register_unverified

from .ingest import ingest
from .publish import publish_ingest

logger = logging.getLogger(__name__)
SERIAL_RE = re.compile(r"^[A-Za-z0-9._-]{4,64}$")
TOPIC_PARTS = ("mill", None, "readings")  # mill/<serial>/readings


def gateway_for_serial(serial):
    """The gateway that may store data for this serial. Unknown serials register themselves
    and are approved by this first message; disabled gateways are refused."""
    if not isinstance(serial, str) or not SERIAL_RE.match(serial):
        raise ApiError("A valid gateway serial is required.", 422, "validation")
    gateway, created = register_unverified(serial)
    if created:
        logger.info("Gateway %s registered itself over MQTT and was approved.", serial)
    if not gateway.enabled:
        raise ApiError("This gateway is disabled.", 403, "gateway_disabled")
    ensure_verified(gateway)
    return gateway


def serial_from_topic(topic):
    parts = str(topic).split("/")
    if len(parts) == 3 and parts[0] == "mill" and parts[2] == "readings":
        return parts[1]
    return None


def handle_message(topic, payload):
    """Store one MQTT message. Returns a short status string; never raises, so one bad message
    cannot stop the subscriber."""
    serial = serial_from_topic(topic)
    if serial is None:
        return "ignored: unexpected topic"
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return "rejected: not JSON"
    if not isinstance(data, dict):
        return "rejected: payload must be an object"
    try:
        gateway = gateway_for_serial(serial)
        result = ingest(gateway, {"readings": data.get("readings")})
        publish_ingest(gateway, result)
    except ApiError as exc:
        return f"refused: {exc.message}"
    except Exception:  # noqa: BLE001 - keep the subscriber alive
        logger.exception("Could not store MQTT message for %s", serial)
        return "error: see log"
    return f"stored {result.accepted}, rejected {result.rejected}"
