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
      // ignore
    }
  },
  clear() {
    memory = null;
    try {
      localStorage.removeItem(KEY);
    } catch {
      // ignore
    }
  },
};
