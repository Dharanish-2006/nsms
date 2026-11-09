import { useState } from "react";
import { api } from "../../api";
import { ErrorPanel } from "../../components/PageState";
import { act, useLoad } from "./useLoad";
import { Confirm, Notice, Pill, Table, when } from "./ui";

const TABS = [
  ["pending", "Pending"],
  ["active", "Approved"],
  ["rejected", "Rejected"],
  ["", "All"],
];

export default function AdminUsers() {
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [dialog, setDialog] = useState(null);
  const { data, error, loading, reload } = useLoad(
    () => api.admin.users({ status, q }),
    [status, q],
  );
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  const rows = (data ?? []).map((u) => [
    <>
      <strong>{u.fullName || u.username}</strong>
      <br />
      <small>@{u.username}</small>
    </>,
    <>
      {u.email}
      {u.mobile && (
        <>
          <br />
          <small>{u.mobile}</small>
        </>
      )}
    </>,
    when(u.registeredAt),
    <Pill
      key="s"
      value={u.status}
      label={u.status === "active" ? "approved" : u.status}
    />,
    u.status === "pending" ? (
      <div className="adm-actions inline" key="a">
        <button
          className="adm-btn primary"
          onClick={() => setDialog({ kind: "approve", u })}
        >
          Approve
        </button>
        <button
          className="adm-btn danger"
          onClick={() => setDialog({ kind: "reject", u })}
        >
          Reject
        </button>
      </div>
    ) : (
      <small key="d">
        {u.decidedBy ? `by ${u.decidedBy.username}, ${when(u.decidedAt)}` : ""}
        {u.rejectionReason && (
          <>
            <br />
            {u.rejectionReason}
          </>
        )}
      </small>
    ),
  ]);
  return (
    <>
      <h1>User approval</h1>
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
          placeholder="Search name, username, email"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <section className="adm-card">
        {loading && !data ? (
          <p className="adm-empty">Loading…</p>
        ) : (
          <Table
            head={["Plant owner", "Contact", "Registered", "Status", "Decision"]}
            rows={rows}
            empty="No users match."
          />
        )}
      </section>
      {dialog?.kind === "approve" && (
        <Confirm
          title="Approve this user?"
          body={`${dialog.u.fullName || dialog.u.username} will be able to sign in. They will not see any machine until you connect a gateway to them.`}
          action="Approve"
          onClose={() => setDialog(null)}
          onConfirm={() => act(() => api.admin.approveUser(dialog.u.id), reload)}
        />
      )}
      {dialog?.kind === "reject" && (
        <Confirm
          title="Reject this registration?"
          body={`${dialog.u.fullName || dialog.u.username} will not be able to sign in.`}
          field="Reason (optional)"
          action="Reject"
          danger
          onClose={() => setDialog(null)}
          onConfirm={(reason) =>
            act(() => api.admin.rejectUser(dialog.u.id, reason), reload)
          }
        />
      )}
      <Notice />
    </>
  );
}
