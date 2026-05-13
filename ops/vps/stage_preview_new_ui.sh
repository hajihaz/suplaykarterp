#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
STAGE_ROOT="${1:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

if [ -z "$STAGE_ROOT" ]; then
  echo "usage: APP_ROOT=/path/to/app $0 /path/to/extracted-stage-root"
  exit 1
fi

PREVIEW_DIR="$APP_ROOT/preview"
BACKUP_DIR="$APP_ROOT/tmp/ui-stage-backups/$STAMP"

FILES=(
  "preview/new-ui.html"
  "preview/hajihaz-ui.css"
  "preview/hajihaz-ui.js"
)

mkdir -p "$PREVIEW_DIR" "$BACKUP_DIR"

for relative_path in "${FILES[@]}"; do
  source_path="$STAGE_ROOT/$relative_path"
  target_path="$APP_ROOT/$relative_path"
  target_dir="$(dirname "$target_path")"

  if [ ! -f "$source_path" ]; then
    echo "missing staged file: $source_path"
    exit 1
  fi

  mkdir -p "$target_dir"
  if [ -f "$target_path" ]; then
    cp "$target_path" "$BACKUP_DIR/$(basename "$target_path").bak"
  fi
  install -m 0644 "$source_path" "$target_path"
done

echo "--- STAGED FILE CHECK ---"
ls -lh \
  "$PREVIEW_DIR/new-ui.html" \
  "$PREVIEW_DIR/hajihaz-ui.css" \
  "$PREVIEW_DIR/hajihaz-ui.js"

echo "--- CONTENT CHECK ---"
grep -n "/preview/hajihaz-ui.css" "$PREVIEW_DIR/new-ui.html"
grep -n "/preview/hajihaz-ui.js" "$PREVIEW_DIR/new-ui.html"
grep -n 'fetch(`${API_BASE}/chat`' "$PREVIEW_DIR/hajihaz-ui.js"

echo "--- APP HEALTH CHECK ---"
(curl -fsS http://127.0.0.1:8091/health || curl -fsS http://127.0.0.1:8000/health || true)
echo

echo "backup saved to $BACKUP_DIR"
echo "staged UI ready at: https://hajihazai.allbeesolutions.com/preview/new-ui.html"
echo "homepage / remains untouched"
