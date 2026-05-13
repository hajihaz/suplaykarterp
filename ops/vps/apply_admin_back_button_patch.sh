#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cp "$PATCH_ROOT/preview/admin.html" "$APP_ROOT/preview/admin.html"
chown hajirp:hajirp "$APP_ROOT/preview/admin.html"

echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo
echo "--- LOCAL ADMIN CHECK ---"
grep -nE "Back to chat|Runtime pulse|Admin workspace" "$APP_ROOT/preview/admin.html"
