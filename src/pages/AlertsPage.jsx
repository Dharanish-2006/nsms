import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useData } from "../context/DataContext";
import { istWhen } from "../lib/format";
import { fmtParam, PARAMS } from "../lib/params";

const KIND_LABEL = { critical: "Critical", warning: "Warning", recovered: "Recovered" };

// Where the limit bar starts and ends, per parameter.
const SCALE = { powerFactor: [0.5, 1] };

const kindOf = (a) => (a.status === "recovered" ? "recovered" : a.severity);

/** The reading (dot) against its limit (tick): the shaded part is the bad side. */
function LimitBar({ alert, kind }) {
  const [lo, hi] = SCALE[alert.param] ?? [
    0,
    Math.max(alert.reading, alert.limit, 1) * 1.25,
  ];
  const pos = (v) => `${Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100))}%`;
  const label = `Reading ${fmtParam(alert.param, alert.reading)}, limit ${fmtParam(alert.param, alert.limit)}`;
  return (
    <span
      className={`limit-bar ${kind}`}
      style={{ "--limit": pos(alert.limit), "--reading": pos(alert.reading) }}
      role="img"
      aria-label={label}
    >
      <i />
    </span>
  );
}

function AlertDetail({ alert, kind }) {
  const { label, dir } = PARAMS[alert.param];
  const limit = fmtParam(alert.param, alert.limit);
  const summary =
    kind === "recovered"
      ? `${label} is back within its limit. It was ${dir} ${limit} from ${istWhen(alert.since)} until ${istWhen(alert.recoveredAt ?? alert.since)}.`
      : `${label} is ${fmtParam(alert.param, alert.reading)}, ${dir} the ${alert.severity} limit of ${limit}. It has been outside its limit since ${istWhen(alert.since)}.`;
  return (
    <section className="panel alert-detail" aria-label="Alert details">
      <p>{summary}</p>
      <Link className="ghost-button" to={`/machines/${alert.machineId}`}>
        Open {alert.machineName}
      </Link>
    </section>
  );
}

export default function AlertsPage() {
  const { alerts, machines } = useData();
  const [machineF, setMachineF] = useState("all");
  const [sevF, setSevF] = useState("all");
  const [statusF, setStatusF] = useState("active");
  // undefined = first alert is open, null = all closed, string = that alert's key
  const [openKey, setOpenKey] = useState(undefined);

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
  const open = openKey === undefined ? filtered[0]?.key : openKey;
  const activeCount = alerts.filter((a) => a.status === "active").length;
  const nothingActive = statusF === "active" && sevF === "all" && machineF === "all";

  return (
    <div className="content-page standard-page">
      <div className="page-heading">
        <h1>Alerts</h1>
        <span className="alert-summary">
          {activeCount === 0 ? "No active alerts" : `${activeCount} active`}
        </span>
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
            <strong>
              {nothingActive ? "No active alerts." : "No alerts match these filters."}
            </strong>
            <span>
              {nothingActive
                ? "All readings are within their limits."
                : "Try a different machine, severity or status."}
            </span>
          </div>
        )}
        {filtered.map((a) => {
          const kind = kindOf(a);
          const isOpen = open === a.key;
          return (
            <div key={a.key} className="alert-item">
              <button
                type="button"
                className={`alert-row ${kind} ${isOpen ? "picked" : ""}`}
                aria-expanded={isOpen}
                onClick={() => setOpenKey(isOpen ? null : a.key)}
              >
                <span className="alert-symbol" aria-hidden="true">
                  {kind === "recovered" ? "✓" : "△"}
                </span>
                <span className="alert-name">
                  <strong>
                    {a.machineName} · {PARAMS[a.param].label}
                  </strong>
                  <small>
                    {a.plant} ·{" "}
                    {a.status === "recovered"
                      ? `recovered ${istWhen(a.recoveredAt ?? a.since)}`
                      : `since ${istWhen(a.since)}`}
                  </small>
                </span>
                <span className="reading">
                  <small>READING</small>
                  <strong>{fmtParam(a.param, a.reading)}</strong>
                  <span className="limit-text">limit {fmtParam(a.param, a.limit)}</span>
                </span>
                <LimitBar alert={a} kind={kind} />
                <span className={`severity ${kind}`}>{KIND_LABEL[kind]}</span>
              </button>
              {isOpen && <AlertDetail alert={a} kind={kind} />}
            </div>
          );
        })}
      </div>
    </div>
  );
}
