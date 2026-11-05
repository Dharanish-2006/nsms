import { icons, images, machineImage } from "../assets";
import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { EnergyChart, RuntimeBand } from "../components/Charts";
import { AssetIcon, StatusBadge } from "../components/Icon";
import { useData } from "../context/DataContext";
import {
  downloadCsv,
  fmt,
  fmtDuration,
  istDay,
  istHour,
  istStamp,
  istTime,
} from "../lib/format";
import { statusOf } from "../lib/status";
function InfoCard({ title, icon, children }) {
  return (
    <article className="info-card">
      <h3>
        <span>
          <AssetIcon src={icon} size={20} />
        </span>
        {title}
      </h3>
      {children}
    </article>
  );
}
const Row = ({ k, v }) => (
  <div>
    <span>{k}</span>
    <strong>{v}</strong>
  </div>
);
export default function ProcessPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { machines, plant, lastUpdate } = useData();
  const [windowHrs, setWindowHrs] = useState(24);
  const m = machines.find((x) => x.id === id);
  if (!m)
    return <Navigate to={machines[0] ? `/machines/${machines[0].id}` : "/"} replace />;
  const status = statusOf(m, lastUpdate);
  const on = status === "on";
  const na = "N/A";
  const hour = istHour(lastUpdate);
  const startHour = Math.max(0, hour - windowHrs + 1);
  const series = m.hourlyKwh.slice(startHour, hour + 1);
  const download = () =>
    downloadCsv(`${m.id}-${istDay(lastUpdate).replace(" ", "-")}.csv`, [
      ["Machine", m.name],
      ["Plant", m.plant],
      ["Generated (IST)", istStamp(lastUpdate)],
      [],
      ["Measurement", "Value", "Unit"],
      ["Status", status.toUpperCase(), ""],
      ["Average current", on ? m.current.toFixed(2) : na, "A"],
      ["Power factor", on ? m.pf.toFixed(3) : na, ""],
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
        <section className="machine-banner">
          <img src={images.machineBanner} alt="" />
          <div>
            <h1>{m.name}</h1>
            <p>
              {m.plant} · SLEC MFM384 meter · Updated {istTime(m.updatedAt)} IST
            </p>
          </div>
          <StatusBadge status={status} />
          <select
            className="select-button"
            aria-label="Time range"
            value={windowHrs}
            onChange={(e) => setWindowHrs(Number(e.target.value))}
          >
            <option value={24}>Last 24 hours</option>
            <option value={12}>Last 12 hours</option>
            <option value={6}>Last 6 hours</option>
          </select>
          <button className="primary-button download" onClick={download}>
            ↓ &nbsp; Download report
          </button>
        </section>

        <div className="analysis-grid">
          <InfoCard title="Electrical measurements" icon={icons.cardElectrical}>
            <div className="data-list">
              <Row k="Average current" v={on ? `${fmt(m.current)} A` : na} />
              <Row k="Power factor" v={on ? fmt(m.pf, 3) : na} />
              <Row k="Active power" v={on ? `${fmt(m.kw)} kW` : na} />
              <Row k="Reactive power" v={on ? `${fmt(m.kvar)} kVAR` : na} />
              <Row k="Apparent power" v={on ? `${fmt(m.kva)} kVA` : na} />
            </div>
            <p className="info-note">
              ⓘ &nbsp; Different electrical quantities. Do not add them together.
            </p>
          </InfoCard>

          <InfoCard title="Energy and demand" icon={icons.cardEnergy}>
            <div className="data-list compact">
              <Row
                k="Total active energy"
                v={
                  <span className="counter">
                    {m.totalKwh.toFixed(1).padStart(8, "0")} <small>kWh</small>
                  </span>
                }
              />
              <Row k="Total reactive energy" v={`${fmt(m.totalKvarh, 1)} kVARh`} />
              <Row k="Total apparent energy" v={`${fmt(m.totalKvah, 1)} kVAh`} />
              <Row k="Maximum demand" v={na} />
              <Row k="Energy used (this run)" v={on ? `${fmt(m.runKwh, 1)} kWh` : na} />
            </div>
            <p className="chart-label">Energy used per hour today (kWh)</p>
            <EnergyChart values={series} startHour={startHour} />
          </InfoCard>

          <InfoCard title="Operating performance" icon={icons.cardPerformance}>
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
              <Row k="Total runtime" v={fmtDuration(m.totalRuntimeSec)} />
              <Row k="Running duration (this run)" v={on ? fmtDuration(m.runSec) : na} />
              <Row
                k="Average power factor (this run)"
                v={on && m.avgPfRun ? fmt(m.avgPfRun, 3) : na}
              />
            </div>
            <RuntimeBand hours={m.hourOn} />
          </InfoCard>

          <InfoCard title="Motor information" icon={icons.cardMotor}>
            <div className="data-list">
              <Row k="Motor name" v={m.name} />
              <Row k="Motor ON" v={m.runStart ? istStamp(m.runStart) : na} />
              <Row k="Motor OFF (last stop)" v={m.lastStop ? istStamp(m.lastStop) : na} />
              <Row k="Motor status" v={<StatusBadge status={status} />} />
            </div>
            <p className="success-note">
              ◷ &nbsp; Offline machines show Unknown, never OFF, unless the system
              confirms the stop.
            </p>
          </InfoCard>
        </div>
      </div>
    </div>
  );
}
