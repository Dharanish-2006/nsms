const RANK = { critical: 0, warning: 1 };

/** Active alerts first (critical, then newest), then recovered (newest first). */
export function sortAlerts(list) {
  return list.slice().sort((a, b) => {
    if (a.status !== b.status) return a.status === "active" ? -1 : 1;
    if (a.status === "active") {
      return RANK[a.severity] - RANK[b.severity] || b.since - a.since;
    }
    return (b.recoveredAt ?? 0) - (a.recoveredAt ?? 0);
  });
}
