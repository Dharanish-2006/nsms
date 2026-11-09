# NSMS: usage and setup guide

Rice mill energy monitoring. Energy meters → an industrial gateway → AWS → the Django backend → the React
dashboard. This guide covers setup from zero, how each kind of user works with it, how to connect a
gateway, and how to go to production. Deeper reference: [`../backend/README.md`](../backend/README.md),
[`API.md`](API.md), [`AWS-IOT.md`](AWS-IOT.md), and [`DEPLOY.md`](DEPLOY.md) for putting it on a server.

## 1. Who uses what

| Role | Who | Where | Can do |
|---|---|---|---|
| **Plant owner** (`user`) | The mill owner, your customer | `/` (dashboard) | See live data, reports, alerts of the gateways connected to them. Set alert limits, SMS numbers, report emails, machine names and HP. |
| **Admin** | You, owner of the Smart Mill system | `/admin` (Admin Portal) | Approve owners, verify and assign gateways, connect or disconnect them, read the audit log. **Cannot see any machine data.** |

An admin who signs in is sent to `/admin`; an owner who opens `/admin` is sent back to `/`.

## 2. Run it locally

You need Python 3.12+ and Node 20+ with pnpm.

### Backend

```bash
cd backend
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                                # then edit, see section 3
python manage.py migrate
python manage.py seed_demo                          # creates an admin, a demo owner, a gateway, 4 machines
daphne -b 127.0.0.1 -p 8000 config.asgi:application # or: python manage.py runserver
```

`seed_demo` prints the demo logins and the gateway key (shown once). **The demo passwords are in the
command's source: change them, and never run `seed_demo` on a real server.** On a real server create the
admin yourself:

```bash
python manage.py createsuperuser        # username, email, password
```

It creates an active **admin** (role and status are set automatically). The Django admin site is at `/django-admin/` on the backend (for example `http://127.0.0.1:8000/django-admin/`); `/admin` is the React Admin Portal. Admins are never created from the sign-up form.

Leave `DATABASE_URL` empty for a local SQLite file. A remote database (for example Neon) makes every
request slow from a laptop.

### Frontend

```bash
pnpm install
```

The frontend has two modes:

- **Demo mode** (`VITE_USE_MOCK=true`, the default in `.env.development`): no backend needed. Data is
  simulated and stored in the browser. Logins: `admin` / `admin123` (admin), `meena` / `owner123`
  (approved owner), `ravi` / `owner123` (pending owner).
- **Real backend**: create `.env.development.local` (it overrides `.env.development`):

```
VITE_USE_MOCK=false
VITE_DEV_API_PROXY=http://127.0.0.1:8000
```

Restart `pnpm dev` after any env change. If the Network tab shows no `/api` calls you are still in demo mode.

### Test everything

```bash
cd backend && pytest          # 88 tests
pnpm check                    # lint, 28 tests, build
```

## 3. Backend configuration (`backend/.env`)

Copy `.env.example`. The settings that matter:

| Setting | Meaning |
|---|---|
| `DJANGO_SECRET_KEY` | Required when `DJANGO_DEBUG=0`. Generate a long random value. |
| `DJANGO_DEBUG` | `1` locally, `0` in production. |
| `DJANGO_ALLOWED_HOSTS` | Your hostnames. WebSocket origins are checked against it. |
| `DATABASE_URL` | Empty = SQLite. Production: `postgres://user:pass@host:5432/nsms`. |
| `REDIS_URL` | Empty = in-memory (one process only). Needed as soon as you run more than one process. |
| `CORS_ALLOWED_ORIGINS` | Only if the dashboard is on another origin than the API. |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | SMTP for OTP codes and report emails. Console backend just prints. |
| `SMS_BACKEND` | `console` (log) or `sns` (AWS SNS). India needs DLT registration for real SMS. |
| `GATEWAY_PROVISION_KEY` | Shared key gateways use to register themselves. Empty = off. |
| `IOT_RULE_SECRET` | Shared secret for the AWS IoT Rule. Empty = off. |
| `AUTO_REPORT_HOUR` | IST hour (0-23) after which automatic reports go out. Default 6. |
| `NOMINAL_VOLTAGE` | Used when a gateway does not send voltage (default 415). |
| `DEFAULT_PLANT_NAME` | Plant given to self-registered gateways. |
| `STALE_AFTER_SEC`, `RAW_SAMPLE_INTERVAL_SEC`, `RAW_RETENTION_DAYS` | Telemetry tuning. |

### Sending email (OTP and reports) with Gmail

1. Turn on 2-step verification on the Gmail account and create an **app password**.
2. In `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<app password>
DEFAULT_FROM_EMAIL=you@gmail.com
```

3. Restart the server. Never commit `.env` or paste the password anywhere; if it leaks, revoke it. For
production use Amazon SES instead of Gmail.

## 4. The two background jobs

The web server alone does not roll up reports or send automatic emails. Run one worker process:

```bash
python manage.py run_maintenance --loop 300
```

It rebuilds daily reports, deletes raw samples older than `RAW_RETENTION_DAYS`, expires tokens and sends
due automatic reports. To send reports by hand: `python manage.py send_auto_reports` (`--now` ignores `AUTO_REPORT_HOUR`,
`--user NAME` sends for one owner only). Without a worker, automatic reports are never sent.

## 5. Day-to-day flow

### Admin

1. Sign in at `/login` with an admin account. You land on the Admin Portal.
2. **User approval**: new owners register and wait as *Pending*. Approve, or reject with a reason.
3. **Gateways**: a freshly installed gateway registers itself and appears as *Unverified*. Check its
   serial number against the box you installed and press **Verify**. Unverified gateways cannot send data
   or be assigned.
4. **Assign** a verified, available gateway to an approved owner. The owner still sees nothing.
5. **Connect**. From now on the owner sees that gateway's machines, reports and alerts.
6. **Disconnect** frees the gateway. The owner loses live access but keeps reports for the period they
   were connected. A disconnected record can be reconnected, or the gateway assigned to someone else.
7. **New key** issues a fresh gateway key (replaced or reset device). The old key stops at once and the new
   one is shown once.
8. **Audit log** lists every action with admin, time, target and remarks. It cannot be edited.

### Plant owner

1. Register on `/register` (email code, optional phone code). Wait for approval.
2. After the admin connects a gateway, the dashboard shows its machines. Auto-registered machines start
   as "Meter 1", type sheller, rating 0: open the machine page, press **Rename** to give it a real name and
   type (Sheller, Whitener, Sortex), and **Edit** to set the **HP** (confirmation required).
3. **Settings**: alert limit for power factor, SMS numbers, and **automatic report** (email a CSV daily,
   weekly or monthly). Turning it on or changing the frequency means the first report is for the next period.
4. **Reports** and each machine page show usage for the periods you were connected.

## 6. Connecting a gateway

The backend does not care about the gateway model. Pick one path:

**A. HTTPS (simplest).** First boot: `POST /api/gateways/provision` with header `X-Provision-Key`, body
`{ "serial": "...", "name": "..." }` → returns an `apiKey` once. Then send readings:

```
POST /api/ingest        X-Gateway-Key: <apiKey>
{ "readings": [ { "meterId": "1", "ts": 1762400000000, "kw": 26.1, "kwh": 1042.7, "on": true } ] }
```

Only `meterId` and `kw` are required; send up to 500 readings per call, oldest first after an outage.
Retries are safe.

**B. MQTT through AWS IoT Core** (typical for Modbus gateways). The gateway publishes to
`mill/<serial>/readings`; an IoT Rule POSTs it to `/api/iot/ingest` with `X-IoT-Secret`. Full steps
(Thing, certificate, policy, rule, destination confirmation) are in [`AWS-IOT.md`](AWS-IOT.md).
This path is not yet tested against a real AWS account.

Meters: the Selec MFM384 speaks Modbus RTU over RS485. Confirm every register address and the kWh
registers against the meter's manual before relying on the numbers.

Hardware under consideration: Teltonika TRB145 (RS485 Modbus master, MQTT with TLS certificates). Check
that it buffers readings while offline, and that its JSON can be shaped to the format above.

Test without hardware: `python manage.py simulate_gateway --key gw_...`.

## 7. Going to production (AWS)

- **App**: the `backend/Dockerfile` image on ECS Fargate or EC2 behind an ALB. Health check
  `/api/healthz`. Raise the ALB idle timeout (for example 3600 s) for WebSockets. Set
  `TRUST_PROXY_SSL_HEADER=1` and `NUM_PROXIES=1`.
- **Database**: RDS PostgreSQL. **Redis**: ElastiCache.
- **Worker**: a second task running `run_maintenance --loop 300`.
- **Secrets**: keep `DJANGO_SECRET_KEY`, database, Redis and SMTP credentials in Secrets Manager.
- **Frontend**: `pnpm build`, serve `dist/` from S3 + CloudFront or nginx, and route `/api/` (REST and
  WebSocket) to the backend (`deploy/nginx.conf` has an example). Build with `VITE_USE_MOCK=false`.
- **Before launch**: change or remove the `seed_demo` passwords, rotate any credential that was ever
  committed, and register for SMS (DLT in India).

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Login page shows mock data / no `/api` calls | `VITE_USE_MOCK` is still true. Use `.env.development.local` and restart. |
| "Wrong username or password" on the real backend | Demo accounts only exist in demo mode. Use the `seed_demo` or `createsuperuser` account. |
| Create account does nothing | Check the message under the form; both the email (and phone, if given) must be verified first. |
| OTP request returns 429 | Rate limit on OTP sending: wait a few minutes. |
| OTP request returns 503 or `Name or service not known` | `EMAIL_HOST` is empty or wrong. |
| Owner sees no machines | A gateway must be assigned **and connected** to them, and have sent data. |
| Gateway data rejected | The gateway is unverified, disabled, or the key is old. Verify it or issue a new key. |
| Automatic report never arrives | The worker is not running, SMTP is not configured, or the owner has no connected machine. |
| Admin opens `/` and is sent to `/admin` | By design: admins have no machine data. |
