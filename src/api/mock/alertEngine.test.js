import { describe, expect, it } from "vitest";
import { evaluate } from "./alertEngine";

const machine = (over = {}) => ({
  id: "m1",
  name: "Sheller 1",
  plant: "Plant 1",
  on: true,
  pf: 0.95,
  current: 20,
  kw: 10,
  updatedAt: 1000,
  ...over,
});
const pfLimit = {
  id: "t1",
  param: "powerFactor",
  machineId: "all",
  warning: 0.9,
  critical: 0.8,
};

describe("alert evaluation", () => {
  it("raises nothing while readings are inside their limits", () => {
    expect(evaluate([machine()], [pfLimit], new Map(), 2000).size).toBe(0);
  });

  it("raises a warning, then escalates to critical, keeping the start time", () => {
    const warn = evaluate([machine({ pf: 0.85 })], [pfLimit], new Map(), 2000);
    const a1 = [...warn.values()][0];
    expect(a1).toMatchObject({ severity: "warning", status: "active", since: 2000 });

    const crit = evaluate([machine({ pf: 0.75 })], [pfLimit], warn, 3000);
    const a2 = [...crit.values()][0];
    expect(a2).toMatchObject({ severity: "critical", status: "active", since: 2000 });
  });

  it("marks an alert recovered once the reading returns to normal", () => {
    const active = evaluate([machine({ pf: 0.75 })], [pfLimit], new Map(), 2000);
    const after = evaluate([machine({ pf: 0.95 })], [pfLimit], active, 4000);
    expect([...after.values()][0]).toMatchObject({
      status: "recovered",
      recoveredAt: 4000,
    });
  });

  it("does not alert on electrical limits while the machine is off", () => {
    const off = machine({ on: false, pf: 0.1 });
    expect(evaluate([off], [pfLimit], new Map(), 2000).size).toBe(0);
  });

  it("applies a machine-specific limit only to that machine", () => {
    const only = { ...pfLimit, machineId: "other" };
    expect(evaluate([machine({ pf: 0.5 })], [only], new Map(), 2000).size).toBe(0);
  });

  it("drops alerts whose threshold was deleted", () => {
    const active = evaluate([machine({ pf: 0.75 })], [pfLimit], new Map(), 2000);
    expect(evaluate([machine({ pf: 0.75 })], [], active, 3000).size).toBe(0);
  });
});
