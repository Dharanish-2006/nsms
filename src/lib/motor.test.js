import { describe, expect, it } from "vitest";
import { hpToKw, kwToHp, MAX_HP, parseHp } from "./motor";

describe("motor rating", () => {
  it("converts between kW and HP", () => {
    expect(kwToHp(36)).toBe(48.3);
    expect(hpToKw(50)).toBe(37.285);
  });

  it("round-trips a rating typed in HP", () => {
    for (const hp of [5, 7.5, 30, 40, 48.3, 100, 250.5]) {
      expect(kwToHp(hpToKw(hp))).toBe(hp);
    }
  });

  it("accepts plain numbers with at most one decimal", () => {
    expect(parseHp("40")).toBe(40);
    expect(parseHp(" 7.5 ")).toBe(7.5);
    expect(parseHp(String(MAX_HP))).toBe(MAX_HP);
  });

  it("rejects anything else", () => {
    for (const bad of [
      "",
      " ",
      "0",
      "-5",
      "abc",
      "4e2",
      "7.55",
      "40.",
      ".5",
      "1001",
      "1,000",
    ]) {
      expect(parseHp(bad)).toBeNull();
    }
    expect(parseHp(undefined)).toBeNull();
  });
});
