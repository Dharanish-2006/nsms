import { MACHINES } from "./sim";
import { load, save, uid } from "./storage";

// Browser-only stand-in for the Admin Portal API (see backend/apps/adminportal).
// It mirrors the server rules: an approved user, a free gateway,
// one live record per gateway, and an audit entry for every action.

const KEY = "rmm.mock.admin";
const DAY = 86_400_000;

function seed() {
  const now = Date.now();
  return {
    gateways: [
      {
        id: "gw-1",
        name: "Gateway 1",
        serialNumber: "TRB145-0001",
        verified: true,
        enabled: true,
        lastSeenAt: now - 20_000,
        registeredAt: now - 30 * DAY,
        apiKeyPrefix: "gw_a1b2",
      },
      {
        id: "gw-2",
        name: "Gateway 2",
        serialNumber: "TRB145-0002",
        verified: true,
        enabled: true,
        lastSeenAt: now - 90_000,
        registeredAt: now - 12 * DAY,
        apiKeyPrefix: "gw_c3d4",
      },
      {
        id: "gw-3",
        name: "TRB145-0003",
        serialNumber: "TRB145-0003",
        verified: true,
        enabled: true,
        lastSeenAt: now - 120_000,
        registeredAt: now - 3_600_000,
        apiKeyPrefix: "gw_e5f6",
      },
    ],
    assignments: [],
    audit: [],
    machines: seedMachines(now),
  };
}

// Gateway 1 already has its machines named (they are the demo plant's). Gateway 2's meters have
// just reported in and wait for the admin to name them.
function seedMachines(now) {
  return [
    ...MACHINES.map((m, i) => ({
      id: m.id,
      gatewayId: "gw-1",
      meterId: String(i + 1),
      name: m.name,
      type: m.type,
      ratedKw: m.ratedKw,
      configured: true,
      lastSeenAt: now - 20_000,
    })),
    ...["1", "2"].map((n) => ({
      id: `gw2-m${n}`,
      gatewayId: "gw-2",
      meterId: n,
      name: `Meter ${n}`,
      type: "sheller",
      ratedKw: 0,
      configured: true,
      lastSeenAt: now - 90_000,
    })),
  ];
}
const db = () => {
  const d = load(KEY, null) ?? seed();
  d.machines ??= seedMachines(Date.now()); // older saved demo data
  return d;
};
const commit = (d) => save(KEY, d);

export function createAdminMock({ users, saveUsers, requireAdmin, fail }) {
  const person = (u) =>
    u ? { id: u.id, username: u.username, fullName: u.fullName } : null;
  const byId = (id) => users().find((u) => u.id === String(id));
  const log = (d, admin, action, targetType, targetId, remarks = "") =>
    d.audit.unshift({
      id: uid(),
      admin: admin.username,
      action,
      targetType,
      targetId: String(targetId),
      remarks,
      timestamp: Date.now(),
    });
  const live = (d) =>
    Object.fromEntries(
      d.assignments
        .filter((a) => a.status !== "disconnected")
        .map((a) => [a.gatewayId, a]),
    );
  const owners = () => users().filter((u) => u.role === "user");
  const userRow = (u) => ({
    id: u.id,
    username: u.username,
    fullName: u.fullName,
    email: u.email,
    mobile: u.mobile,
    status: u.status,
    registeredAt: u.registeredAt ?? null,
    decidedAt: u.decidedAt ?? null,
    decidedBy: u.decidedBy ?? null,
    rejectionReason: u.rejectionReason ?? "",
  });
  const gwRow = (g, l, apiKey) => ({
    ...g,
    machineCount: db().machines.filter((m) => m.gatewayId === g.id).length,
    availability: l ? "assigned" : "available",
    online: g.lastSeenAt !== null && Date.now() - g.lastSeenAt < 120_000,
    assignmentId: l?.id ?? null,
    assignedTo: l ? person(byId(l.userId)) : null,
    connection: l?.status ?? null,
    ...(apiKey ? { apiKey } : {}),
  });
  const asRow = (d, a) => {
    const g = d.gateways.find((x) => x.id === a.gatewayId);
    return {
      id: a.id,
      user: person(byId(a.userId)),
      gateway: { id: g.id, name: g.name, serialNumber: g.serialNumber },
      status: a.status,
      assignedAt: a.assignedAt,
      assignedBy: a.assignedBy,
      connectedAt: a.connectedAt ?? null,
      connectedBy: a.connectedBy ?? null,
      disconnectedAt: a.disconnectedAt ?? null,
      disconnectedBy: a.disconnectedBy ?? null,
    };
  };
  const match = (text, q) => !q || text.toLowerCase().includes(String(q).toLowerCase());

  async function decide(id, approve, reason = "") {
    const me = await requireAdmin();
    const u =
      owners().find((x) => x.id === String(id)) ?? fail(404, "Not found.", "not_found");
    if (u.status !== "pending")
      fail(409, "This request has already been decided.", "already_decided");
    saveUsers(
      users().map((x) =>
        x.id !== u.id
          ? x
          : {
              ...x,
              status: approve ? "active" : "rejected",
              decidedAt: Date.now(),
              decidedBy: person(me),
              rejectionReason: approve ? "" : reason,
            },
      ),
    );
    const d = db();
    log(d, me, approve ? "user_approved" : "user_rejected", "user", u.id, reason);
    commit(d);
    return userRow(byId(u.id));
  }

  const EQ_KEY = "rmm.mock.enquiries";
  const enquiries = () => load(EQ_KEY, []);

  return {
    async enquiries(query = {}) {
      await requireAdmin();
      return enquiries().filter((e) => !query.status || e.status === query.status);
    },
    async setEnquiryStatus(id, status) {
      const me = await requireAdmin();
      if (!["new", "contacted", "closed"].includes(status))
        fail(422, "Unknown status.", "validation");
      let row = null;
      save(
        EQ_KEY,
        enquiries().map((e) => {
          if (e.id !== Number(id)) return e;
          row = {
            ...e,
            status,
            handledAt: status === "new" ? null : Date.now(),
            handledBy: status === "new" ? null : me.username,
          };
          return row;
        }),
      );
      return row ?? fail(404, "Not found.", "not_found");
    },
    async dashboard() {
      await requireAdmin();
      const d = db(),
        l = live(d),
        o = owners();
      return {
        pendingUsers: o.filter((u) => u.status === "pending").length,
        approvedUsers: o.filter((u) => u.status === "active").length,
        registeredGateways: d.gateways.length,
        activeConnections: d.assignments.filter((a) => a.status === "connected").length,
        availableGateways: d.gateways.filter((g) => !l[g.id]).length,
        assignedGateways: Object.keys(l).length,
        newEnquiries: enquiries().filter((e) => e.status === "new").length,
        gateways: d.gateways.map((g) => gwRow(g, l[g.id])),
      };
    },
    async users(query = {}) {
      await requireAdmin();
      return owners()
        .filter((u) => !query.status || u.status === query.status)
        .filter((u) => match(`${u.username} ${u.fullName} ${u.email}`, query.q))
        .map(userRow);
    },
    approveUser: (id) => decide(id, true),
    rejectUser: (id, reason) => decide(id, false, (reason ?? "").trim()),
    async gateways(query = {}) {
      await requireAdmin();
      const d = db(),
        l = live(d);
      return d.gateways
        .filter((g) => match(`${g.name} ${g.serialNumber}`, query.q))
        .map((g) => gwRow(g, l[g.id]))
        .filter((r) => !query.availability || r.availability === query.availability);
    },
    async rotateKey(id, remarks = "") {
      const me = await requireAdmin();
      const d = db();
      const g =
        d.gateways.find((x) => x.id === id) ?? fail(404, "Not found.", "not_found");
      const raw = `gw_${uid()}${uid()}`;
      g.apiKeyPrefix = raw.slice(0, 7);
      log(d, me, "gateway_key_rotated", "gateway", g.id, remarks);
      commit(d);
      return gwRow(g, live(d)[g.id], raw);
    },
    async assignments(query = {}) {
      await requireAdmin();
      const d = db();
      return d.assignments
        .map((a) => asRow(d, a))
        .filter((a) => !query.status || a.status === query.status)
        .filter((a) =>
          match(
            `${a.user?.username} ${a.user?.fullName} ${a.gateway.name} ${a.gateway.serialNumber}`,
            query.q,
          ),
        )
        .reverse();
    },
    async assign(userId, gatewayId, remarks = "") {
      const me = await requireAdmin();
      const d = db();
      const u = owners().find((x) => x.id === String(userId));
      if (!u || u.status !== "active") fail(422, "Pick an approved user.", "validation");
      const g =
        d.gateways.find((x) => x.id === gatewayId) ??
        fail(404, "Gateway not found.", "not_found");
      if (live(d)[g.id])
        fail(
          409,
          "This gateway is already assigned. Disconnect it first.",
          "gateway_in_use",
        );
      const a = {
        id: uid(),
        userId: u.id,
        gatewayId: g.id,
        status: "assigned",
        assignedAt: Date.now(),
        assignedBy: person(me),
      };
      d.assignments.push(a);
      log(d, me, "gateway_assigned", "assignment", a.id, remarks);
      commit(d);
      return asRow(d, a);
    },
    async connect(id, remarks = "") {
      const me = await requireAdmin();
      const d = db();
      const a =
        d.assignments.find((x) => x.id === id) ?? fail(404, "Not found.", "not_found");
      if (a.status === "connected") fail(409, "Already connected.", "already_connected");
      if (byId(a.userId)?.status !== "active")
        fail(409, "Only approved users can be connected.", "user_not_approved");
      if (
        d.assignments.some(
          (x) =>
            x.id !== a.id && x.gatewayId === a.gatewayId && x.status !== "disconnected",
        )
      )
        fail(409, "Another user holds this gateway.", "gateway_in_use");
      Object.assign(a, {
        status: "connected",
        connectedAt: Date.now(),
        connectedBy: person(me),
        disconnectedAt: null,
        disconnectedBy: null,
      });
      log(d, me, "gateway_connected", "assignment", a.id, remarks);
      commit(d);
      return asRow(d, a);
    },
    async disconnect(id, remarks = "") {
      const me = await requireAdmin();
      const d = db();
      const a =
        d.assignments.find((x) => x.id === id) ?? fail(404, "Not found.", "not_found");
      if (a.status === "disconnected")
        fail(409, "Already disconnected.", "already_disconnected");
      Object.assign(a, {
        status: "disconnected",
        disconnectedAt: Date.now(),
        disconnectedBy: person(me),
      });
      log(d, me, "gateway_disconnected", "assignment", a.id, remarks);
      commit(d);
      return asRow(d, a);
    },
    async gatewayMachines(id) {
      await requireAdmin();
      const d = db();
      const g =
        d.gateways.find((x) => x.id === id) ?? fail(404, "Not found.", "not_found");
      const rows = d.machines
        .filter((m) => m.gatewayId === id)
        .sort((a, b) => a.meterId.localeCompare(b.meterId))
        .map(({ gatewayId, ...m }) => (void gatewayId, m));
      return { gateway: gwRow(g, live(d)[g.id]), machines: rows };
    },
    async auditLog(query = {}) {
      await requireAdmin();
      return db()
        .audit.filter((e) => !query.action || e.action === query.action)
        .slice(0, 200);
    },
  };
}
