export const PARAMS = {
  powerFactor: {
    label: "Power factor",
    unit: "",
    dir: "below",
    decimals: 2,
    get: (m) => (m.on ? m.pf : null),
  },
  avgCurrent: {
    label: "Average current",
    unit: "A",
    dir: "above",
    decimals: 1,
    get: (m) => (m.on ? m.current : null),
  },
  activePower: {
    label: "Active power",
    unit: "kW",
    dir: "above",
    decimals: 1,
    get: (m) => (m.on ? m.kw : null),
  },
  freshness: {
    label: "Data freshness",
    unit: "s",
    dir: "above",
    decimals: 0,
    get: (m, now) => Math.max(0, Math.round((now - m.updatedAt) / 1000)),
  },
};
export const fmtParam = (p, v) =>
  v === null
    ? "No limit"
    : `${v.toFixed(PARAMS[p].decimals)}${PARAMS[p].unit ? ` ${PARAMS[p].unit}` : ""}`;
