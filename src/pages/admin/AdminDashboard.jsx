import { Link } from "react-router-dom";
import { api } from "../../api";
import { ErrorPanel, PageLoader } from "../../components/PageState";
import { useLoad } from "./useLoad";
import { Pill, Stat, Table, when } from "./ui";

export default function AdminDashboard() {
  const { data: d, error, loading, reload } = useLoad(() => api.admin.dashboard(), []);
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  if (!d || loading) return d ? null : <PageLoader label="Loading…" />;
  return (
    <>
      <h1>Dashboard</h1>
      <div className="adm-stats">
        <Link to="/admin/users">
          <Stat
            label="Pending approvals"
            value={d.pendingUsers}
            tone={d.pendingUsers ? "warn" : ""}
          />
        </Link>
        <Stat label="Approved users" value={d.approvedUsers} />
        <Stat label="Registered gateways" value={d.registeredGateways} />
        {d.unverifiedGateways > 0 && (
          <Link to="/admin/gateways">
            <Stat
              label="Awaiting verification"
              value={d.unverifiedGateways}
              tone="warn"
            />
          </Link>
        )}
        <Link to="/admin/gateways">
          <Stat
            label="Machines needing a name"
            value={d.machinesNeedingSetup}
            tone={d.machinesNeedingSetup ? "warn" : ""}
          />
        </Link>
        <Stat label="Available gateways" value={d.availableGateways} />
        <Stat label="Assigned gateways" value={d.assignedGateways} />
        <Link to="/admin/connections">
          <Stat label="Active connections" value={d.activeConnections} tone="ok" />
        </Link>
      </div>
      <section className="adm-card">
        <h2>Gateways</h2>
        <Table
          head={[
            "Gateway",
            "Serial",
            "Verified",
            "Link",
            "Availability",
            "Assigned to",
            "Last seen",
          ]}
          empty="No gateways have registered yet."
          rows={d.gateways.map((g) => [
            g.name,
            g.serialNumber || "—",
            <Pill key="v" value={g.verified ? "verified" : "unverified"} />,
            <Pill key="o" value={g.online ? "online" : "offline"} />,
            <Pill key="a" value={g.connection ?? g.availability} />,
            g.assignedTo ? g.assignedTo.fullName || g.assignedTo.username : "—",
            when(g.lastSeenAt),
          ])}
        />
      </section>
    </>
  );
}
