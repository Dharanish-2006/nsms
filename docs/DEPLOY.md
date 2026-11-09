# Deploying NSMS

One small Linux server runs everything with Docker Compose: HTTPS (Caddy), the React app, Django, the
background worker, PostgreSQL and Redis. This is the simplest setup that is correct for production. When
you outgrow it, move PostgreSQL to RDS and Redis to ElastiCache by changing two URLs (section 9).

```
Internet ─▶ Caddy (80/443, automatic HTTPS)
             ├─ /api/*, /django-admin/*, /static/* ─▶ web (Django + WebSocket)  ─▶ PostgreSQL, Redis
             └─ everything else (/, /admin, …)     ─▶ frontend (nginx, the built React app)
worker: reports, cleanup, automatic report emails       bridge (optional): MQTT from AWS IoT Core
```

## 1. What you need

- An AWS account (or any VPS provider). A Linux server with **2 GB RAM** is enough to start: EC2 `t3.small`
  or a Lightsail 2 GB plan, Ubuntu 24.04.
- A **domain name** you control. HTTPS needs one, and AWS IoT will only call a valid HTTPS certificate.
  (A free subdomain from a service like DuckDNS works for testing.)
- An SMTP account for OTP and report emails (Gmail app password for testing, Amazon SES for production).

## 2. Create the server

1. Launch the instance. In its firewall (security group) allow inbound **22** (SSH, ideally only from your
   IP), **80** and **443**. Do not open 5432 or 6379.
2. Give it a fixed address (Elastic IP on EC2, static IP on Lightsail).
3. At your domain registrar, create an **A record**: `mill.example.com` → that IP. Wait until
   `nslookup mill.example.com` shows it.

## 3. Install Docker

```bash
ssh ubuntu@mill.example.com
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && exit        # log in again so the group applies
docker compose version
```

## 4. Get the code and configure it

```bash
git clone https://github.com/Dharanish-2006/nsms.git && cd nsms
cp deploy/prod.env.example deploy/prod.env
nano deploy/prod.env
```

Fill in at least:

| Setting | Value |
|---|---|
| `DOMAIN`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | your hostname (`CORS` as `https://…`) |
| `POSTGRES_PASSWORD` | a new password, letters and digits only |
| `DJANGO_SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | your SMTP account (`DEFAULT_FROM_EMAIL` must match the Gmail address if you use Gmail) |
| `IOT_RULE_SECRET`, `GATEWAY_PROVISION_KEY` | long random values (same command as the secret key), or empty to switch the feature off |
| `COMPANY_*` | shown in the app |

`prod.env` is ignored by git. Keep a copy somewhere safe (a password manager); never paste it in chat or
a screenshot.

## 5. Start it

```bash
docker compose --env-file deploy/prod.env -f deploy/docker-compose.prod.yml up -d --build
docker compose --env-file deploy/prod.env -f deploy/docker-compose.prod.yml ps
```

The first build takes a few minutes. Migrations run automatically when `web` starts. Caddy fetches the
HTTPS certificate the first time someone opens the site (ports 80 and 443 must be reachable).

To avoid typing the long command, add an alias:

```bash
echo "alias nsms='docker compose --env-file ~/nsms/deploy/prod.env -f ~/nsms/deploy/docker-compose.prod.yml'" >> ~/.bashrc && . ~/.bashrc
```

## 6. Create the admin and check it

```bash
nsms exec web python manage.py createsuperuser
```

Open `https://mill.example.com`, sign in with that account: you land on the Admin Portal.
Check `https://mill.example.com/api/healthz` returns `{"status": "ok"}`.

**Do not run `seed_demo` on a server**: it creates accounts with known passwords.

## 7. Connect gateways

- **Over HTTPS**: the gateway uses `https://mill.example.com/api/gateways/provision` and
  `/api/ingest` (see [GUIDE.md](GUIDE.md) section 6).
- **Over MQTT with AWS IoT Core**: choose one.
  - *IoT Rule*: destination `https://mill.example.com/api/iot/ingest`, header `X-IoT-Secret`. See
    [AWS-IOT.md](AWS-IOT.md).
  - *Bridge*: copy the bridge certificate, key and `AmazonRootCA1.pem` into `deploy/certs/` as
    `bridge.cert.pem`, `bridge.private.key`, `AmazonRootCA1.pem`, set `IOT_ENDPOINT` in `prod.env`, then
    `nsms --profile bridge up -d bridge`. No public endpoint is needed for this path. Run one bridge only.

## 8. Operating it

| Task | Command |
|---|---|
| Logs | `nsms logs -f web` (also `worker`, `caddy`, `bridge`) |
| Update to the latest code | `cd ~/nsms && git pull && nsms up -d --build` |
| Restart one service | `nsms restart web` |
| Django shell | `nsms exec web python manage.py shell` |
| Send automatic reports now | `nsms exec web python manage.py send_auto_reports --now` |
| Back up the database | `nsms exec -T db pg_dump -U nsms nsms \| gzip > nsms-$(date +%F).sql.gz` |
| Restore | `gunzip -c nsms-DATE.sql.gz \| nsms exec -T db psql -U nsms nsms` |

Back up daily (a cron job running the backup line, copied off the server to S3) and test a restore once.
Also turn on automatic snapshots of the server disk.

## 9. Growing later

- **Managed database**: create an RDS PostgreSQL instance, set `DATABASE_URL` in the `web`, `worker` and
  `bridge` environment (edit `x-backend` in the compose file), and remove the `db` service.
- **Managed Redis**: same with ElastiCache and `REDIS_URL`.
- **More than one app server**: needs the managed Redis (live updates and rate limits are shared through it),
  an ALB with a long idle timeout (3600 s) for WebSockets, and **one** worker and **one** bridge only.
- **Email**: move from Gmail to Amazon SES SMTP when you have real customers.
- **SMS**: set `SMS_BACKEND=sns`, give the instance's IAM role `sns:Publish`, and register your sender ID and
  templates under DLT (required in India).

## 10. Security checklist before real customers

- [ ] `DJANGO_DEBUG=0`, a long random `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` set to your hostname only.
- [ ] No `seed_demo` accounts. The admin password is long and not reused.
- [ ] Any password or key that ever appeared in a screenshot, chat or git history is revoked and replaced
      (the Gmail app password, and the old `backend/.env` committed earlier).
- [ ] Ports 5432 and 6379 closed; SSH limited to your IP; server updates on (`sudo apt upgrade`).
- [ ] Backups run and one restore has been tested.
- [ ] `GATEWAY_PROVISION_KEY` and `IOT_RULE_SECRET` are random and not shared outside the gateway setup.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Browser shows a certificate error or Caddy keeps retrying | DNS does not point at the server yet, or ports 80/443 are blocked. `nsms logs caddy`. |
| Site loads but login says network error | `DJANGO_ALLOWED_HOSTS` or `CORS_ALLOWED_ORIGINS` does not match the hostname; fix and `nsms up -d`. |
| `web` restarts in a loop | `nsms logs web`: usually a missing `DJANGO_SECRET_KEY` or a wrong `POSTGRES_PASSWORD`. If you change the Postgres password after first start, the old password is still stored in the volume. |
| Live values do not update | WebSocket blocked by something in front of Caddy (a CDN or proxy that does not pass `Upgrade`). |
| `/admin` shows the React portal, not Django's admin | By design. Django's admin is `/django-admin/`. |
