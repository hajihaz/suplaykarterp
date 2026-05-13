#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
ARCHIVE_PATH="$WORK_DIR/hajihaz-chatgpt-ui.tar.gz"
BASE64_PATH="$WORK_DIR/hajihaz-chatgpt-ui.tar.gz.b64"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

tar -czf "$ARCHIVE_PATH" \
  preview/admin.html \
  preview/app.js \
  preview/index.html \
  preview/hajihaz-ui.css \
  preview/hajihaz-ui.js \
  preview/styles.css \
  ops/vps/apply_chatgpt_ui_patch.sh

base64 <"$ARCHIVE_PATH" >"$BASE64_PATH"

cat <<'HEADER'
APP_ROOT=${APP_ROOT:-/home/hajirp/hajihaz-app}
set +e
rm -rf /tmp/hajihaz-chatgpt-ui
mkdir -p /tmp/hajihaz-chatgpt-ui
cat >/tmp/hajihaz-chatgpt-ui.tar.gz.b64 <<'B64'
HEADER

cat "$BASE64_PATH"

cat <<'FOOTER'
B64
base64 -d /tmp/hajihaz-chatgpt-ui.tar.gz.b64 >/tmp/hajihaz-chatgpt-ui.tar.gz
tar -xzf /tmp/hajihaz-chatgpt-ui.tar.gz -C /tmp/hajihaz-chatgpt-ui
chmod +x /tmp/hajihaz-chatgpt-ui/ops/vps/apply_chatgpt_ui_patch.sh
APP_ROOT="$APP_ROOT" bash /tmp/hajihaz-chatgpt-ui/ops/vps/apply_chatgpt_ui_patch.sh /tmp/hajihaz-chatgpt-ui
APPLY_STATUS=$?
rm -rf /tmp/hajihaz-chatgpt-ui /tmp/hajihaz-chatgpt-ui.tar.gz /tmp/hajihaz-chatgpt-ui.tar.gz.b64
exit "$APPLY_STATUS"
FOOTER
