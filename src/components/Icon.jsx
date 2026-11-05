import { icons } from "../assets";

export function AssetIcon({ src, size = 22 }) {
  return <img src={src} width={size} height={size} alt="" aria-hidden="true" />;
}

export function StatusBadge({ status }) {
  const on = status === "on";
  return (
    <span className={`status-badge ${on ? "on" : "off"}`}>
      <AssetIcon src={on ? icons.statusOn : icons.statusOff} size={18} />
      {status === "on" ? "ON" : status === "off" ? "OFF" : "UNKNOWN"}
    </span>
  );
}
