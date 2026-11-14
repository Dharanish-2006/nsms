import { Link, useParams } from "react-router-dom";
import { api } from "../../api";
import { ErrorPanel, PageLoader } from "../../components/PageState";
import { useLoad } from "./useLoad";
import { Pill, Table, when } from "./ui";

/** The meters a gateway has reported. Read-only: the plant owner names their machines. */
export default function AdminGatewayDetail() {
  const { id } = useParams();
  const { data, error, reload } = useLoad(() => api.admin.gatewayMachines(id), [id]);
  if (error) return <ErrorPanel message={error} onRetry={reload} />;
  if (!data) return <PageLoader label="Loading…" />;
  const { gateway: g, machines } = data;
  return (
    <>
      <p className="adm-crumb">
        <Link to="/admin/gateways">← Gateways</Link>
      </p>
      <h1>{g.name}</h1>
      <div className="adm-meta">
        <span>Serial {g.serialNumber || "—"}</span>
        <Pill value={g.online ? "online" : "offline"} />
        <Pill value={g.connection ?? g.availability} />
        {g.assignedTo && (
          <span>Owner {g.assignedTo.fullName || g.assignedTo.username}</span>
        )}
      </div>
      <p className="adm-note">
        Each meter on this gateway is identified by its Meter ID (the Modbus address set
        on the meter). The plant owner names their machines. Readings are never shown
        here.
      </p>
      <section className="adm-card">
        <Table
          head={["Meter ID", "Name", "Last data"]}
          rows={machines.map((m) => [m.meterId, m.name, when(m.lastSeenAt)])}
          empty="No meters have reported yet. They appear here when the gateway first sends data."
        />
      </section>
    </>
  );
}
