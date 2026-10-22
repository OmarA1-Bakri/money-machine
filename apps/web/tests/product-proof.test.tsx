import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { fetchRunSummary } from "../lib/operator-summary";
import { GET as artifactGET } from "../app/api/runs/[runId]/artifacts/[artifactId]/route";
import { operatorViews } from "../lib/operator";
import { OperatorViewPage } from "../components/operator-view";

const summary = {
  execution_mode: "fixture", workflow_completed: true, pending_effects: 0,
  run_id: "run-one", workflow_id: "workflow-one", product_id: "product-one",
  listing_version_id: "listing-one", product_title: "Stored weekly planner",
  fixture_completed: true, completed_at: "2026-10-22T10:00:00Z", product_state: "DISCOVERED",
  jobs: [{ id: "job-one", job_type: "DraftListingJob", status: "READY" },
    { id: "job-two", job_type: "NegativeFixtureJob", status: "BLOCKED" }],
  recoveries: [],
  artifacts: [{ id: "ca11a410-cdde-5af8-9a96-b436cc4ef822", label: "Product HTML", kind: "product_html",
    media_type: "text/html", byte_size: 123, href: "/operator/runs/run-one/artifacts/ca11a410-cdde-5af8-9a96-b436cc4ef822" },
  { id: "A9F30C26-4F08-5206-BCFA-6B51BEC15732", label: "Printable PDF", kind: "delivery_pdf", media_type: "application/pdf",
    byte_size: 456, href: "/operator/runs/run-one/artifacts/A9F30C26-4F08-5206-BCFA-6B51BEC15732" }],
};
const context = { params: Promise.resolve({ runId: "run-one", artifactId: "ca11a410-cdde-5af8-9a96-b436cc4ef822" }) };
const request = new Request("http://localhost/api/runs/run-one/artifacts/ca11a410-cdde-5af8-9a96-b436cc4ef822");
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
    { ...summary, execution_mode: ["fixture"] }, { ...summary, pending_effects: 1 },
    { ...summary, execution_mode: "live" }, { ...summary, execution_mode: undefined },
    { ...summary, pending_effects: -1 }, { ...summary, pending_effects: 1.2 },
    { ...summary, workflow_completed: false },
    { ...summary, execution_mode: "real_draft", fixture_completed: true },
    { ...summary, execution_mode: "fixture", listing_version_id: null },
    { ...summary, run_id: "another-run" }, { ...summary, jobs: [{ status: "READY" }] },
    { ...summary, fixture_completed: true, completed_at: null },
    { ...summary, fixture_completed: false },
    { ...summary, artifacts: [{ ...summary.artifacts[0], id: "artifact-one" }] },
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
  it("rejects non-UUID artifact identifiers before making a request", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockResolvedValue(new Response("unexpected"));
    vi.stubGlobal("fetch", fetch);
    const response = await artifactGET(request, { params: Promise.resolve({ runId: "run-one", artifactId: "artifact-one" }) });
    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("rejects run identifiers longer than the backend limit before making a request", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const fetch = vi.fn().mockResolvedValue(new Response("unexpected"));
    vi.stubGlobal("fetch", fetch);
    const response = await artifactGET(request, { params: Promise.resolve({ runId: "r".repeat(81), artifactId: summary.artifacts[0]!.id }) });
    expect(response.status).toBe(404);
    expect(fetch).not.toHaveBeenCalled();
  });
  it("forwards verified bytes and content safety headers from only the configured API", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const csp = "sandbox; default-src 'none'; style-src 'unsafe-inline'; form-action 'none'";
    const fetch = vi.fn().mockResolvedValue(new Response("<h1>Actual stored template</h1>", { headers: {
      "content-type": "text/html", "content-security-policy": csp,
      "x-content-type-options": "nosniff", "content-disposition": "inline; filename=ca11a410-cdde-5af8-9a96-b436cc4ef822.html",
    } }));
    vi.stubGlobal("fetch", fetch);
    const response = await artifactGET(request, context);
    expect(response.status).toBe(200);
    expect(await response.text()).toBe("<h1>Actual stored template</h1>");
    expect(response.headers.get("content-security-policy")).toBe(csp);
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8100/operator/runs/run-one/artifacts/ca11a410-cdde-5af8-9a96-b436cc4ef822",
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
      url.endsWith("/summary") ? summary : { execution_mode: "fixture", run_id: "run-one", view, items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view, searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Fixture completed");
    expect(html).toContain(summary.completed_at);
    expect(html).toContain("DraftListingJob");
    expect(html).toContain("READY");
    expect(html).toContain("BLOCKED");
    expect(html).toContain("DISCOVERED");
    expect(html).toContain("Production lifecycle: DISCOVERED");
  });
  it.each(["now", "shop"] as const)("embeds the stored product in an inert frame and links real files on %s", async (view) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? summary : { execution_mode: "fixture", run_id: "run-one", view, items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view, searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain('sandbox=""');
    expect(html).toContain('src="/api/runs/run-one/artifacts/ca11a410-cdde-5af8-9a96-b436cc4ef822"');
    expect(html).toContain('href="/api/runs/run-one/artifacts/A9F30C26-4F08-5206-BCFA-6B51BEC15732"');
    expect(html).not.toContain("127.0.0.1:8100");
    expect(html).not.toContain("allow-scripts");
  });
  it("does not render completion or previews when summary fails", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => url.endsWith("/summary")
      ? new Response(null, { status: 503 }) : new Response(JSON.stringify({ execution_mode: "fixture", run_id: "run-one", view: "now", items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view: "now", searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Product proof unavailable");
    expect(html).not.toContain("Fixture completed");
    expect(html).not.toContain("<iframe");
  });
});


describe("real private draft progress", () => {
  const realSummary = { ...summary, execution_mode: "real_draft", workflow_completed: false,
    fixture_completed: false, completed_at: null, listing_version_id: null, pending_effects: 1,
    artifacts: [], jobs: [{ id: "real-job", job_type: "BuildNotionJob", status: "RUNNING" }] };
  it("accepts a real run before a listing exists", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(realSummary))));
    expect(await fetchRunSummary("run-one")).toEqual({ kind: "ready", data: realSummary });
  });
  it("shows the held provider outcome without claiming completed or fixture proof", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? realSummary : { execution_mode: "real_draft", run_id: "run-one", view: "now", items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view: "now", searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Real draft run");
    expect(html).toContain("Held for provider reconciliation");
    expect(html).toContain("1 uncertain provider operation");
    expect(html).toContain("RUNNING");
    expect(html).not.toContain("Fixture completed");
    expect(html).not.toContain("Fixture only");
    expect(html).not.toContain("Draft workflow completed");
    expect(html).not.toContain("<iframe");
  });
  it("labels a verified completed real draft separately from fixture completion", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? { ...realSummary, pending_effects: 0, workflow_completed: true,
        completed_at: summary.completed_at } : { execution_mode: "real_draft", run_id: "run-one", view: "pipeline", items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view: "pipeline", searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("Draft workflow completed");
    expect(html).not.toContain("Fixture completed");
    expect(html).toContain("Publishing and spend remain disabled");
  });
});


it("rejects a mode mismatch between view and proof", async () => {
  vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
    url.endsWith("/summary") ? summary : { execution_mode: "real_draft", run_id: "run-one", view: "now", items: [] }))));
  const html = renderToStaticMarkup(await OperatorViewPage({ view: "now", searchParams: Promise.resolve({ run_id: "run-one" }) }));
  expect(html).toContain("Product proof unavailable");
  expect(html).not.toContain("Fixture completed");
  expect(html).not.toContain("<iframe");
});


describe("persisted A07 recovery proof", () => {
  const proof = {
    job_id: "4f24f619-a439-447f-a921-6d87ffddc3a7",
    agent_run_id: "fd640c88-4adf-43c3-b621-0cb806111936", agent_run_status: "SUCCESS",
    effect_state: "CONFIRMED", database_id: "c2c145da-908c-47a7-9635-bcfc9e8a01ca",
    data_source_id: "a2f8495e-e2bb-4827-b219-b59b25e9a01d",
  };
  const recoverySummary = { ...summary, execution_mode: "real_draft", workflow_completed: false,
    fixture_completed: false, completed_at: null, listing_version_id: null, pending_effects: 1,
    jobs: [{ id: proof.job_id, job_type: "BuildRepairJob", status: "RUNNING" }],
    recoveries: [proof], artifacts: [] };
  it.each(["now", "pipeline", "incidents"] as const)("shows retained outcome and actionable hold on %s", async (view) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? recoverySummary : { execution_mode: "real_draft", run_id: "run-one", view, items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view, searchParams: Promise.resolve({ run_id: "run-one" }) }));
    for (const value of [proof.job_id, proof.agent_run_id, proof.database_id, proof.data_source_id, "SUCCESS", "CONFIRMED"])
      expect(html).toContain(value);
    expect(html).toContain("original UNKNOWN");
    expect(html).toContain("canonical selection");
    expect(html).toContain("Effect confirmation does not complete the repair or workflow");
    expect(html).not.toContain("Draft workflow completed");
    expect(html).not.toContain("<button");
  });
  it("shows uncertain readback with a read-only next step and no resend control", async () => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    const data = { ...recoverySummary, pending_effects: 2,
      recoveries: [{ ...proof, agent_run_status: "UNCERTAIN_EXTERNAL_EFFECT", effect_state: "UNKNOWN" }] };
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async (url: string) => new Response(JSON.stringify(
      url.endsWith("/summary") ? data : { execution_mode: "real_draft", run_id: "run-one", view: "incidents", items: [] }))));
    const html = renderToStaticMarkup(await OperatorViewPage({ view: "incidents", searchParams: Promise.resolve({ run_id: "run-one" }) }));
    expect(html).toContain("UNCERTAIN_EXTERNAL_EFFECT");
    expect(html).toContain("original authorized connection");
    expect(html).toContain("Do not resend create");
    expect(html).toContain("Retained response identities");
    expect(html).not.toContain("<button");
  });
  it.each([
    { ...proof, database_id: "https://private.invalid" },
    { ...proof, agent_run_status: "COMPLETED" },
    { ...proof, agent_run_status: ["SUCCESS"] },
    { ...proof, effect_state: ["CONFIRMED"] },
    { ...proof, agent_run_id: null },
    { ...proof, effect_state: "VERIFIED" },
    { ...proof, job_id: "fd640c88-4adf-43c3-b621-0cb806111936" },
  ])("rejects malformed or unrelated recovery proof", async (invalid) => {
    vi.stubEnv("API_BASE_URL", "http://127.0.0.1:8100");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...recoverySummary, recoveries: [invalid] }))));
    expect(await fetchRunSummary("run-one")).toEqual({ kind: "unavailable" });
  });
});
