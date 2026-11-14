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
        <Stat label="Total gateways" value={d.registeredGateways} />
        <Stat
          label="Assigned / available gateways"
          value={`${d.assignedGateways}/${d.availableGateways}`}
        />
        <Stat label="Disconnected users" value={d.disconnectedUsers} />
      </div>
      <section className="adm-card">
        <h2>Gateways</h2>
        <Table
          head={["Gateway", "Serial", "Link", "Availability", "Assigned to", "Last seen"]}
          empty="No gateways have registered yet."
          rows={d.gateways.map((g) => [
            g.name,
            g.serialNumber || "—",
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
