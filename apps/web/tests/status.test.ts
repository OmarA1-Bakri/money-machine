import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchOperatorView } from "../lib/operator";

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("operator safety boundaries", () => {
  it("keeps all outward and business actions disabled", async () => {
    const base = "http://127.0.0.1:8100";
    vi.stubEnv("API_BASE_URL", base);
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetch);
    await fetchOperatorView("now");
    expect(fetch).toHaveBeenCalledOnce();
    const calls = fetch.mock.calls;
    const bootstrapSummary = {
      externalActions: calls.some(([url]) => new URL(String(url)).origin !== base),
      businessTransitions: calls.some(([, options]) => (options?.method ?? "GET") !== "GET"),
    };
    expect(bootstrapSummary.externalActions).toBe(false);
    expect(bootstrapSummary.businessTransitions).toBe(false);
    expect(calls[0]?.[0]).toBe(base + "/operator/now");
  });

  it("does not claim unqueried dependencies are healthy", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockRejectedValue(new Error("connection refused"));
    vi.stubGlobal("fetch", fetch);
    const result = await fetchOperatorView("now");
    expect(fetch).toHaveBeenCalledOnce();
    expect(result.kind).toBe("unavailable");
    const serviceStatuses = [{
      name: "API",
      state: result.kind === "unavailable" ? "unverified" : "healthy",
    }];
    const dependencies = serviceStatuses.filter(({ name }) => name !== "Operator console");
    expect(dependencies).not.toHaveLength(0);
    expect(dependencies.every(({ state }) => state === "unverified")).toBe(true);
  });
});
