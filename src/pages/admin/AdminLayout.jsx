import { useEffect, useState } from "react";
import logo from "../../assets/images/logo.png";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { icons } from "../../assets";
import { AssetIcon } from "../../components/Icon";
import { PageLoader } from "../../components/PageState";
import { USE_MOCK } from "../../config";
import { useAuth } from "../../context/AuthContext";
import { istClock, istDate } from "../../lib/format";
import "./admin.css";

const items = [
  { label: "Dashboard", to: "/admin", end: true, icon: icons.navDashboard },
  { label: "User approval", to: "/admin/users", icon: icons.navAlerts },
  { label: "Gateways", to: "/admin/gateways", icon: icons.navSettings },
  { label: "Enquiries", to: "/admin/enquiries", icon: icons.navAlerts },
  { label: "Connections", to: "/admin/connections", icon: icons.navReports },
  { label: "Audit log", to: "/admin/audit", icon: icons.navReports },
  { label: "Profile", to: "/admin/profile", icon: icons.navSettings },
];

function Clock() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return (
    <div className="live-datetime">
      <strong>{istDate(now)}</strong>
      <span>{istClock(now)}</span>
    </div>
  );
}

/** Route guard and shell for the Admin Portal: administrators only. */
export function AdminLayout() {
  const { user, ready, logout } = useAuth();
  const { pathname } = useLocation();
  if (!ready) return <PageLoader label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: pathname }} />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return (
    <div className="app-shell admin-shell">
      <aside className="sidebar">
        <div className="brand">
          <img className="brand-logo" src={logo} alt="RicemillMart.com" />
          <span className="brand-tag">Admin portal</span>
        </div>
        <nav aria-label="Admin navigation">
          {items.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              end={i.end}
              className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
            >
              <AssetIcon src={i.icon} />
              <span>{i.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="account">
          <div className="account-info">
            <span className="avatar">
              {(user.fullName || user.username || "?").slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.username}</strong>
              <span>Admin</span>
            </div>
          </div>
          <button
            className="logout"
            onClick={() => window.confirm("Log out of this device?") && logout()}
          >
            <AssetIcon src={icons.logout} size={18} />
            Log out
          </button>
        </div>
      </aside>
      <main id="main">
        <header className="topbar">
          <Clock />
          <span className="topbar-divider" />
          <strong>Admin Portal</strong>
        </header>
        {USE_MOCK && (
          <div className="banner demo" role="note">
            Demo mode: data is stored in this browser only.
          </div>
        )}
        <div className="page admin-page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
