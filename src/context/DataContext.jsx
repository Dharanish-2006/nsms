import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "../api";
import { config } from "../config";
import { sortAlerts } from "../lib/alerts";

const PLANT_KEY = "rmm.plant";
const MAX_BACKOFF_MS = 60000;

const Ctx = createContext(null);

const readPlant = () => {
  try {
    return localStorage.getItem(PLANT_KEY) ?? "";
  } catch {
    return "";
  }
};
const writePlant = (name) => {
  try {
    localStorage.setItem(PLANT_KEY, name);
  } catch {
    /* ignore */
  }
};

export function DataProvider({ children }) {
  const [plants, setPlants] = useState([]);
  const [plant, setPlantState] = useState(readPlant);
  const [thresholds, setThresholds] = useState([]);
  const [phones, setPhones] = useState([]);
  const [live, setLive] = useState({ machines: [], alerts: [], serverTime: 0 });
  const [staticReady, setStaticReady] = useState(false);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState("");
  const [offline, setOffline] = useState(false); // live refresh failing after a good load
  const [reloadKey, setReloadKey] = useState(0);
  const [refreshKey, setRefreshKey] = useState(0);

  // Slow-changing data: plants, thresholds, phone numbers.
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.plants.list(), api.thresholds.list(), api.phones.list()])
      .then(([p, t, ph]) => {
        if (cancelled) return;
        setPlants(p);
        setThresholds(t);
        setPhones(ph);
        setPlantState((cur) => (p.includes(cur) ? cur : (p[0] ?? "")));
        setStaticReady(true);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // Live readings and alerts. Polls, backs off while the server is failing, and
  // pauses while the tab is hidden.
  useEffect(() => {
    if (!staticReady || !plant) return undefined;
    let cancelled = false;
    let running = false;
    let failures = 0;
    let timer;
    let controller = new AbortController();

    const run = async () => {
      if (running) return;
      if (document.hidden) {
        timer = setTimeout(run, config.pollMs);
        return;
      }
      running = true;
      controller = new AbortController();
      try {
        const opts = { signal: controller.signal };
        const [m, a] = await Promise.all([
          api.machines.list(plant, opts),
          api.alerts.list(plant, opts),
        ]);
        if (cancelled) return;
        failures = 0;
        setLive({ machines: m.machines, alerts: a, serverTime: m.serverTime });
        setOffline(false);
        setStatus("ready");
      } catch (err) {
        if (cancelled || controller.signal.aborted) return;
        failures += 1;
        setOffline(true);
        setError(err.message);
        setStatus((s) => (s === "ready" ? s : "error"));
      } finally {
        running = false;
      }
      if (!cancelled) {
        timer = setTimeout(run, Math.min(config.pollMs * 2 ** failures, MAX_BACKOFF_MS));
      }
    };

    const onVisible = () => {
      if (document.hidden) return;
      clearTimeout(timer);
      run();
    };

    run();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      controller.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [staticReady, plant, reloadKey, refreshKey]);

  const refresh = useCallback(() => setRefreshKey((n) => n + 1), []);
  const reload = useCallback(() => {
    setStatus("loading");
    setError("");
    setStaticReady(false);
    setReloadKey((n) => n + 1);
  }, []);

  const setPlant = useCallback((name) => {
    setPlantState(name);
    writePlant(name);
  }, []);

  // Changes go to the server first; the list is then re-read so the screen shows
  // exactly what was saved. Errors are thrown so the form can show them.
  const saveThreshold = useCallback(
    async (t) => {
      await api.thresholds.save(t);
      setThresholds(await api.thresholds.list());
      refresh();
    },
    [refresh],
  );
  const removeThreshold = useCallback(
    async (id) => {
      await api.thresholds.remove(id);
      setThresholds(await api.thresholds.list());
      refresh();
    },
    [refresh],
  );
  const savePhone = useCallback(async (p) => {
    await api.phones.save(p);
    setPhones(await api.phones.list());
  }, []);
  const removePhone = useCallback(async (id) => {
    await api.phones.remove(id);
    setPhones(await api.phones.list());
  }, []);

  const alerts = useMemo(() => sortAlerts(live.alerts), [live.alerts]);
  const activeAlertCount = useMemo(
    () => alerts.filter((a) => a.status === "active").length,
    [alerts],
  );

  const value = useMemo(
    () => ({
      plants,
      plant,
      setPlant,
      machines: live.machines,
      lastUpdate: live.serverTime,
      alerts,
      activeAlertCount,
      status,
      error,
      offline,
      reload,
      thresholds,
      saveThreshold,
      removeThreshold,
      phones,
      savePhone,
      removePhone,
    }),
    [
      plants,
      plant,
      setPlant,
      live,
      alerts,
      activeAlertCount,
      status,
      error,
      offline,
      reload,
      thresholds,
      saveThreshold,
      removeThreshold,
      phones,
      savePhone,
      removePhone,
    ],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useData() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useData must be used inside DataProvider");
  return c;
}
