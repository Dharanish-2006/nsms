import { useEffect, useState } from "react";
import { api } from "../../api";
import { ErrorPanel } from "../../components/PageState";
import { Link } from "react-router-dom";
import { act, useLoad } from "./useLoad";
import { Confirm, Pill, Table, when } from "./ui";

const FILTERS = [
  ["", "All"],
  ["available", "Available"],
  ["assigned", "Assigned"],
];

function AssignDialog({ gateway, onClose, reload }) {
  const [users, setUsers] = useState(null);
  const [userId, setUserId] = useState("");
  useEffect(() => {
    api.admin.users({ status: "active" }).then(setUsers, () => setUsers([]));
  }, []);
  return (
    <Confirm
      title={`Assign ${gateway.name}`}
      body="Choose the plant owner who will own this gateway. Data stays hidden from them until you connect it."
      field="Remarks (optional)"
      action="Assign"
      onClose={onClose}
      onConfirm={(remarks) =>
        userId
          ? act(() => api.admin.assign(userId, gateway.id, remarks), reload)
          : Promise.resolve("Pick a user.")
      }
    >
      <label className="adm-field">
        Plant owner
        <select
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          disabled={!users}
        >
          <option value="">{users ? "Select an approved user" : "Loading…"}</option>
          {(users ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.fullName || u.username} (@{u.username})
            </option>
          ))}
        </select>
      </label>
    </Confirm>
  );
}

export default function AdminGateways() {
  const [availability, setAvailability] = useState("");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(null);
  const [newKey, setNewKey] = useState(null);
  const { data, error, loading, reload } = useLoad(
    () => api.admin.gateways({ availability, q }),
    [availability, q],
  );
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  const rows = (data ?? []).map((g) => {
    const open = (kind) => setDialog({ kind, g });
    return [
      <>
        <Link className="adm-link" to={`/admin/gateways/${g.id}`}>
          <strong>{g.name}</strong>
        </Link>
        <br />
        <small>{g.serialNumber || "no serial"}</small>
        <br />
        <Link className="adm-link" to={`/admin/gateways/${g.id}`}>
          <small>
            {g.machineCount} machine{g.machineCount === 1 ? "" : "s"}
          </small>
        </Link>
      </>,
      <>
        <Pill value={g.online ? "online" : "offline"} />
        <br />
        <small>{when(g.lastSeenAt)}</small>
      </>,
      <Pill key="a" value={g.connection ?? g.availability} />,
      g.assignedTo ? g.assignedTo.fullName || g.assignedTo.username : "—",
      <div className="adm-actions inline" key="x">
        {!g.assignmentId && (
          <button className="adm-btn primary" onClick={() => open("assign")}>
            Assign
          </button>
        )}
        {g.connection === "assigned" && (
          <button className="adm-btn primary" onClick={() => open("connect")}>
            Connect
          </button>
        )}
        {g.assignmentId && (
          <button className="adm-btn danger" onClick={() => open("disconnect")}>
            {g.connection === "assigned" ? "Unassign" : "Disconnect"}
          </button>
        )}
        <button className="adm-btn" onClick={() => open("rotate")}>
          New key
        </button>
      </div>,
    ];
  });
  const g = dialog?.g;
  const close = () => setDialog(null);
  return (
    <>
      <h1>Gateways</h1>
      <p className="adm-note">
        A gateway appears here, ready to assign, as soon as it sends its first message.
        There is nothing to approve.
      </p>
      <div className="adm-toolbar">
        <div className="adm-tabs" role="tablist">
          {FILTERS.map(([v, l]) => (
            <button
              key={l}
              role="tab"
              aria-selected={availability === v}
              className={availability === v ? "on" : ""}
              onClick={() => setAvailability(v)}
            >
              {l}
            </button>
          ))}
        </div>
        <input
          className="adm-search"
          type="search"
          placeholder="Search name or serial"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <section className="adm-card">
        {loading && !data ? (
          <p className="adm-empty">Loading…</p>
        ) : (
          <Table
            head={["Gateway", "Link", "Status", "Assigned to", "Actions"]}
            rows={rows}
            empty="No gateways match."
          />
        )}
      </section>
      {dialog?.kind === "assign" && (
        <AssignDialog gateway={g} onClose={close} reload={reload} />
      )}
      {dialog?.kind === "connect" && (
        <Confirm
          title={`Connect ${g.name}?`}
          body={`${g.assignedTo?.fullName || g.assignedTo?.username} will start seeing this gateway's machines and reports from now on.`}
          field="Remarks (optional)"
          action="Connect"
          onClose={close}
          onConfirm={(r) => act(() => api.admin.connect(g.assignmentId, r), reload)}
        />
      )}
      {dialog?.kind === "disconnect" && (
        <Confirm
          title={`${g.connection === "assigned" ? "Unassign" : "Disconnect"} ${g.name}?`}
          body="The owner loses access to its live data. Reports already recorded for their connected period stay available to them."
          field="Remarks (optional)"
          action={g.connection === "assigned" ? "Unassign" : "Disconnect"}
          danger
          onClose={close}
          onConfirm={(r) => act(() => api.admin.disconnect(g.assignmentId, r), reload)}
        />
      )}
      {dialog?.kind === "rotate" && (
        <Confirm
          title={`Issue a new key for ${g.name}?`}
          body="The old key stops working immediately. Use this for a replaced or reset device."
          field="Remarks (optional)"
          action="Issue key"
          danger
          onClose={close}
          onConfirm={async (r) => {
            try {
              const res = await api.admin.rotateKey(g.id, r);
              setNewKey({ name: g.name, key: res.apiKey });
              reload();
              return "";
            } catch (e) {
              return e?.message || "That did not work.";
            }
          }}
        />
      )}
      {newKey && (
        <div className="adm-backdrop" role="presentation">
          <div
            className="adm-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="New gateway key"
          >
            <h2>New key for {newKey.name}</h2>
            <p>Copy it into the gateway now. It is shown only once.</p>
            <code className="adm-key">{newKey.key}</code>
            <div className="adm-actions">
              <button
                className="adm-btn"
                onClick={() => navigator.clipboard?.writeText(newKey.key)}
              >
                Copy
              </button>
              <button className="adm-btn primary" onClick={() => setNewKey(null)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
