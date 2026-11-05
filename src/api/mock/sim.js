import { istDayKey, istHour } from "../../lib/format";
export const PLANTS = ["Plant 1"];
export const MACHINES = [
  {
    id: "sheller-1",
    name: "Sheller 1",
    plant: "Plant 1",
    type: "sheller",
    ratedKw: 36,
    baseKw: 26,
    basePf: 0.93,
    baseTotalKwh: 41250.4,
    baseRuntimeHrs: 3120,
    schedule: () => true,
  },
  {
    id: "whitener-1",
    name: "Whitener 1",
    plant: "Plant 1",
    type: "whitener",
    ratedKw: 25,
    baseKw: 15.2,
    basePf: 0.94,
    baseTotalKwh: 28910.2,
    baseRuntimeHrs: 2740,
    schedule: () => true,
  },
  {
    id: "whitener-2",
    name: "Whitener 2",
    plant: "Plant 1",
    type: "whitener",
    ratedKw: 22,
    baseKw: 15,
    basePf: 0.79,
    baseTotalKwh: 25104.9,
    baseRuntimeHrs: 2615,
    schedule: () => true,
  },
  {
    id: "polisher",
    name: "Polisher",
    plant: "Plant 1",
    type: "polisher",
    ratedKw: 15,
    baseKw: 9,
    basePf: 0.9,
    baseTotalKwh: 9120.7,
    baseRuntimeHrs: 1010,
    schedule: () => false,
  },
  {
    id: "sortex-1",
    name: "Colour Sortex 1",
    plant: "Plant 1",
    type: "sortex",
    ratedKw: 22,
    baseKw: 16.07,
    basePf: 0.861,
    baseTotalKwh: 18432.6,
    baseRuntimeHrs: 1284.6,
    schedule: (h) => !(h >= 13 && h < 17),
  },
];
const SQRT3_V = Math.sqrt(3) * 415;
const rnd = () => Math.random() - 0.5;
function electrics(kw, pf) {
  const kva = kw / pf;
  const kvar = Math.sqrt(Math.max(kva * kva - kw * kw, 0));
  const current = (kva * 1000) / SQRT3_V;
  return { kva, kvar, current };
}
export function createInitial(def, now) {
  const hour = istHour(now);
  const dayKey = istDayKey(now);
  const frac = (now % 3600000) / 3600000;
  const hourlyKwh = [];
  const hourOn = [];
  let todaySec = 0;
  for (let h = 0; h < 24; h++) {
    if (h > hour) {
      hourlyKwh.push(0);
      hourOn.push(2);
    } else if (def.schedule(h)) {
      const portion = h === hour ? frac : 1;
      hourlyKwh.push(def.baseKw * (0.92 + Math.random() * 0.16) * portion);
      hourOn.push(1);
      todaySec += 3600 * portion;
    } else {
      hourlyKwh.push(0);
      hourOn.push(0);
    }
  }
  const on = def.schedule(hour);
  let runSec = 0;
  let runStart = null;
  let lastStop = null;
  if (on) {
    let k = hour;
    while (k > 0 && def.schedule(k - 1)) k--;
    runSec = (hour - k) * 3600 + frac * 3600;
    runStart = now - runSec * 1000;
    lastStop = k > 0 ? runStart - 12 * 60000 : null;
  } else if (def.schedule(Math.max(hour - 1, 0))) {
    lastStop = now - 1000 * 60 * 20;
  }
  const trend = [];
  for (let i = 72; i >= 0; i--) {
    const t = now - i * 5 * 60000;
    const th = istHour(t);
    if (!def.schedule(th)) continue;
    const kw = def.baseKw + rnd() * 2;
    const pf = Math.min(0.99, def.basePf + rnd() * 0.03);
    trend.push({ t, pf, kw, current: electrics(kw, pf).current });
  }
  const kw = on ? def.baseKw : 0;
  const pf = on ? def.basePf : 0;
  const e = on ? electrics(kw, pf) : { kva: 0, kvar: 0, current: 0 };
  return {
    def,
    on,
    updatedAt: now,
    kw,
    pf,
    ...e,
    loadFactor: on ? (kw / def.ratedKw) * 100 : 0,
    totalKwh: def.baseTotalKwh,
    totalKvarh: def.baseTotalKwh * 0.59,
    totalKvah: def.baseTotalKwh * 1.16,
    runKwh: on ? (def.baseKw * runSec) / 3600 : 0,
    runStart,
    lastStop,
    runSec,
    todaySec,
    totalRuntimeSec: def.baseRuntimeHrs * 3600 + todaySec,
    pfRunSum: pf * 100,
    pfRunN: on ? 100 : 0,
    dayKey,
    hourlyKwh,
    hourOn,
    trend,
  };
}
/** Advance one machine by `dt` seconds. Pure: returns a new state. */
export function tick(m, now, dt) {
  const hour = istHour(now);
  const dayKey = istDayKey(now);
  let hourlyKwh = m.hourlyKwh.slice();
  let hourOn = m.hourOn.slice();
  let todaySec = m.todaySec;
  if (dayKey !== m.dayKey) {
    hourlyKwh = new Array(24).fill(0);
    hourOn = new Array(24).fill(2);
    todaySec = 0;
  }
  for (let h = 0; h < hour; h++) if (hourOn[h] === 2) hourOn[h] = 0;
  const on = m.def.schedule(hour);
  const next = {
    ...m,
    on,
    updatedAt: now,
    dayKey,
    hourlyKwh,
    hourOn,
  };
  if (!on) {
    hourOn[hour] = hourOn[hour] === 1 ? 1 : 0;
    if (m.on) {
      next.lastStop = now;
      next.runStart = null;
      next.runSec = 0;
      next.runKwh = 0;
      next.pfRunSum = 0;
      next.pfRunN = 0;
    }
    return { ...next, kw: 0, pf: 0, kva: 0, kvar: 0, current: 0, loadFactor: 0 };
  }
  if (!m.on) {
    next.runStart = now;
    next.runSec = 0;
    next.runKwh = 0;
    next.pfRunSum = 0;
    next.pfRunN = 0;
  }
  hourOn[hour] = 1;
  const kw = Math.max(
    m.def.baseKw * 0.85,
    Math.min(
      m.def.baseKw * 1.15,
      (m.on ? m.kw : m.def.baseKw) +
        (m.def.baseKw - (m.on ? m.kw : m.def.baseKw)) * 0.12 +
        rnd() * 0.5,
    ),
  );
  const pf = Math.min(
    0.99,
    (m.on ? m.pf : m.def.basePf) +
      (m.def.basePf - (m.on ? m.pf : m.def.basePf)) * 0.15 +
      rnd() * 0.008,
  );
  const e = electrics(kw, pf);
  const kwh = (kw * dt) / 3600;
  hourlyKwh[hour] += kwh;
  todaySec += dt;
  next.todaySec = todaySec;
  next.kw = kw;
  next.pf = pf;
  next.kva = e.kva;
  next.kvar = e.kvar;
  next.current = e.current;
  next.loadFactor = (kw / m.def.ratedKw) * 100;
  next.totalKwh = m.totalKwh + kwh;
  next.totalKvarh = m.totalKvarh + (e.kvar * dt) / 3600;
  next.totalKvah = m.totalKvah + (e.kva * dt) / 3600;
  next.runKwh = next.runKwh + kwh;
  next.runSec = next.runSec + dt;
  next.totalRuntimeSec = m.totalRuntimeSec + dt;
  next.pfRunSum = next.pfRunSum + pf;
  next.pfRunN = next.pfRunN + 1;
  const last = m.trend[m.trend.length - 1];
  if (!last || now - last.t > 60000) {
    const cutoff = now - 6 * 3600000;
    next.trend = [
      ...m.trend.filter((p) => p.t >= cutoff),
      { t: now, pf, kw, current: e.current },
    ];
  }
  return next;
}
