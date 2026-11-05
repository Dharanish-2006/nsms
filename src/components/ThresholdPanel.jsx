import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import { fmtParam, PARAMS } from "../lib/params";

const parseLimit = (s) => (s.trim() === "" ? null : Number(s));
export function ThresholdPanel() {
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
