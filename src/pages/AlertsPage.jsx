import { images } from "../assets";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { TrendChart } from "../components/Charts";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import { istHm } from "../lib/format";
import { fmtParam, PARAMS } from "../lib/params";
const PICK = {
  powerFactor: (p) => p.pf,
  avgCurrent: (p) => p.current,
  activePower: (p) => p.kw,
  freshness: () => 0,
};
function markerPct(a, t) {
  if (!t) return 50;
  const dir = PARAMS[a.param].dir;
  const w = t.warning ?? t.critical ?? a.limit;
  const c = t.critical ?? t.warning ?? a.limit;
  const d = Math.max(Math.abs(w - c), Math.abs(w) * 0.1, 0.01);
  const lo = Math.min(w, c) - d;
  const hi = Math.max(w, c) + d;
  let p = (a.reading - lo) / (hi - lo);
  if (dir === "above") p = 1 - p;
  return Math.max(0, Math.min(1, p)) * 90;
}
const parseLimit = (s) => (s.trim() === "" ? null : Number(s));
function ThresholdPanel() {
  const { thresholds, saveThreshold, removeThreshold, machines } = useData();
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const [editId, setEditId] = useState(null);
  const blank = {
    param: "powerFactor",
    machineId: "all",
    warning: "",
    critical: "",
  };
  const [form, setForm] = useState(blank);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const startEdit = (t) => {
    setEditId(t.id);
    setError("");
    setForm({
      param: t.param,
      machineId: t.machineId,
      warning: t.warning === null ? "" : String(t.warning),
      critical: t.critical === null ? "" : String(t.critical),
    });
  };
  const submit = async () => {
    const warning = parseLimit(form.warning);
    const critical = parseLimit(form.critical);
    if (
      (warning !== null && !Number.isFinite(warning)) ||
      (critical !== null && !Number.isFinite(critical))
    )
      return setError("Limits must be numbers.");
    if (warning === null && critical === null)
      return setError("Set at least a warning or a critical limit.");
    if (warning !== null && critical !== null) {
      const dir = PARAMS[form.param].dir;
      if (dir === "below" && critical > warning)
        return setError("For this parameter, critical must be lower than warning.");
      if (dir === "above" && critical < warning)
        return setError("For this parameter, critical must be higher than warning.");
    }
    setBusy(true);
    try {
      await saveThreshold({
        id: editId ?? undefined,
        param: form.param,
        machineId: form.machineId,
        warning,
        critical,
      });
      setEditId(null);
      setForm(blank);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id) => {
    if (!window.confirm("Delete this threshold?")) return;
    try {
      await removeThreshold(id);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  };
  const name = (id) =>
    id === "all" ? "All machines" : (machines.find((m) => m.id === id)?.name ?? id);
  return (
    <section className="threshold-panel panel">
      <div className="threshold-title">
        <div>
          <h3>Threshold settings</h3>
          <p>
            {admin
              ? "Admins can add and edit limits. Alerts use saved values only."
              : "Only admins can change limits."}
          </p>
        </div>
      </div>
      <div className="threshold-scroll">
        <div className="threshold-table editable">
          <div className="table-head">
            <span>PARAMETER</span>
            <span>APPLIES TO</span>
            <span>WARNING</span>
            <span>CRITICAL</span>
            <span>STATE</span>
            <span />
          </div>
          {thresholds.map((t) => {
            const meta = PARAMS[t.param];
            return (
              <div className="table-row" key={t.id}>
                <span>
                  {meta.label}{" "}
                  <small className="dir">
                    ({meta.dir === "below" ? "alert when below" : "alert when above"})
                  </small>
                </span>
                <span>{name(t.machineId)}</span>
                <span>{fmtParam(t.param, t.warning)}</span>
                <span>{fmtParam(t.param, t.critical)}</span>
                <span className="saved">✓ Saved</span>
                <span className="row-actions">
                  {admin && (
                    <>
                      <button onClick={() => startEdit(t)}>Edit</button>
                      <button className="danger" onClick={() => remove(t.id)}>
                        Delete
                      </button>
                    </>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {admin && (
        <div className="threshold-form">
          <strong>{editId ? "Edit threshold" : "Add threshold"}</strong>
          <div className="threshold-form-row">
            <select
              aria-label="Parameter"
              value={form.param}
              onChange={(e) => setForm({ ...form, param: e.target.value })}
            >
              {Object.keys(PARAMS).map((p) => (
                <option key={p} value={p}>
                  {PARAMS[p].label}
                </option>
              ))}
            </select>
            <select
              aria-label="Applies to"
              value={form.machineId}
              onChange={(e) => setForm({ ...form, machineId: e.target.value })}
            >
              <option value="all">All machines</option>
              {machines.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
            <input
              aria-label="Warning limit"
              placeholder={`Warning ${PARAMS[form.param].unit}`}
              inputMode="decimal"
              value={form.warning}
              onChange={(e) => setForm({ ...form, warning: e.target.value })}
            />
            <input
              aria-label="Critical limit"
              placeholder={`Critical ${PARAMS[form.param].unit}`}
              inputMode="decimal"
              value={form.critical}
              onChange={(e) => setForm({ ...form, critical: e.target.value })}
            />
            <button className="primary-button" onClick={submit} disabled={busy}>
              {editId ? "Save changes" : "＋ Add threshold"}
            </button>
            {editId && (
              <button
                className="ghost-button"
                onClick={() => {
                  setEditId(null);
                  setForm(blank);
                  setError("");
                }}
              >
                Cancel
              </button>
            )}
          </div>
          {error && (
            <small className="form-error" role="alert">
              {error}
            </small>
          )}
        </div>
      )}
    </section>
  );
}
export default function AlertsPage() {
  const { alerts, machines, thresholds, plant, lastUpdate } = useData();
  const [tab, setTab] = useState("alerts");
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
  const selMachine = selected && machines.find((m) => m.id === selected.machineId);
  const selMachineId = selected?.machineId;
  const [trend, setTrend] = useState({ id: null, points: [] });
  // Re-read the 6-hour trend about once a minute while an alert is selected.
  const trendTick = Math.floor(lastUpdate / 60000);
  useEffect(() => {
    if (!selMachineId) return undefined;
    const controller = new AbortController();
    api.machines
      .trend(selMachineId, 6, { signal: controller.signal })
      .then((points) => setTrend({ id: selMachineId, points }))
      .catch(() => {});
    return () => controller.abort();
  }, [selMachineId, trendTick]);
  const trendPoints = trend.id === selMachineId ? trend.points : [];
  const selThreshold = selected && thresholds.find((t) => t.id === selected.thresholdId);
  return (
    <div className="content-page standard-page">
      <div className="page-heading">
        <div>
          <h1>Alerts &amp; Thresholds</h1>
          <p>What needs attention now, and the limits that trigger it.</p>
        </div>
        <div className="segmented" role="tablist">
          <button
            role="tab"
            aria-selected={tab === "alerts"}
            className={tab === "alerts" ? "selected" : ""}
            onClick={() => setTab("alerts")}
          >
            Alerts
          </button>
          <button
            role="tab"
            aria-selected={tab === "thresholds"}
            className={tab === "thresholds" ? "selected" : ""}
            onClick={() => setTab("thresholds")}
          >
            Thresholds
          </button>
        </div>
      </div>

      {tab === "thresholds" ? (
        <ThresholdPanel />
      ) : (
        <>
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
              const t = thresholds.find((x) => x.id === a.thresholdId);
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
                    <small>
                      {a.plant} ·{" "}
                      {a.status === "recovered"
                        ? `recovered ${istHm(a.recoveredAt ?? a.since)}`
                        : `since ${istHm(a.since)}`}{" "}
                      IST
                    </small>
                  </span>
                  <span className="reading">
                    <small>READING</small>
                    <strong>{fmtParam(a.param, a.reading)}</strong>
                  </span>
                  <span className="threshold-bar">
                    <i style={{ marginLeft: `${markerPct(a, t)}%` }} />
                  </span>
                  <span className={`severity ${kind}`}>
                    {kind[0].toUpperCase() + kind.slice(1)}
                  </span>
                </button>
              );
            })}
          </div>

          {selected && selMachine && (
            <section className="selected-alert panel">
              <img src={images.alertMachine} alt="" />
              <div>
                <small>SELECTED ALERT</small>
                <h3>
                  {selected.machineName} · {PARAMS[selected.param].label}
                </h3>
                <span
                  className={`severity ${
                    selected.status === "recovered" ? "recovered" : selected.severity
                  }`}
                >
                  {selected.status === "recovered"
                    ? "Recovered"
                    : selected.severity[0].toUpperCase() + selected.severity.slice(1)}
                </span>
                <p>
                  {selected.status === "recovered"
                    ? `Back within limits at ${istHm(selected.recoveredAt ?? selected.since)} IST.`
                    : `${
                        PARAMS[selected.param].dir === "below"
                          ? "Dropped below"
                          : "Rose above"
                      } the ${fmtParam(selected.param, selected.limit)} ${selected.severity} limit at ${istHm(selected.since)} IST and is still outside it.`}
                </p>
              </div>
              {selected.param !== "freshness" && (
                <div className="trend">
                  <span>{PARAMS[selected.param].label}, last 6 hours</span>
                  <TrendChart
                    points={trendPoints}
                    pick={PICK[selected.param]}
                    warning={selThreshold?.warning ?? null}
                    critical={selThreshold?.critical ?? null}
                    decimals={PARAMS[selected.param].decimals}
                  />
                </div>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
