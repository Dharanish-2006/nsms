import { useState } from "react";
import { api } from "../../api";
import { ErrorPanel } from "../../components/PageState";
import { act, useLoad } from "./useLoad";
import { Confirm, Pill, Table, when } from "./ui";

const TABS = [
  ["", "All"],
  ["connected", "Connected"],
  ["assigned", "Assigned"],
  ["disconnected", "Disconnected"],
];

export default function AdminConnections() {
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(null);
  const { data, error, loading, reload } = useLoad(
    () => api.admin.assignments({ status, q }),
    [status, q],
  );
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  const name = (u) => (u ? u.fullName || u.username : "—");
  const rows = (data ?? []).map((a) => [
    name(a.user),
    <>
      <strong>{a.gateway.name}</strong>
      <br />
      <small>{a.gateway.serialNumber}</small>
    </>,
    <Pill key="s" value={a.status} />,
    <>
      {when(a.assignedAt)}
      <br />
      <small>{a.assignedBy ? `by ${a.assignedBy.username}` : ""}</small>
    </>,
    a.connectedAt ? (
      <>
        {when(a.connectedAt)}
        <br />
        <small>{a.connectedBy ? `by ${a.connectedBy.username}` : ""}</small>
      </>
    ) : (
      "—"
    ),
    a.disconnectedAt ? (
      <>
        {when(a.disconnectedAt)}
        <br />
        <small>{a.disconnectedBy ? `by ${a.disconnectedBy.username}` : ""}</small>
      </>
    ) : (
      "—"
    ),
    <div className="adm-actions inline" key="x">
      {a.status !== "connected" && (
        <button
          className="adm-btn primary"
          onClick={() => setDialog({ kind: "connect", a })}
        >
          {a.status === "disconnected" ? "Reconnect" : "Connect"}
        </button>
      )}
      {a.status !== "disconnected" && (
        <button
          className="adm-btn danger"
          onClick={() => setDialog({ kind: "disconnect", a })}
        >
          Disconnect
        </button>
      )}
    </div>,
  ]);
  const a = dialog?.a;
  const close = () => setDialog(null);
  return (
    <>
      <h1>Connections</h1>
      <div className="adm-toolbar">
        <div className="adm-tabs" role="tablist">
          {TABS.map(([v, l]) => (
            <button
              key={l}
              role="tab"
              aria-selected={status === v}
              className={status === v ? "on" : ""}
              onClick={() => setStatus(v)}
            >
              {l}
            </button>
          ))}
        </div>
        <input
          className="adm-search"
          type="search"
          placeholder="Search user or gateway"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <section className="adm-card">
        {loading && !data ? (
          <p className="adm-empty">Loading…</p>
        ) : (
          <Table
            head={[
              "User",
              "Gateway",
              "Status",
              "Assigned",
              "Connected",
              "Disconnected",
              "Actions",
            ]}
            rows={rows}
            empty="No connections yet. Assign a gateway from the Gateways page."
          />
        )}
      </section>
      {dialog?.kind === "connect" && (
        <Confirm
          title={`${a.status === "disconnected" ? "Reconnect" : "Connect"} ${a.gateway.name}?`}
          body={`${name(a.user)} will see this gateway's data from now on.`}
          field="Remarks (optional)"
          action="Connect"
          onClose={close}
          onConfirm={(r) => act(() => api.admin.connect(a.id, r), reload)}
        />
      )}
      {dialog?.kind === "disconnect" && (
        <Confirm
          title={`Disconnect ${a.gateway.name}?`}
          body={`${name(a.user)} loses access to its live data. Their recorded reports for the connected period stay available.`}
          field="Remarks (optional)"
          action="Disconnect"
          danger
          onClose={close}
          onConfirm={(r) => act(() => api.admin.disconnect(a.id, r), reload)}
        />
      )}
    </>
  );
}
