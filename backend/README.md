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

`POST /api/ingest`, header `X-Gateway-Key: gw_…`. The key comes from self-registration (below) or from Django
admin, and is shown once. A gateway that registered itself is verified automatically (`GATEWAY_AUTO_VERIFY=1`, the default); with `0` it cannot send data until an admin verifies it.

```json
{ "readings": [
  { "meterId": "1", "ts": 1762400000000, "kw": 26.1, "pf": 0.93,
    "kva": 28.0, "kvar": 10.2, "current": 39.1, "voltage": 415, "frequency": 50.0,
    "kwh": 1042.7, "kvarh": 311.0, "kvah": 1120.4, "on": true } ] }
```

- `meterId` maps to a machine (`Machine.meter_id`, unique per gateway). Register machines with
  Django admin. A meter a verified gateway reports for the first time is registered automatically as
  "Meter <id>" (type `sheller`, rating 0): the plant owner renames it and sets its HP. At most
  `MAX_AUTO_MACHINES_PER_GATEWAY` (32) are created this way; the rest come back in `unknownMeters`.
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

## Gateways register themselves

Install the gateway, then set its server address and the shared provisioning key (`GATEWAY_PROVISION_KEY`).
On first boot it calls:

```
POST /api/gateways/provision      X-Provision-Key: <shared key>
{ "serial": "SN-2026-0001", "name": "Mill gateway" }   ->  201 { "gatewayId", "apiKey", "status": "verified" }
```

The gateway stores `apiKey` and uses it as `X-Gateway-Key` from then on (it is shown only once). The gateway
appears in the admin portal at once and is verified automatically, so it can send data and be assigned. (With
`GATEWAY_AUTO_VERIFY=0` it starts *unverified* and the admin must verify it first.) It reaches no owner until
the admin assigns and connects it. A serial can register only once; a replaced
device gets a new key from the admin (`rotate-key`). Leave `GATEWAY_PROVISION_KEY` empty to turn this off.
Nothing here depends on the gateway model: any device that can send an HTTPS POST with a header will do.

## MQTT gateways (AWS IoT Core)

Gateways that speak MQTT (typical for Modbus gateways) publish to AWS IoT Core; an IoT Rule forwards
each message to `POST /api/iot/ingest` (header `X-IoT-Secret`, set `IOT_RULE_SECRET`). Registration and
verification work the same way as above. Setup, policy, rule and the Selec MFM384 register mapping are
in [`../docs/AWS-IOT.md`](../docs/AWS-IOT.md).

## Two kinds of user

**Plant owners** (`role: user`) are the customers. They register, wait for approval, then monitor the gateways
they are connected to: live data, alerts, reports, and their own alert limits, SMS numbers, notification
settings and machine ratings (HP). **Admins** run the Smart Mill system. They have no access to machine data,
alerts or reports (those endpoints return 403 for them and the WebSocket sends them nothing).

## Admin Portal API (`/api/admin-portal/`, admin only)

| Screen | Endpoints |
|---|---|
| Dashboard | `GET dashboard`: pending/approved users, gateways, active connections, availability |
| User Approval | `GET users?status=pending\|active\|rejected&q=`, `POST users/:id/approve`, `POST users/:id/reject {reason?}` |
| Gateway Assignment | `GET gateways?availability=&verified=&q=`, `POST gateways/:id/verify`, `POST gateways/:id/rotate-key`, `POST assignments {userId, gatewayId}` |
| Connections | `GET assignments?status=&userId=&gatewayId=&q=`, `POST assignments/:id/connect`, `POST assignments/:id/disconnect` |
| Profile | `GET/PATCH /api/auth/me` (name only), logout is `POST /api/auth/logout` |
| Audit | `GET audit-log?action=&limit=` |

Rules, all enforced on the server and in database transactions:

- Only **approved** users can be assigned. A decided request (approved or rejected) cannot be decided again;
  a rejected user stays in the database with the reason.
- A gateway has **one live record** at a time (`assigned` or `connected`), enforced by a database constraint
  as well as in code, so two admins cannot assign it twice. A user can hold many gateways.
- `assigned` reserves the gateway; the owner sees its data only once it is `connected`. Disconnecting frees
  the gateway at once and keeps the record as history. A disconnected record can be connected again while
  the gateway is free.
- Every approval, rejection, verification, key rotation, assignment, connection and disconnection writes
  the admin, action, target, time and remarks to the audit log (append-only, read-only in Django admin).
- Readings are always stored. An owner's reports, usage, trend and live "today" numbers cover only the
  periods they were connected (hours that overlap a connection are included whole), so a new owner never
  sees the previous owner's data.
- Open dashboards update at once when a connection starts or ends.

## Access model

- Auth is an opaque bearer token (only its hash is stored; 7-day expiry; revoked on logout and on password
  change elsewhere). Login is rate limited per IP and per account; OTP codes are limited and lock after 5 wrong tries.
- Sign-up creates a `pending` user. Asking for the admin role at sign-up is ignored (`requestedRole` is only
  recorded); create admins with `createsuperuser` or in Django admin.
- Gateway keys are stored hashed, shown once, rotatable, and can be disabled.

## Alerts and SMS

Evaluated on the server for every batch (no browser needed). Power factor below the limit raises a
`warning`/`critical` alert; off machines and sortex machines are skipped; a machine-specific threshold
overrides the "all machines" one. Limits (`/api/thresholds`), SMS numbers (`/api/phones`) and `/api/settings/notifications` belong to each plant owner, and apply to the gateways they are connected to; with `alertsEnabled` off no SMS is sent. SMS goes to the owner's numbers when an alert is raised or gets
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
- MQTT: either the IoT Core → HTTPS rule above, or `python manage.py iot_bridge` (subscribes to IoT Core
  itself; handy on a laptop with no public address). The bridge only sees messages published while it runs.
- Django's own admin site is at `/django-admin/`; `/admin` belongs to the React Admin Portal.
