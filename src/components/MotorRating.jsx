import { useState } from "react";
import { hpToKw, kwToHp, parseHp } from "../lib/motor";

/** A machine's motor rating in HP. Admins get an inline editor. */
export function MotorRating({ machine, canEdit, onSave }) {
  const hp = machine.ratedKw ? kwToHp(machine.ratedKw) : null;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null); // HP awaiting confirmation
  const [saved, setSaved] = useState(false);

  const start = () => {
    setText(hp === null ? "" : String(hp));
    setError("");
    setEditing(true);
  };
  const cancel = () => {
    setEditing(false);
    setPending(null);
    setError("");
  };
  const submit = (e) => {
    e.preventDefault();
    const value = parseHp(text);
    if (value === null) {
      setError("Enter HP above 0, with at most one decimal.");
      return;
    }
    if (value === hp) {
      cancel();
      return;
    }
    setError("");
    setPending(value);
  };
  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      await onSave(machine.id, hpToKw(pending));
      setEditing(false);
      setPending(null);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <span className="motor-cell">
        <span>{hp === null ? "--" : `${hp} HP`}</span>
        {saved && (
          <small className="motor-saved" role="status">
            Saved
          </small>
        )}
        {canEdit && (
          <button
            type="button"
            className="motor-btn"
            onClick={start}
            aria-label={`Change motor HP for ${machine.name}`}
          >
            Edit
          </button>
        )}
      </span>
    );
  }
  if (pending !== null) {
    return (
      <span
        className="motor-cell motor-edit"
        role="alertdialog"
        aria-label="Confirm HP change"
      >
        <span>
          Change {machine.name} from {hp === null ? "--" : hp} HP to <b>{pending} HP</b>?
        </span>
        <button
          type="button"
          className="motor-btn primary"
          onClick={confirm}
          disabled={busy}
        >
          {busy ? "Saving" : "Confirm"}
        </button>
        <button
          type="button"
          className="motor-btn"
          onClick={() => setPending(null)}
          disabled={busy}
        >
          Back
        </button>
        {error && (
          <small className="form-error motor-error" role="alert">
            {error}
          </small>
        )}
      </span>
    );
  }
  return (
    <form className="motor-cell motor-edit" onSubmit={submit}>
      <input
        autoFocus
        type="text"
        inputMode="decimal"
        value={text}
        aria-label={`Motor HP for ${machine.name}`}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && cancel()}
      />
      <span>HP</span>
      <button type="submit" className="motor-btn primary" disabled={busy}>
        {busy ? "Saving" : "Save"}
      </button>
      <button type="button" className="motor-btn" onClick={cancel} disabled={busy}>
        Cancel
      </button>
      {error && (
        <small className="form-error motor-error" role="alert">
          {error}
        </small>
      )}
    </form>
  );
}
