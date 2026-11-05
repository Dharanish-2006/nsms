import { icons, images } from "../assets";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { AssetIcon } from "../components/Icon";
import { Field } from "../components/Field";
import { USE_MOCK, config } from "../config";
import { useAuth } from "../context/AuthContext";
function CompanyPanel() {
  return (
    <section className="company-panel">
      <div className="auth-brand">
        <AssetIcon src={icons.brandAuth} size={44} />
        <div>
          <strong>Rice Mill Monitor</strong>
          <span>Energy &amp; motor monitoring</span>
        </div>
      </div>
      <div className="company-copy">
        <h1>{config.company.name}</h1>
        <p>Live status, power quality and energy use for every motor in your mill.</p>
        <ul>
          <li>
            <AssetIcon src={icons.contactAddress} size={20} />
            {config.company.address}
          </li>
          <li>
            <AssetIcon src={icons.contactPhone} size={20} />
            {config.company.phone}
          </li>
          <li>
            <AssetIcon src={icons.contactMail} size={20} />
            {config.company.email}
          </li>
        </ul>
      </div>
      <img className="auth-mill" src={images.authMill} alt="Rice mill" />
    </section>
  );
}
function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = useLocation().state?.from ?? "/";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const err = await login(username, password);
    setBusy(false);
    if (err) return setError(err);
    navigate(from, { replace: true });
  };
  return (
    <form className="auth-card" onSubmit={submit} noValidate>
      <h2>Sign in</h2>
      <p>Use your mill account to continue.</p>
      <Field
        label="Username"
        value={username}
        onChange={setUsername}
        autoComplete="username"
      />
      <Field
        label="Password"
        type="password"
        icon={icons.fieldLock}
        value={password}
        onChange={setPassword}
        autoComplete="current-password"
        error={error}
      />
      <button className="primary-button" type="submit" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
      <p className="auth-switch">
        New here? <Link to="/register">Create an account</Link>
      </p>
    </form>
  );
}
function RegisterForm() {
  const { register } = useAuth();
  const [f, setF] = useState({
    fullName: "",
    username: "",
    email: "",
    mobile: "",
    password: "",
    confirm: "",
  });
  const [role, setRole] = useState("user");
  const [errors, setErrors] = useState({});
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const set = (k) => (v) => setF((p) => ({ ...p, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    const mobile = f.mobile.replace(/\s|-/g, "").replace(/^\+?91/, "");
    const er = {};
    if (!f.fullName.trim()) er.fullName = "Enter your full name";
    if (f.username.trim().length < 3) er.username = "At least 3 characters";
    if (!/^\S+@\S+\.\S+$/.test(f.email)) er.email = "Enter a valid email";
    if (!/^\d{10}$/.test(mobile)) er.mobile = "Enter a valid 10-digit number";
    if (f.password.length < 8) er.password = "Use at least 8 characters";
    if (f.confirm !== f.password) er.confirm = "Passwords do not match";
    setErrors(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    const err = await register({ ...f, mobile, role });
    setBusy(false);
    if (err) return setErrors({ username: err });
    setDone(true);
  };
  if (done)
    return (
      <div className="auth-card register">
        <h2>Request sent</h2>
        <p>
          Your account was created. An administrator needs to approve it before you can
          sign in.
        </p>
        <Link className="primary-button as-link" to="/login">
          Back to sign in
        </Link>
      </div>
    );
  return (
    <form className="auth-card register" onSubmit={submit} noValidate>
      <h2>Create account</h2>
      <p>An administrator approves new accounts.</p>
      <div className="account-type">
        <span>Account type</span>
        <div>
          <button
            type="button"
            className={role === "admin" ? "selected" : ""}
            onClick={() => setRole("admin")}
          >
            Admin
          </button>
          <button
            type="button"
            className={role === "user" ? "selected" : ""}
            onClick={() => setRole("user")}
          >
            User
          </button>
        </div>
      </div>
      <div className="form-grid">
        <Field
          label="Full name"
          value={f.fullName}
          onChange={set("fullName")}
          error={errors.fullName}
        />
        <Field
          label="Username"
          value={f.username}
          onChange={set("username")}
          error={errors.username}
          autoComplete="username"
        />
        <Field
          label="Email"
          icon={icons.fieldMail}
          value={f.email}
          onChange={set("email")}
          error={errors.email}
          autoComplete="email"
        />
        <Field
          label="Mobile number"
          icon={icons.fieldPhone}
          value={f.mobile}
          onChange={set("mobile")}
          error={errors.mobile}
          autoComplete="tel"
        />
      </div>
      <Field
        label="Password"
        type="password"
        icon={icons.fieldLock}
        value={f.password}
        onChange={set("password")}
        error={errors.password}
        autoComplete="new-password"
      />
      <Field
        label="Confirm password"
        type="password"
        icon={icons.fieldLock}
        value={f.confirm}
        onChange={set("confirm")}
        error={errors.confirm}
        autoComplete="new-password"
      />
      <button className="primary-button" type="submit" disabled={busy}>
        {busy ? "Creating…" : "Create account"}
      </button>
      <p className="auth-switch">
        Already registered? <Link to="/login">Back to sign in</Link>
      </p>
    </form>
  );
}
export default function AuthPage({ mode }) {
  const { user, ready } = useAuth();
  if (ready && user) return <Navigate to="/" replace />;
  return (
    <div className="auth-layout">
      <CompanyPanel />
      <div className="auth-form-wrap">
        {mode === "login" ? <LoginForm /> : <RegisterForm />}
      </div>
    </div>
  );
}
