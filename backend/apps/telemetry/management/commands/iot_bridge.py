"""Subscribe to AWS IoT Core and store what gateways publish, without a public HTTPS endpoint.

    python manage.py iot_bridge --endpoint xxxx-ats.iot.ap-south-1.amazonaws.com \\
        --cert bridge.cert.pem --key bridge.private.key --ca AmazonRootCA1.pem

Use it for local development (your laptop can reach AWS but AWS cannot reach your laptop), or in
production as a worker instead of an IoT Rule. The certificate needs a policy that allows Connect,
Subscribe and Receive on `mill/+/readings` (docs/AWS-IOT.md). Run only one bridge per environment.
"""

import os
import ssl

from django.core.management.base import BaseCommand, CommandError

from apps.telemetry.iot import handle_message

TOPIC = "mill/+/readings"


class Command(BaseCommand):
    help = "Subscribe to AWS IoT Core and store gateway readings."

    def add_arguments(self, parser):
        parser.add_argument("--endpoint", default=os.environ.get("IOT_ENDPOINT", ""), help="IoT Core data endpoint")
        parser.add_argument("--cert", required=True, help="bridge certificate (.pem.crt)")
        parser.add_argument("--key", required=True, help="bridge private key")
        parser.add_argument("--ca", required=True, help="Amazon root CA (AmazonRootCA1.pem)")
        parser.add_argument("--client-id", default="nsms-bridge")
        parser.add_argument("--port", type=int, default=8883)

    def handle(self, *args, endpoint, cert, key, ca, client_id, port, **options):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover
            raise CommandError("Install paho-mqtt: pip install -r requirements.txt") from exc
        if not endpoint:
            raise CommandError("Pass --endpoint or set IOT_ENDPOINT.")
        for label, path in (("certificate", cert), ("private key", key), ("CA file", ca)):
            if not os.path.isfile(path):
                raise CommandError(f"The {label} file was not found: {path}")

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        client.tls_set(ca_certs=ca, certfile=cert, keyfile=key, tls_version=ssl.PROTOCOL_TLS_CLIENT)

        def on_connect(c, userdata, flags, reason, properties=None):
            if reason.is_failure:
                self.stderr.write(f"Connection refused: {reason}")
                return
            c.subscribe(TOPIC, qos=1)
            self.stdout.write(
                f"Connected to {endpoint}; listening on {TOPIC}. "
                "Nothing appearing while a gateway publishes means the policy blocks iot:Receive "
                "(resource topic/mill/*/readings, with *, not +)."
            )

        def on_subscribe(c, userdata, mid, reasons, properties=None):
            if any(r.is_failure for r in reasons):
                self.stderr.write(
                    f"AWS refused the subscription to {TOPIC}. Check the bridge policy: iot:Subscribe on "
                    "topicfilter/mill/+/readings and iot:Connect on client/<client-id>."
                )

        def on_disconnect(c, userdata, flags, reason, properties=None):
            self.stderr.write(f"Disconnected ({reason}); reconnecting. If this repeats, check the certificate and policy.")

        def on_message(c, userdata, msg):
            self.stdout.write(f"{msg.topic}: {handle_message(msg.topic, msg.payload)}")

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_subscribe = on_subscribe
        client.on_disconnect = on_disconnect
        client.reconnect_delay_set(min_delay=1, max_delay=60)
        client.connect(endpoint, port, keepalive=60)
        try:
            client.loop_forever(retry_first_connection=True)
        except KeyboardInterrupt:
            client.disconnect()
