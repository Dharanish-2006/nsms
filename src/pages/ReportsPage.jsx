import { Link } from "react-router-dom";
import { StatusBadge } from "../components/Icon";
import { useData } from "../context/DataContext";
import {
  downloadCsv,
  fmt,
  fmtDuration,
  istDate,
  istDayKey,
  istStamp,
} from "../lib/format";
import { statusOf } from "../lib/status";
export default function ReportsPage() {
  const { machines, alerts, plant, lastUpdate } = useData();
  const rows = machines.map((m) => {
    const kwh = m.hourlyKwh.reduce((a, b) => a + b, 0);
    return {
      m,
      kwh,
      avgPf: m.avgPfRun,
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
      ...rows.map(({ m, kwh, avgPf, active }) => [
        m.name,
        statusOf(m, lastUpdate).toUpperCase(),
        fmtDuration(m.todaySec),
        kwh.toFixed(1),
        avgPf ? avgPf.toFixed(3) : "N/A",
        m.on ? Math.round(m.loadFactor) : 0,
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
            {rows.map(({ m, kwh, avgPf, active }) => (
              <div className="table-row" key={m.id}>
                <span>
                  <Link to={`/machines/${m.id}`}>{m.name}</Link>
                </span>
                <span>
                  <StatusBadge status={statusOf(m, lastUpdate)} />
                </span>
                <span>{m.todaySec > 0 ? fmtDuration(m.todaySec) : "--"}</span>
                <span>{kwh > 0 ? `${fmt(kwh, 1)} kWh` : "--"}</span>
                <span>{avgPf ? fmt(avgPf, 3) : "N/A"}</span>
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
  );
}
