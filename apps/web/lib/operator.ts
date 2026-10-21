export const operatorViews = ["now", "pipeline", "shop", "blocked", "decisions", "incidents", "settings"] as const;
export type OperatorView = typeof operatorViews[number];

export interface OperatorRecord {
  id: string;
  label: string;
  state: string;
  detail: string;
  product_id: string | null;
  listing_version_id: string | null;
}
export interface OperatorEnvelope {
  run_id: string;
  view: OperatorView;
  items: OperatorRecord[];
}
export type OperatorResult = { kind: "ready"; data: OperatorEnvelope } | { kind: "unavailable" };

function isRecord(value: unknown): value is OperatorRecord {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  return ["id", "label", "state", "detail"].every((key) => typeof row[key] === "string") &&
    [row.product_id, row.listing_version_id].every((id) => id === null || typeof id === "string");
}

export async function fetchOperatorView(view: OperatorView, runId?: string): Promise<OperatorResult> {
  const base = process.env.API_BASE_URL;
  if (!base) return { kind: "unavailable" };
  try {
    const url = new URL(base.replace(/\/$/, "") + "/operator/" + view);
    if (runId !== undefined) url.searchParams.set("run_id", runId);
    const response = await fetch(url.toString(), { cache: "no-store", signal: AbortSignal.timeout(5000) });
    if (!response.ok) return { kind: "unavailable" };
    const data: unknown = await response.json();
    if (!data || typeof data !== "object") return { kind: "unavailable" };
    const envelope = data as Record<string, unknown>;
    if (typeof envelope.run_id !== "string" || !envelope.run_id || envelope.view !== view ||
      (runId !== undefined && envelope.run_id !== runId) ||
      !Array.isArray(envelope.items) || !envelope.items.every(isRecord)) {
      return { kind: "unavailable" };
    }
    return { kind: "ready", data: envelope as unknown as OperatorEnvelope };
  } catch {
    return { kind: "unavailable" };
  }
}
