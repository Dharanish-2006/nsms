import { icons, images } from "../assets";
import { useEffect, useState } from "react";
import { api } from "../api";
import { Field } from "../components/Field";
import { ThresholdPanel } from "../components/ThresholdPanel";
import { useAuth } from "../context/AuthContext";
import { useData } from "../context/DataContext";
import { fmt, fmtPhone } from "../lib/format";
const clean = (s) => s.replace(/\s|-/g, "").replace(/^\+?91/, "");
function PasswordPanel() {
  const { changePassword } = useAuth();
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [conf, setConf] = useState("");
  const [errors, setErrors] = useState({});
  const [ok, setOk] = useState(false);
  const submit = async () => {
    setOk(false);
    const er = {};
    if (!cur) er.cur = "Enter your current password";
    if (next.length < 8) er.next = "Use at least 8 characters";
    if (conf !== next) er.conf = "Passwords do not match";
    setErrors(er);
    if (Object.keys(er).length) return;
    const err = await changePassword(cur, next);
    if (err) return setErrors({ cur: err });
    setCur("");
    setNext("");
    setConf("");
    setOk(true);
  };
  return (
    <section className="settings-panel panel">
      <img src={images.settingsPassword} alt="" />
      <div className="settings-body">
        <h2>Change password</h2>
        <p>Use at least 8 characters. You stay signed in on this device.</p>
        <div className="settings-fields">
          <Field
            label="Current password"
            type="password"
            icon={icons.fieldLock}
            value={cur}
            onChange={setCur}
            error={errors.cur}
            autoComplete="current-password"
          />
          <Field
            label="New password"
            type="password"
            icon={icons.fieldLock}
            value={next}
            onChange={setNext}
            error={errors.next}
            autoComplete="new-password"
          />
          <Field
            label="Confirm new password"
            type="password"
            icon={icons.fieldLock}
            value={conf}
            onChange={setConf}
            error={errors.conf}
            autoComplete="new-password"
          />
        </div>
        <button className="primary-button compact-button" onClick={submit}>
          Update password
        </button>
        {ok && (
          <span className="ok-text" role="status">
            Password updated.
          </span>
        )}
      </div>
    </section>
  );
}
function PhonePanel() {
  const { user } = useAuth();
  const { phones, savePhone, removePhone } = useData();
  const admin = user?.role === "admin";
  const [confirmId, setConfirmId] = useState(null);
  const [editId, setEditId] = useState(null);
  const [editVal, setEditVal] = useState("");
  const [newVal, setNewVal] = useState("");
  const [error, setError] = useState("");
  const valid = (v) => /^\d{10}$/.test(clean(v));
  const confirming = phones.find((p) => p.id === confirmId);
  // Runs a change on the server; shows the server's message if it is refused.
  const run = async (fn) => {
    try {
      await fn();
      setError("");
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };
  const add = async () => {
    if (!valid(newVal)) return setError("Enter a valid 10-digit number");
    if (phones.some((p) => p.digits === clean(newVal)))
      return setError("That number is already added");
    const saved = await run(() =>
      savePhone({
        digits: clean(newVal),
        label: phones.length ? "Alert contact" : "Primary contact",
      }),
    );
    if (saved) setNewVal("");
  };
  return (
    <section className="settings-panel panel phones">
      <img src={images.settingsPhone} alt="" />
      <div className="settings-body">
        <div className="settings-title">
          <div>
            <h2>Alert phone numbers</h2>
            <p>These numbers receive alert messages.</p>
          </div>
          <span className="admin-only">▣ Admins only</span>
        </div>

        {phones.map((p) => (
          <div className="phone-row" key={p.id}>
            <span className="phone-icon">⌕</span>
            {editId === p.id ? (
              <input
                className="phone-edit"
                aria-label="Phone number"
                value={editVal}
                onChange={(e) => setEditVal(e.target.value)}
                autoFocus
              />
            ) : (
              <div>
                <strong>{fmtPhone(p.digits)}</strong>
                <small>{p.label}</small>
              </div>
            )}
            {admin &&
              (editId === p.id ? (
                <>
                  <button
                    onClick={async () => {
                      if (!valid(editVal))
                        return setError("Enter a valid 10-digit number");
                      const saved = await run(() =>
                        savePhone({ ...p, digits: clean(editVal) }),
                      );
                      if (saved) setEditId(null);
                    }}
                  >
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setEditId(null);
                      setError("");
                    }}
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => {
                      setEditId(p.id);
                      setEditVal(p.digits);
                      setError("");
                    }}
                  >
                    Edit
                  </button>
                  <button className="danger" onClick={() => setConfirmId(p.id)}>
                    Remove
                  </button>
                </>
              ))}
          </div>
        ))}

        {confirming && (
          <div className="remove-confirm">
            <strong>Remove {fmtPhone(confirming.digits)}?</strong>
            <span>This number will stop receiving alerts.</span>
            <button onClick={() => setConfirmId(null)}>Keep</button>
            <button
              className="danger"
              onClick={async () => {
                await run(() => removePhone(confirming.id));
                setConfirmId(null);
              }}
            >
              Yes, remove
            </button>
          </div>
        )}

        {admin && (
          <div className="add-phone">
            <span>⌕</span>
            <input
              aria-label="New phone number"
              placeholder="+91  Enter 10-digit number"
              inputMode="tel"
              value={newVal}
              onChange={(e) => setNewVal(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()}
            />
            <button className="primary-button" onClick={add}>
              ＋ Add number
            </button>
          </div>
        )}
        {error && (
          <small className="form-error" role="alert">
            {error}
          </small>
        )}
      </div>
    </section>
  );
}
function NotificationPanel() {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const [prefs, setPrefs] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    api.notifications
      .get()
      .then((n) => !cancelled && setPrefs(n))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, []);
  const toggle = async (key) => {
    const next = { ...prefs, [key]: !prefs[key] };
    setPrefs(next); // optimistic; rolled back if the server refuses
    try {
      setPrefs(await api.notifications.save(next));
      setError("");
    } catch (err) {
      setPrefs(prefs);
      setError(err.message);
    }
  };
  return (
    <section className="panel notify-panel">
      <div className="settings-title">
        <div>
          <h2>Notifications</h2>
          <p>Choose what the system sends automatically.</p>
        </div>
        <span className="admin-only">▣ Admins only</span>
      </div>
      {prefs && (
        <>
          <label className="toggle-row">
            <span>
              Alerts
              <small>Send alert messages to the saved phone numbers.</small>
            </span>
            <input
              type="checkbox"
              checked={prefs.alertsEnabled}
              disabled={!admin}
              onChange={() => toggle("alertsEnabled")}
            />
            <i aria-hidden="true" />
          </label>
          <label className="toggle-row">
            <span>
              Automatic reports
              <small>Send the plant report automatically on schedule.</small>
            </span>
            <input
              type="checkbox"
              checked={prefs.autoReports}
              disabled={!admin}
              onChange={() => toggle("autoReports")}
            />
            <i aria-hidden="true" />
          </label>
        </>
      )}
      {error && (
        <small className="form-error" role="alert">
          {error}
        </small>
      )}
    </section>
  );
}
function PendingPanel() {
  const [pending, setPending] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    api.users
      .list("pending")
      .then((list) => !cancelled && setPending(list))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, []);
  const act = async (fn, id) => {
    try {
      await fn(id);
      setPending(await api.users.list("pending"));
      setError("");
    } catch (err) {
      setError(err.message);
    }
  };
  if (pending.length === 0 && !error) return null;
  return (
    <section className="panel pending-panel">
      <h2>Accounts waiting for approval</h2>
      {error && (
        <small className="form-error" role="alert">
          {error}
        </small>
      )}
      {pending.map((u) => (
        <div className="phone-row" key={u.id}>
          <span className="phone-icon">{u.fullName.slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>
              {u.fullName} · {u.username}
            </strong>
            <small>
              Requested {u.role === "admin" ? "Admin" : "User"} access · {u.email} ·{" "}
              {u.mobile ? fmtPhone(u.mobile) : "No phone"}
            </small>
          </div>
          <button onClick={() => act(api.users.approve, u.id)}>Approve</button>
          <button className="danger" onClick={() => act(api.users.reject, u.id)}>
            Reject
          </button>
        </div>
      ))}
    </section>
  );
}
function ThresholdCard() {
  const { thresholds } = useData();
  const { user } = useAuth();
  const [editing, setEditing] = useState(false);
  const pf =
    thresholds.find((t) => t.param === "powerFactor" && t.machineId === "all") ??
    thresholds.find((t) => t.param === "powerFactor");
  const range = (lo, hi) => `${fmt(lo)} – ${fmt(hi)}`;
  const critical = pf && pf.critical !== null ? range(0, pf.critical) : "No limit";
  const warning =
    pf && pf.warning !== null ? range(pf.critical ?? 0, pf.warning) : "No limit";
  return (
    <>
      <section className="settings-panel panel threshold-card">
        <img src={images.settingsThreshold} alt="" />
        <div>
          <h2>Threshold Settings</h2>
          <p>Set value ranges for Power Factor alerts.</p>
        </div>
        <div className="threshold-chips">
          <div className="threshold-chip critical">
            <span aria-hidden="true">⚠</span>
            <div>
              <strong>Critical</strong>
              <span>{critical}</span>
            </div>
          </div>
          <div className="threshold-chip warning">
            <span aria-hidden="true">ⓘ</span>
            <div>
              <strong>Warning</strong>
              <span>{warning}</span>
            </div>
          </div>
        </div>
        {user?.role === "admin" && (
          <button className="edit-btn" onClick={() => setEditing(!editing)}>
            {editing ? "Close" : "✎ Edit"}
          </button>
        )}
      </section>
      {editing && <ThresholdPanel />}
    </>
  );
}
export default function SettingsPage() {
  const { user, logout } = useAuth();
  return (
    <div className="content-page standard-page settings-page">
      <div className="page-heading">
        <div>
          <h1>Settings</h1>
          <p>Your account and who gets alert messages.</p>
        </div>
      </div>
      <PasswordPanel />
      <PhonePanel />
      <NotificationPanel />
      <ThresholdCard />
      {user?.role === "admin" && <PendingPanel />}
      <section className="settings-panel panel logout-panel">
        <img src={images.settingsLogout} alt="" />
        <div>
          <h2>Log out</h2>
          <p>End your session on this device. You will be asked to confirm.</p>
        </div>
        <button onClick={() => window.confirm("Log out of this device?") && logout()}>
          Log out
        </button>
      </section>
    </div>
  );
}
