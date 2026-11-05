export function load(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}
export function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable (private mode etc.) */
  }
}
export const uid = () =>
  Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
export async function hash(text) {
  if (globalThis.crypto?.subtle) {
    const buf = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(`rice-mill:${text}`),
    );
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  return btoa(`rice-mill:${text}`);
}
