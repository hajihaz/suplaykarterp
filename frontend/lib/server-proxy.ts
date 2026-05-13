import { NextRequest, NextResponse } from "next/server";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function getApiBaseUrl(): string {
  const explicitBaseUrl = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
  if (explicitBaseUrl) {
    return trimTrailingSlash(explicitBaseUrl);
  }

  const hostPort = process.env.API_BASE_HOSTPORT?.trim();
  if (hostPort) {
    return `http://${trimTrailingSlash(hostPort)}`;
  }

  return DEFAULT_API_BASE_URL;
}

export async function proxyRequest(request: NextRequest, path: string): Promise<NextResponse> {
  const targetUrl = `${getApiBaseUrl()}${path}${request.nextUrl.search || ""}`;
  const body =
    request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();
  const contentType = request.headers.get("content-type");

  try {
    const upstreamResponse = await fetch(targetUrl, {
      method: request.method,
      headers: {
        ...(contentType ? { "Content-Type": contentType } : {}),
        ...(request.headers.get("authorization")
          ? { Authorization: request.headers.get("authorization") as string }
          : {})
      },
      body: body || undefined,
      cache: "no-store"
    });

    const responseText = await upstreamResponse.text();
    const contentType = upstreamResponse.headers.get("content-type") || "application/json";

    return new NextResponse(responseText, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "no-store"
      }
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend service is unavailable. Check API_BASE_URL and backend health." },
      { status: 503 }
    );
  }
}
