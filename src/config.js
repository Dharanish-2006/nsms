// Central place for build-time settings. Values come from VITE_* env variables
// (see .env.example). Everything here is public: it ends up in the browser.

const env = import.meta.env;

const flag = (value, fallback = false) =>
  value === undefined || value === "" ? fallback : value === "true";
const num = (value, fallback) => {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? n : fallback;
};

// Written as a plain comparison on purpose: the bundler replaces it with a constant
// at build time and removes the demo data (fake accounts, simulator) from production
// builds. Demo data is opt-in so production can never ship it by accident.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export const config = {
  apiUrl: env.VITE_API_URL || "/api",
  apiCredentials: flag(env.VITE_API_CREDENTIALS, false),
  apiTimeoutMs: num(env.VITE_API_TIMEOUT_MS, 15000),
  pollMs: num(env.VITE_POLL_INTERVAL_MS, 5000),
  /** A machine that has not reported for this long shows as Unknown. */
  staleAfterMs: 120000,
  company: {
    name: env.VITE_COMPANY_NAME || "Your Company Name",
    address: env.VITE_COMPANY_ADDRESS || "Company address, city",
    phone: env.VITE_COMPANY_PHONE || "Company phone number",
    email: env.VITE_COMPANY_EMAIL || "Company email address",
  },
};
