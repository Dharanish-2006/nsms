import { istHm } from "../lib/format";
export function ConsumptionBars({ muted = false }) {
  return (
    <div
      className={muted ? "consumption-bars muted" : "consumption-bars"}
      aria-hidden="true"
    >
      <i />
      <i />
      <i />
      <i />
    </div>
  );
}
export function RuntimeBand({ hours }) {
  return (
    <div className="runtime-chart">
      <div className="runtime-band" role="img" aria-label="Runtime by hour">
        {hours.map((s, i) => (
          <span
            key={i}
            title={`${String(i).padStart(2, "0")}:00`}
            className={s === 1 ? "running" : s === 2 ? "future" : ""}
          />
        ))}
      </div>
      <div className="runtime-axis">
        <span>00</span>
        <span>06</span>
        <span>12</span>
        <span>18</span>
        <span>Now</span>
      </div>
    </div>
  );
}
/** Hourly kWh area chart. */
export function EnergyChart({ values, startHour }) {
  const W = 320;
  const H = 90;
  const pad = 4;
  const max = Math.max(...values, 1);
  const pts = values.map((v, i) => {
    const x = pad + (i / Math.max(values.length - 1, 1)) * (W - pad * 2);
    const y = H - 14 - (v / max) * (H - 26);
    return [x, y];
  });
  const line = pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${pad},${H - 14} ${line} ${W - pad},${H - 14}`;
  return (
    <svg
      className="svg-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Energy used per hour"
    >
      <polygon points={area} fill="#dff0e5" />
      <polyline points={line} fill="none" stroke="#217944" strokeWidth="2" />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="2" fill="#217944">
          <title>{`${String((startHour + i) % 24).padStart(2, "0")}:00 · ${values[i].toFixed(1)} kWh`}</title>
        </circle>
      ))}
      <line x1={pad} x2={W - pad} y1={H - 14} y2={H - 14} stroke="#dce2d6" />
      <text x={pad} y={H - 2} fontSize="9" fill="#617068">
        {String(startHour).padStart(2, "0")}:00
      </text>
      <text x={W - pad} y={H - 2} fontSize="9" fill="#617068" textAnchor="end">
        now
      </text>
    </svg>
  );
}
/** Recent trend for one parameter with threshold guide lines. */
export function TrendChart({ points, pick, warning, critical, decimals = 2 }) {
  const W = 420;
  const H = 130;
  if (points.length < 2) return <svg className="svg-chart" viewBox={`0 0 ${W} ${H}`} />;
  const vals = points.map(pick);
  const guides = [warning, critical].filter((v) => v !== null);
  const all = [...vals, ...guides];
  let lo = Math.min(...all);
  let hi = Math.max(...all);
  const span = hi - lo || 1;
  lo -= span * 0.12;
  hi += span * 0.12;
  const t0 = points[0].t;
  const t1 = points[points.length - 1].t;
  const x = (t) => 8 + ((t - t0) / Math.max(t1 - t0, 1)) * (W - 52);
  const y = (v) => H - 18 - ((v - lo) / (hi - lo)) * (H - 30);
  const line = points
    .map((p) => `${x(p.t).toFixed(1)},${y(pick(p)).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      className="svg-chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Recent trend"
    >
      {warning !== null && (
        <>
          <line
            x1="8"
            x2={W - 44}
            y1={y(warning)}
            y2={y(warning)}
            stroke="#e7a82b"
            strokeDasharray="4 3"
          />
          <text x={W - 40} y={y(warning) + 3} fontSize="9" fill="#8b4b00">
            {warning.toFixed(decimals)}
          </text>
        </>
      )}
      {critical !== null && (
        <>
          <line
            x1="8"
            x2={W - 44}
            y1={y(critical)}
            y2={y(critical)}
            stroke="#d5413b"
            strokeDasharray="4 3"
          />
          <text x={W - 40} y={y(critical) + 3} fontSize="9" fill="#b42318">
            {critical.toFixed(decimals)}
          </text>
        </>
      )}
      <polyline points={line} fill="none" stroke="#172019" strokeWidth="2" />
      <line x1="8" x2={W - 44} y1={H - 18} y2={H - 18} stroke="#dce2d6" />
      <text x="8" y={H - 4} fontSize="9" fill="#617068">
        {istHm(t0)}
      </text>
      <text x={W - 44} y={H - 4} fontSize="9" fill="#617068" textAnchor="end">
        {istHm(t1)}
      </text>
    </svg>
  );
}
