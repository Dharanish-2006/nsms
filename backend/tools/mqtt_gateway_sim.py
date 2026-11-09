#!/usr/bin/env python3
"""A pretend gateway that publishes meter readings to AWS IoT Core over MQTT + TLS.

    pip install paho-mqtt
    python tools/mqtt_gateway_sim.py --endpoint xxxx-ats.iot.ap-south-1.amazonaws.com \\
        --serial SIM-GW-0001 --cert SIM-GW-0001.cert.pem --key SIM-GW-0001.private.key --ca AmazonRootCA1.pem

The serial must equal the IoT Thing name; it becomes part of the topic `mill/<serial>/readings`.
Meters 1-4 match `seed_demo`. Meter 3 runs at a low power factor so an alert fires.
"""

import argparse
import json
import math
import random
import ssl
import time

import paho.mqtt.client as mqtt

PROFILES = {"1": (26.0, 0.93), "2": (19.0, 0.92), "3": (15.0, 0.79), "4": (11.0, 0.9)}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--endpoint", required=True)
    a.add_argument("--serial", required=True)
    a.add_argument("--cert", required=True)
    a.add_argument("--key", required=True)
    a.add_argument("--ca", required=True)
    a.add_argument("--interval", type=float, default=5.0, help="seconds between messages")
    a.add_argument("--count", type=int, default=0, help="messages to send (0 = until Ctrl-C)")
    a.add_argument("--off", default="", help="comma separated meter ids that are switched off")
    args = a.parse_args()

    topic = f"mill/{args.serial}/readings"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=args.serial)  # client id = Thing name
    client.tls_set(ca_certs=args.ca, certfile=args.cert, keyfile=args.key, tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.connect(args.endpoint, 8883, keepalive=60)
    client.loop_start()

    off = {m.strip() for m in args.off.split(",") if m.strip()}
    kwh = {m: 1000.0 * (i + 1) for i, m in enumerate(PROFILES)}
    sent = 0
    try:
        while not args.count or sent < args.count:
            now = time.time()
            readings = []
            for meter, (base_kw, base_pf) in PROFILES.items():
                on = meter not in off
                kw = max(base_kw + random.uniform(-1.5, 1.5), 0) if on else 0.0
                pf = min(max(base_pf + random.uniform(-0.02, 0.02), 0.5), 0.99) if on else 0.0
                kva = kw / pf if pf else 0.0
                kwh[meter] += kw * args.interval / 3600
                readings.append(
                    {
                        "meterId": meter,
                        "ts": int(now * 1000),
                        "kw": round(kw, 2),
                        "pf": round(pf, 3),
                        "kva": round(kva, 2),
                        "kvar": round(math.sqrt(max(kva * kva - kw * kw, 0)), 2),
                        "current": round(kva * 1000 / (math.sqrt(3) * 415), 2),
                        "voltage": 415,
                        "frequency": 50.0,
                        "kwh": round(kwh[meter], 3),
                    }
                )
            info = client.publish(topic, json.dumps({"readings": readings}), qos=1)
            info.wait_for_publish(timeout=10)
            sent += 1
            print(f"published #{sent} to {topic}: {'ok' if info.is_published() else 'not confirmed'}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
