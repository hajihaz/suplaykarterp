#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
ARCHIVE_PATH="$WORK_DIR/hajihaz-backend-quality-fix.tar.gz"
BASE64_PATH="$WORK_DIR/hajihaz-backend-quality-fix.tar.gz.b64"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

tar -czf "$ARCHIVE_PATH" \
  backend/app/routes/chat.py \
  backend/app/services/response_builder.py \
  ops/vps/manage_hajihaz.sh \
  ops/vps/apply_backend_quality_fix.sh

base64 <"$ARCHIVE_PATH" >"$BASE64_PATH"

cat <<'HEADER'
APP_ROOT=${APP_ROOT:-/home/hajirp/hajihaz-app}
set -euo pipefail
rm -rf /tmp/hajihaz-backend-quality-fix
mkdir -p /tmp/hajihaz-backend-quality-fix
cat >/tmp/hajihaz-backend-quality-fix.tar.gz.b64 <<'B64'
HEADER

cat "$BASE64_PATH"

cat <<'FOOTER'
B64
base64 -d /tmp/hajihaz-backend-quality-fix.tar.gz.b64 >/tmp/hajihaz-backend-quality-fix.tar.gz
tar -xzf /tmp/hajihaz-backend-quality-fix.tar.gz -C /tmp/hajihaz-backend-quality-fix
chmod +x /tmp/hajihaz-backend-quality-fix/ops/vps/apply_backend_quality_fix.sh
APP_ROOT="$APP_ROOT" /tmp/hajihaz-backend-quality-fix/ops/vps/apply_backend_quality_fix.sh /tmp/hajihaz-backend-quality-fix
rm -rf /tmp/hajihaz-backend-quality-fix /tmp/hajihaz-backend-quality-fix.tar.gz /tmp/hajihaz-backend-quality-fix.tar.gz.b64
FOOTER
