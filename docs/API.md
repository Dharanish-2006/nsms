# Backend API contract

The frontend talks to the backend only through `src/api/http.js`. This file is the
contract that backend must meet. A runnable reference that answers every endpoint
with fake data is in `scripts/dev-api.mjs` (`pnpm dev:api`).

## Conventions

- Base URL: `VITE_API_URL` (default `/api`). All bodies are JSON.
- Times are **milliseconds since the Unix epoch (UTC)**. The UI shows them in IST.
- Authentication: `Authorization: Bearer <token>` on every request except
  login and register. If the backend prefers an httpOnly session cookie, set
  `VITE_API_CREDENTIALS=true`, return no `token` from login, and enable CORS
  credentials (or serve both from one origin).
- **401** on any authenticated call signs the user out in the app.
- Errors: any non-2xx response should be `{ "message": "…", "code": "snake_case" }`.
  `message` is shown to the user as-is for 4xx, so keep it plain and safe.
  For 5xx the UI shows a generic message and ignores the body.
- **Enforce permissions on the server.** The UI hides admin controls from regular
  users, but that is only a convenience. Admin-only endpoints must return 403 to
  non-admins.
- Never return password hashes.

## Auth

| Method | Path                    | Body                                                    | Response                                                                                              |
| ------ | ----------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| POST   | `/auth/login`           | `{ username, password }`                                | `{ token, user }`. 401 wrong credentials; 403 with `code: "pending_approval"` if not yet approved     |
| POST   | `/auth/register`        | `{ fullName, username, email, mobile, password, role }` | 201. Account starts as `pending`. 409 if username is taken. Treat `role: "admin"` as a _request_ only |
| GET    | `/auth/me`              |                                                         | `user`                                                                                                |
| POST   | `/auth/logout`          |                                                         | 204                                                                                                   |
| POST   | `/auth/change-password` | `{ currentPassword, newPassword }`                      | 204. 400 if current password is wrong                                                                 |

`user`: `{ id, username, fullName, email, mobile, role: "admin" | "user", status: "active" | "pending" }`

Rate-limit login and registration on the server.

## Users (admin only)

| Method | Path                    | Response                       |
| ------ | ----------------------- | ------------------------------ |
| GET    | `/users?status=pending` | `[user]`                       |
| POST   | `/users/:id/approve`    | 204                            |
| DELETE | `/users/:id`            | 204 (used to reject a request) |

## Plants, machines, alerts (any signed-in user)

| Method | Path                          | Response                                                                       |
| ------ | ----------------------------- | ------------------------------------------------------------------------------ |
| GET    | `/plants`                     | `["Plant 1"]`                                                                  |
| GET    | `/machines?plant=Plant 1`     | `{ serverTime, machines: [machine] }`                                          |
| GET    | `/machines/:id/trend?hours=6` | `[{ t, pf, current, kw }]`, oldest first                                       |
| GET    | `/alerts?plant=Plant 1`       | `[alert]`, active first (critical, then newest), then recovered (newest first) |

The app calls `/machines` and `/alerts` every `VITE_POLL_INTERVAL_MS` (5 s).
Keep them fast. It backs off automatically when they fail.

`machine`:

```json
{
  "id": "sheller-1",
  "name": "Sheller 1",
  "plant": "Plant 1",
  "type": "sheller",
  "ratedKw": 36,
  "on": true,
  "updatedAt": 1762320000000,
  "kw": 26.1,
  "pf": 0.93,
  "kva": 28.1,
  "kvar": 10.4,
  "current": 39.1,
  "loadFactor": 72.5,
  "totalKwh": 41250.4,
  "totalKvarh": 24337.7,
  "totalKvah": 47850.5,
  "runKwh": 143.0,
  "runStart": 1762291200000,
  "lastStop": null,
  "runSec": 28800,
  "todaySec": 28800,
  "totalRuntimeSec": 11232000,
  "avgPfRun": 0.93,
  "hourlyKwh": [/* 24 numbers, hour 0..23 IST, energy used in that hour */],
  "hourOn": [/* 24 values: 1 ran, 0 did not, 2 hour not reached yet */]
}
```

- `type` is one of `sheller | whitener | polisher | sortex`; it only picks the picture.
- `serverTime` is the server's clock. The UI compares it with `updatedAt` to decide
  whether a machine is "unknown" (no data for 2 minutes), so it never relies on the
  viewer's clock.
- Send `0` for electrical values and `avgPfRun: null` while a machine is off.
- `runStart` / `lastStop` are epoch ms or `null`.

`alert`:

```json
{
  "key": "t1:whitener-2",
  "thresholdId": "t1",
  "machineId": "whitener-2",
  "machineName": "Whitener 2",
  "plant": "Plant 1",
  "param": "powerFactor",
  "severity": "critical",
  "status": "active",
  "reading": 0.79,
  "limit": 0.8,
  "since": 1762319000000,
  "recoveredAt": null
}
```

`param`: `powerFactor | avgCurrent | activePower | freshness`.
`severity`: `critical | warning`. `status`: `active | recovered`.
`key` must be stable for the same threshold and machine.

Alerts are evaluated **by the backend** (so they fire even when nobody has the page
open, and so SMS can be sent to the phone numbers below). The rules:
power factor alerts when **below** its limit; current, active power and data
freshness (seconds since `updatedAt`) alert when **above**. Electrical limits are
skipped while a machine is off. Critical wins over warning.

## Thresholds and phone numbers

| Method | Path              | Body                   | Response                 |
| ------ | ----------------- | ---------------------- | ------------------------ |
| GET    | `/thresholds`     |                        | `[threshold]` (any user) |
| POST   | `/thresholds`     | threshold without `id` | 201 `threshold` (admin)  |
| PUT    | `/thresholds/:id` | threshold              | 200 (admin)              |
| DELETE | `/thresholds/:id` |                        | 204 (admin)              |
| GET    | `/phones`         |                        | `[phone]` (any user)     |
| POST   | `/phones`         | phone without `id`     | 201 `phone` (admin)      |
| PUT    | `/phones/:id`     | phone                  | 200 (admin)              |
| DELETE | `/phones/:id`     |                        | 204 (admin)              |

`threshold`: `{ id, param, machineId: "all" | "<machine id>", warning: number | null, critical: number | null }`
Validate on the server: at least one limit set; for `powerFactor` critical ≤ warning;
for the others critical ≥ warning.

`phone`: `{ id, digits: "9000000001", label }`. `digits` is exactly 10 digits
(Indian mobile, no country code). Reject duplicates with 409.
