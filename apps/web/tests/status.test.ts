import { afterEach, describe, expect, it, vi } from "vitest";
import { GET as healthGET } from "../app/api/health/route";
import { fetchOperatorView } from "../lib/operator";

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("operator safety boundaries", () => {
  it("keeps all outward and business actions disabled", async () => {
    const base = "http://127.0.0.1:8100";
    vi.stubEnv("API_BASE_URL", base);
    const fetch = vi.fn<typeof globalThis.fetch>().mockResolvedValue(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetch);
    const response = await healthGET();
    const bootstrapSummary = await response.json();
    expect(fetch).toHaveBeenCalledOnce();
    const calls = fetch.mock.calls;
    expect(bootstrapSummary.externalActions).toBe(false);
    expect(bootstrapSummary.businessTransitions).toBe(false);
    expect(calls[0]?.[0]).toBe(base + "/operator/now");
    expect(calls[0]?.[1]?.method ?? "GET").toBe("GET");
    expect(response.status).toBe(503);
    expect(bootstrapSummary.status).toBe("unavailable");
  });

  it("does not claim unqueried dependencies are healthy", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockRejectedValue(new Error("connection refused"));
    vi.stubGlobal("fetch", fetch);
    const result = await fetchOperatorView("now");
    expect(fetch).toHaveBeenCalledOnce();
    expect(result.kind).toBe("unavailable");
    const response = await healthGET();
    expect(response.status).toBe(503);
    const summary = await response.json();
    expect(summary.status).toBe("unavailable");
    const serviceStatuses: { name: string; state: string }[] = summary.dependencies;
    const dependencies = serviceStatuses.filter(({ name }) => name !== "Operator console");
    expect(dependencies).not.toHaveLength(0);
    expect(dependencies.every(({ state }) => state === "unverified")).toBe(true);
    expect(serviceStatuses).toEqual([{ name: "API", state: "unverified" }]);
  });
});

describe("request-time console probes", () => {
  it("reports ready only after receiving a valid stored-run view", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      execution_mode: "fixture", run_id: "stored-run", view: "now", items: [],
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetch);
    const response = await healthGET();
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      service: "operator-console", status: "available",
      externalActions: false, businessTransitions: false,
      dependencies: [{ name: "API", state: "verified" }],
    });
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8100/operator/now",
      expect.objectContaining({ cache: "no-store" }));
  });

  it.each([404, 503])("keeps readiness unavailable on API HTTP %s", async (status) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status })));
    const response = await healthGET();
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({
      status: "unavailable", dependencies: [{ name: "API", state: "unverified" }],
    });
  });

  it("fails readiness closed without an API URL and makes no dependency request", async () => {
    vi.stubEnv("API_BASE_URL", "");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    const response = await healthGET();
    expect(response.status).toBe(503);
    expect(await response.json()).toMatchObject({
      status: "unavailable", dependencies: [{ name: "API", state: "unverified" }],
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(["", "http://127.0.0.1:8100"])("reports process liveness independently of API configuration %s", async (base) => {
    vi.stubEnv("API_BASE_URL", base);
    const fetch = vi.fn().mockRejectedValue(new Error("connection refused"));
    vi.stubGlobal("fetch", fetch);
    const { GET, dynamic } = await import("../app/api/live/route");
    const response = await GET();
    expect(dynamic).toBe("force-dynamic");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ service: "operator-console", status: "alive" });
    expect(fetch).not.toHaveBeenCalled();
  });
});
