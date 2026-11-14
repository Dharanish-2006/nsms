import { request } from "./client";
import { tokenStore } from "./token";

// Real backend. The endpoints below are the contract the backend must provide;
// see docs/API.md for request and response shapes.

const enc = encodeURIComponent;

export const httpApi = {
  auth: {
    async login(username, password) {
      const data = await request("/auth/login", {
        method: "POST",
        body: { username, password },
        auth: false,
      });
      if (data.token) tokenStore.set(data.token);
      return data.user;
    },
    register: (input) =>
      request("/auth/register", { method: "POST", body: input, auth: false }),
    /** channel: "email" | "phone" -> 204 (code is sent out of band) */
    sendOtp: (channel, target) =>
      request("/auth/otp/send", {
        method: "POST",
        body: { channel, target },
        auth: false,
      }),
    /** -> { token }, a short-lived proof of verification to pass to register */
    verifyOtp: (channel, target, code) =>
      request("/auth/otp/verify", {
        method: "POST",
        body: { channel, target, code },
        auth: false,
      }),
    me: () => request("/auth/me"),
    async logout() {
      try {
        await request("/auth/logout", { method: "POST" });
      } finally {
        tokenStore.clear();
      }
    },
    changePassword: (currentPassword, newPassword) =>
      request("/auth/change-password", {
        method: "POST",
        body: { currentPassword, newPassword },
      }),
  },

  // Public Contact form on the Smart Milling page (no login).
  contact: {
    /** { name, mobile, requirement, website } -> { ok: true }. `website` is a hidden spam trap. */
    send: (input) => request("/contact", { method: "POST", body: input, auth: false }),
  },

  // Admin Portal (administrators only; no machine data is reachable from here).
  admin: {
    enquiries: (query) => request("/admin-portal/enquiries", { query }),
    setEnquiryStatus: (id, status) =>
      request(`/admin-portal/enquiries/${enc(id)}`, { method: "PUT", body: { status } }),
    dashboard: () => request("/admin-portal/dashboard"),
    users: (query) => request("/admin-portal/users", { query }),
    approveUser: (id) =>
      request(`/admin-portal/users/${enc(id)}/approve`, { method: "POST" }),
    rejectUser: (id, reason) =>
      request(`/admin-portal/users/${enc(id)}/reject`, {
        method: "POST",
        body: { reason },
      }),
    gateways: (query) => request("/admin-portal/gateways", { query }),
    rotateKey: (id, remarks) =>
      request(`/admin-portal/gateways/${enc(id)}/rotate-key`, {
        method: "POST",
        body: { remarks },
      }),
    assignments: (query) => request("/admin-portal/assignments", { query }),
    assign: (userId, gatewayId, remarks) =>
      request("/admin-portal/assignments", {
        method: "POST",
        body: { userId: Number(userId), gatewayId, remarks },
      }),
    connect: (id, remarks) =>
      request(`/admin-portal/assignments/${enc(id)}/connect`, {
        method: "POST",
        body: { remarks },
      }),
    disconnect: (id, remarks) =>
      request(`/admin-portal/assignments/${enc(id)}/disconnect`, {
        method: "POST",
        body: { remarks },
      }),
    gatewayMachines: (id) => request(`/admin-portal/gateways/${enc(id)}/machines`),
    auditLog: (query) => request("/admin-portal/audit-log", { query }),
  },

  plants: {
    list: (opts) => request("/plants", opts),
  },

  machines: {
    /** -> { serverTime, machines: [...] } */
    list: (plant, opts) => request("/machines", { ...opts, query: { plant } }),
    /** range: "week" | "month" -> { consumedKwh, actualKwh } totals for the plant */
    usage: (plant, range, opts) =>
      request("/machines/usage", { ...opts, query: { plant, range } }),
    /** -> [{ t, pf, current, kw }] oldest first */
    trend: (id, hours, opts) =>
      request(`/machines/${enc(id)}/trend`, { ...opts, query: { hours } }),
    /** hours: 12 | 24 | 168 | 720 -> { kwh, runKwh, runSeconds, avgLoadFactor, avgPf } for one machine */
    summary: (id, hours, opts) =>
      request(`/machines/${enc(id)}/summary`, { ...opts, query: { hours } }),
    /** patch: { name, type, ratedKw, onThresholdKw } -> the updated machine (the owner names their machines) */
    update: (id, patch) =>
      request(`/machines/${enc(id)}`, { method: "PUT", body: patch }),
  },

  alerts: {
    list: (plant, opts) => request("/alerts", { ...opts, query: { plant } }),
  },

  thresholds: {
    list: () => request("/thresholds"),
    save: (t) =>
      t.id
        ? request(`/thresholds/${enc(t.id)}`, { method: "PUT", body: t })
        : request("/thresholds", { method: "POST", body: t }),
    remove: (id) => request(`/thresholds/${enc(id)}`, { method: "DELETE" }),
  },

  phones: {
    list: () => request("/phones"),
    save: (p) =>
      p.id
        ? request(`/phones/${enc(p.id)}`, { method: "PUT", body: p })
        : request("/phones", { method: "POST", body: p }),
    remove: (id) => request(`/phones/${enc(id)}`, { method: "DELETE" }),
  },

  /** -> { alertsEnabled, autoReports, reportFrequency } ; PUT saves and returns the same shape */
  notifications: {
    get: () => request("/settings/notifications"),
    save: (n) => request("/settings/notifications", { method: "PUT", body: n }),
  },
};
