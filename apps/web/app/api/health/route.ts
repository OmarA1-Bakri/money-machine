import { NextResponse } from "next/server";
import { fetchOperatorView } from "../../../lib/operator";

export const dynamic = "force-dynamic";

export async function GET() {
  const result = await fetchOperatorView("now");
  return NextResponse.json({
    service: "operator-console",
    status: result.kind === "ready" ? "available" : "unavailable",
    externalActions: false,
    businessTransitions: false,
    dependencies: [{ name: "API", state: result.kind === "ready" ? "verified" : "unverified" }],
  }, { status: result.kind === "ready" ? 200 : 503 });
}
