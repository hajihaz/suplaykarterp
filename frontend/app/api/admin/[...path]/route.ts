import { NextRequest } from "next/server";

import { proxyRequest } from "../../../../lib/server-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

async function proxyAdminPath(request: NextRequest, context: RouteContext) {
  const params = await context.params;
  const suffix = (params.path || []).map(encodeURIComponent).join("/");
  return proxyRequest(request, `/admin/${suffix}`);
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyAdminPath(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyAdminPath(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyAdminPath(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyAdminPath(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyAdminPath(request, context);
}
