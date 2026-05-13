#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WORK_DIR="$(mktemp -d)"
ARCHIVE_PATH="$WORK_DIR/hajihaz-platform-hardening.tar.gz"
BASE64_PATH="$WORK_DIR/hajihaz-platform-hardening.tar.gz.b64"

cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

cd "$REPO_ROOT"

tar -czf "$ARCHIVE_PATH" \
  README.md \
  backend/requirements.txt \
  backend/app/core/config.py \
  backend/app/core/security.py \
  backend/app/core/rate_limit.py \
  backend/app/main.py \
  backend/app/routes/admin.py \
  backend/app/routes/auth.py \
  backend/app/routes/chat.py \
  backend/app/routes/user_auth.py \
  backend/app/schemas.py \
  backend/app/services/anthropic_client.py \
  backend/app/services/ingestion.py \
  backend/app/services/response_builder.py \
  docs/production-architecture.md \
  ops/vps/deploy_release.sh \
  ops/vps/manage_hajihaz.sh \
  ops/vps/apply_platform_hardening.sh \
  preview/admin.html \
  preview/app.js \
  preview/favicon.svg \
  preview/hajihaz-ui.js \
  preview/index.html \
  preview/new-ui.html \
  preview/privacy-policy.html

base64 <"$ARCHIVE_PATH" >"$BASE64_PATH"

cat <<'HEADER'
APP_ROOT=${APP_ROOT:-/home/hajirp/hajihaz-app}
set -euo pipefail
rm -rf /tmp/hajihaz-platform-hardening
mkdir -p /tmp/hajihaz-platform-hardening
cat >/tmp/hajihaz-platform-hardening.tar.gz.b64 <<'B64'
HEADER

cat "$BASE64_PATH"

cat <<'FOOTER'
B64
base64 -d /tmp/hajihaz-platform-hardening.tar.gz.b64 >/tmp/hajihaz-platform-hardening.tar.gz
tar -xzf /tmp/hajihaz-platform-hardening.tar.gz -C /tmp/hajihaz-platform-hardening
chmod +x /tmp/hajihaz-platform-hardening/ops/vps/apply_platform_hardening.sh
APP_ROOT="$APP_ROOT" /tmp/hajihaz-platform-hardening/ops/vps/apply_platform_hardening.sh /tmp/hajihaz-platform-hardening
rm -rf /tmp/hajihaz-platform-hardening /tmp/hajihaz-platform-hardening.tar.gz /tmp/hajihaz-platform-hardening.tar.gz.b64
FOOTER
