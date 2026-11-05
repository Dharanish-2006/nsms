import { PARAMS } from "../../lib/params";
function breach(value, limit, dir) {
  if (limit === null) return false;
  return dir === "below" ? value < limit : value > limit;
}
export function evaluate(machines, thresholds, prev, now) {
  const next = new Map();
  const live = new Set();
  const thresholdIds = new Set(thresholds.map((t) => t.id));
  for (const t of thresholds) {
    const meta = PARAMS[t.param];
    for (const m of machines) {
      if (t.machineId !== "all" && t.machineId !== m.id) continue;
      const value = meta.get(m, now);
      if (value === null) continue;
      let severity = null;
      let limit = 0;
      if (breach(value, t.critical, meta.dir)) {
        severity = "critical";
        limit = t.critical;
      } else if (breach(value, t.warning, meta.dir)) {
        severity = "warning";
        limit = t.warning;
      }
      if (!severity) continue;
      const key = `${t.id}:${m.id}`;
      live.add(key);
      const old = prev.get(key);
      next.set(key, {
        key,
        thresholdId: t.id,
        machineId: m.id,
        machineName: m.name,
        plant: m.plant,
        param: t.param,
        severity,
        status: "active",
        reading: value,
        limit,
        since: old && old.status === "active" ? old.since : now,
      });
    }
  }
  for (const [key, old] of prev) {
    if (live.has(key) || !thresholdIds.has(old.thresholdId)) continue;
    next.set(
      key,
      old.status === "active" ? { ...old, status: "recovered", recoveredAt: now } : old,
    );
  }
  // keep only the 20 most recent recoveries
  const recovered = [...next.values()]
    .filter((a) => a.status === "recovered")
    .sort((a, b) => (b.recoveredAt ?? 0) - (a.recoveredAt ?? 0));
  for (const a of recovered.slice(20)) next.delete(a.key);
  return next;
}
