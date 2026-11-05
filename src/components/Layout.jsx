import { useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { icons } from "../assets";
import { USE_MOCK } from "../config";
import { useAuth } from "../context/AuthContext";
import { DataProvider, useData } from "../context/DataContext";
import { istDate, istTime } from "../lib/format";
import { AssetIcon } from "./Icon";
import { ErrorPanel, PageLoader } from "./PageState";

const navItems = [
  { label: "Dashboard", to: "/", icon: icons.navDashboard },
  { label: "Reports", to: "/reports", icon: icons.navReports },
  { label: "Alerts", to: "/alerts", icon: icons.navAlerts },
  { label: "Settings", to: "/settings", icon: icons.navSettings },
];

function titleFor(path) {
  if (path.startsWith("/machines")) return "Process Analysis";
  if (path.startsWith("/alerts")) return "Alerts & Thresholds";
  if (path.startsWith("/reports")) return "Reports";
  if (path.startsWith("/settings")) return "Settings";
  return "Dashboard";
}

function Sidebar() {
  const { user, logout } = useAuth();
  const { activeAlertCount } = useData();
  const { pathname } = useLocation();

  const confirmLogout = () => {
    if (window.confirm("Log out of this device?")) logout();
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <AssetIcon src={icons.brand} size={48} />
        <div>
          <strong>Rice Mill Monitor</strong>
          <span>Energy &amp; motors</span>
        </div>
      </div>

      <nav aria-label="Primary navigation">
        {navItems.map((item) => {
          // Machine detail pages belong to the Dashboard section.
          const forced = item.to === "/" && pathname.startsWith("/machines");
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                isActive || forced ? "nav-item active" : "nav-item"
              }
            >
              <AssetIcon src={item.icon} />
              <span>{item.label}</span>
              {item.to === "/alerts" && activeAlertCount > 0 && (
                <b className="nav-badge" aria-label={`${activeAlertCount} active alerts`}>
                  {activeAlertCount}
                </b>
              )}
            </NavLink>
          );
        })}
      </nav>

      <div className="account">
        <div className="account-info">
          <span className="avatar">
            {(user?.fullName || user?.username || "?").slice(0, 2).toUpperCase()}
          </span>
          <div>
            <strong>{user?.username}</strong>
            <span>{user?.role === "admin" ? "Admin" : "User"}</span>
          </div>
        </div>
        <button className="logout" onClick={confirmLogout}>
          <AssetIcon src={icons.logout} size={18} />
          Log out
        </button>
      </div>
    </aside>
  );
}

function Topbar() {
  const { plant, plants, setPlant, lastUpdate } = useData();
  const { pathname } = useLocation();
  const [now, setNow] = useState(() => Date.now());
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <header className="topbar">
      <div className="live-datetime">
        <strong>{istDate(now)}</strong>
        <span>{istTime(now)}</span>
      </div>
      <span className="topbar-divider" />
      <strong>{titleFor(pathname)}</strong>
      <div className="chip-wrap">
        <button
          className="plant-chip"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          <AssetIcon src={icons.plant} size={18} />
          {plant}
          <AssetIcon src={icons.chevronSm} size={16} />
        </button>
        {open && (
          <div className="plant-menu chip-menu" role="listbox">
            {plants.map((p) => (
              <button
                key={p}
                role="option"
                aria-selected={p === plant}
                onClick={() => {
                  setPlant(p);
                  setOpen(false);
                }}
              >
                {p} {p === plant && <span>Selected</span>}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="updated">
        <i />
        {lastUpdate ? `Last updated ${istTime(lastUpdate)} IST` : "Waiting for data…"}
      </div>
    </header>
  );
}

function Banners() {
  const { offline, error } = useData();
  return (
    <>
      {USE_MOCK && (
        <div className="banner demo" role="note">
          Demo mode: readings are simulated and accounts are stored in this browser only.
        </div>
      )}
      {offline && (
        <div className="banner offline" role="alert">
          Connection problem: {error || "retrying"}. Showing the last values received.
        </div>
      )}
    </>
  );
}

function Shell() {
  const { status, error, reload } = useData();
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Sidebar />
      <main id="main">
        <Topbar />
        <Banners />
        <div className="page">
          {status === "loading" && <PageLoader label="Loading plant data…" />}
          {status === "error" && <ErrorPanel message={error} onRetry={reload} />}
          {status === "ready" && <Outlet />}
        </div>
      </main>
    </div>
  );
}

/** Route guard: signed-out visitors go to /login; signed-in ones get live data. */
export function Layout() {
  const { user, ready } = useAuth();
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  if (!ready) return <PageLoader label="Checking your session…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: pathname }} />;
  return (
    <DataProvider>
      <Shell />
    </DataProvider>
  );
}
