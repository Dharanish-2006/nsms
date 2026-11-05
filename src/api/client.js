import { config } from "../config";
import { tokenStore } from "./token";

export class ApiError extends Error {
  constructor(message, { status = 0, code = "error", details } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let onUnauthorized = () => {};
/** The auth layer registers a callback that signs the user out on a 401. */
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

const origin = () => globalThis.location?.origin ?? "http://localhost";

function buildUrl(path, query) {
  const url = new URL(config.apiUrl.replace(/\/$/, "") + path, origin());
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  }
  return url;
}

function withTimeout(signal) {
  const timeout = AbortSignal.timeout(config.apiTimeoutMs);
  return signal && AbortSignal.any
    ? AbortSignal.any([signal, timeout])
    : (signal ?? timeout);
}

async function readBody(res) {
  if (res.status === 204) return null;
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("json")) return null;
  try {
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * JSON request to the backend. Throws ApiError with a message that is safe to
 * show to the user. `auth: false` skips the sign-in header and the
 * sign-out-on-401 behaviour (used by login and register).
 */
export async function request(
  path,
  { method = "GET", body, query, signal, auth = true } = {},
) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: config.apiCredentials ? "include" : "same-origin",
      signal: withTimeout(signal),
    });
  } catch (err) {
    if (signal?.aborted) throw err; // caller cancelled on purpose
    const timedOut = err?.name === "TimeoutError";
    throw new ApiError(
      timedOut
        ? "The server took too long to respond."
        : "Cannot reach the server. Check your connection.",
      { code: timedOut ? "timeout" : "network" },
    );
  }

  const data = await readBody(res);
  if (res.ok) return data;

  if (res.status === 401 && auth) {
    tokenStore.clear();
    onUnauthorized();
  }
  throw new ApiError(
    data?.message ??
      (res.status >= 500 ? "Something went wrong on the server." : "Request failed."),
    { status: res.status, code: data?.code ?? "http_error", details: data?.details },
  );
}
