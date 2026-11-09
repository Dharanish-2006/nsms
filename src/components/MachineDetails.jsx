import { useState } from "react";

export const MACHINE_TYPES = [
  ["sheller", "Sheller"],
  ["whitener", "Whitener"],
  ["sortex", "Sortex"],
];

/** The machine's name and type, with an inline editor (gateway meters arrive as "Meter 1", "Meter 2"…). */
export function MachineDetails({ machine, onSave }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("sheller");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const start = () => {
    setName(machine.name);
    setType(machine.type);
    setError("");
    setEditing(true);
  };
  const submit = async (e) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return setError("Enter a name, for example Sheller 1.");
    if (trimmed === machine.name && type === machine.type) return setEditing(false);
    setBusy(true);
    setError("");
    try {
      await onSave(machine.id, { name: trimmed, type });
      setEditing(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  if (!editing)
    return (
      <span className="motor-cell">
        <h1>{machine.name}</h1>
        <button
          type="button"
          className="motor-btn"
          onClick={start}
          aria-label={`Rename ${machine.name} or change its type`}
        >
          Rename
        </button>
      </span>
    );
  return (
    <form className="motor-cell motor-edit" onSubmit={submit}>
      <input
        autoFocus
        type="text"
        maxLength={100}
        value={name}
        aria-label="Machine name"
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && setEditing(false)}
      />
      <select
        value={type}
        aria-label="Machine type"
        onChange={(e) => setType(e.target.value)}
      >
        {MACHINE_TYPES.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
      <button type="submit" className="motor-btn primary" disabled={busy}>
        {busy ? "Saving" : "Save"}
      </button>
      <button
        type="button"
        className="motor-btn"
        onClick={() => setEditing(false)}
        disabled={busy}
      >
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
