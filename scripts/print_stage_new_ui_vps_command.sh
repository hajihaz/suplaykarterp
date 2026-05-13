#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
ARCHIVE_PATH="$WORK_DIR/hajihaz-stage-new-ui.tar.gz"
BASE64_PATH="$WORK_DIR/hajihaz-stage-new-ui.tar.gz.b64"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

tar -czf "$ARCHIVE_PATH" \
  preview/new-ui.html \
  preview/hajihaz-ui.css \
  preview/hajihaz-ui.js \
  ops/vps/stage_preview_new_ui.sh

base64 <"$ARCHIVE_PATH" >"$BASE64_PATH"

cat <<'HEADER'
APP_ROOT=${APP_ROOT:-/home/hajirp/hajihaz-app}
set -euo pipefail
rm -rf /tmp/hajihaz-stage-new-ui
mkdir -p /tmp/hajihaz-stage-new-ui
cat >/tmp/hajihaz-stage-new-ui.tar.gz.b64 <<'B64'
HEADER

cat "$BASE64_PATH"

cat <<'FOOTER'
B64
base64 -d /tmp/hajihaz-stage-new-ui.tar.gz.b64 >/tmp/hajihaz-stage-new-ui.tar.gz
tar -xzf /tmp/hajihaz-stage-new-ui.tar.gz -C /tmp/hajihaz-stage-new-ui
chmod +x /tmp/hajihaz-stage-new-ui/ops/vps/stage_preview_new_ui.sh
APP_ROOT="$APP_ROOT" /tmp/hajihaz-stage-new-ui/ops/vps/stage_preview_new_ui.sh /tmp/hajihaz-stage-new-ui
rm -rf /tmp/hajihaz-stage-new-ui /tmp/hajihaz-stage-new-ui.tar.gz /tmp/hajihaz-stage-new-ui.tar.gz.b64
FOOTER
