import { describe, expect, it } from "vitest";
import { bootstrapSummary, serviceStatuses } from "../lib/status";

describe("bootstrap operator status", () => {
  it("keeps all outward and business actions disabled", () => {
    expect(bootstrapSummary.externalActions).toBe(false);
    expect(bootstrapSummary.businessTransitions).toBe(false);
  });

  it("does not claim unqueried dependencies are healthy", () => {
    const dependencies = serviceStatuses.filter(({ name }) => name !== "Operator console");

    expect(dependencies).not.toHaveLength(0);
    expect(dependencies.every(({ state }) => state === "unverified")).toBe(true);
  });
});
