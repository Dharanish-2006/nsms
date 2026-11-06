import { useState } from "react";
import { hpToKw, kwToHp, parseHp } from "../lib/motor";

/** A machine's motor rating in HP. Admins get an inline editor. */
export function MotorRating({ machine, canEdit, onSave }) {
  const hp = machine.ratedKw ? kwToHp(machine.ratedKw) : null;
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const start = () => {
    setText(hp === null ? "" : String(hp));
    setError("");
    setEditing(true);
  };
  const cancel = () => {
    setEditing(false);
    setError("");
  };
  const submit = async (e) => {
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
    setBusy(true);
    setError("");
    try {
      await onSave(machine.id, hpToKw(value));
      setEditing(false);
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
