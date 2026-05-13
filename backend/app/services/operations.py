from __future__ import annotations

import json
import os
import shutil
import socket
import zipfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.core.config import settings
from app.db import get_db
from app.services.monitoring import record_alert, record_health_check, tail_logs, uptime_seconds
from app.services.rag import export_documents


def _cutoff_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _memory_stats() -> tuple[int, int]:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return 0, 0
    values: dict[str, int] = {}
    for line in meminfo.read_text().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parts = value.strip().split()
        if not parts:
            continue
        try:
            values[key.strip()] = int(parts[0]) * 1024
        except ValueError:
            continue
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    used = max(0, total - available)
    return used, total


def gather_resource_metrics() -> dict[str, Any]:
    load_1, load_5, load_15 = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    disk = shutil.disk_usage(settings.database_path.parent)
    memory_used, memory_total = _memory_stats()
    database_size = _path_size(settings.database_path)
    log_size = _path_size(settings.app_log_path)
    uploads_size = _path_size(settings.uploads_dir)
    backup_size = _path_size(settings.backup_dir)
    memory_percent = round((memory_used / memory_total) * 100, 2) if memory_total else 0.0
    disk_percent = round((disk.used / disk.total) * 100, 2) if disk.total else 0.0
    ollama_reachable = False
    if settings.ollama_base_url:
        try:
            response = httpx.get(f"{settings.ollama_base_url}/tags", timeout=1.6)
            ollama_reachable = response.status_code == 200
        except httpx.HTTPError:
            ollama_reachable = False
    return {
        "hostname": socket.gethostname(),
        "cpu_load_1": round(load_1, 3),
        "cpu_load_5": round(load_5, 3),
        "cpu_load_15": round(load_15, 3),
        "memory_used_bytes": memory_used,
        "memory_total_bytes": memory_total,
        "memory_percent": memory_percent,
        "disk_used_bytes": disk.used,
        "disk_total_bytes": disk.total,
        "disk_percent": disk_percent,
        "database_size_bytes": database_size,
        "log_size_bytes": log_size,
        "uploads_size_bytes": uploads_size,
        "backup_size_bytes": backup_size,
        "ollama_reachable": ollama_reachable,
        "uptime_seconds": uptime_seconds(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def record_metric_snapshot(notes: str = "") -> dict[str, Any]:
    metrics = gather_resource_metrics()
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO metric_snapshots (
                cpu_load_1,
                cpu_load_5,
                cpu_load_15,
                memory_used_bytes,
                memory_total_bytes,
                disk_used_bytes,
                disk_total_bytes,
                ollama_reachable,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics["cpu_load_1"],
                metrics["cpu_load_5"],
                metrics["cpu_load_15"],
                metrics["memory_used_bytes"],
                metrics["memory_total_bytes"],
                metrics["disk_used_bytes"],
                metrics["disk_total_bytes"],
                1 if metrics["ollama_reachable"] else 0,
                notes[:400],
            ),
        )
        conn.commit()
    return metrics


def recent_metric_snapshots(limit: int | None = None) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                cpu_load_1,
                cpu_load_5,
                cpu_load_15,
                memory_used_bytes,
                memory_total_bytes,
                disk_used_bytes,
                disk_total_bytes,
                ollama_reachable,
                notes,
                created_at
            FROM metric_snapshots
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, limit or settings.metrics_snapshot_limit),),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "cpu_load_1": float(row["cpu_load_1"]),
            "cpu_load_5": float(row["cpu_load_5"]),
            "cpu_load_15": float(row["cpu_load_15"]),
            "memory_used_bytes": int(row["memory_used_bytes"]),
            "memory_total_bytes": int(row["memory_total_bytes"]),
            "disk_used_bytes": int(row["disk_used_bytes"]),
            "disk_total_bytes": int(row["disk_total_bytes"]),
            "ollama_reachable": bool(row["ollama_reachable"]),
            "notes": str(row["notes"] or ""),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def record_usage_event(
    event_type: str,
    route: str,
    *,
    mode: str = "",
    prompt_length: int = 0,
    answer_length: int = 0,
    citation_count: int = 0,
    provider: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO usage_events (event_type, route, mode, prompt_length, answer_length, citation_count, provider, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type[:80],
                route[:120],
                mode[:80],
                max(0, prompt_length),
                max(0, answer_length),
                max(0, citation_count),
                provider[:80],
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()


def build_usage_analytics(days: int | None = None) -> dict[str, Any]:
    window = max(1, days or settings.analytics_window_days)
    cutoff = _cutoff_iso(window)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT event_type, route, mode, prompt_length, answer_length, citation_count, provider, created_at
            FROM usage_events
            WHERE created_at >= ?
            ORDER BY created_at DESC
            """,
            (cutoff,),
        ).fetchall()

    total_requests = len(rows)
    mode_counter = Counter(str(row["mode"] or "unknown") for row in rows)
    route_counter = Counter(str(row["route"] or "unknown") for row in rows)
    day_counter = Counter(str(row["created_at"])[:10] for row in rows)
    citation_total = sum(int(row["citation_count"] or 0) for row in rows)
    prompt_total = sum(int(row["prompt_length"] or 0) for row in rows)
    answer_total = sum(int(row["answer_length"] or 0) for row in rows)
    return {
        "window_days": window,
        "total_requests": total_requests,
        "by_mode": dict(mode_counter),
        "top_routes": [{"route": route, "count": count} for route, count in route_counter.most_common(5)],
        "daily_requests": [{"day": day, "count": count} for day, count in sorted(day_counter.items())],
        "average_citations": round(citation_total / total_requests, 2) if total_requests else 0.0,
        "average_prompt_length": round(prompt_total / total_requests, 1) if total_requests else 0.0,
        "average_answer_length": round(answer_total / total_requests, 1) if total_requests else 0.0,
    }


def _sanitized_config_snapshot() -> dict[str, Any]:
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "public_base_url": settings.public_base_url,
        "ai_provider": settings.ai_provider,
        "online_search_enabled": settings.online_search_enabled,
        "alert_webhook_configured": bool(settings.alert_webhook_url),
        "alert_email_configured": bool(settings.alert_email_host and settings.alert_email_recipients),
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "backup_retention_days": settings.backup_retention_days,
        "backup_retention_count": settings.backup_retention_count,
        "ocr_enabled": settings.ocr_enabled,
        "ocr_languages": settings.ocr_languages,
    }


def create_backup(note: str = "manual backup") -> dict[str, Any]:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_name = f"hajihaz-backup-{timestamp}.zip"
    archive_path = settings.backup_dir / archive_name

    library_export, _media_type, _filename = export_documents("json")
    config_snapshot = json.dumps(_sanitized_config_snapshot(), indent=2)

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if settings.database_path.exists():
            archive.write(settings.database_path, arcname="data/hajihaz.db")
        archive.writestr("exports/library.json", library_export)
        archive.writestr("config/config_snapshot.json", config_snapshot)
        if settings.include_logs_in_backup and settings.app_log_path.exists():
            archive.write(settings.app_log_path, arcname="logs/hajihaz.log")
        if settings.uploads_dir.exists():
            for item in settings.uploads_dir.rglob("*"):
                if item.is_file():
                    archive.write(item, arcname=f"uploads/{item.relative_to(settings.uploads_dir)}")

    size_bytes = archive_path.stat().st_size if archive_path.exists() else 0
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO backup_runs (archive_name, archive_path, size_bytes, status, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (archive_name, str(archive_path), size_bytes, "ready", note[:300]),
        )
        conn.commit()
        backup_id = int(cursor.lastrowid)

    cleanup_backups()
    return {
        "id": backup_id,
        "archive_name": archive_name,
        "archive_path": str(archive_path),
        "size_bytes": size_bytes,
        "status": "ready",
        "note": note,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def list_backups(limit: int = 20) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, archive_name, archive_path, size_bytes, status, note, created_at
            FROM backup_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "archive_name": str(row["archive_name"]),
            "archive_path": str(row["archive_path"]),
            "size_bytes": int(row["size_bytes"]),
            "status": str(row["status"]),
            "note": str(row["note"] or ""),
            "created_at": str(row["created_at"]),
            "download_ready": Path(str(row["archive_path"])).exists(),
        }
        for row in rows
    ]


def cleanup_backups() -> dict[str, Any]:
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, settings.backup_retention_days))
    backups = list_backups(limit=500)
    kept = 0
    for backup in backups:
        backup_path = Path(backup["archive_path"])
        created_at = datetime.fromisoformat(backup["created_at"].replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        should_keep = kept < settings.backup_retention_count and created_at >= cutoff
        if should_keep:
            kept += 1
            continue
        if backup_path.exists():
            backup_path.unlink()
            removed.append(backup["archive_name"])
    if removed:
        with get_db() as conn:
            placeholders = ",".join("?" for _ in removed)
            conn.execute(
                f"DELETE FROM backup_runs WHERE archive_name IN ({placeholders})",
                tuple(removed),
            )
            conn.commit()
    return {"removed": removed, "remaining": list_backups(limit=50)}


def backup_due() -> bool:
    backups = list_backups(limit=1)
    if not backups:
        return True
    latest = backups[0]
    created_at = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    interval = timedelta(hours=max(1, settings.backup_interval_hours))
    return datetime.now(timezone.utc) - created_at >= interval


def backup_file_path(backup_id: int) -> Path | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT archive_path
            FROM backup_runs
            WHERE id = ?
            """,
            (backup_id,),
        ).fetchone()
    if row is None:
        return None
    path = Path(str(row["archive_path"]))
    if not path.exists():
        return None
    return path


def build_secret_audit() -> dict[str, Any]:
    checks = [
        {
            "name": "secret_key",
            "ok": settings.secret_key not in {"", "dev-secret-key"},
            "detail": "Application secret key is configured." if settings.secret_key not in {"", "dev-secret-key"} else "Default or empty SECRET_KEY is still in use.",
        },
        {
            "name": "admin_password",
            "ok": bool(settings.admin_password_hash or settings.admin_password not in {"", "change-this-password"}),
            "detail": "Admin password has been customized." if (settings.admin_password_hash or settings.admin_password not in {"", "change-this-password"}) else "Admin password still looks like a placeholder.",
        },
        {
            "name": "webhook_alerts",
            "ok": bool(settings.alert_webhook_url),
            "detail": "External webhook alerts are configured." if settings.alert_webhook_url else "No external webhook alert target is configured yet.",
        },
        {
            "name": "email_alerts",
            "ok": bool(settings.alert_email_host and settings.alert_email_recipients),
            "detail": "Email alerts are configured." if (settings.alert_email_host and settings.alert_email_recipients) else "Email alerts are not configured yet.",
        },
        {
            "name": "public_base_url",
            "ok": bool(settings.public_base_url),
            "detail": "Public base URL is configured." if settings.public_base_url else "PUBLIC_BASE_URL is empty, so some audit and health features use localhost defaults.",
        },
    ]
    issues = [item["detail"] for item in checks if not item["ok"]]
    return {
        "status": "healthy" if not issues else "needs-attention",
        "issues": issues,
        "checks": checks,
    }


def prune_operational_data() -> dict[str, Any]:
    result: dict[str, Any] = {}
    retention_map = {
        "request_logs": settings.request_log_retention_days,
        "alerts": settings.alert_retention_days,
        "health_checks": settings.health_check_retention_days,
        "usage_events": settings.usage_event_retention_days,
        "metric_snapshots": settings.metric_snapshot_retention_days,
    }
    with get_db() as conn:
        for table_name, retention_days in retention_map.items():
            cutoff = _cutoff_iso(retention_days)
            cursor = conn.execute(f"DELETE FROM {table_name} WHERE created_at < ?", (cutoff,))
            result[table_name] = cursor.rowcount
        conn.commit()
    return result


def run_watchdog_checks() -> dict[str, Any]:
    metrics = record_metric_snapshot("watchdog")
    record_health_check(
        "resource_usage",
        metrics["disk_percent"] < 92 and metrics["memory_percent"] < 95,
        f"disk={metrics['disk_percent']}% memory={metrics['memory_percent']}% load1={metrics['cpu_load_1']}",
    )
    if settings.ollama_base_url:
        record_health_check(
            "ollama_watchdog",
            metrics["ollama_reachable"],
            f"ollama_reachable={metrics['ollama_reachable']} base={settings.ollama_base_url}",
        )
        if not metrics["ollama_reachable"]:
            record_alert("warning", "Ollama runtime unreachable", "The local/server Ollama endpoint did not answer the watchdog probe.", source="watchdog")
    if settings.public_base_url:
        try:
            response = httpx.get(f"{settings.public_base_url}/health", timeout=4.0, follow_redirects=True)
            ok = response.status_code == 200 and "HajiHaz AI" in response.text
            record_health_check(
                "public_edge_health",
                ok,
                f"status={response.status_code} url={settings.public_base_url}/health",
            )
        except httpx.HTTPError as exc:
            record_health_check("public_edge_health", False, f"url={settings.public_base_url}/health error={exc.__class__.__name__}")
            record_alert(
                "warning",
                "Public health endpoint unreachable",
                f"The public health check for {settings.public_base_url}/health failed.",
                source="watchdog",
            )
    if metrics["disk_percent"] >= 92:
        record_alert("warning", "Disk usage high", f"Disk usage reached {metrics['disk_percent']}%.", source="watchdog")
    return metrics


def operational_overview() -> dict[str, Any]:
    latest_metrics = gather_resource_metrics()
    return {
        "metrics": latest_metrics,
        "metric_history": recent_metric_snapshots(),
        "analytics": build_usage_analytics(),
        "backups": list_backups(),
        "secret_audit": build_secret_audit(),
        "log_tail": tail_logs(),
    }
