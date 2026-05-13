from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.monitoring import record_alert  # noqa: E402
from app.services.operations import (  # noqa: E402
    backup_due,
    cleanup_backups,
    create_backup,
    prune_operational_data,
    recent_metric_snapshots,
    record_metric_snapshot,
    run_watchdog_checks,
)


def _rotate_uvicorn_log() -> dict[str, Any]:
    log_path = settings.uvicorn_log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = 4 * 1024 * 1024
    rotated = False
    archive_path = None
    if log_path.exists() and log_path.stat().st_size > max_bytes:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive_path = log_path.with_name(f"{log_path.name}.{stamp}")
        log_path.rename(archive_path)
        log_path.touch()
        rotated = True

    removed: list[str] = []
    cutoff_seconds = max(1, settings.log_file_retention_days) * 86400
    now = datetime.now(timezone.utc).timestamp()
    for candidate in sorted(log_path.parent.glob(f"{log_path.name}.*")):
        try:
            if now - candidate.stat().st_mtime > cutoff_seconds:
                candidate.unlink()
                removed.append(candidate.name)
        except OSError:
            continue

    return {
        "log_path": str(log_path),
        "rotated": rotated,
        "archive_path": str(archive_path) if archive_path else "",
        "removed": removed,
    }


def _run_scheduled_cycle() -> dict[str, Any]:
    metrics = run_watchdog_checks()
    rotated = _rotate_uvicorn_log()
    pruned = prune_operational_data()
    backup = None
    if backup_due():
        backup = create_backup("scheduled backup")
    cleanup = cleanup_backups()
    return {
        "metrics": metrics,
        "log_rotation": rotated,
        "pruned": pruned,
        "backup": backup,
        "cleanup": cleanup,
        "metric_history_size": len(recent_metric_snapshots()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HajiHaz AI maintenance tasks.")
    parser.add_argument(
        "task",
        nargs="?",
        default="scheduled",
        choices=["scheduled", "watchdog", "backup", "cleanup", "snapshot", "rotate-logs"],
    )
    args = parser.parse_args()

    try:
        if args.task == "scheduled":
            payload = _run_scheduled_cycle()
        elif args.task == "watchdog":
            payload = {"metrics": run_watchdog_checks()}
        elif args.task == "backup":
            payload = {"backup": create_backup("manual script backup")}
        elif args.task == "cleanup":
            payload = {"cleanup": cleanup_backups(), "pruned": prune_operational_data()}
        elif args.task == "snapshot":
            payload = {"metrics": record_metric_snapshot("manual snapshot")}
        else:
            payload = {"log_rotation": _rotate_uvicorn_log()}
        print(json.dumps(payload, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - defensive operational wrapper
        record_alert("error", "Maintenance task failed", f"task={args.task} error={exc}", source="ops-maintenance")
        print(json.dumps({"ok": False, "task": args.task, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
