import { describe, expect, it } from "vitest";
import { usageTotals } from "./usage";

const defs = [{ id: "a", baseKw: 10 }];

describe("usageTotals", () => {
  it("is repeatable for the same day", () => {
    expect(usageTotals(defs, 7, "2026-11-06")).toEqual(
      usageTotals(defs, 7, "2026-11-06"),
    );
  });
  it("grows with the length of the range, and actual stays below consumed", () => {
    const week = usageTotals(defs, 7, "2026-11-06");
    const month = usageTotals(defs, 30, "2026-11-06");
    expect(month.consumedKwh).toBeGreaterThan(week.consumedKwh);
    expect(week.actualKwh).toBeLessThan(week.consumedKwh);
  });
});
