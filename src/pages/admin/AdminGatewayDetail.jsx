import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../../api";
import { ErrorPanel, PageLoader } from "../../components/PageState";
import { hpToKw, kwToHp } from "../../lib/motor";
import { act, useLoad } from "./useLoad";
import { Notice, Pill, Table, when } from "./ui";

const TYPES = [
  ["sheller", "Sheller"],
  ["whitener", "Whitener"],
  ["sortex", "Sortex"],
];

/** One meter of the gateway: the admin names it and gives its type (and, optionally, its HP). */
function MachineRow({ m, reload }) {
  const [name, setName] = useState(m.configured ? m.name : "");
  const [type, setType] = useState(m.type);
  const [hp, setHp] = useState(m.ratedKw > 0 ? String(kwToHp(m.ratedKw)) : "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  const changed =
    name.trim() !== (m.configured ? m.name : "") ||
    type !== m.type ||
    hp !== (m.ratedKw > 0 ? String(kwToHp(m.ratedKw)) : "");

  const submit = async (e) => {
    e.preventDefault();
    setSaved(false);
    if (!name.trim()) return setError("Enter the machine name.");
    const body = { name: name.trim(), type };
    if (hp.trim() !== "") {
      const n = Number(hp);
      if (!Number.isFinite(n) || n <= 0) return setError("HP must be a number above 0.");
      body.ratedKw = hpToKw(n);
    }
    setBusy(true);
    setError("");
    const err = await act(() => api.admin.configureMachine(m.id, body), reload);
    setBusy(false);
    if (err) setError(err);
    else setSaved(true);
  };

  return (
    <form className="adm-machine" onSubmit={submit}>
      <div className="adm-machine-id">
        <span>Meter ID</span>
        <strong>{m.meterId}</strong>
      </div>
      <label className="adm-field">
        Machine name
        <input
          type="text"
          maxLength={100}
          value={name}
          placeholder="e.g. Sheller 1"
          onChange={(e) => setName(e.target.value)}
        />
      </label>
      <label className="adm-field">
        Type
        <select value={type} onChange={(e) => setType(e.target.value)}>
          {TYPES.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label className="adm-field">
        Motor HP (optional)
        <input
          type="number"
          min="0"
          step="0.5"
          inputMode="decimal"
          value={hp}
          onChange={(e) => setHp(e.target.value)}
        />
      </label>
      <div className="adm-machine-state">
        <Pill
          value={m.configured ? "active" : "pending"}
          label={m.configured ? "Visible to owner" : "Needs a name"}
        />
        <small>Last data {when(m.lastSeenAt)}</small>
      </div>
      <div className="adm-machine-save">
        <button className="adm-btn primary" disabled={busy || (m.configured && !changed)}>
          {busy ? "Saving…" : m.configured ? "Save" : "Name it"}
        </button>
        {saved && !error && <small className="adm-note">Saved</small>}
      </div>
      {error && (
        <div className="adm-machine-error">
          <Notice error={error} />
        </div>
      )}
    </form>
  );
}

export default function AdminGatewayDetail() {
  const { id } = useParams();
  const { data, error, reload } = useLoad(() => api.admin.gatewayMachines(id), [id]);
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  if (!data) return <PageLoader label="Loading…" />;
  const { gateway: g, machines } = data;
  const pending = machines.filter((m) => !m.configured).length;
  return (
    <>
      <p className="adm-crumb">
        <Link to="/admin/gateways">← Gateways</Link>
      </p>
      <h1>{g.name}</h1>
      <div className="adm-meta">
        <span>Serial {g.serialNumber || "—"}</span>
        <Pill value={g.verified ? "verified" : "unverified"} />
        <Pill value={g.online ? "online" : "offline"} />
        <Pill value={g.connection ?? g.availability} />
        {g.assignedTo && (
          <span>Owner {g.assignedTo.fullName || g.assignedTo.username}</span>
        )}
      </div>
      <p className="adm-note">
        Each meter on this gateway is identified by its Meter ID (the Modbus address set
        on the meter). Give it the name the plant owner will see. A meter stays hidden
        from the owner until you name it. Readings are never shown here.
      </p>
      {pending > 0 && (
        <p className="adm-banner-warn" role="status">
          {pending} meter{pending === 1 ? "" : "s"} waiting for a name.
        </p>
      )}
      <section className="adm-card">
        {machines.length === 0 ? (
          <Table
            head={["Meter"]}
            rows={[]}
            empty="No meters have reported yet. They appear here when the gateway first sends data."
          />
        ) : (
          <div className="adm-machines">
            {machines.map((m) => (
              <MachineRow
                key={`${m.id}-${m.name}-${m.type}-${m.ratedKw}-${m.configured}`}
                m={m}
                reload={reload}
              />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
