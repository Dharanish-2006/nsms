import { icons, images } from "../assets";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { AssetIcon } from "../components/Icon";
import { Field } from "../components/Field";
import { OtpVerify } from "../components/OtpVerify";
import { config } from "../config";
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
        placeholder={"email or phone number"}
      />
      <Field
        label="Password"
        type="password"
        placeholder={"********"}
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
/** Which field a server error message belongs to (the server sends one plain message). */
function fieldFor(message) {
  if (/password/i.test(message)) return "password";
  if (/mobile|phone/i.test(message)) return "mobile";
  if (/email/i.test(message)) return "email";
  return "username";
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
  const [errors, setErrors] = useState({});
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [usePhone, setUsePhone] = useState(false);
  const [emailToken, setEmailToken] = useState(null);
  const [phoneToken, setPhoneToken] = useState(null);
  const mobileDigits = f.mobile.replace(/\s|-/g, "").replace(/^\+?91/, "");
  const set = (k) => (v) => setF((p) => ({ ...p, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    const mobile = usePhone ? mobileDigits : "";
    const er = {};
    if (!f.fullName.trim()) er.fullName = "Enter your full name";
    if (f.username.trim().length < 3) er.username = "At least 3 characters";
    if (!/^\S+@\S+\.\S+$/.test(f.email)) er.email = "Enter a valid email";
    if (!emailToken) er.email ||= "Verify your email with the OTP";
    if (usePhone) {
      if (!/^\d{10}$/.test(mobile)) er.mobile = "Enter a valid 10-digit number";
      else if (!phoneToken) er.mobile = "Verify your phone with the OTP";
    }
    if (f.password.length < 8) er.password = "Use at least 8 characters";
    if (f.confirm !== f.password) er.confirm = "Passwords do not match";
    setErrors(er);
    if (Object.keys(er).length) return;
    setBusy(true);
    const { confirm: _c, ...rest } = f;
    const err = await register({
      ...rest,
      mobile,
      role: "user", // plant owners register here; admins are created by us
      emailToken,
      ...(usePhone ? { phoneToken } : {}),
    });
    setBusy(false);
    if (err) return setErrors({ [fieldFor(err)]: err, form: err });
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
      <p>Plant owners register here. An administrator approves new accounts.</p>
      <div className="form-grid">
        <Field
          label="Username"
          placeholder={"your name"}
          value={f.username}
          onChange={set("username")}
          error={errors.username}
          autoComplete="username"
        />
      </div>
      <OtpVerify
        channel="email"
        label="Email"

        icon={icons.fieldMail}
        value={f.email}
        onChange={set("email")}
        target={f.email.trim()}
        valid={/^\S+@\S+\.\S+$/.test(f.email.trim())}
        verified={Boolean(emailToken)}
        onVerified={setEmailToken}
        error={errors.email}
        autoComplete="email"
      />
      <label className="toggle-row">
        <span>Add a phone number (optional)</span>
        <input
          type="checkbox"
          role="switch"
          checked={usePhone}
          onChange={(e) => {
            setUsePhone(e.target.checked);
            if (!e.target.checked) setPhoneToken(null);
          }}
        />
        <i aria-hidden="true" />
      </label>
      {usePhone && (
        <OtpVerify
          channel="phone"
          label="Mobile number"
          icon={icons.fieldPhone}
          value={f.mobile}
          onChange={set("mobile")}
          target={mobileDigits}
          valid={/^\d{10}$/.test(mobileDigits)}
          verified={Boolean(phoneToken)}
          onVerified={setPhoneToken}
          error={errors.mobile}
          autoComplete="tel"
          inputMode="tel"
        />
      )}
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
      {errors.form && (
        <small className="form-error" role="alert">
          {errors.form}
        </small>
      )}
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
