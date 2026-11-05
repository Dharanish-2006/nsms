export const PARAMS = {
  powerFactor: {
    label: "Power factor",
    unit: "",
    dir: "below",
    decimals: 2,
    get: (m) => (m.on && m.type !== "sortex" ? m.pf : null),
  },
};
export const fmtParam = (p, v) =>
  v === null
    ? "No limit"
    : `${v.toFixed(PARAMS[p].decimals)}${PARAMS[p].unit ? ` ${PARAMS[p].unit}` : ""}`;
