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

  users: {
    list: (status) => request("/users", { query: { status } }),
    approve: (id) => request(`/users/${enc(id)}/approve`, { method: "POST" }),
    reject: (id) => request(`/users/${enc(id)}`, { method: "DELETE" }),
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
    /** Admin only. patch: { ratedKw } -> the updated machine */
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

  /** -> { alertsEnabled, autoReports, reportFrequency } ; PUT (admin) saves and returns the same shape */
  notifications: {
    get: () => request("/settings/notifications"),
    save: (n) => request("/settings/notifications", { method: "PUT", body: n }),
  },
};
