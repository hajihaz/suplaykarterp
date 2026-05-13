#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cp "$PATCH_ROOT/preview/index.html" "$APP_ROOT/preview/index.html"
cp "$PATCH_ROOT/preview/admin.html" "$APP_ROOT/preview/admin.html"
cp "$PATCH_ROOT/preview/app.js" "$APP_ROOT/preview/app.js"
cp "$PATCH_ROOT/preview/styles.css" "$APP_ROOT/preview/styles.css"

chown hajirp:hajirp "$APP_ROOT/preview/index.html" "$APP_ROOT/preview/admin.html" "$APP_ROOT/preview/app.js" "$APP_ROOT/preview/styles.css"

echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo
echo "--- LOCAL HTML CHECK ---"
grep -n "20260411-inlinecite1" "$APP_ROOT/preview/index.html" "$APP_ROOT/preview/admin.html"
echo "--- LOCAL APP CHECK ---"
grep -nE "secondary-button--inline|Open source" "$APP_ROOT/preview/app.js"
echo "--- LOCAL STYLE CHECK ---"
grep -nE "secondary-button--inline" "$APP_ROOT/preview/styles.css"
