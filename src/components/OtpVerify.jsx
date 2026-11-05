import { useEffect, useState } from "react";
import { icons } from "../assets";
import { useAuth } from "../context/AuthContext";
import { USE_MOCK } from "../config";
import { Field } from "./Field";

const COOLDOWN_S = 30;

/**
 * A contact field with Send OTP -> enter code -> Verify. `target` is the
 * normalised value sent to the server and `valid` says whether it is well
 * formed. Changing the value drops any earlier verification. The server issues
 * the proof `token`; verification is never decided in the browser.
 */
export function OtpVerify({
  channel,
  label,
  icon,
  value,
  onChange,
  target,
  valid,
  verified,
  onVerified,
  error,
  autoComplete,
  inputMode,
}) {
  const { sendOtp, verifyOtp } = useAuth();
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [demoCode, setDemoCode] = useState("");
  const [wait, setWait] = useState(0);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (wait <= 0) return undefined;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const change = (v) => {
    onChange(v);
    if (sent || verified) {
      setSent(false);
      setCode("");
      setMsg("");
      setDemoCode("");
      onVerified(null);
    }
  };

  const send = async () => {
    if (!valid)
      return setMsg(`Enter a valid ${channel === "email" ? "email" : "number"} first`);
    setBusy(true);
    const res = await sendOtp(channel, target);
    setBusy(false);
    if (res.error) return setMsg(res.error);
    setSent(true);
    setCode("");
    setMsg("");
    setWait(COOLDOWN_S);
    setDemoCode(USE_MOCK ? (res.demoCode ?? "") : "");
  };

  const verify = async () => {
    if (!/^\d{6}$/.test(code)) return setMsg("Enter the 6-digit code");
    setBusy(true);
    const res = await verifyOtp(channel, target, code);
    setBusy(false);
    if (res.error) return setMsg(res.error);
    setMsg("");
    onVerified(res.token);
  };

  const sendLabel = wait > 0 ? `Resend in ${wait}s` : sent ? "Resend OTP" : "Send OTP";

  return (
    <>
      <Field
        label={label}
        icon={icon}
        value={value}
        onChange={change}
        error={error}
        autoComplete={autoComplete}
        inputMode={inputMode}
        action={
          verified ? (
            <span className="otp-badge">Verified</span>
          ) : (
            <button
              type="button"
              className="otp-action"
              onClick={send}
              disabled={busy || wait > 0}
            >
              {sendLabel}
            </button>
          )
        }
      />
      {sent && !verified && (
        <>
          <Field
            label={`${label} OTP`}
            icon={icons.fieldLock}
            value={code}
            onChange={(v) => setCode(v.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            maxLength={6}
            autoComplete="one-time-code"
            placeholder="6-digit code"
            error={msg}
            action={
              <button
                type="button"
                className="otp-action"
                onClick={verify}
                disabled={busy}
              >
                Verify
              </button>
            }
          />
          {demoCode && <p className="otp-demo">Demo mode: your code is {demoCode}</p>}
        </>
      )}
      {!sent && !verified && msg && <small className="otp-msg">{msg}</small>}
    </>
  );
}
