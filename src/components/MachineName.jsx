import { useState } from "react";

const TYPES = [
  ["sheller", "Sheller"],
  ["whitener", "Whitener"],
  ["sortex", "Sortex"],
];

export function MachineName({ machine, onSave }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const cancel = () => {
    setEditing(false);
    setError("");
  };
  const changeType = async (type) => {
    setBusy(true);
    setError("");
    try {
      await onSave(machine.id, { type });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const submit = async (e) => {
    e.preventDefault();
    const name = text.trim();
    if (!name) return setError("Enter a machine name.");
    if (name === machine.name) return cancel();
    setBusy(true);
    setError("");
    try {
      await onSave(machine.id, { name });
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!editing) {
    return (
      <div className="machine-name">
        <h1>{machine.name}</h1>
        <button
          type="button"
          className="motor-btn"
          aria-label={`Rename ${machine.name}`}
          onClick={() => {
            setText(machine.name);
            setError("");
            setEditing(true);
          }}
        >
          Rename
        </button>
        <select
          className="machine-type"
          aria-label={`Machine type for ${machine.name}`}
          value={machine.type}
          disabled={busy}
          onChange={(e) => changeType(e.target.value)}
        >
          {TYPES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
        {error && (
          <small className="form-error motor-error" role="alert">
            {error}
          </small>
        )}
      </div>
    );
  }
  return (
    <form className="machine-name motor-edit" onSubmit={submit}>
      <input
        autoFocus
        type="text"
        maxLength={100}
        value={text}
        aria-label="Machine name"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && cancel()}
      />
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
