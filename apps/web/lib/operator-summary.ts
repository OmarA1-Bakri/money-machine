import type { ExecutionMode } from "./operator";

export interface RunJob { id: string; job_type: string; status: string }
export interface RunRecovery {
  job_id: string; agent_run_id: string | null;
  agent_run_status: "RUNNING" | "SUCCESS" | "FAILURE" | "BLOCKED" | "UNCERTAIN_EXTERNAL_EFFECT" | null;
  effect_state: "CONFIRMED" | "ABSENT" | "UNKNOWN" | null;
  database_id: string | null; data_source_id: string | null;
}
export interface RunArtifact {
  id: string; label: string; kind: string; media_type: string; byte_size: number; href: string;
}
export interface RunSummary {
  execution_mode: ExecutionMode; workflow_completed: boolean; pending_effects: number;
  run_id: string; workflow_id: string; product_id: string; listing_version_id: string | null;
  product_title: string; fixture_completed: boolean; completed_at: string | null;
  product_state: string; jobs: RunJob[]; recoveries: RunRecovery[]; artifacts: RunArtifact[];
}
export type RunSummaryResult = { kind: "ready"; data: RunSummary } | { kind: "unavailable" };

export function isRunIdentifier(value: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(value);
}
export function isArtifactIdentifier(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
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
function isRecovery(value: unknown, jobs: RunJob[]): value is RunRecovery {
  if (!isObject(value) || typeof value.job_id !== "string" || !isArtifactIdentifier(value.job_id) ||
      !jobs.some((job) => job.id === value.job_id && job.job_type === "BuildRepairJob")) return false;
  return ["agent_run_id", "database_id", "data_source_id"].every((key) =>
    value[key] === null || typeof value[key] === "string" && isArtifactIdentifier(value[key])) &&
    (value.agent_run_status === null || typeof value.agent_run_status === "string" && ["RUNNING", "SUCCESS", "FAILURE", "BLOCKED", "UNCERTAIN_EXTERNAL_EFFECT"].includes(value.agent_run_status)) &&
    (value.agent_run_id === null) === (value.agent_run_status === null) &&
    (value.effect_state === null || typeof value.effect_state === "string" && ["CONFIRMED", "ABSENT", "UNKNOWN"].includes(value.effect_state));
}
function isSummary(value: unknown, runId: string): value is RunSummary {
  if (!isObject(value) || value.run_id !== runId ||
      !hasStrings(value, ["workflow_id", "product_id", "product_title", "product_state"]) ||
      (value.execution_mode !== "fixture" && value.execution_mode !== "real_draft") ||
      !(typeof value.listing_version_id === "string" && value.listing_version_id !== "" ||
        value.execution_mode === "real_draft" && value.listing_version_id === null) ||
      typeof value.workflow_completed !== "boolean" ||
      typeof value.pending_effects !== "number" || !Number.isSafeInteger(value.pending_effects) || value.pending_effects < 0 ||
      typeof value.fixture_completed !== "boolean" ||
      !(value.completed_at === null || (typeof value.completed_at === "string" && Number.isFinite(Date.parse(value.completed_at)))) ||
      (value.workflow_completed !== (value.completed_at !== null)) ||
      (value.fixture_completed !== (value.execution_mode === "fixture" && value.workflow_completed)) ||
      (value.workflow_completed && value.pending_effects > 0) ||
      !Array.isArray(value.jobs) || !Array.isArray(value.recoveries) || !Array.isArray(value.artifacts)) return false;
  return value.jobs.every((job) => isObject(job) && hasStrings(job, ["id", "job_type", "status"])) &&
    value.recoveries.every((proof) => isRecovery(proof, value.jobs as RunJob[])) &&
    new Set(value.recoveries.map((proof) => proof.job_id)).size === value.recoveries.length &&
    value.artifacts.every((artifact) => isObject(artifact) &&
      hasStrings(artifact, ["id", "label", "kind", "media_type", "href"]) &&
      typeof artifact.id === "string" && isArtifactIdentifier(artifact.id) &&
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
