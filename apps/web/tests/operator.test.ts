import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchOperatorView } from "../lib/operator";

const record = { id: "stored-row", label: "Stored title", state: "BLOCKED",
  detail: "Expected fixture negative", product_id: null, listing_version_id: null };
const envelope = { execution_mode: "fixture", run_id: "run-one", view: "blocked", items: [record] };

afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("request-time operator reads", () => {
  it("uses configured API and bypasses cached responses on every call", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100/");
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => envelope });
    vi.stubGlobal("fetch", fetch);
    expect(await fetchOperatorView("blocked", "run-one")).toEqual({ kind: "ready", data: envelope });
    await fetchOperatorView("blocked", "run-one");
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8100/operator/blocked?run_id=run-one",
      expect.objectContaining({ cache: "no-store" }));
  });
  it("lets the API select the newest run when none is selected", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => envelope });
    vi.stubGlobal("fetch", fetch);
    await fetchOperatorView("blocked");
    expect(fetch.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8100/operator/blocked");
  });
  it("fails closed without configuration and does not query dependencies", async () => {
    vi.stubEnv("API_BASE_URL", "");
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect(await fetchOperatorView("blocked")).toEqual({ kind: "unavailable" });
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each([404, 503])("does not manufacture records on HTTP %s", async (status) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status }));
    expect(await fetchOperatorView("blocked")).toEqual({ kind: "unavailable" });
  });
  it("recovers on the next request after an outage", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValueOnce(new Error("connection refused"))
      .mockResolvedValueOnce({ ok: true, json: async () => envelope }));
    expect(await fetchOperatorView("blocked")).toEqual({ kind: "unavailable" });
    expect(await fetchOperatorView("blocked")).toEqual({ kind: "ready", data: envelope });
  });
  it.each([
    { ...envelope, execution_mode: ["fixture"] }, { ...envelope, execution_mode: "live" }, { ...envelope, execution_mode: undefined },
    { ...envelope, view: "shop" }, { ...envelope, run_id: "wrong-run" },
    { ...envelope, items: [{ ...record, state: null }] }, { ...envelope, items: null },
  ])("rejects an invalid or mismatched envelope", async (invalid) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => invalid }));
    expect(await fetchOperatorView("blocked", "run-one")).toEqual({ kind: "unavailable" });
  });
});
