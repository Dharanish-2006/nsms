import { useState } from "react";
import { istDate, istHm12 } from "../../lib/format";

export const when = (ms) => (ms ? `${istDate(ms)}, ${istHm12(ms)}` : "—");

const TONES = {
  pending: "warn",
  active: "ok",
  rejected: "bad",
  assigned: "warn",
  connected: "ok",
  disconnected: "muted",
  available: "ok",
  online: "ok",
  offline: "muted",
  verified: "ok",
  unverified: "warn",
};
export const Pill = ({ value, label }) => (
  <span className={`adm-pill ${TONES[value] ?? "muted"}`}>{label ?? value}</span>
);

export const Stat = ({ label, value, tone }) => (
  <div className={`adm-stat ${tone ?? ""}`}>
    <strong>{value ?? "…"}</strong>
    <span>{label}</span>
  </div>
);

export function Table({ head, rows, empty = "Nothing to show." }) {
  if (!rows.length) return <p className="adm-empty">{empty}</p>;
  return (
    <div className="adm-table-wrap">
      <table className="adm-table">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i}>
              {cells.map((c, j) => (
                <td key={j} data-label={head[j]}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const Notice = ({ error, children }) =>
  error ? (
    <p className="adm-error" role="alert">
      {error}
    </p>
  ) : children ? (
    <p className="adm-note">{children}</p>
  ) : null;

/**
 * Confirmation dialog for an admin action. `field` adds a text box (a reason or
 * remarks); `children` can hold extra inputs. `onConfirm(text)` returns an
 * error message or "" and the dialog closes on success.
 */
export function Confirm({
  title,
  body,
  field,
  required,
  action = "Confirm",
  danger,
  onConfirm,
  onClose,
  children,
}) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const go = async (e) => {
    e.preventDefault();
    if (required && !text.trim()) return setError("This is required.");
    setBusy(true);
    const err = await onConfirm(text.trim());
    setBusy(false);
    if (err) setError(err);
    else onClose();
  };
  return (
    <div className="adm-backdrop" role="presentation" onClick={onClose}>
      <form
        className="adm-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onSubmit={go}
        onClick={(e) => e.stopPropagation()}
      >
        <h2>{title}</h2>
        {body && <p>{body}</p>}
        {children}
        {field && (
          <label className="adm-field">
            {field}
            <textarea
              rows={3}
              maxLength={300}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
        )}
        <Notice error={error} />
        <div className="adm-actions">
          <button type="button" className="adm-btn" onClick={onClose}>
            Cancel
          </button>
          <button
            className={danger ? "adm-btn danger" : "adm-btn primary"}
            disabled={busy}
          >
            {busy ? "Working…" : action}
          </button>
        </div>
      </form>
    </div>
  );
}
