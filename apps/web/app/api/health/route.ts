import { NextResponse } from "next/server";

export const dynamic = "force-static";

export function GET() {
  return NextResponse.json({
    service: "operator-console",
    status: "healthy",
    dependencies: "unverified",
    externalActions: false,
  });
}
