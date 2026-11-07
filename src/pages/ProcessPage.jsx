import { images, machineImage } from "../assets";
import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { AutoReportPanel } from "../components/AutoReportPanel";
import { StatusBadge } from "../components/Icon";
import { useData } from "../context/DataContext";
import runtime_icon from "../assets/images/runtime-icon.svg";
import { MotorRating } from "../components/MotorRating";
// import power from "../assets/images/"
import {
  downloadCsv,
  fmtDuration,
  istDay,
  istHour,
  istStamp,
  istStamp12,
} from "../lib/format";
import { hasPowerQuality } from "../lib/machine";
import { statusOf } from "../lib/status";

const Row = ({ k, v }) => (
  <div>
    <span>{k}</span>
    <strong>{v}</strong>
  </div>
);
const RANGES = [
  { hours: 720, label: "Last Month", short: "Last Month" },
  { hours: 168, label: "Last Week", short: "Last Week" },
  { hours: 24, label: "Last 24 hours", short: "Last 24 hrs" },
  { hours: 12, label: "Last 12 hours", short: "Last 12 hrs" },
];
export default function ProcessPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { machines, plant, lastUpdate, saveMotorRating } = useData();
  const [windowHrs, setWindowHrs] = useState(24);
  const m = machines.find((x) => x.id === id);
  if (!m)
    return <Navigate to={machines[0] ? `/machines/${machines[0].id}` : "/"} replace />;
  const status = statusOf(m, lastUpdate);
  const on = status === "on";
  const pq = hasPowerQuality(m);
  const na = "N/A";
  const hour = istHour(lastUpdate);
  const rangeLabel = RANGES.find((r) => r.hours === windowHrs)?.short ?? "Last 24 hrs";
  const download = () =>
    downloadCsv(`${m.id}-${istDay(lastUpdate).replace(" ", "-")}.csv`, [
      ["Machine", m.name],
      ["Plant", m.plant],
      ["Generated (IST)", istStamp(lastUpdate)],
      [],
      ["Measurement", "Value", "Unit"],
      ["Status", status.toUpperCase(), ""],
      ["Average current", on ? m.current.toFixed(2) : na, "A"],
      ...(pq ? [["Power factor", on ? m.pf.toFixed(3) : na, ""]] : []),
      ["Active power", on ? m.kw.toFixed(2) : na, "kW"],
      ["Reactive power", on ? m.kvar.toFixed(2) : na, "kVAR"],
      ["Apparent power", on ? m.kva.toFixed(2) : na, "kVA"],
      ["Total active energy", m.totalKwh.toFixed(1), "kWh"],
      ["Total reactive energy", m.totalKvarh.toFixed(1), "kVARh"],
      ["Total apparent energy", m.totalKvah.toFixed(1), "kVAh"],
      ["Energy used (this run)", m.runKwh.toFixed(1), "kWh"],
      ["Total runtime", fmtDuration(m.totalRuntimeSec), ""],
      [],
      ["Hour (IST)", "Energy (kWh)"],
      ...m.hourlyKwh
        .slice(0, hour + 1)
        .map((v, h) => [`${String(h).padStart(2, "0")}:00`, v.toFixed(2)]),
    ]);
  return (
    <div className="content-page process-page">
      <aside className="machine-rail">
        <span>MACHINES · {plant.toUpperCase()}</span>
        {machines.map((x) => (
          <button
            key={x.id}
            className={x.id === m.id ? "selected" : ""}
            aria-current={x.id === m.id}
            onClick={() => navigate(`/machines/${x.id}`)}
          >
            <img src={machineImage(x.type, "rail")} alt="" />
            <strong>{x.name}</strong>
            <small>{statusOf(x, lastUpdate) === "on" ? "◎ ON" : "◷ OFF"}</small>
          </button>
        ))}
      </aside>
      <div className="process-content">
        <AutoReportPanel />
        <section className="machine-banner">
          <img src={images.machineBanner} alt="" />
          <div>
            <h1>{m.name}</h1>
            <p>
              {m.plant} · <MotorRating machine={m} canEdit onSave={saveMotorRating} /> ·
              Updated {istStamp12(m.updatedAt)}
            </p>
            <Row k="Motor ON Time " v={m.runStart ? istStamp12(m.runStart) : na} />
            <Row
              k="Motor OFF Time "
              v={on ? "RUNNING" : m.lastStop ? istStamp12(m.lastStop) : na}
            />
          </div>
          <StatusBadge status={status} />
          <div className="banner-actions">
            <select
              className="select-button"
              aria-label="Time range"
              value={windowHrs}
              onChange={(e) => setWindowHrs(Number(e.target.value))}
            >
              {RANGES.map((r) => (
                <option key={r.hours} value={r.hours}>
                  {r.label}
                </option>
              ))}
            </select>
            <button className="primary-button download" onClick={download}>
              ↓ &nbsp; Download report
            </button>
          </div>
        </section>

        <div className="analysis-grid">
          {pq && (
            <article className="info-card load-card">
              <div className="load-visual">
                <img src={images.loadGauge} alt="" />
                <div>
                  <span>Load factor</span>
                  <strong>
                    {on ? Math.round(m.loadFactor) : 0}
                    <small>%</small>
                  </strong>
                </div>
              </div>
              <div className="data-list compact">
                <Row
                  k={`Average Load Factor (${rangeLabel})`}
                  v={`${on ? Math.round(m.loadFactor) : 0} %`}
                />
              </div>
            </article>
          )}

          {pq && (
            <article className="info-card load-card">
              <div className="load-visual">
                <img src={images.powerfactor} alt="" />
                <div>
                  <span>Power factor</span>
                  <strong>{0.85}</strong>
                </div>
              </div>
              <div className="data-list compact">
                <Row k={`Average Power Factor (${rangeLabel})`} v={`0.85`} />
              </div>
            </article>
          )}
          <article className="info-card load-card">
            <div className="load-visual">
              <img src={runtime_icon} alt="" />
              <div>
                <span>Runtime</span>
                <strong>{on ? fmtDuration(m.runSec) : na}</strong>
              </div>
            </div>
            <div className="data-list compact">
              <Row
                k={`Total Runtime (${rangeLabel})`}
                v={on ? fmtDuration(m.runSec) : na}
              />
            </div>
          </article>
          <article className="info-card load-card">
            <div className="load-visual">
              {/* <img src={runtime_icon} alt="" /> */}
              <span className="energy-icon">ϟ</span>

              <div>
                <strong style={{ fontSize: 20, padding: 0 }}>
                  Units Consumed
                  <br />
                  423 kwh
                </strong>
              </div>

              <hr
                style={{
                  height: "70px",
                  border: "none",
                  borderLeft: "1px solid #dce3d8",
                  margin: "0 0px",
                }}
              />

              <div>
                <strong style={{ fontSize: 20 }}>
                  Actual Usage
                  <br />
                  246 kwh
                </strong>
              </div>
            </div>
            <div className="data-list compact">
              <Row k={`Energy usage in {${rangeLabel}}`} />
            </div>
          </article>
        </div>
      </div>
    </div>
  );
}
