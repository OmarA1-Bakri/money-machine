import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { fetchRunSummary } from "../lib/operator-summary";
import { GET as artifactGET } from "../app/api/runs/[runId]/artifacts/[artifactId]/route";
import { operatorViews } from "../lib/operator";
import { OperatorViewPage } from "../components/operator-view";

const summary = {
  run_id: "run-one", workflow_id: "workflow-one", product_id: "product-one",
  listing_version_id: "listing-one", product_title: "Stored weekly planner",
  fixture_completed: true, completed_at: "2026-10-22T10:00:00Z", product_state: "DISCOVERED",
  jobs: [{ id: "job-one", job_type: "DraftListingJob", status: "READY" },
    { id: "job-two", job_type: "NegativeFixtureJob", status: "BLOCKED" }],
  artifacts: [{ id: "artifact-one", label: "Product HTML", kind: "product_html",
    media_type: "text/html", byte_size: 123, href: "/operator/runs/run-one/artifacts/artifact-one" },
  { id: "artifact-two", label: "Printable PDF", kind: "delivery_pdf", media_type: "application/pdf",
    byte_size: 456, href: "/operator/runs/run-one/artifacts/artifact-two" }],
};
const context = { params: Promise.resolve({ runId: "run-one", artifactId: "artifact-one" }) };
const request = new Request("http://localhost/api/runs/run-one/artifacts/artifact-one");
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals(); });

describe("stored run summary", () => {
  it("reads the selected run at request time without caching", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100/");
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(summary)));
    vi.stubGlobal("fetch", fetch);
    expect(await fetchRunSummary("run-one")).toEqual({ kind: "ready", data: summary });
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8100/operator/runs/run-one/summary",
      expect.objectContaining({ cache: "no-store", redirect: "error" }));
  });
  it.each([
    { ...summary, run_id: "another-run" }, { ...summary, jobs: [{ status: "READY" }] },
    { ...summary, fixture_completed: true, completed_at: null },
    { ...summary, fixture_completed: false },
    { ...summary, artifacts: [{ ...summary.artifacts[0], byte_size: -1 }] },
  ])("rejects malformed or mismatched completion evidence", async (invalid) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(invalid))));
    expect(await fetchRunSummary("run-one")).toEqual({ kind: "unavailable" });
  });
  it("fails closed without configuration or when API is offline", async () => {
    vi.stubEnv("API_BASE_URL", "");
    const fetch = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetch);
    expect(await fetchRunSummary("run-one")).toEqual({ kind: "unavailable" });
    expect(fetch).not.toHaveBeenCalled();
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    expect(await fetchRunSummary("run-one")).toEqual({ kind: "unavailable" });
  });
});

describe("artifact byte proxy", () => {
  it("forwards verified bytes and content safety headers from only the configured API", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const csp = "sandbox; default-src 'none'; style-src 'unsafe-inline'; form-action 'none'";
    const fetch = vi.fn().mockResolvedValue(new Response("<h1>Actual stored template</h1>", { headers: {
      "content-type": "text/html", "content-security-policy": csp,
      "x-content-type-options": "nosniff", "content-disposition": "inline; filename=artifact-one.html",
    } }));
    vi.stubGlobal("fetch", fetch);
    const response = await artifactGET(request, context);
    expect(response.status).toBe(200);
    expect(await response.text()).toBe("<h1>Actual stored template</h1>");
    expect(response.headers.get("content-security-policy")).toBe(csp);
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8100/operator/runs/run-one/artifacts/artifact-one",
      expect.objectContaining({ cache: "no-store", redirect: "error" }));
  });
  it.each([404, 409, 503])("preserves artifact failure HTTP %s without exposing upstream detail", async (status) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("private host path", { status })));
    const response = await artifactGET(request, context);
    expect(response.status).toBe(status);
    expect(await response.text()).not.toContain("private host path");
  });
  it("rejects path inputs and fails closed on outage", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockRejectedValue(new Error("private error"));
    vi.stubGlobal("fetch", fetch);
    const bad = await artifactGET(request, { params: Promise.resolve({ runId: "..", artifactId: "http://evil" }) });
    expect(bad.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
    expect((await artifactGET(request, context)).status).toBe(503);
  });
});

describe("product proof views", () => {
  it.each(operatorViews)("keeps %s unavailable on outage without fabricated product proof", async (view) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetch);
    const html = renderToStaticMarkup(await OperatorViewPage({ view, searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Data unavailable");
    expect(html).not.toContain("Fixture completed");
    expect(html).not.toContain("Stored weekly planner");
    expect(html).not.toContain("<iframe");
    expect(fetch).toHaveBeenCalledOnce();
  });
  it.each(["now", "pipeline"] as const)("shows real fixture completion and held job states on %s", async (view) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? summary : { run_id: "run-one", view, items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view, searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Fixture completed");
    expect(html).toContain(summary.completed_at);
    expect(html).toContain("DraftListingJob");
    expect(html).toContain("READY");
    expect(html).toContain("BLOCKED");
    expect(html).toContain("DISCOVERED");
  });
  it.each(["now", "shop"] as const)("embeds the stored product in an inert frame and links real files on %s", async (view) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? summary : { run_id: "run-one", view, items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view, searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain('sandbox=""');
    expect(html).toContain('src="/api/runs/run-one/artifacts/artifact-one"');
    expect(html).toContain('href="/api/runs/run-one/artifacts/artifact-two"');
    expect(html).not.toContain("127.0.0.1:8100");
    expect(html).not.toContain("allow-scripts");
  });
  it("does not render completion or previews when summary fails", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => url.endsWith("/summary")
      ? new Response(null, { status: 503 }) : new Response(JSON.stringify({ run_id: "run-one", view: "now", items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view: "now", searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Product proof unavailable");
    expect(html).not.toContain("Fixture completed");
    expect(html).not.toContain("<iframe");
  });
});
