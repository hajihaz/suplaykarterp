#!/bin/bash
set -euo pipefail

APP_NAME="${APP_NAME:-hajihaz}"
APP_ROOT="${APP_ROOT:-$HOME/htdocs/hajihaz.82.29.160.39.sslip.io}"
RELEASES_DIR="${RELEASES_DIR:-$HOME/releases/$APP_NAME}"
ARCHIVE_PATH="${1:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
NEW_RELEASE_DIR="$RELEASES_DIR/$STAMP"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/$APP_NAME}"
WORK_DIR="$(mktemp -d)"
EXCLUDES=(
  --exclude=.env
  --exclude=.venv
  --exclude=backend/data
  --exclude=logs
  --exclude=tmp
  --exclude=.well-known
)

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

if [ -z "$ARCHIVE_PATH" ]; then
  echo "usage: $0 /path/to/release.tar.gz"
  exit 1
fi

mkdir -p "$RELEASES_DIR" "$BACKUP_DIR"
tar -xzf "$ARCHIVE_PATH" -C "$WORK_DIR"

EXTRACTED_DIR="$WORK_DIR"
DIR_COUNT="$(find "$WORK_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l | tr -d ' ')"
FILE_COUNT="$(find "$WORK_DIR" -maxdepth 1 -mindepth 1 | wc -l | tr -d ' ')"
if [ "$DIR_COUNT" = "1" ] && [ "$FILE_COUNT" = "1" ]; then
  EXTRACTED_DIR="$(find "$WORK_DIR" -maxdepth 1 -mindepth 1 -type d | head -n 1)"
fi

mkdir -p "$NEW_RELEASE_DIR"
rsync -a --checksum "${EXCLUDES[@]}" "$EXTRACTED_DIR"/ "$NEW_RELEASE_DIR"/

if [ -d "$APP_ROOT" ]; then
  mkdir -p "$BACKUP_DIR/pre-deploy-$STAMP"
  rsync -a --checksum "${EXCLUDES[@]}" "$APP_ROOT"/ "$BACKUP_DIR/pre-deploy-$STAMP"/
fi

rsync -a --checksum --delete "${EXCLUDES[@]}" "$NEW_RELEASE_DIR"/ "$APP_ROOT"/
if [ -f "$APP_ROOT/backend/requirements.txt" ]; then
  if [ -x "$APP_ROOT/.venv/bin/pip" ]; then
    "$APP_ROOT/.venv/bin/pip" install -r "$APP_ROOT/backend/requirements.txt"
  else
    python3 -m pip install --break-system-packages -r "$APP_ROOT/backend/requirements.txt"
  fi
fi
if [ -x "$APP_ROOT/ops/vps/manage_hajihaz.sh" ]; then
  APP_ROOT="$APP_ROOT" "$APP_ROOT/ops/vps/manage_hajihaz.sh" restart
fi
echo "release deployed to $APP_ROOT"
echo "backup saved to $BACKUP_DIR/pre-deploy-$STAMP"
