import { useMemo, useState } from "react";
import { useData } from "../context/DataContext";
import { istWhen } from "../lib/format";
import { fmtParam, PARAMS } from "../lib/params";

export default function AlertsPage() {
  const { alerts, machines, plant } = useData();
  const [machineF, setMachineF] = useState("all");
  const [sevF, setSevF] = useState("all");
  const [statusF, setStatusF] = useState("active");

  const filtered = useMemo(
    () =>
      alerts.filter(
        (a) =>
          (machineF === "all" || a.machineId === machineF) &&
          (statusF === "all" || a.status === statusF) &&
          (sevF === "all" || (a.status === "active" && a.severity === sevF)),
      ),
    [alerts, machineF, sevF, statusF],
  );

  return (
    <div className="content-page standard-page alerts-page">
      <div className="page-heading">
        <div>
          <h1>Alerts</h1>
          <p>{plant} · readings outside their limits</p>
        </div>
      </div>

      <div className="filters">
        <select
          aria-label="Machine"
          value={machineF}
          onChange={(e) => setMachineF(e.target.value)}
        >
          <option value="all">All machines</option>
          {machines.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Severity"
          value={sevF}
          onChange={(e) => setSevF(e.target.value)}
        >
          <option value="all">All severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
        </select>
        <select
          aria-label="Status"
          value={statusF}
          onChange={(e) => setStatusF(e.target.value)}
        >
          <option value="active">Active</option>
          <option value="recovered">Recovered</option>
          <option value="all">All</option>
        </select>
      </div>

      <div className="alert-list">
        {filtered.length === 0 && (
          <div className="empty-state panel">
            <strong>No alerts match these filters.</strong>
            <span>All readings are within their limits.</span>
          </div>
        )}
        {filtered.map((a) => {
          const recovered = a.status === "recovered";
          const kind = recovered ? "recovered" : a.severity;
          return (
            <article key={a.key} className={`alert-row ${kind}`}>
              <span className="alert-symbol" aria-hidden="true">
                {recovered ? "✓" : "△"}
              </span>
              <div className="alert-name">
                <strong>
                  {a.machineName} Load Factor
                </strong>
                <small>{a.plant}</small>
              </div>
              <div className="reading">
                <small>READING</small>
                <strong>{fmtParam(a.param, a.reading)}</strong>
              </div>
              <time className="alert-time">
                <small>{recovered ? "Recovered" : "Since"}</small>
                <span>{istWhen(recovered ? (a.recoveredAt ?? a.since) : a.since)}</span>
              </time>
            </article>
          );
        })}
      </div>
    </div>
  );
}
