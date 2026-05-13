import { NextRequest } from "next/server";

import { proxyRequest } from "../../../lib/server-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  return proxyRequest(request, "/chat");
}
