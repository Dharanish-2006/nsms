import { icons, images, machineImage } from "../assets";
import { useEffect, useState } from "react";
import { api } from "../api";
import { useNavigate } from "react-router-dom";
import { statusOf } from "../lib/status";
import { ConsumptionBars } from "../components/Charts";
import { AssetIcon, StatusBadge } from "../components/Icon";
import { useData } from "../context/DataContext";
import { fmt, fmtDuration } from "../lib/format";
import { hasPowerQuality } from "../lib/machine";
import loadfactor_img from "../assets/images/load-gauge.svg";
const todayKwh = (m) => m.hourlyKwh.reduce((a, b) => a + b, 0);
// "Actual usage" is the part of today's energy used while the machine was running.
const RANGES = [
  { id: "day", label: "Today" },
  { id: "week", label: "This week" },
  { id: "month", label: "This month" },
];
const actualKwh = (m) => Math.max(m.todayRunKwh ?? m.runKwh ?? 0, 0);
function MachineCard({ m, now, onOpen }) {
  const status = statusOf(m, now);
  const on = status === "on";
  const kwh = todayKwh(m);
  const actual = actualKwh(m);
  const pq = hasPowerQuality(m);
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

      <div className={pq ? "machine-stats" : "machine-stats no-pq"}>
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
        {pq && (
          <>
            <div className="machine-stat">
              <span className="stat-title">
                <b className="line-icon gauge" />
                Power Factor
              </span>
              <strong>{on ? fmt(m.pf) : "N/A"}</strong>
            </div>
            <div className="machine-stat">
              <span className="stat-title">
                <img src={loadfactor_img} height={25} width={20} />
                Load Factor
              </span>
              <strong>{on ? Math.round(m.loadFactor) : 0} %</strong>
              <div className="load-track">
                <i style={{ width: `${on ? Math.min(m.loadFactor, 100) : 0}%` }} />
              </div>
            </div>
          </>
        )}
        <div className="machine-stat">
          <span className="stat-title">
            <b className="bolt">ϟ</b>Power Consumed
          </span>
          <strong>{kwh > 0 ? `${fmt(kwh, 1)} kWh` : "-- kWh"}</strong>
        </div>
        <div className="machine-stat">
          <span className="stat-title">
            <b className="bolt">ϟ</b>
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
  const [range, setRange] = useState("day");
  // Totals for the longer ranges come from the API; "day" is summed from the
  // live machine readings above so it always matches the cards below.
  const [past, setPast] = useState({ key: "", totals: null });
  const pastKey = `${plant}:${range}`;
  useEffect(() => {
    if (range === "day") return undefined;
    const controller = new AbortController();
    api.machines
      .usage(plant, range, { signal: controller.signal })
      .then((totals) => setPast({ key: pastKey, totals }))
      .catch(() => setPast({ key: pastKey, totals: null }));
    return () => controller.abort();
  }, [plant, range, pastKey]);
  const loading = range !== "day" && past.key !== pastKey;
  const shown =
    range === "day"
      ? { consumedKwh: total, actualKwh: actualTotal }
      : past.key === pastKey
        ? past.totals
        : null;
  const value = (v) =>
    loading ? "…" : v === undefined ? "--" : Math.round(v).toLocaleString("en-IN");
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

      <fieldset className="range-radios">
        <legend className="sr-only">Time range</legend>
        {RANGES.map((r) => (
          <label key={r.id} className={range === r.id ? "selected" : ""}>
            <input
              type="radio"
              name="usage-range"
              value={r.id}
              checked={range === r.id}
              onChange={() => setRange(r.id)}
            />
            {r.label}
          </label>
        ))}
      </fieldset>

      <section className="usage-panel" aria-label="Plant metrics" aria-busy={loading}>
        <article>
          <h2>POWER CONSUMED</h2>
          <div className="energy-value">
            <span className="energy-icon">ϟ</span>
            <strong>{value(shown?.consumedKwh)}</strong>
            <span>kWh</span>
            <ConsumptionBars />
          </div>
        </article>
        <article>
          <h2>ACTUAL USAGE</h2>
          <div className="energy-value">
            <span className="energy-icon">ϟ</span>
            <strong>{value(shown?.actualKwh)}</strong>
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
