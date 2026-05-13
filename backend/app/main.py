from __future__ import annotations

from pathlib import Path
from time import perf_counter
from urllib.parse import urlunsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.rate_limit import rate_limit_retry_after
from app.core.security import ensure_primary_admin
from app.db import init_db
from app.routes.admin import router as admin_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.health import router as health_router
from app.routes.user_auth import router as user_auth_router
from app.sample_data import seed_if_empty
from app.services.monitoring import configure_logging, log_request, record_alert, record_health_check
from app.services.operations import prune_operational_data, record_metric_snapshot
from app.services.rag import repair_source_metadata


def create_app() -> FastAPI:
    docs_enabled = settings.app_env == "development"
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    preview_dir = Path(__file__).resolve().parents[2] / "preview"
    allow_origins = settings.cors_origins
    allow_credentials = False
    if settings.app_env == "development":
        allow_origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup() -> None:
        configure_logging()
        init_db()
        ensure_primary_admin()
        seed_if_empty()
        settings.backup_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        repair_source_metadata()
        prune_operational_data()
        record_metric_snapshot("startup")
        record_health_check("startup", True, f"Application booted in {settings.app_env} mode.")

    @app.middleware("http")
    async def monitor_requests(request: Request, call_next):
        request_host = request.headers.get("host", "").split(":", 1)[0].lower()
        if (
            settings.app_env != "development"
            and settings.public_base_url
            and request_host
            and request_host in settings.legacy_host_redirects
            and request_host != settings.public_host
        ):
            canonical_url = urlunsplit(
                (
                    request.url.scheme,
                    settings.public_host,
                    request.url.path,
                    request.url.query,
                    "",
                )
            )
            return RedirectResponse(url=canonical_url, status_code=308)

        retry_after = rate_limit_retry_after(request)
        if retry_after is not None:
            response = JSONResponse(
                {"detail": "Too many requests. Please wait a moment and try again."},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            _apply_security_headers(response)
            return response

        started_at = perf_counter()
        should_log_request = not request.url.path.startswith("/preview/")
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (perf_counter() - started_at) * 1000
            if should_log_request:
                log_request(request.method, request.url.path, 500, duration_ms, str(exc))
            record_alert("error", "Unhandled application error", str(exc), source=request.url.path)
            raise

        duration_ms = (perf_counter() - started_at) * 1000
        error_message = None if response.status_code < 500 else f"HTTP {response.status_code}"
        if should_log_request:
            log_request(request.method, request.url.path, response.status_code, duration_ms, error_message)
        _apply_security_headers(response)
        return response

    @app.get("/")
    def root():
        if preview_dir.exists():
            return FileResponse(preview_dir / "index.html")
        return {"app": settings.app_name, "status": "running"}

    @app.get("/new-ui")
    def new_ui_page():
        if preview_dir.exists():
            return FileResponse(preview_dir / "new-ui.html")
        return {"detail": "New UI is unavailable."}

    @app.get("/admin")
    def admin_page():
        if preview_dir.exists():
            return FileResponse(preview_dir / "admin.html")
        return {"detail": "Admin UI is unavailable."}

    @app.get("/privacy-policy")
    def privacy_policy_page():
        if preview_dir.exists():
            return FileResponse(preview_dir / "privacy-policy.html")
        return {"detail": "Privacy policy is unavailable."}

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots_txt() -> str:
        return "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n"

    @app.get("/sitemap.xml")
    def sitemap_xml(request: Request) -> Response:
        base_url = settings.public_base_url or str(request.base_url).rstrip("/")
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base_url}/</loc></url>
  <url><loc>{base_url}/privacy-policy</loc></url>
</urlset>
"""
        return Response(content=body, media_type="application/xml")

    @app.get("/favicon.ico")
    def favicon():
        favicon_path = preview_dir / "favicon.svg"
        if favicon_path.exists():
            return FileResponse(favicon_path, media_type="image/svg+xml")
        raise HTTPException(status_code=404, detail="Asset not found.")

    @app.get("/play-assets/{asset_path:path}")
    def play_asset(asset_path: str):
        asset_file = preview_dir / "play-assets" / asset_path
        if not asset_file.exists() or not asset_file.is_file():
            raise HTTPException(status_code=404, detail="Asset not found.")
        return FileResponse(asset_file, headers={"Access-Control-Allow-Origin": "*"})

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(user_auth_router)
    app.include_router(chat_router)
    app.include_router(admin_router)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.uploads_dir), name="uploads")
    if preview_dir.exists():
        app.mount("/preview", StaticFiles(directory=preview_dir, html=True), name="preview")
    return app


app = create_app()


def _apply_security_headers(response: Response) -> None:
    csp = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'; "
        "object-src 'none'; "
        "connect-src 'self' http://127.0.0.1:8000 http://localhost:8000 https://accounts.google.com; "
        "img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' https://accounts.google.com; "
        "frame-src 'self' https://accounts.google.com"
    )
    response.headers.setdefault("Content-Security-Policy", csp)
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    if settings.app_env != "development":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
