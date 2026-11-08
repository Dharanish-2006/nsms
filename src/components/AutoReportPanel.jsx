import { useEffect, useState } from "react";
import { api } from "../api";

const FREQUENCIES = [
  { value: "day", label: "Every day" },
  { value: "week", label: "Every week" },
  { value: "month", label: "Every month" },
];

export function AutoReportPanel() {
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
  const update = async (patch) => {
    const before = prefs;
    const next = { ...prefs, ...patch };
    setPrefs(next); // optimistic; rolled back if the server refuses
    try {
      setPrefs(await api.notifications.save(next));
      setError("");
    } catch (err) {
      setPrefs(before);
      setError(err.message);
    }
  };
  return (
    <aside className="panel auto-report">
      <h2>Automatic report</h2>
      <p>Email this report to you on its own, without anyone pressing a button.</p>
      {prefs && (
        <>
          <label className="toggle-row">
            <span>Send automatically</span>
            <input
              type="checkbox"
              checked={prefs.autoReports}
              onChange={() => update({ autoReports: !prefs.autoReports })}
            />
            <i aria-hidden="true" />
          </label>
          <label className="auto-report-when">
            <span>Send</span>
            <select
              value={prefs.reportFrequency}
              disabled={!prefs.autoReports}
              onChange={(e) => update({ reportFrequency: e.target.value })}
            >
              {FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
      {error && (
        <small className="form-error" role="alert">
          {error}
        </small>
      )}
    </aside>
  );
}
