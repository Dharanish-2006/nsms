import { describe, expect, it } from "vitest";
import { utilisationPct } from "./machine";

describe("utilisationPct", () => {
  it("is the share of energy used while running", () => {
    expect(utilisationPct(80, 100)).toBe(80);
  });
  it("is empty when nothing was consumed", () => {
    expect(utilisationPct(0, 0)).toBeNull();
  });
  it("stays within 0 to 100", () => {
    expect(utilisationPct(120, 100)).toBe(100);
    expect(utilisationPct(-5, 100)).toBe(0);
  });
});
