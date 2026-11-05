const TZ = "Asia/Kolkata";
export const istTime = (ms) =>
  new Date(ms).toLocaleTimeString("en-GB", {
    timeZone: TZ,
    hourCycle: "h23",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
export const istHm = (ms) =>
  new Date(ms).toLocaleTimeString("en-GB", {
    timeZone: TZ,
    hourCycle: "h23",
    hour: "2-digit",
    minute: "2-digit",
  });
export const istDay = (ms) =>
  new Date(ms).toLocaleDateString("en-GB", {
    timeZone: TZ,
    day: "2-digit",
    month: "short",
  });
export const istDate = (ms) =>
  new Date(ms).toLocaleDateString("en-GB", {
    timeZone: TZ,
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
export const istStamp = (ms) => `${istDay(ms)}, ${istHm(ms)}`;
export const istDayKey = (ms) =>
  new Date(ms).toLocaleDateString("en-CA", { timeZone: TZ });
export const istHour = (ms) =>
  parseInt(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: TZ,
      hourCycle: "h23",
      hour: "2-digit",
    }).format(ms),
    10,
  );
export const fmtDuration = (sec) => {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h.toLocaleString("en-IN")} h ${m} min`;
};
export const fmt = (v, d = 2) =>
  v.toLocaleString("en-IN", {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
export const fmtPhone = (digits) => `+91 ${digits.slice(0, 5)} ${digits.slice(5)}`;
export function downloadCsv(filename, rows) {
  const esc = (v) => {
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const blob = new Blob([rows.map((r) => r.map(esc).join(",")).join("\n")], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
