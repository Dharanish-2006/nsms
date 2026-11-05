import { icons, images, machineImage } from "../assets";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { statusOf } from "../lib/status";
import { ConsumptionBars } from "../components/Charts";
import { AssetIcon, StatusBadge } from "../components/Icon";
import { useData } from "../context/DataContext";
import { fmt, fmtDuration } from "../lib/format";
const todayKwh = (m) => m.hourlyKwh.reduce((a, b) => a + b, 0);
// "Actual usage" is the energy used in the machine's current run.
const actualKwh = (m) => (m.runKwh > 0 ? m.runKwh : 0);
function MachineCard({ m, now, onOpen }) {
  const status = statusOf(m, now);
  const on = status === "on";
  const kwh = todayKwh(m);
  const actual = actualKwh(m);
  return (
    <button
      className="machine-card"
      aria-label={`Open ${m.name} process analysis`}
      onClick={onOpen}
    >
      <div className="machine-heading">
        <div className="machine-art">
          <img src={machineImage(m.type, "card")} alt="" />
          <span className={on ? "machine-dot on" : "machine-dot"} />
        </div>
        <div>
          <h3>{m.name}</h3>
          <StatusBadge status={status} />
        </div>
      </div>

      <div className="machine-stats">
        <div className="machine-stat">
          <span>Status</span>
          <StatusBadge status={status} />
        </div>
        <div className="machine-stat">
          <span className="stat-title">
            <b className="line-icon clock" />
            Runtime
          </span>
          <strong>{m.todaySec > 0 ? fmtDuration(m.todaySec) : "--"}</strong>
        </div>
        <div className="machine-stat">
          <span className="stat-title">
            <b className="line-icon gauge" />
            Power Factor
          </span>
          <strong>{on ? fmt(m.pf) : "N/A"}</strong>
        </div>
        <div className="machine-stat">
          <span className="stat-title">
            <b className="line-icon battery" />
            Load Factor
          </span>
          <strong>{on ? Math.round(m.loadFactor) : 0} %</strong>
          <div className="load-track">
            <i style={{ width: `${on ? Math.min(m.loadFactor, 100) : 0}%` }} />
          </div>
        </div>
        <div className="machine-stat">
          <span className="stat-title">
            <b className="bolt">ϟ</b>Power Consumed
          </span>
          <strong>{kwh > 0 ? `${fmt(kwh, 1)} kWh` : "-- kWh"}</strong>
        </div>
        <div className="machine-stat">
          <span className="stat-title">
            <b className="line-icon layers" />
            Actual Usage
          </span>
          <strong>{actual > 0 ? `${fmt(actual, 1)} kWh` : "-- kWh"}</strong>
        </div>
      </div>
    </button>
  );
}
export default function DashboardPage() {
  const { machines, plant, plants, setPlant, lastUpdate } = useData();
  const navigate = useNavigate();
  const [menu, setMenu] = useState(false);
  const total = machines.reduce((s, m) => s + todayKwh(m), 0);
  const actualTotal = machines.reduce((s, m) => s + actualKwh(m), 0);
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <div>
            <h1>Dashboard</h1>
            <p>Today at a glance for the selected plant.</p>
          </div>
          <div className="hero-select">
            <span id="plant-label">SELECT PLANT</span>
            <button
              className="plant-select"
              aria-labelledby="plant-label"
              aria-haspopup="listbox"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              <AssetIcon src={icons.plantSelect} />
              <strong>{plant}</strong>
              <AssetIcon src={icons.chevronLg} size={20} />
            </button>
            {menu && (
              <div className="plant-menu" role="listbox">
                {plants.map((p) => (
                  <button
                    key={p}
                    role="option"
                    aria-selected={p === plant}
                    onClick={() => {
                      setPlant(p);
                      setMenu(false);
                    }}
                  >
                    {p} {p === plant && <span>Selected</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <img className="mill-art" src={images.heroMill} alt="Rice mill illustration" />
      </section>

      <section className="usage-panel" aria-label="Plant metrics">
        <article>
          <h2>POWER CONSUMED</h2>
          <div className="energy-value">
            <span className="energy-icon">ϟ</span>
            <strong>{Math.round(total).toLocaleString("en-IN")}</strong>
            <span>kWh</span>
            <ConsumptionBars />
          </div>
        </article>
        <article>
          <h2>ACTUAL USAGE</h2>
          <div className="energy-value">
            <b className="line-icon layers usage-icon" />
            <strong>{Math.round(actualTotal).toLocaleString("en-IN")}</strong>
            <span>kWh</span>
          </div>
        </article>
      </section>

      <section className="machines">
        <div className="machines-header">
          <div>
            <h2>Machine overview</h2>
            <p>
              {plant} · {machines.length} machines · Select a machine to open Process
              Analysis
            </p>
          </div>
          <p>N/A = no valid reading. 0 % = machine is OFF.</p>
        </div>
        <div className="machine-list">
          {machines.map((m) => (
            <MachineCard
              key={m.id}
              m={m}
              now={lastUpdate}
              onOpen={() => navigate(`/machines/${m.id}`)}
            />
          ))}
        </div>
      </section>
    </>
  );
}
