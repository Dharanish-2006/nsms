#!/usr/bin/env node
// Contract stub, NOT a real backend. It answers every endpoint in docs/API.md with
// in-memory data so the frontend can be exercised in production mode
// (VITE_USE_MOCK=false) and so backend developers have a runnable reference for the
// request and response shapes. Nothing here is persisted or secure.
//
//   node scripts/dev-api.mjs                 API on http://localhost:8000
//   node scripts/dev-api.mjs --static dist   also serves the built site (like nginx)
//
// Test hooks: GET /__fail?on=1 makes live endpoints return 500, GET /__expire
// invalidates the current token (next call returns 401).

import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";

const args = process.argv.slice(2);
const port = Number(process.env.PORT) || 8000;
const staticDir = args.includes("--static") ? args[args.indexOf("--static") + 1] : null;

let token = "stub-token";
let failing = false;
let nextId = 100;

const users = [
  {
    id: "u1",
    username: "admin",
    fullName: "Administrator",
    email: "a@example.com",
    mobile: "9000000000",
    role: "admin",
    status: "active",
    password: "admin123",
  },
  {
    id: "u2",
    username: "asha",
    fullName: "Asha K",
    email: "asha@example.com",
    mobile: "9111111111",
    role: "user",
    status: "pending",
    password: "asha12345",
  },
];
let thresholds = [
  { id: "t1", param: "powerFactor", machineId: "all", warning: 0.9, critical: 0.8 },
];
let phones = [{ id: "p1", digits: "9000000001", label: "Primary contact" }];

const defs = [
  {
    id: "sheller-1",
    name: "Sheller 1",
    type: "sheller",
    on: true,
    kw: 26,
    pf: 0.93,
    rated: 36,
  },
  {
    id: "whitener-2",
    name: "Whitener 2",
    type: "whitener",
    on: true,
    kw: 15,
    pf: 0.79,
    rated: 22,
  },
  {
    id: "polisher",
    name: "Polisher",
    type: "polisher",
    on: false,
    kw: 0,
    pf: 0,
    rated: 15,
  },
];

const wobble = (v, a) => v + (Math.random() - 0.5) * a;

function machine(d) {
  const now = Date.now();
  const kw = d.on ? wobble(d.kw, 1) : 0;
  const pf = d.on ? Math.min(0.99, wobble(d.pf, 0.02)) : 0;
  const kva = d.on ? kw / pf : 0;
  return {
    id: d.id,
    name: d.name,
    plant: "Plant 1",
    type: d.type,
    ratedKw: d.rated,
    on: d.on,
    updatedAt: now - 1500,
    kw,
    pf,
    kva,
    kvar: Math.sqrt(Math.max(kva * kva - kw * kw, 0)),
    current: (kva * 1000) / (Math.sqrt(3) * 415),
    loadFactor: d.on ? (kw / d.rated) * 100 : 0,
    totalKwh: 41250.4,
    totalKvarh: 24337.7,
    totalKvah: 47850.5,
    runKwh: d.on ? 143 : 0,
    runStart: d.on ? now - 8 * 3600e3 : null,
    lastStop: d.on ? null : now - 3600e3,
    runSec: d.on ? 8 * 3600 : 0,
    todaySec: 8 * 3600,
    totalRuntimeSec: 3120 * 3600,
    avgPfRun: d.on ? d.pf : null,
    hourlyKwh: Array.from({ length: 24 }, (_, h) => (h <= 8 ? d.kw : 0)),
    hourOn: Array.from({ length: 24 }, (_, h) => (h <= 8 ? 1 : 2)),
  };
}

function alerts() {
  const out = [];
  for (const t of thresholds) {
    for (const d of defs) {
      if (t.machineId !== "all" && t.machineId !== d.id) continue;
      if (t.param !== "powerFactor" || !d.on) continue;
      const m = machine(d);
      const sev = m.pf < t.critical ? "critical" : m.pf < t.warning ? "warning" : null;
      if (!sev) continue;
      out.push({
        key: `${t.id}:${d.id}`,
        thresholdId: t.id,
        machineId: d.id,
        machineName: d.name,
        plant: "Plant 1",
        param: t.param,
        severity: sev,
        status: "active",
        reading: m.pf,
        limit: sev === "critical" ? t.critical : t.warning,
        since: Date.now() - 20 * 60e3,
      });
    }
  }
  return out;
}

const publicUser = (user) => {
  const copy = { ...user };
  delete copy.password;
  return copy;
};
const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(body === undefined ? "" : JSON.stringify(body));
};
const readBody = (req) =>
  new Promise((resolve) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch {
        resolve({});
      }
    });
  });

async function api(req, res, url) {
  const route = `${req.method} ${url.pathname.replace(/^\/api/, "")}`;
  const body = await readBody(req);

  if (route === "POST /auth/login") {
    const u = users.find(
      (x) => x.username === body.username && x.password === body.password,
    );
    if (!u)
      return json(res, 401, {
        message: "Wrong username or password.",
        code: "invalid_credentials",
      });
    if (u.status !== "active")
      return json(res, 403, {
        message: "Your account is waiting for administrator approval.",
        code: "pending_approval",
      });
    token = `stub-${Date.now()}`;
    return json(res, 200, { token, user: publicUser(u) });
  }
  if (route === "POST /auth/register") {
    users.push({ id: `u${nextId++}`, status: "pending", role: "user", ...body });
    return json(res, 201, { ok: true });
  }

  // Everything below needs a valid token.
  if (req.headers.authorization !== `Bearer ${token}`)
    return json(res, 401, { message: "Please sign in again.", code: "unauthenticated" });

  switch (route) {
    case "GET /auth/me":
      return json(res, 200, publicUser(users[0]));
    case "POST /auth/logout":
      return json(res, 204);
    case "POST /auth/change-password":
      if (body.currentPassword !== users[0].password)
        return json(res, 400, {
          message: "Current password is incorrect.",
          code: "wrong_password",
        });
      users[0].password = body.newPassword;
      return json(res, 204);
    case "GET /users": {
      const s = url.searchParams.get("status");
      return json(res, 200, users.filter((u) => !s || u.status === s).map(publicUser));
    }
    case "GET /plants":
      return json(res, 200, ["Plant 1"]);
    case "GET /machines":
      if (failing) return json(res, 500, { message: "boom" });
      return json(res, 200, { serverTime: Date.now(), machines: defs.map(machine) });
    case "GET /alerts":
      if (failing) return json(res, 500, { message: "boom" });
      return json(res, 200, alerts());
    case "GET /thresholds":
      return json(res, 200, thresholds);
    case "POST /thresholds": {
      const row = { ...body, id: `t${nextId++}` };
      thresholds.push(row);
      return json(res, 201, row);
    }
    case "GET /phones":
      return json(res, 200, phones);
    case "POST /phones": {
      const row = { ...body, id: `p${nextId++}` };
      phones.push(row);
      return json(res, 201, row);
    }
  }

  let m;
  if (
    (m = url.pathname.match(/^\/api\/machines\/([^/]+)\/trend$/)) &&
    req.method === "GET"
  ) {
    const d = defs.find((x) => x.id === m[1]);
    if (!d) return json(res, 404, { message: "Machine not found.", code: "not_found" });
    const hours = Number(url.searchParams.get("hours")) || 6;
    const points = [];
    for (let t = Date.now() - hours * 3600e3; t <= Date.now(); t += 5 * 60e3) {
      const kw = wobble(d.kw, 2),
        pf = Math.min(0.99, wobble(d.pf, 0.03));
      points.push({ t, kw, pf, current: ((kw / pf) * 1000) / (Math.sqrt(3) * 415) });
    }
    return json(res, 200, points);
  }
  if ((m = url.pathname.match(/^\/api\/users\/([^/]+)(\/approve)?$/))) {
    const u = users.find((x) => x.id === m[1]);
    if (!u) return json(res, 404, { message: "User not found.", code: "not_found" });
    if (req.method === "POST" && m[2]) {
      u.status = "active";
      return json(res, 204);
    }
    if (req.method === "DELETE") {
      users.splice(users.indexOf(u), 1);
      return json(res, 204);
    }
  }
  if ((m = url.pathname.match(/^\/api\/thresholds\/([^/]+)$/))) {
    if (req.method === "PUT") {
      thresholds = thresholds.map((t) => (t.id === m[1] ? { ...body, id: m[1] } : t));
      return json(res, 200, body);
    }
    if (req.method === "DELETE") {
      thresholds = thresholds.filter((t) => t.id !== m[1]);
      return json(res, 204);
    }
  }
  if ((m = url.pathname.match(/^\/api\/phones\/([^/]+)$/))) {
    if (req.method === "PUT") {
      phones = phones.map((p) => (p.id === m[1] ? { ...body, id: m[1] } : p));
      return json(res, 200, body);
    }
    if (req.method === "DELETE") {
      phones = phones.filter((p) => p.id !== m[1]);
      return json(res, 204);
    }
  }
  return json(res, 404, { message: "Not found.", code: "not_found" });
}

const TYPES = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
  ".txt": "text/plain",
};

async function serveStatic(res, pathname) {
  const safe = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
  for (const file of [safe, "/index.html"]) {
    try {
      const data = await readFile(join(staticDir, file));
      res.writeHead(200, {
        "content-type": TYPES[extname(file)] ?? "application/octet-stream",
      });
      return res.end(data);
    } catch {
      /* try the SPA fallback */
    }
  }
  res.writeHead(404).end();
}

createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname === "/__fail") {
    failing = url.searchParams.get("on") === "1";
    return json(res, 200, { failing });
  }
  if (url.pathname === "/__expire") {
    token = "expired";
    return json(res, 200, { ok: true });
  }
  if (url.pathname.startsWith("/api/")) return api(req, res, url);
  if (staticDir) return serveStatic(res, url.pathname);
  json(res, 404, { message: "Not found." });
}).listen(port, () =>
  console.log(
    `Contract stub on http://localhost:${port}${staticDir ? ` (site: ${staticDir})` : ""}`,
  ),
);
