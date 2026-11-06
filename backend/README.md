# Rice Mill Monitor: backend

Django + Django REST Framework + Channels. It implements the contract in
[`../docs/API.md`](../docs/API.md) and adds the gateway ingest pipeline and the realtime feed.

```
industrial gateway ──HTTPS POST /api/ingest──▶  Django (ASGI)
  (energy meters)        X-Gateway-Key              │
                                                    ├─ MachineState   live values, run/stop, runtime
                                                    ├─ Reading        raw samples (7 days, for trend charts)
                                                    ├─ HourlyReport   consolidated, updated on every sample
                                                    ├─ DailyReport    rolled up by run_maintenance
                                                    ├─ Alerts         evaluated on every batch → SMS
                                                    └─ Channels group_send
                                                              │
                       dashboard ◀── WebSocket /api/live/ ────┘   (REST polling still works)
```

## Run it locally

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1                 # or copy .env.example to .env
python manage.py migrate
python manage.py seed_demo            # admin + operator + a gateway + 4 machines (prints the gateway key once)
daphne -b 127.0.0.1 -p 8000 config.asgi:application   # or: python manage.py runserver
python manage.py simulate_gateway --key gw_…          # pretend to be the gateway
pytest
```

Point the frontend at it with `VITE_USE_MOCK=false` and proxy `/api/` (REST and WebSocket) to port 8000
(see `deploy/nginx.conf`).

## How the gateway sends data

`POST /api/ingest`, header `X-Gateway-Key: gw_…` (created in the admin API or Django admin; shown once).

```json
{ "readings": [
  { "meterId": "1", "ts": 1762400000000, "kw": 26.1, "pf": 0.93,
    "kva": 28.0, "kvar": 10.2, "current": 39.1, "voltage": 415, "frequency": 50.0,
    "kwh": 1042.7, "kvarh": 311.0, "kvah": 1120.4, "on": true } ] }
```

- `meterId` maps to a machine (`Machine.meter_id`, unique per gateway). Register machines with
  `POST /api/machines` or in Django admin. Unknown meters are returned in `unknownMeters`.
- Only `meterId` and `kw` are required. Missing `pf`/`kva`/`kvar`/`current`/`on` are derived; without `on`,
  a machine is on at or above its `on_threshold_kw`.
- Send the meter's lifetime counters (`kwh`…) when you can: energy is then exact even across gaps.
  Without them it is integrated from power.
- Batches of up to 500 readings. Send buffered readings oldest first after an outage.
- Safe to retry: duplicate or older-than-latest samples never change live state or reports.
- Bad readings are rejected one by one (`rejected`), the rest are kept. Nothing valid → `422`.
- **AWS**: the simplest path is the gateway calling this endpoint over HTTPS through an ALB. If the gateway
  speaks MQTT to **AWS IoT Core**, add an IoT rule with an *HTTPS action* to the same URL (add the header
  there); no extra code is needed.

## What is stored

| Table | Purpose | Kept |
|---|---|---|
| `MachineState` | latest values and counters; the dashboard reads this | always |
| `Reading` | raw samples (thinned to one per 15 s plus every on/off change) | 7 days |
| `HourlyReport` | per machine and IST hour: kWh, running kWh, runtime, avg/max kW, avg PF | always |
| `DailyReport` | per machine and IST day, rolled up from hourly | always |

`python manage.py run_maintenance --loop 300` (the compose `worker`) rebuilds the daily rows, prunes old raw
readings and expires tokens. The daily report endpoint also builds today's row on demand.

## Access model

- Roles: `admin` and `user`. Sign-up creates a `pending` user; an admin approves it. Asking for the admin
  role at sign-up is only a request (`requestedRole`); promote people in Django admin.
- **An admin assigns gateways to users** (`/api/gateways/:id/users`). A user sees only the machines, plants and
  alerts of gateways assigned to them, in REST and on the WebSocket. Admins see everything. Changes reach
  open dashboards immediately.
- Auth is an opaque bearer token (only its hash is stored; 7-day expiry; revoked on logout and on password
  change elsewhere). Login is rate limited per IP and per account; OTP codes are limited and lock after 5 wrong tries.
- Gateway keys are stored hashed, shown once, rotatable, and can be disabled.

## Alerts and SMS

Evaluated on the server for every batch (no browser needed). Power factor below the limit raises a
`warning`/`critical` alert; off machines and sortex machines are skipped; a machine-specific threshold
overrides the "all machines" one. SMS goes to the numbers in `/api/phones` when an alert is raised or gets
worse; the same alert is not re-sent within `ALERT_SMS_COOLDOWN_MIN` (default 30) unless it escalates.
`SMS_BACKEND=console` logs messages; `SMS_BACKEND=sns` uses AWS SNS (grant `sns:Publish`; in India you must
register a DLT sender/template).

## Deploying on AWS

- **App**: the image in `Dockerfile` on ECS Fargate (or EC2) behind an ALB. Target-group health check
  `/api/healthz`; raise the ALB idle timeout (e.g. 3600 s) for WebSockets. Set `TRUST_PROXY_SSL_HEADER=1`
  and `NUM_PROXIES=1`.
- **Database**: RDS PostgreSQL (`DATABASE_URL`). **Redis**: ElastiCache (`REDIS_URL`), required as soon as
  there is more than one app process (realtime fan-out and rate limits share it).
- **Worker**: one more task running `python manage.py run_maintenance --loop 300`.
- **Secrets**: `DJANGO_SECRET_KEY`, DB and Redis URLs from Secrets Manager. Set `DJANGO_ALLOWED_HOSTS` to the
  public hostname (WebSocket origins are checked against it).
- **Email** (OTP): SES via SMTP settings in `.env.example`.

## Known limits and next steps

- WebSocket clients must send an `Origin` header (browsers do); the origin must be in `DJANGO_ALLOWED_HOSTS`.
- A sample older than a machine's newest applied sample is stored (if not a duplicate) but does not change
  live state or reports, so energy recorded out of order is not back-filled.
- Daily and hourly boundaries are IST (`TIME_ZONE`).
- No MQTT subscriber is included; use the IoT Core → HTTPS rule above, or add a small consumer that calls
  `apps.telemetry.ingest.ingest()`.
