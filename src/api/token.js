// Remembers the sign-in token between page loads. When the backend uses an
// httpOnly cookie instead (VITE_API_CREDENTIALS=true) no token is stored here.
const KEY = "rmm.token";
let memory = null;

export const tokenStore = {
  get() {
    try {
      return localStorage.getItem(KEY) ?? memory;
    } catch {
      return memory;
    }
  },
  set(token) {
    memory = token;
    try {
      localStorage.setItem(KEY, token);
    } catch {
      /* storage blocked: the in-memory copy still works for this tab */
    }
  },
  clear() {
    memory = null;
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  },
};
