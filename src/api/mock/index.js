import { ApiError } from "../client";
import { istDayKey } from "../../lib/format";
import { tokenStore } from "../token";
import {
  getPhones,
  getThresholds,
  listAlerts,
  listMachines,
  machineTrend,
  plants,
  reevaluate,
  setPhones,
  setRatedKw,
  setThresholds,
} from "./engine";
import { MACHINES } from "./sim";
import { hash, load, save, uid } from "./storage";
import { RANGE_DAYS, usageTotals } from "./usage";

// Demo backend that lives entirely in the browser. Passwords are only hashed
// with plain SHA-256 and stored in localStorage: this is NOT secure and exists
// only so the UI can be built before the real backend. It is excluded from
// production builds (VITE_USE_MOCK=false).

const USERS_KEY = "rmm.mock.users";
const NOTIFY_KEY = "rmm.mock.notifications";
const DEFAULT_NOTIFY = {
  alertsEnabled: true,
  autoReports: false,
  reportFrequency: "day",
};
const FREQUENCIES = ["day", "week", "month"];
const OTP_TTL_MS = 5 * 60 * 1000;
const OTP_MAX_TRIES = 5;
const otps = new Map(); // `${channel}:${target}` -> { code, expires, tries }
const proofs = new Map(); // token -> `${channel}:${target}`
const otpKey = (channel, target) => `${channel}:${String(target).trim().toLowerCase()}`;
const checkTarget = (channel, target) => {
  if (channel === "email" && !/^\S+@\S+\.\S+$/.test(target))
    fail(422, "Enter a valid email.", "validation");
  if (channel === "phone" && !/^\d{10}$/.test(target))
    fail(422, "Enter a valid 10-digit number.", "validation");
  if (channel !== "email" && channel !== "phone")
    fail(422, "Unknown channel.", "validation");
};
const PARAMS = ["powerFactor"];

let seeding = null;
function ensureSeed() {
  seeding ??= (async () => {
    if (load(USERS_KEY, []).length === 0) {
      save(USERS_KEY, [
        {
          id: uid(),
          username: "admin",
          fullName: "Administrator",
          email: "",
          mobile: "",
          role: "admin",
          status: "active",
          passHash: await hash("admin123"),
        },
      ]);
    }
  })();
  return seeding;
}

const users = () => load(USERS_KEY, []);
const publicUser = ({ passHash: _omit, ...rest }) => rest;
const fail = (status, message, code) => {
  throw new ApiError(message, { status, code });
};

async function currentUser() {
  await ensureSeed();
  const u = users().find((x) => x.id === tokenStore.get() && x.status === "active");
  return u ?? fail(401, "Please sign in again.", "unauthenticated");
}
async function requireAdmin() {
  const u = await currentUser();
  if (u.role !== "admin") fail(403, "Only administrators can do this.", "forbidden");
  return u;
}

function checkThreshold(t) {
  if (!PARAMS.includes(t.param)) fail(422, "Unknown parameter.", "validation");
  if (t.warning === null && t.critical === null)
    fail(422, "Set at least a warning or a critical limit.", "validation");
}

export const mockApi = {
  auth: {
    async login(username, password) {
      await ensureSeed();
      const u = users().find(
        (x) => x.username.toLowerCase() === String(username).trim().toLowerCase(),
      );
      if (!u || u.passHash !== (await hash(password)))
        fail(401, "Wrong username or password.", "invalid_credentials");
      if (u.status === "pending")
        fail(
          403,
          "Your account is waiting for administrator approval.",
          "pending_approval",
        );
      tokenStore.set(u.id);
      return publicUser(u);
    },
    async sendOtp(channel, target) {
      checkTarget(channel, target);
      const code = String(Math.floor(100000 + Math.random() * 900000));
      otps.set(otpKey(channel, target), {
        code,
        expires: Date.now() + OTP_TTL_MS,
        tries: 0,
      });
      // Demo only: there is no SMS/email gateway, so the code is handed to the UI.
      return { demoCode: code };
    },
    async verifyOtp(channel, target, code) {
      checkTarget(channel, target);
      const key = otpKey(channel, target);
      const rec = otps.get(key);
      if (!rec || rec.expires < Date.now())
        fail(400, "That code has expired. Request a new one.", "otp_expired");
      if (rec.tries >= OTP_MAX_TRIES) {
        otps.delete(key);
        fail(429, "Too many attempts. Request a new code.", "otp_locked");
      }
      if (rec.code !== String(code).trim()) {
        rec.tries += 1;
        fail(400, "Incorrect code.", "otp_invalid");
      }
      otps.delete(key);
      const token = uid();
      proofs.set(token, key);
      return { token };
    },
    async register(input) {
      await ensureSeed();
      const needProof = (channel, target, token) => {
        if (proofs.get(token) !== otpKey(channel, target))
          fail(400, `Verify your ${channel} first.`, "not_verified");
        proofs.delete(token);
      };
      needProof("email", input.email, input.emailToken);
      if (input.mobile) needProof("phone", input.mobile, input.phoneToken);
      const list = users();
      if (
        list.some((u) => u.username.toLowerCase() === input.username.trim().toLowerCase())
      )
        fail(409, "That username is already taken.", "username_taken");
      save(USERS_KEY, [
        ...list,
        {
          id: uid(),
          username: input.username.trim(),
          fullName: input.fullName.trim(),
          email: input.email.trim(),
          mobile: input.mobile || "",
          role: input.role === "admin" ? "admin" : "user",
          status: "pending",
          passHash: await hash(input.password),
        },
      ]);
    },
    async me() {
      return publicUser(await currentUser());
    },
    async logout() {
      tokenStore.clear();
    },
    async changePassword(current, next) {
      const me = await currentUser();
      if (me.passHash !== (await hash(current)))
        fail(400, "Current password is incorrect.", "wrong_password");
      const passHash = await hash(next);
      save(
        USERS_KEY,
        users().map((u) => (u.id === me.id ? { ...u, passHash } : u)),
      );
    },
  },

  users: {
    async list(status) {
      await requireAdmin();
      return users()
        .filter((u) => !status || u.status === status)
        .map(publicUser);
    },
    async approve(id) {
      await requireAdmin();
      save(
        USERS_KEY,
        users().map((u) => (u.id === id ? { ...u, status: "active" } : u)),
      );
    },
    async reject(id) {
      await requireAdmin();
      save(
        USERS_KEY,
        users().filter((u) => u.id !== id),
      );
    },
  },

  plants: {
    async list() {
      await currentUser();
      return plants();
    },
  },

  machines: {
    async list(plant) {
      await currentUser();
      return listMachines(plant);
    },
    async usage(plant, range) {
      await currentUser();
      const days = RANGE_DAYS[range];
      if (!days) fail(422, "Unknown range.", "validation");
      const defs = MACHINES.filter((m) => !plant || m.plant === plant);
      return usageTotals(defs, days, istDayKey(Date.now()));
    },
    async trend(id, hours) {
      await currentUser();
      return machineTrend(id, hours) ?? fail(404, "Machine not found.", "not_found");
    },
    async update(id, patch) {
      await currentUser();
      const kw = patch?.ratedKw;
      if (!Number.isFinite(kw) || kw <= 0 || kw > 1000 * 0.7457)
        fail(422, "Enter a motor rating above 0.", "validation");
      return setRatedKw(id, kw) ?? fail(404, "Machine not found.", "not_found");
    },
  },

  alerts: {
    async list(plant) {
      await currentUser();
      return listAlerts(plant);
    },
  },

  thresholds: {
    async list() {
      await currentUser();
      return getThresholds();
    },
    async save(t) {
      await requireAdmin();
      checkThreshold(t);
      const list = getThresholds();
      const row = { ...t, id: t.id ?? uid() };
      setThresholds(t.id ? list.map((x) => (x.id === t.id ? row : x)) : [...list, row]);
      reevaluate();
      return row;
    },
    async remove(id) {
      await requireAdmin();
      setThresholds(getThresholds().filter((x) => x.id !== id));
      reevaluate();
    },
  },

  phones: {
    async list() {
      await currentUser();
      return getPhones();
    },
    async save(p) {
      await requireAdmin();
      if (!/^\d{10}$/.test(p.digits))
        fail(422, "Enter a valid 10-digit number.", "validation");
      const list = getPhones();
      if (list.some((x) => x.digits === p.digits && x.id !== p.id))
        fail(409, "That number is already added.", "duplicate");
      const row = { ...p, id: p.id ?? uid() };
      setPhones(p.id ? list.map((x) => (x.id === p.id ? row : x)) : [...list, row]);
      return row;
    },
    async remove(id) {
      await requireAdmin();
      setPhones(getPhones().filter((x) => x.id !== id));
    },
  },

  notifications: {
    async get() {
      await currentUser();
      return { ...DEFAULT_NOTIFY, ...load(NOTIFY_KEY, {}) };
    },
    async save(n) {
      await requireAdmin();
      if (!FREQUENCIES.includes(n.reportFrequency))
        fail(422, "Choose day, week or month.", "validation");
      const row = {
        alertsEnabled: Boolean(n.alertsEnabled),
        autoReports: Boolean(n.autoReports),
        reportFrequency: n.reportFrequency,
      };
      save(NOTIFY_KEY, row);
      return row;
    },
  },
};
