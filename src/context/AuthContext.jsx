import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../api";
import { config } from "../config";

const Ctx = createContext(null);

const mightHaveSession = () => Boolean(tokenStore.get() || config.apiCredentials);
const messageOf = (err) => err?.message || "Something went wrong. Please try again.";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(() => !mightHaveSession());

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));
    return () => setUnauthorizedHandler(() => {});
  }, []);

  useEffect(() => {
    if (!mightHaveSession()) return undefined;
    let cancelled = false;
    api.auth
      .me()
      .then((u) => !cancelled && setUser(u))
      .catch(() => tokenStore.clear())
      .finally(() => !cancelled && setReady(true));
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (username, password) => {
    try {
      setUser(await api.auth.login(username, password));
      return null;
    } catch (err) {
      return messageOf(err);
    }
  }, []);

  const register = useCallback(async (input) => {
    try {
      await api.auth.register(input);
      return null;
    } catch (err) {
      return messageOf(err);
    }
  }, []);

  const sendOtp = useCallback(async (channel, target) => {
    try {
      const res = await api.auth.sendOtp(channel, target);
      return { error: null, demoCode: res?.demoCode };
    } catch (err) {
      return { error: messageOf(err) };
    }
  }, []);

  const verifyOtp = useCallback(async (channel, target, code) => {
    try {
      const res = await api.auth.verifyOtp(channel, target, code);
      return { token: res.token };
    } catch (err) {
      return { error: messageOf(err) };
    }
  }, []);

  const changePassword = useCallback(async (current, next) => {
    try {
      await api.auth.changePassword(current, next);
      return null;
    } catch (err) {
      return messageOf(err);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // ignore
    }
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ ready, user, login, register, sendOtp, verifyOtp, logout, changePassword }),
    [ready, user, login, register, sendOtp, verifyOtp, logout, changePassword],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}
