import { isArtifactIdentifier, isRunIdentifier } from "../../../../../../lib/operator-summary";

export const dynamic = "force-dynamic";
const safeHeaders = ["content-type", "content-disposition", "content-security-policy", "x-content-type-options",
  "referrer-policy", "cross-origin-resource-policy"];
const inertPolicy = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'; frame-ancestors 'self'";
function unavailable(status: number) {
  return Response.json({ detail: "Artifact unavailable" }, { status, headers: { "Cache-Control": "no-store" } });
}

export async function GET(_request: Request, { params }: {
  params: Promise<{ runId: string; artifactId: string }>;
}) {
  const { runId, artifactId } = await params;
  if (!isRunIdentifier(runId) || !isArtifactIdentifier(artifactId)) return unavailable(404);
  const base = process.env.API_BASE_URL;
  if (!base) return unavailable(503);
  try {
    const url = new URL(base.replace(/\/$/, "") +
      `/operator/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactId)}`);
    const upstream = await fetch(url.toString(), {
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000),
    });
    if (!upstream.ok) return unavailable([404, 409, 503].includes(upstream.status) ? upstream.status : 502);
    const headers = new Headers();
    for (const name of safeHeaders) {
      const value = upstream.headers.get(name);
      if (value) headers.set(name, value);
    }
    headers.set("Cache-Control", "no-store");
    headers.set("X-Content-Type-Options", "nosniff");
    if (!headers.has("Content-Security-Policy")) headers.set("Content-Security-Policy", inertPolicy);
    return new Response(upstream.body, { status: 200, headers });
  } catch {
    return unavailable(503);
  }
}
