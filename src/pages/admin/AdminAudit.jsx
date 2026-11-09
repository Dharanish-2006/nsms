import { useState } from "react";
import { api } from "../../api";
import { ErrorPanel } from "../../components/PageState";
import { useLoad } from "./useLoad";
import { Table, when } from "./ui";

const ACTIONS = [
  ["", "All actions"],
  ["user_approved", "User approved"],
  ["user_rejected", "User rejected"],
  ["gateway_verified", "Gateway verified"],
  ["gateway_key_rotated", "Key rotated"],
  ["gateway_assigned", "Gateway assigned"],
  ["gateway_connected", "Gateway connected"],
  ["gateway_disconnected", "Gateway disconnected"],
];
const label = Object.fromEntries(ACTIONS);

export default function AdminAudit() {
  const [action, setAction] = useState("");
  const { data, error, loading, reload } = useLoad(
    () => api.admin.auditLog({ action }),
    [action],
  );
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  return (
    <>
      <h1>Audit log</h1>
      <p className="adm-note">
        Every admin action is recorded here. Entries cannot be edited or deleted.
      </p>
      <div className="adm-toolbar">
        <select
          className="adm-search"
          aria-label="Action"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        >
          {ACTIONS.map(([v, l]) => (
            <option key={l} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
      <section className="adm-card">
        {loading && !data ? (
          <p className="adm-empty">Loading…</p>
        ) : (
          <Table
            head={["When", "Admin", "Action", "Target", "Remarks"]}
            empty="No actions recorded yet."
            rows={(data ?? []).map((e) => [
              when(e.timestamp),
              e.admin,
              label[e.action] ?? e.action,
              `${e.targetType} ${e.targetId}`,
              e.remarks || "—",
            ])}
          />
        )}
      </section>
    </>
  );
}
