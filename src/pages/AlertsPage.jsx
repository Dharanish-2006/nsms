import { useMemo, useState } from "react";
import { useData } from "../context/DataContext";
import { istWhen } from "../lib/format";
import { fmtParam, PARAMS } from "../lib/params";

export default function AlertsPage() {
  const { alerts, machines, plant } = useData();
  const [machineF, setMachineF] = useState("all");
  const [sevF, setSevF] = useState("all");
  const [statusF, setStatusF] = useState("active");
  const [selectedKey, setSelectedKey] = useState(null);
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
  const selected = filtered.find((a) => a.key === selectedKey) ?? filtered[0];

  return (
    <div className="content-page standard-page">
      <div className="page-heading">
        <h1>Alerts</h1>
        <span className="segmented">
          <button type="button" className="selected" disabled>
            Alerts
          </button>
        </span>
      </div>

      <div className="filters">
        <select aria-label="Plant" disabled>
          <option>{plant}</option>
        </select>
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
          const kind = a.status === "recovered" ? "recovered" : a.severity;
          return (
            <button
              key={a.key}
              className={`alert-row ${kind} ${selected?.key === a.key ? "picked" : ""}`}
              onClick={() => setSelectedKey(a.key)}
            >
            <span className="alert-symbol">{kind === "recovered" ? "✓" : "△"}</span>
              
              <span className="alert-name">
                <strong>
                  {a.machineName} · {PARAMS[a.param].label}
                </strong>
              </span>

              <span className="alert-row">  
                {a.plant} ·{" "}
                {a.status === "recovered"
                  ? `recovered ${istWhen(a.recoveredAt ?? a.since)}`
                  : istWhen(a.since)}
              </span>
              <span className="reading">
                <small>READING</small>
                <strong>{fmtParam(a.param, a.reading)}</strong>
              </span>

            </button>
          );
        })}
      </div>
    </div>
  );
}
