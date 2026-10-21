export interface RunJob { id: string; job_type: string; status: string }
export interface RunArtifact {
  id: string; label: string; kind: string; media_type: string; byte_size: number; href: string;
}
export interface RunSummary {
  run_id: string; workflow_id: string; product_id: string; listing_version_id: string;
  product_title: string; fixture_completed: boolean; completed_at: string | null;
  product_state: string; jobs: RunJob[]; artifacts: RunArtifact[];
}
export type RunSummaryResult = { kind: "ready"; data: RunSummary } | { kind: "unavailable" };

export function isRunIdentifier(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(value);
}
export function artifactPath(runId: string, artifactId: string): string {
  return `/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`;
}
function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function hasStrings(value: Record<string, unknown>, keys: string[]): boolean {
  return keys.every((key) => typeof value[key] === "string" && value[key] !== "");
}
function isSummary(value: unknown, runId: string): value is RunSummary {
  if (!isObject(value) || value.run_id !== runId ||
      !hasStrings(value, ["workflow_id", "product_id", "listing_version_id", "product_title", "product_state"]) ||
      typeof value.fixture_completed !== "boolean" ||
      !(value.completed_at === null || (typeof value.completed_at === "string" && Number.isFinite(Date.parse(value.completed_at)))) ||
      (value.fixture_completed !== (value.completed_at !== null)) ||
      !Array.isArray(value.jobs) || !Array.isArray(value.artifacts)) return false;
  return value.jobs.every((job) => isObject(job) && hasStrings(job, ["id", "job_type", "status"])) &&
    value.artifacts.every((artifact) => isObject(artifact) &&
      hasStrings(artifact, ["id", "label", "kind", "media_type", "href"]) &&
      typeof artifact.id === "string" && isRunIdentifier(artifact.id) &&
      typeof artifact.byte_size === "number" && Number.isSafeInteger(artifact.byte_size) && artifact.byte_size >= 0);
}
export async function fetchRunSummary(runId: string): Promise<RunSummaryResult> {
  const base = process.env.API_BASE_URL;
  if (!base || !isRunIdentifier(runId)) return { kind: "unavailable" };
  try {
    const url = new URL(base.replace(/\/$/, "") + `/operator/runs/${encodeURIComponent(runId)}/summary`);
    const response = await fetch(url.toString(), {
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return { kind: "unavailable" };
    const data: unknown = await response.json();
    return isSummary(data, runId) ? { kind: "ready", data } : { kind: "unavailable" };
  } catch {
    return { kind: "unavailable" };
  }
}
