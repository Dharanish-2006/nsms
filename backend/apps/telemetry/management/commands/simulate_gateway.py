"""Pretend to be an industrial gateway: push synthetic meter readings to /api/ingest so
you can watch the dashboard update in real time.

    python manage.py simulate_gateway --key gw_xxx --url http://localhost:8000/api/ingest

Meters 1-4 match `seed_demo`. Meter 3 runs at a low power factor so an alert fires.
"""

import json
import math
import random
import time
import urllib.error
import urllib.request

from django.core.management.base import BaseCommand, CommandError

# meter id -> (typical kW, typical power factor)
PROFILES = {"1": (26.0, 0.93), "2": (19.0, 0.92), "3": (15.0, 0.79), "4": (11.0, 0.9)}


class Command(BaseCommand):
    help = "Send synthetic readings to the ingest endpoint, like a gateway would."

    def add_arguments(self, parser):
        parser.add_argument("--url", default="http://localhost:8000/api/ingest")
        parser.add_argument("--key", required=True, help="the gateway API key")
        parser.add_argument("--interval", type=float, default=2.0, help="seconds between batches")
        parser.add_argument("--count", type=int, default=0, help="batches to send (0 = until Ctrl-C)")
        parser.add_argument("--off", default="", help="comma separated meter ids that are switched off")

    def handle(self, *args, url, key, interval, count, off, **options):
        off_meters = {m.strip() for m in off.split(",") if m.strip()}
        kwh = {m: 1000.0 * (i + 1) for i, m in enumerate(PROFILES)}
        sent = 0
        try:
            while not count or sent < count:
                now = time.time()
                readings = []
                for meter, (base_kw, base_pf) in PROFILES.items():
                    on = meter not in off_meters
                    kw = max(base_kw + random.uniform(-1.5, 1.5), 0) if on else 0.0
                    pf = min(max(base_pf + random.uniform(-0.02, 0.02), 0.5), 0.99) if on else 0.0
                    kva = kw / pf if pf else 0.0
                    kwh[meter] += kw * interval / 3600
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
                body = json.dumps({"readings": readings}).encode()
                request = urllib.request.Request(
                    url, data=body, method="POST",
                    headers={"Content-Type": "application/json", "X-Gateway-Key": key},
                )  # fmt: skip
                try:
                    with urllib.request.urlopen(request, timeout=10) as response:
                        self.stdout.write(f"{time.strftime('%H:%M:%S')}  sent {len(readings)} readings -> {response.status}")
                except urllib.error.HTTPError as err:
                    raise CommandError(f"server answered {err.code}: {err.read().decode()[:300]}") from None
                except urllib.error.URLError as err:
                    self.stderr.write(f"cannot reach {url}: {err.reason} (will retry)")
                sent += 1
                if not count or sent < count:
                    time.sleep(interval)
        except KeyboardInterrupt:
            self.stdout.write("stopped")
