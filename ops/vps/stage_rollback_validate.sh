#!/bin/bash
set -euo pipefail

HOME_DIR="${HOME_DIR:-$HOME}"
LIVE_APP_ROOT="${LIVE_APP_ROOT:-$HOME_DIR/htdocs/hajihaz.82.29.160.39.sslip.io}"
STAGE_ROOT="${STAGE_ROOT:-$HOME_DIR/staging/hajihaz-stage}"
STAGE_PORT="${STAGE_PORT:-8092}"
STAGE_PID_FILE="$STAGE_ROOT/tmp/hajihaz-stage.pid"
ROLLBACK_ROOT="${ROLLBACK_ROOT:-$HOME_DIR/staging/rollback-target}"
ROLLBACK_RELEASES="${ROLLBACK_RELEASES:-$HOME_DIR/staging/releases}"
ROLLBACK_BACKUPS="${ROLLBACK_BACKUPS:-$HOME_DIR/staging/backups}"
TMP_DIR="${TMP_DIR:-$HOME_DIR/tmp}"
ARCHIVE_PATH="$TMP_DIR/stage-release-v2.tar.gz"

cleanup() {
  if [ -f "$STAGE_PID_FILE" ]; then
    APP_ROOT="$STAGE_ROOT" APP_PID_FILE="$STAGE_PID_FILE" PORT_VALUE="$STAGE_PORT" "$STAGE_ROOT/ops/vps/manage_hajihaz.sh" stop >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

mkdir -p "$HOME_DIR/staging" "$TMP_DIR"
rm -rf "$STAGE_ROOT" "$ROLLBACK_ROOT" "$ROLLBACK_RELEASES" "$ROLLBACK_BACKUPS"
mkdir -p "$STAGE_ROOT" "$ROLLBACK_ROOT" "$ROLLBACK_RELEASES" "$ROLLBACK_BACKUPS"

rsync -a \
  --exclude=.venv \
  --exclude=backend/data \
  --exclude=logs \
  --exclude=tmp \
  --exclude=.well-known \
  "$LIVE_APP_ROOT"/ "$STAGE_ROOT"/

mkdir -p "$STAGE_ROOT/backend/data" "$STAGE_ROOT/logs/app" "$STAGE_ROOT/tmp"
cp "$LIVE_APP_ROOT/.env" "$STAGE_ROOT/.env"

python3 - "$STAGE_ROOT/.env" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
raw = env_path.read_text(encoding="utf-8")
lines = raw.splitlines()
updates = {
    "APP_ENV": "staging",
    "DATABASE_URL": "sqlite:///backend/data/hajihaz-stage.db",
    "APP_LOG_PATH": "logs/app/hajihaz-stage.log",
    "BACKUP_DIR": "backend/data/backups-stage",
    "UVICORN_LOG_PATH": "logs/app/uvicorn-stage.log",
}
found = set()
new_lines = []
for line in lines:
    if not line or line.lstrip().startswith("#") or "=" not in line:
        new_lines.append(line)
        continue
    key, _ = line.split("=", 1)
    if key in updates:
        new_lines.append(f"{key}={updates[key]}")
        found.add(key)
    else:
        new_lines.append(line)
for key, value in updates.items():
    if key not in found:
        new_lines.append(f"{key}={value}")
env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
PY

APP_ROOT="$STAGE_ROOT" APP_PID_FILE="$STAGE_PID_FILE" PORT_VALUE="$STAGE_PORT" "$STAGE_ROOT/ops/vps/manage_hajihaz.sh" start >/tmp/hajihaz-stage-start.log 2>&1

STAGE_HEALTH=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if STAGE_HEALTH="$(curl -fsS "http://127.0.0.1:${STAGE_PORT}/health" 2>/dev/null)"; then
    break
  fi
  sleep 1
done
if [ -z "$STAGE_HEALTH" ]; then
  echo "staging health check failed"
  cat /tmp/hajihaz-stage-start.log || true
  exit 1
fi

printf 'version=one\n' >"$ROLLBACK_ROOT/ROLLBACK_MARKER.txt"
mkdir -p "$TMP_DIR/stage-release-v2"
printf 'version=two\n' >"$TMP_DIR/stage-release-v2/ROLLBACK_MARKER.txt"
tar -czf "$ARCHIVE_PATH" -C "$TMP_DIR" stage-release-v2

APP_ROOT="$ROLLBACK_ROOT" RELEASES_DIR="$ROLLBACK_RELEASES" BACKUP_DIR="$ROLLBACK_BACKUPS" "$LIVE_APP_ROOT/ops/vps/deploy_release.sh" "$ARCHIVE_PATH" >/tmp/hajihaz-rollback-deploy.log 2>&1
DEPLOYED_MARKER="$(cat "$ROLLBACK_ROOT/ROLLBACK_MARKER.txt")"
LATEST_BACKUP="$(find "$ROLLBACK_BACKUPS" -maxdepth 1 -mindepth 1 -type d -name 'pre-deploy-*' | sort | tail -n 1)"
if [ -z "$LATEST_BACKUP" ]; then
  echo "rollback backup directory missing"
  cat /tmp/hajihaz-rollback-deploy.log || true
  exit 1
fi

APP_ROOT="$ROLLBACK_ROOT" "$LIVE_APP_ROOT/ops/vps/rollback_release.sh" "$LATEST_BACKUP" >/tmp/hajihaz-rollback-run.log 2>&1
ROLLED_BACK_MARKER="$(cat "$ROLLBACK_ROOT/ROLLBACK_MARKER.txt")"

APP_ROOT="$STAGE_ROOT" APP_PID_FILE="$STAGE_PID_FILE" PORT_VALUE="$STAGE_PORT" "$STAGE_ROOT/ops/vps/manage_hajihaz.sh" stop >/dev/null 2>&1 || true

printf 'STAGE_HEALTH=%s\n' "$STAGE_HEALTH"
printf 'DEPLOYED_MARKER=%s\n' "$DEPLOYED_MARKER"
printf 'ROLLED_BACK_MARKER=%s\n' "$ROLLED_BACK_MARKER"
printf 'ROLLBACK_BACKUP=%s\n' "$LATEST_BACKUP"
