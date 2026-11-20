export const RANGE_DAYS = { day: 1, week: 7, month: 30 };

const hash = (s) => {
  let h = 2166136261;
  for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return (h >>> 0) / 4294967296;
};

export function usageTotals(defs, days, endDayKey) {
  let consumed = 0;
  for (const d of defs) {
    for (let i = 1; i <= days; i += 1) {
      const runHours = 8 + hash(`${d.id}:${endDayKey}:${i}`) * 4;
      consumed += d.baseKw * runHours;
    }
  }
  return { consumedKwh: consumed, actualKwh: consumed * 0.94 };
}
