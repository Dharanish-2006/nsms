import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { Notice } from "./ui";

export default function AdminProfile() {
  const { user, changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setDone(false);
    if (next.length < 8) return setError("Use at least 8 characters.");
    const err = await changePassword(current, next);
    setError(err ?? "");
    if (!err) {
      setDone(true);
      setCurrent("");
      setNext("");
    }
  };
  return (
    <>
      <h1>Profile</h1>
      <section className="adm-card">
        <dl className="adm-dl">
          <dt>Name</dt>
          <dd>{user.fullName || "—"}</dd>
          <dt>Username</dt>
          <dd>{user.username}</dd>
          <dt>Email</dt>
          <dd>{user.email || "—"}</dd>
          <dt>Role</dt>
          <dd>Administrator</dd>
        </dl>
      </section>
      <form className="adm-card adm-form" onSubmit={submit}>
        <h2>Change password</h2>
        <label className="adm-field">
          Current password
          <input
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </label>
        <label className="adm-field">
          New password
          <input
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </label>
        <Notice error={error} />
        {done && <p className="adm-note">Password changed.</p>}
        <button className="adm-btn primary">Update password</button>
      </form>
    </>
  );
}
