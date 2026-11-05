import { describe, expect, it } from "vitest";
import { fmtParam, PARAMS } from "./params";
import { sortAlerts } from "./alerts";
import { statusOf } from "./status";

describe("parameters", () => {
  it("formats limits with their unit, or says there is none", () => {
    expect(fmtParam("avgCurrent", 38)).toBe("38.0 A");
    expect(fmtParam("powerFactor", 0.9)).toBe("0.90");
    expect(fmtParam("freshness", null)).toBe("No limit");
  });

  it("ignores electrical readings while a machine is off", () => {
    const off = { on: false, pf: 0.5, current: 99, kw: 99, updatedAt: 0 };
    expect(PARAMS.powerFactor.get(off)).toBeNull();
    expect(PARAMS.avgCurrent.get(off)).toBeNull();
  });
});

describe("machine status", () => {
  const m = { on: true, updatedAt: 1_000_000 };
  it("is on or off while data is fresh", () => {
    expect(statusOf(m, 1_010_000)).toBe("on");
    expect(statusOf({ ...m, on: false }, 1_010_000)).toBe("off");
  });
  it("is unknown, never off, when data has gone stale", () => {
    expect(statusOf(m, 1_000_000 + 121_000)).toBe("unknown");
  });
});

describe("alert ordering", () => {
  const a = (key, status, severity, since, recoveredAt) => ({
    key,
    status,
    severity,
    since,
    recoveredAt,
  });
  it("puts critical before warning, newest first, with recovered last", () => {
    const sorted = sortAlerts([
      a("rec", "recovered", "critical", 1, 50),
      a("warn-old", "active", "warning", 10),
      a("crit-old", "active", "critical", 20),
      a("crit-new", "active", "critical", 30),
    ]).map((x) => x.key);
    expect(sorted).toEqual(["crit-new", "crit-old", "warn-old", "rec"]);
  });
});
