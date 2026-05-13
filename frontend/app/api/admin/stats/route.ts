import { NextRequest } from "next/server";

import { proxyRequest } from "../../../../lib/server-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  return proxyRequest(request, "/admin/stats");
}
