// Simulated plant energy totals for the dashboard's "last week / last month"
// views. The mock keeps no multi-day history, so each past day is derived from
// the machine's base load and a repeatable pseudo-random run time. A real
// backend returns metered values instead (see docs/API.md).

export const RANGE_DAYS = { day: 1, week: 7, month: 30 };

const hash = (s) => {
  let h = 2166136261;
  for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return (h >>> 0) / 4294967296;
};

/** Total { consumedKwh, actualKwh } for the machine definitions over `days`. */
export function usageTotals(defs, days, endDayKey) {
  let consumed = 0;
  for (const d of defs) {
    for (let i = 1; i <= days; i += 1) {
      const runHours = 8 + hash(`${d.id}:${endDayKey}:${i}`) * 4; // 8 to 12 h
      consumed += d.baseKw * runHours;
    }
  }
  return { consumedKwh: consumed, actualKwh: consumed * 0.94 };
}
