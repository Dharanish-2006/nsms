import { sortAlerts } from "../../lib/alerts";
import { evaluate } from "./alertEngine";
import { createInitial, MACHINES, PLANTS, tick } from "./sim";
import { load, save } from "./storage";

// Demo-only: simulates the plant in the browser so the UI can be built and
// shown before the backend exists.

const TH_KEY = "rmm.mock.thresholds";
const PH_KEY = "rmm.mock.phones";
const DETAILS_KEY = "rmm.mock.details"; // machine id -> { name, type } edited by the owner
const RATING_KEY = "rmm.mock.ratings"; // machine id -> ratedKw edited by an admin

const DEFAULT_THRESHOLDS = [
  { id: "t1", param: "powerFactor", machineId: "all", warning: 0.9, critical: 0.8 },
];
const DEFAULT_PHONES = [
  { id: "p1", digits: "9000000001", label: "Primary contact" },
  { id: "p2", digits: "9000000002", label: "Maintenance" },
];

let machines = null;
let lastTick = 0;
let alertMap = new Map();

export const plants = () => [...PLANTS];
// Only power factor is supported; drop limits saved earlier for removed parameters.
export const getThresholds = () =>
  load(TH_KEY, DEFAULT_THRESHOLDS).filter((t) => t.param === "powerFactor");
export const setThresholds = (list) => save(TH_KEY, list);
export const getPhones = () => load(PH_KEY, DEFAULT_PHONES);
export const setPhones = (list) => save(PH_KEY, list);

/** What the real API returns for one machine: plain JSON, no internals. */
function snapshot(m) {
  return {
    id: m.def.id,
    name: m.def.name,
    plant: m.def.plant,
    type: m.def.type,
    ratedKw: m.def.ratedKw,
    on: m.on,
    updatedAt: m.updatedAt,
    kw: m.kw,
    pf: m.pf,
    kvar: m.kvar,
    kva: m.kva,
    current: m.current,
    loadFactor: m.loadFactor,
    totalKwh: m.totalKwh,
    totalKvarh: m.totalKvarh,
    totalKvah: m.totalKvah,
    runKwh: m.runKwh,
    runStart: m.runStart,
    lastStop: m.lastStop,
    runSec: m.runSec,
    todaySec: m.todaySec,
    totalRuntimeSec: m.totalRuntimeSec,
    avgPfRun: m.pfRunN ? m.pfRunSum / m.pfRunN : null,
    hourlyKwh: m.hourlyKwh,
    hourOn: m.hourOn,
  };
}

export function reevaluate(now = Date.now()) {
  if (!machines) return;
  alertMap = evaluate(machines.map(snapshot), getThresholds(), alertMap, now);
}

/** Move the simulation forward to "now". Cheap to call repeatedly. */
export function advance(now = Date.now()) {
  if (!machines) {
    const ratings = load(RATING_KEY, {});
    const details = load(DETAILS_KEY, {});
    machines = MACHINES.map((d) =>
      createInitial(
        { ...d, ...details[d.id], ...(ratings[d.id] ? { ratedKw: ratings[d.id] } : {}) },
        now,
      ),
    );
    lastTick = now;
  }
  const dt = Math.min((now - lastTick) / 1000, 10);
  if (dt >= 1) {
    machines = machines.map((m) => tick(m, now, dt));
    lastTick = now;
  }
  reevaluate(now);
}

export function listMachines(plant) {
  advance();
  return {
    serverTime: Date.now(),
    machines: machines.filter((m) => !plant || m.def.plant === plant).map(snapshot),
  };
}

/** Change a machine's rated power. Returns the machine, or null if unknown. */
export function setRatedKw(id, ratedKw) {
  advance();
  const i = machines.findIndex((x) => x.def.id === id);
  if (i < 0) return null;
  save(RATING_KEY, { ...load(RATING_KEY, {}), [id]: ratedKw });
  const m = machines[i];
  machines[i] = {
    ...m,
    def: { ...m.def, ratedKw },
    loadFactor: m.on ? (m.kw / ratedKw) * 100 : 0,
  };
  return snapshot(machines[i]);
}

/** Rename a machine or change its type. Returns the machine, or null if unknown. */
export function setMachineDetails(id, { name, type }) {
  advance();
  const i = machines.findIndex((x) => x.def.id === id);
  if (i < 0) return null;
  const patch = {
    ...(name === undefined ? {} : { name }),
    ...(type === undefined ? {} : { type }),
  };
  save(DETAILS_KEY, {
    ...load(DETAILS_KEY, {}),
    [id]: { ...load(DETAILS_KEY, {})[id], ...patch },
  });
  machines[i] = { ...machines[i], def: { ...machines[i].def, ...patch } };
  return snapshot(machines[i]);
}

export function machineTrend(id, hours) {
  advance();
  const m = machines.find((x) => x.def.id === id);
  if (!m) return null;
  const cutoff = Date.now() - hours * 3600000;
  return m.trend.filter((p) => p.t >= cutoff);
}

export function listAlerts(plant) {
  advance();
  return sortAlerts([...alertMap.values()].filter((a) => !plant || a.plant === plant));
}
