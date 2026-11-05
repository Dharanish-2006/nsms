import { describe, expect, it } from "vitest";
import { fmt, fmtDuration, fmtPhone, istHm, istDayKey } from "./format";

describe("format helpers", () => {
  it("formats numbers with Indian digit grouping", () => {
    expect(fmt(1234567.891, 1)).toBe("12,34,567.9");
    expect(fmt(0.5)).toBe("0.50");
  });

  it("formats durations as hours and minutes", () => {
    expect(fmtDuration(3 * 3600 + 25 * 60 + 59)).toBe("3 h 25 min");
    expect(fmtDuration(0)).toBe("0 h 0 min");
  });

  it("formats a 10-digit Indian mobile number", () => {
    expect(fmtPhone("9000000001")).toBe("+91 90000 00001");
  });

  it("shows times in Indian Standard Time regardless of the viewer's zone", () => {
    // 2026-11-04 07:30:00 UTC is 13:00 in India.
    const ms = Date.UTC(2026, 10, 4, 7, 30);
    expect(istHm(ms)).toBe("13:00");
    expect(istDayKey(ms)).toBe("2026-11-04");
    // 20:00 UTC is already the next day in India.
    expect(istDayKey(Date.UTC(2026, 10, 4, 20, 0))).toBe("2026-11-05");
  });
});
