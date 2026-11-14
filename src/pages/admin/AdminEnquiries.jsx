import { useState } from "react";
import { api } from "../../api";
import { ErrorPanel } from "../../components/PageState";
import { act, useLoad } from "./useLoad";
import { Notice, Pill, Table, when } from "./ui";

const TABS = [
  ["new", "New"],
  ["contacted", "Contacted"],
  ["closed", "Closed"],
  ["", "All"],
];

export default function AdminEnquiries() {
  const [status, setStatus] = useState("new");
  const { data, error, loading, reload } = useLoad(
    () => api.admin.enquiries({ status }),
    [status],
  );
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  const set = (id, next) => act(() => api.admin.setEnquiryStatus(id, next), reload);
  const rows = (data ?? []).map((e) => [
    <>
      <strong>{e.name}</strong>
      <br />
      <a href={`tel:${e.mobile}`}>{e.mobile}</a>
    </>,
    <span key="r" style={{ whiteSpace: "pre-wrap" }}>
      {e.requirement}
    </span>,
    <>
      {when(e.createdAt)}
      <br />
      <small>{e.emailed ? "Team emailed" : "Not emailed"}</small>
    </>,
    <Pill key="s" value={e.status} />,
    <div className="adm-actions inline" key="a">
      {e.status !== "contacted" && (
        <button className="adm-btn primary" onClick={() => set(e.id, "contacted")}>
          Mark contacted
        </button>
      )}
      {e.status !== "closed" && (
        <button className="adm-btn" onClick={() => set(e.id, "closed")}>
          Close
        </button>
      )}
      {e.status !== "new" && (
        <button className="adm-btn" onClick={() => set(e.id, "new")}>
          Reopen
        </button>
      )}
    </div>,
  ]);
  return (
    <>
      <h1>Enquiries</h1>
      <p className="adm-lead">Messages sent from the public Smart Milling page.</p>
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
      </div>
      <section className="adm-card">
        {loading && !data ? (
          <p className="adm-empty">Loading…</p>
        ) : (
          <Table
            head={["From", "Requirement", "Received", "Status", ""]}
            rows={rows}
            empty="No enquiries here."
          />
        )}
      </section>
      <Notice />
    </>
  );
}
