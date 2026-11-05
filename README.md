# Rice Mill Monitor (frontend)

Live energy and motor monitoring for a rice mill: dashboard, per-machine process
analysis, alerts and thresholds, daily reports, and settings. React 19 + Vite,
plain JavaScript. The backend is built separately; the contract it must meet is in
[docs/API.md](docs/API.md).

## Quick start

```bash
pnpm install
pnpm dev          # http://localhost:5173, uses built-in demo data
```

Demo mode (the default for `pnpm dev`) simulates the plant in the browser. Sign in
with `admin` / `admin123`. Accounts and settings live in that browser only.

| Command                     | What it does                                     |
| --------------------------- | ------------------------------------------------ |
| `pnpm dev`                  | Dev server with demo data                        |
| `pnpm build`                | Production build into `dist/`                    |
| `pnpm preview`              | Serve the production build locally               |
| `pnpm lint` / `pnpm format` | ESLint / Prettier                                |
| `pnpm test`                 | Unit tests (Vitest)                              |
| `pnpm check`                | Lint, test and build, as CI does                 |
| `pnpm dev:api`              | Contract stub: fake API for trying real-API mode |

Needs Node 20+ and pnpm 10 (`corepack enable`).

## Demo data vs the real backend

The app only talks to `src/api/`. Two interchangeable implementations sit behind it:

- `src/api/mock/` – demo data (fake machines, browser-stored accounts). **Insecure by
  design.** It is compiled out of any build where `VITE_USE_MOCK` is not `true`.
- `src/api/http.js` – the real backend over HTTPS.

Production builds use the real backend unless you explicitly opt in to demo data, so
the fake `admin/admin123` account can never ship by accident.

To try real-API mode without a backend:

```bash
pnpm build                      # VITE_USE_MOCK defaults to false
pnpm dev:api -- --static dist   # serves the site and a fake /api on :8000
```

## Configuration

All settings are `VITE_*` environment variables baked in at build time, so they are
**public**. Never put secrets in them. See [.env.example](.env.example) for every
option: API URL, polling interval, company details on the sign-in screen, base path.

## Deploying

Build once, serve the static `dist/` folder, and route `/api` to the backend on the
**same domain** (simplest: no CORS, cookies and CSP just work).

**Docker + nginx** (included):

```bash
docker build -t rice-mill-monitor \
  --build-arg VITE_COMPANY_NAME="Sri Murugan Rice Mill" .
docker run -p 8080:80 rice-mill-monitor
```

`deploy/nginx.conf` already has SPA routing, gzip, long caching for hashed files,
security headers and a `/healthz` check. When the backend exists, uncomment the
`location /api/` block and point it at the backend service.

**Netlify / Vercel:** build command `pnpm build`, output `dist`. Rewrites and headers
are in `public/_redirects` and `vercel.json`. Netlify users should copy the headers
from `deploy/security-headers.conf` into a `_headers` file. Set `VITE_API_URL` to a
full URL, and allow that origin in `connect-src` of the CSP.

**HTTPS is required** in production (tokens are sent on every request).

## Before going live

- [ ] Backend implements [docs/API.md](docs/API.md) and enforces roles itself.
- [ ] `VITE_USE_MOCK` is `false` (or unset) in the production build.
- [ ] Served over HTTPS; the CSP in `deploy/security-headers.conf` allows your API origin.
- [ ] Company details set (`VITE_COMPANY_*`).
- [ ] Login and registration are rate-limited on the backend.
- [ ] Decide on token storage: a bearer token in `localStorage` (default) is simple;
      an httpOnly cookie (`VITE_API_CREDENTIALS=true`) is safer against XSS.

## Project layout

```
src/api/        API client, real HTTP adapter, demo adapter (mock/)
src/assets/     icons and illustrations (imported, fingerprinted by the build)
src/components/ layout shell, shared UI, error boundary
src/context/    sign-in state and live plant data (polling)
src/lib/        formatting, status and alert helpers
src/pages/      one file per screen (each is a separate download)
deploy/         nginx config and security headers
scripts/        contract stub server
docs/API.md     backend contract
```

Times are shown in Indian Standard Time.
