#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
ARCHIVE_PATH="$WORK_DIR/hajihaz-orchestration-ux.tar.gz"
BASE64_PATH="$WORK_DIR/hajihaz-orchestration-ux.tar.gz.b64"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

tar -czf "$ARCHIVE_PATH" \
  backend/app/db.py \
  backend/app/main.py \
  backend/app/schemas.py \
  backend/app/core/security.py \
  backend/app/routes/chat.py \
  backend/app/routes/user_auth.py \
  backend/app/services/anthropic_client.py \
  backend/app/services/orchestration.py \
  backend/app/services/response_builder.py \
  backend/app/services/web_lookup.py \
  preview/index.html \
  preview/hajihaz-ui.css \
  preview/hajihaz-ui.js \
  ops/vps/apply_orchestration_ux_patch.sh

base64 <"$ARCHIVE_PATH" >"$BASE64_PATH"

cat <<'HEADER'
APP_ROOT=${APP_ROOT:-/home/hajirp/hajihaz-app}
set +e
rm -rf /tmp/hajihaz-orchestration-ux
mkdir -p /tmp/hajihaz-orchestration-ux
cat >/tmp/hajihaz-orchestration-ux.tar.gz.b64 <<'B64'
HEADER

cat "$BASE64_PATH"

cat <<'FOOTER'
B64
base64 -d /tmp/hajihaz-orchestration-ux.tar.gz.b64 >/tmp/hajihaz-orchestration-ux.tar.gz
tar -xzf /tmp/hajihaz-orchestration-ux.tar.gz -C /tmp/hajihaz-orchestration-ux
chmod +x /tmp/hajihaz-orchestration-ux/ops/vps/apply_orchestration_ux_patch.sh
APP_ROOT="$APP_ROOT" bash /tmp/hajihaz-orchestration-ux/ops/vps/apply_orchestration_ux_patch.sh /tmp/hajihaz-orchestration-ux
APPLY_STATUS=$?
rm -rf /tmp/hajihaz-orchestration-ux /tmp/hajihaz-orchestration-ux.tar.gz /tmp/hajihaz-orchestration-ux.tar.gz.b64
exit "$APPLY_STATUS"
FOOTER
