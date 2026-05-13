from __future__ import annotations

import logging
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, List
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.db import get_db


APP_STARTED_AT = time.time()
_LOGGER_NAME = "hajihaz.app"
_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"


def _logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def configure_logging() -> None:
    logger = _logger()
    if logger.handlers:
        return

    log_path = settings.app_log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(log_path, maxBytes=1_500_000, backupCount=3)
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.propagate = False
    logger.info("logging_configured path=%s", log_path)


def uptime_seconds() -> int:
    return max(0, int(time.time() - APP_STARTED_AT))


def log_event(level: str, message: str) -> None:
    configure_logging()
    getattr(_logger(), level.lower(), _logger().info)(message)


def log_request(method: str, path: str, status_code: int, duration_ms: float, error_message: str | None = None) -> None:
    configure_logging()
    message = f"request method={method} path={path} status={status_code} duration_ms={duration_ms:.2f}"
    if error_message:
        message += f" error={error_message}"
    _logger().info(message)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO request_logs (method, path, status_code, duration_ms, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (method, path, status_code, duration_ms, error_message),
        )
        conn.commit()


def record_alert(level: str, title: str, detail: str, source: str = "system") -> None:
    configure_logging()
    detail = (detail or "").strip()[:1200] or "No detail provided."
    log_level = level.lower()
    getattr(_logger(), log_level if hasattr(_logger(), log_level) else "warning")(
        "alert level=%s source=%s title=%s detail=%s",
        level.upper(),
        source,
        title,
        detail,
    )
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO alerts (level, title, detail, source)
            VALUES (?, ?, ?, ?)
            """,
            (level.lower(), title.strip()[:160], detail, source.strip()[:160] or "system"),
        )
        conn.commit()
    _dispatch_webhook(level, title, detail, source)
    _dispatch_email(level, title, detail, source)


def record_health_check(name: str, ok: bool, detail: str) -> None:
    configure_logging()
    status = "ok" if ok else "degraded"
    _logger().info("health_check name=%s status=%s detail=%s", name, status, detail)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO health_checks (name, status, detail)
            VALUES (?, ?, ?)
            """,
            (name.strip()[:120], status, detail.strip()[:500]),
        )
        conn.commit()
    if not ok:
        record_alert("warning", f"{name} check degraded", detail, source="monitor")


def tail_logs(limit: int | None = None) -> List[str]:
    log_path = settings.app_log_path
    if not log_path.exists():
        return []
    lines = log_path.read_text(errors="ignore").splitlines()
    return lines[-max(1, limit or settings.log_tail_lines) :]


def recent_alerts(limit: int | None = None) -> List[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, level, title, detail, source, created_at
            FROM alerts
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, limit or settings.recent_alert_limit),),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "level": str(row["level"]),
            "title": str(row["title"]),
            "detail": str(row["detail"]),
            "source": str(row["source"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def recent_health_checks(limit: int | None = None) -> List[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, name, status, detail, created_at
            FROM health_checks
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, limit or settings.recent_log_limit),),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "status": str(row["status"]),
            "detail": str(row["detail"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def recent_request_logs(limit: int | None = None) -> List[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, method, path, status_code, duration_ms, error_message, created_at
            FROM request_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, limit or settings.recent_log_limit),),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "method": str(row["method"]),
            "path": str(row["path"]),
            "status_code": int(row["status_code"]),
            "duration_ms": round(float(row["duration_ms"]), 2),
            "error_message": str(row["error_message"] or ""),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def build_runtime_debug(ai_status: dict[str, Any], rag_stats: dict[str, Any], source_health: List[dict[str, Any]]) -> dict[str, Any]:
    alerts = recent_alerts()
    checks = recent_health_checks()
    logs = recent_request_logs()
    return {
        "uptime_seconds": uptime_seconds(),
        "log_path": str(settings.app_log_path),
        "recent_logs": logs,
        "recent_alerts": alerts,
        "recent_health_checks": checks,
        "log_tail": tail_logs(),
        "provider": ai_status,
        "library": rag_stats,
        "source_health": source_health,
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _dispatch_webhook(level: str, title: str, detail: str, source: str) -> None:
    if not settings.alert_webhook_url:
        return
    payload = {
        "level": level,
        "title": title,
        "detail": detail,
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        parsed = urlparse(settings.alert_webhook_url)
        if parsed.netloc.endswith("ntfy.sh"):
            httpx.post(
                settings.alert_webhook_url,
                content="\n".join(
                    [
                        f"Source: {source}",
                        f"Level: {level.upper()}",
                        "",
                        detail,
                    ]
                ),
                headers={
                    "Title": f"[HajiHaz AI] {title}",
                    "Tags": "warning" if level.lower() == "warning" else "rotating_light",
                },
                timeout=4.0,
            )
        else:
            httpx.post(settings.alert_webhook_url, json=payload, timeout=4.0)
    except httpx.HTTPError:
        _logger().warning("alert_webhook_failed source=%s title=%s", source, title)


def _dispatch_email(level: str, title: str, detail: str, source: str) -> None:
    if not (settings.alert_email_host and settings.alert_email_from and settings.alert_email_recipients):
        return

    message = EmailMessage()
    message["From"] = settings.alert_email_from
    message["To"] = ", ".join(settings.alert_email_recipients)
    message["Subject"] = f"[HajiHaz AI] {level.upper()} - {title}"
    message.set_content(
        "\n".join(
            [
                f"Level: {level}",
                f"Source: {source}",
                f"Time: {datetime.now(timezone.utc).isoformat()}",
                "",
                detail,
            ]
        )
    )

    try:
        with smtplib.SMTP(settings.alert_email_host, settings.alert_email_port, timeout=10) as smtp:
            if settings.alert_email_use_tls:
                smtp.starttls()
            if settings.alert_email_user:
                smtp.login(settings.alert_email_user, settings.alert_email_password)
            smtp.send_message(message)
    except OSError:
        _logger().warning("alert_email_failed source=%s title=%s", source, title)
