"""Load test for a running NSMS server: many fake gateways push readings at once, and
optionally many dashboards poll at the same time. Standard library only.

    # on the server, once:
    nsms exec -T web python manage.py load_test_gateways --count 50 --out /tmp/keys.json
    nsms cp web:/tmp/keys.json ./keys.json          (or print it and save it; keep it private)

    python tools/load_test.py --url https://ricemillmart.tech --keys keys.json \\
        --gateways 20 --interval 10 --duration 300

    # also simulate owners watching dashboards (one login, reused by every dashboard):
    python tools/load_test.py ... --dashboards 10 --username demoowner --password '...'

While it runs, watch the server:  docker stats   and   nsms logs web
Clean up afterwards:  nsms exec -T web python manage.py load_test_gateways --delete
Run it against your own server only.
"""

import argparse
import json
import math
import random
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request

lock = threading.Lock()
lat = {"ingest": [], "dash": []}
count = {"ingest_ok": 0, "ingest_err": 0, "dash_ok": 0, "dash_err": 0}
last_error = {"ingest": "", "dash": ""}
stop = threading.Event()


def post(url, headers, body, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def record(kind, ok, seconds, err=""):
    with lock:
        lat[kind].append(seconds)
        count[f"{kind}_ok" if ok else f"{kind}_err"] += 1
        if err:
            last_error[kind] = err


def gateway(url, serial, key, meters, interval, ramp_delay):
    kwh = {str(m): 1000.0 * m for m in range(1, meters + 1)}
    stop.wait(ramp_delay)
    while not stop.is_set():
        now = time.time()
        readings = []
        for m in range(1, meters + 1):
            kw = max(10 + 3 * m + random.uniform(-1.5, 1.5), 0)
            pf = min(max(0.9 + random.uniform(-0.03, 0.03), 0.5), 0.99)
            kva = kw / pf
            kwh[str(m)] += kw * interval / 3600
            readings.append({
                "meterId": str(m), "ts": int(now * 1000), "kw": round(kw, 2), "pf": round(pf, 3),
                "kva": round(kva, 2), "kvar": round(math.sqrt(max(kva * kva - kw * kw, 0)), 2),
                "current": round(kva * 1000 / (math.sqrt(3) * 415), 2), "voltage": 415, "frequency": 50.0,
                "kwh": round(kwh[str(m)], 3),
            })
        t0 = time.time()
        try:
            status, _ = post(url + "/api/ingest", {"X-Gateway-Key": key}, {"readings": readings})
            record("ingest", status == 202, time.time() - t0, "" if status == 202 else f"HTTP {status}")
        except urllib.error.HTTPError as e:
            record("ingest", False, time.time() - t0, f"HTTP {e.code} from {serial}")
        except Exception as e:  # timeout, connection refused, ...
            record("ingest", False, time.time() - t0, f"{type(e).__name__}: {e}")
        stop.wait(max(interval - (time.time() - now), 0))


def dashboard(url, token, poll, ramp_delay):
    stop.wait(ramp_delay)
    while not stop.is_set():
        t0 = time.time()
        req = urllib.request.Request(url + "/api/machines", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                r.read()
                record("dash", r.status == 200, time.time() - t0)
        except urllib.error.HTTPError as e:
            record("dash", False, time.time() - t0, f"HTTP {e.code}")
        except Exception as e:
            record("dash", False, time.time() - t0, f"{type(e).__name__}: {e}")
        stop.wait(max(poll - (time.time() - t0), 0))


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(int(len(s) * p), len(s) - 1)]


def snapshot(label, since):
    with lock:
        data = {k: v[:] for k, v in lat.items()}
        c = dict(count)
        err = dict(last_error)
    elapsed = time.time() - since
    line = f"[{label} {elapsed:5.0f}s]"
    for kind, name in (("ingest", "gateways"), ("dash", "dashboards")):
        ok, bad = c[f"{kind}_ok"], c[f"{kind}_err"]
        if ok + bad:
            line += f"  {name}: {ok + bad} req ({bad} failed)  p50 {pct(data[kind], .5) * 1000:.0f} ms  p95 {pct(data[kind], .95) * 1000:.0f} ms"
    print(line, flush=True)
    return data, c, err


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="for example https://ricemillmart.tech")
    ap.add_argument("--keys", required=True, help="JSON file written by load_test_gateways")
    ap.add_argument("--gateways", type=int, default=10, help="how many fake gateways to run")
    ap.add_argument("--meters", type=int, default=5, help="meters per gateway")
    ap.add_argument("--interval", type=float, default=10.0, help="seconds between messages per gateway")
    ap.add_argument("--duration", type=int, default=120, help="test length in seconds")
    ap.add_argument("--ramp", type=int, default=20, help="seconds over which the clients start")
    ap.add_argument("--dashboards", type=int, default=0, help="fake dashboards polling /api/machines")
    ap.add_argument("--poll", type=float, default=5.0, help="seconds between dashboard polls")
    ap.add_argument("--username", default="")
    ap.add_argument("--password", default="")
    a = ap.parse_args()
    url = a.url.rstrip("/")

    keys = json.load(open(a.keys))
    if a.gateways > len(keys):
        sys.exit(f"The key file has only {len(keys)} gateways; create more with load_test_gateways --count.")

    token = ""
    if a.dashboards:
        if not (a.username and a.password):
            sys.exit("--dashboards needs --username and --password (a plant owner account).")
        try:
            _, body = post(url + "/api/auth/login", {}, {"username": a.username, "password": a.password})
            token = json.loads(body)["token"]
        except Exception as e:
            sys.exit(f"Could not log in for the dashboards: {e}")

    print(f"Testing {url}: {a.gateways} gateways x {a.meters} meters every {a.interval:g}s"
          + (f", {a.dashboards} dashboards every {a.poll:g}s" if a.dashboards else "") + f", for {a.duration}s")
    print(f"Expected load: {a.gateways / a.interval:.1f} messages/s"
          + (f" + {a.dashboards / a.poll:.1f} dashboard requests/s" if a.dashboards else ""))
    threads = []
    for i in range(a.gateways):
        g = keys[i]
        d = a.ramp * i / max(a.gateways, 1)
        threads.append(threading.Thread(target=gateway, args=(url, g["serial"], g["key"], a.meters, a.interval, d), daemon=True))
    for i in range(a.dashboards):
        d = a.ramp * i / max(a.dashboards, 1)
        threads.append(threading.Thread(target=dashboard, args=(url, token, a.poll, d), daemon=True))
    start = time.time()
    for t in threads:
        t.start()
    try:
        while time.time() - start < a.duration:
            time.sleep(10)
            snapshot("running", start)
    except KeyboardInterrupt:
        print("Stopping early...")
    stop.set()
    time.sleep(1)

    data, c, err = snapshot("final  ", start)
    print("\nSummary")
    worst = "PASS"
    for kind, name in (("ingest", "Gateway messages"), ("dash", "Dashboard polls")):
        total = c[f"{kind}_ok"] + c[f"{kind}_err"]
        if not total:
            continue
        rate = c[f"{kind}_err"] / total
        p95 = pct(data[kind], .95)
        mean = statistics.mean(data[kind]) if data[kind] else 0
        verdict = "OK" if rate <= 0.01 and p95 <= 1.0 else ("SLOW" if rate <= 0.01 else "FAILING")
        if verdict != "OK":
            worst = "CHECK"
        print(f"  {name}: {total} requests, {rate:.1%} failed, mean {mean * 1000:.0f} ms, "
              f"p95 {p95 * 1000:.0f} ms, max {max(data[kind]) * 1000:.0f} ms  ->  {verdict}")
        if err[kind]:
            print(f"    last error: {err[kind]}")
    print("\nOK = under 1% failures and 95% of requests under 1 second. Also check docker stats:\n"
          "memory above about 80% of 2 GB means this many mills is the limit, whatever this script says.")
    sys.exit(0 if worst == "PASS" else 1)


if __name__ == "__main__":
    main()
