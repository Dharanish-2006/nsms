import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { StatusBadge } from "../components/Icon";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import {
  downloadCsv,
  fmt,
  fmtDuration,
  istDate,
  istDayKey,
  istStamp,
} from "../lib/format";
import { hasPowerQuality } from "../lib/machine";
import { statusOf } from "../lib/status";
const FREQUENCIES = [
  { value: "day", label: "Every day" },
  { value: "week", label: "Every week" },
  { value: "month", label: "Every month" },
];
function AutoReportPanel() {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const [prefs, setPrefs] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    api.notifications
      .get()
      .then((n) => !cancelled && setPrefs(n))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, []);
  const update = async (patch) => {
    const before = prefs;
    const next = { ...prefs, ...patch };
    setPrefs(next); // optimistic; rolled back if the server refuses
    try {
      setPrefs(await api.notifications.save(next));
      setError("");
    } catch (err) {
      setPrefs(before);
      setError(err.message);
    }
  };
  return (
    <aside className="panel auto-report">
      <h2>Automatic report</h2>
      <p>Send this report on its own, without anyone pressing a button.</p>
      {prefs && (
        <>
          <label className="toggle-row">
            <span>Send automatically</span>
            <input
              type="checkbox"
              checked={prefs.autoReports}
              disabled={!admin}
              onChange={() => update({ autoReports: !prefs.autoReports })}
            />
            <i aria-hidden="true" />
          </label>
          <label className="auto-report-when">
            <span>Send</span>
            <select
              value={prefs.reportFrequency}
              disabled={!admin || !prefs.autoReports}
              onChange={(e) => update({ reportFrequency: e.target.value })}
            >
              {FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
          {!admin && <small className="admin-only">▣ Admins only</small>}
        </>
      )}
      {error && (
        <small className="form-error" role="alert">
          {error}
        </small>
      )}
    </aside>
  );
}
export default function ReportsPage() {
  const { machines, alerts, plant, lastUpdate } = useData();
  const rows = machines.map((m) => {
    const kwh = m.hourlyKwh.reduce((a, b) => a + b, 0);
    return {
      m,
      kwh,
      avgPf: hasPowerQuality(m) ? m.avgPfRun : null,
      pq: hasPowerQuality(m),
      active: alerts.filter((a) => a.machineId === m.id && a.status === "active").length,
    };
  });
  const total = rows.reduce((s, r) => s + r.kwh, 0);
  const download = () =>
    downloadCsv(`daily-report-${istDayKey(lastUpdate)}.csv`, [
      ["Plant", plant],
      ["Generated (IST)", istStamp(lastUpdate)],
      [],
      [
        "Machine",
        "Status",
        "Runtime today",
        "Energy today (kWh)",
        "Avg power factor (run)",
        "Load factor (%)",
        "Active alerts",
      ],
      ...rows.map(({ m, kwh, avgPf, pq, active }) => [
        m.name,
        statusOf(m, lastUpdate).toUpperCase(),
        fmtDuration(m.todaySec),
        kwh.toFixed(1),
        pq ? (avgPf ? avgPf.toFixed(3) : "N/A") : "--",
        pq ? (m.on ? Math.round(m.loadFactor) : 0) : "--",
        active,
      ]),
      ["Total", "", "", total.toFixed(1), "", "", ""],
    ]);
  return (
    <div className="content-page standard-page">
      <div className="page-heading">
        <div>
          <h1>Reports</h1>
          <p>
            Daily summary for {plant} · {istDate(lastUpdate)}
          </p>
        </div>
        <button className="primary-button" onClick={download}>
          ↓ &nbsp; Download CSV
        </button>
      </div>

      <div className="reports-layout">
        <AutoReportPanel />
        <section className="panel report-panel">
          <div className="threshold-scroll">
            <div className="report-table">
              <div className="table-head">
                <span>MACHINE</span>
                <span>STATUS</span>
                <span>RUNTIME TODAY</span>
                <span>ENERGY TODAY</span>
                <span>AVG PF (RUN)</span>
                <span>ALERTS</span>
              </div>
              {rows.map(({ m, kwh, avgPf, pq, active }) => (
                <div className="table-row" key={m.id}>
                  <span>
                    <Link to={`/machines/${m.id}`}>{m.name}</Link>
                  </span>
                  <span>
                    <StatusBadge status={statusOf(m, lastUpdate)} />
                  </span>
                  <span>{m.todaySec > 0 ? fmtDuration(m.todaySec) : "--"}</span>
                  <span>{kwh > 0 ? `${fmt(kwh, 1)} kWh` : "--"}</span>
                  <span>{pq ? (avgPf ? fmt(avgPf, 3) : "N/A") : "--"}</span>
                  <span>{active ? `${active} active` : "None"}</span>
                </div>
              ))}
              <div className="table-row total-row">
                <span>Plant total</span>
                <span />
                <span />
                <span>{fmt(total, 1)} kWh</span>
                <span />
                <span />
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
