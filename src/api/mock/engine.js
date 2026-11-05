import { sortAlerts } from "../../lib/alerts";
import { evaluate } from "./alertEngine";
import { createInitial, MACHINES, PLANTS, tick } from "./sim";
import { load, save } from "./storage";

// Demo-only: simulates the plant in the browser so the UI can be built and
// shown before the backend exists.

const TH_KEY = "rmm.mock.thresholds";
const PH_KEY = "rmm.mock.phones";

const DEFAULT_THRESHOLDS = [
  { id: "t1", param: "powerFactor", machineId: "all", warning: 0.9, critical: 0.8 },
  { id: "t2", param: "avgCurrent", machineId: "sheller-1", warning: 38, critical: 45 },
  { id: "t3", param: "activePower", machineId: "all", warning: 28, critical: 32 },
  { id: "t4", param: "freshness", machineId: "all", warning: 120, critical: null },
];
const DEFAULT_PHONES = [
  { id: "p1", digits: "9000000001", label: "Primary contact" },
  { id: "p2", digits: "9000000002", label: "Maintenance" },
];

let machines = null;
let lastTick = 0;
let alertMap = new Map();

export const plants = () => [...PLANTS];
export const getThresholds = () => load(TH_KEY, DEFAULT_THRESHOLDS);
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
    machines = MACHINES.map((d) => createInitial(d, now));
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
