import { useState } from "react";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { USE_MOCK } from "../../config";
import { useAuth } from "../../context/AuthContext";
import { PageLoader } from "../../components/PageState";
import "./admin.css";

const items = [
  { label: "Dashboard", to: "/admin", end: true },
  { label: "User approval", to: "/admin/users" },
  { label: "Gateways", to: "/admin/gateways" },
  { label: "Connections", to: "/admin/connections" },
  { label: "Audit log", to: "/admin/audit" },
  { label: "Profile", to: "/admin/profile" },
];

/** Route guard for the Admin Portal: administrators only. */
export function AdminLayout() {
  const { user, ready, logout } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  if (!ready) return <PageLoader label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: pathname }} />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return (
    <div className="adm-shell">
      <header className="adm-top">
        <button className="adm-menu" aria-label="Menu" onClick={() => setOpen(!open)}>
          ☰
        </button>
        <strong>Smart Mill · Admin</strong>
        <span className="adm-spacer" />
        <span className="adm-user">{user.fullName || user.username}</span>
        <button
          className="adm-btn"
          onClick={() => window.confirm("Log out of this device?") && logout()}
        >
          Log out
        </button>
      </header>
      <nav className={open ? "adm-nav open" : "adm-nav"} aria-label="Admin navigation">
        {items.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            end={i.end}
            onClick={() => setOpen(false)}
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            {i.label}
          </NavLink>
        ))}
      </nav>
      <main className="adm-main">
        {USE_MOCK && (
          <div className="banner demo" role="note">
            Demo mode: data is stored in this browser only.
          </div>
        )}
        <Outlet />
      </main>
    </div>
  );
}
