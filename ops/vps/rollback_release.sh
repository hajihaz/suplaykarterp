#!/bin/bash
set -euo pipefail

APP_NAME="${APP_NAME:-hajihaz}"
RELEASES_DIR="${RELEASES_DIR:-$HOME/releases/$APP_NAME}"
APP_ROOT="${APP_ROOT:-$HOME/htdocs/hajihaz.82.29.160.39.sslip.io}"
TARGET_RELEASE="${1:-}"
EXCLUDES=(
  --exclude=.env
  --exclude=.venv
  --exclude=backend/data
  --exclude=logs
  --exclude=tmp
  --exclude=.well-known
)

if [ -z "$TARGET_RELEASE" ]; then
  echo "available releases:"
  find "$RELEASES_DIR" -maxdepth 1 -mindepth 1 -type d | sort
  echo "usage: $0 /full/path/to/release"
  exit 1
fi

if [ ! -d "$TARGET_RELEASE" ]; then
  echo "release not found: $TARGET_RELEASE"
  exit 1
fi

rsync -a --checksum --delete "${EXCLUDES[@]}" "$TARGET_RELEASE"/ "$APP_ROOT"/
echo "rolled back from $TARGET_RELEASE into $APP_ROOT"
