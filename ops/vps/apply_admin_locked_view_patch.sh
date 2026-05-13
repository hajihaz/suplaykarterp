#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
PATCH_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp "$PATCH_ROOT/preview/admin.html" "$APP_ROOT/preview/admin.html"
cp "$PATCH_ROOT/preview/app.js" "$APP_ROOT/preview/app.js"

chown "$APP_USER":"$APP_USER" \
  "$APP_ROOT/preview/admin.html" \
  "$APP_ROOT/preview/app.js"

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - "$APP_USER" -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 6

echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo

echo "--- LOCAL ADMIN VIEW CHECK ---"
curl -fsS http://127.0.0.1:8091/preview/admin.html | grep -nE 'data-admin-gated|admin-stats-grid'

echo "--- LOCAL APP.JS CHECK ---"
curl -fsS http://127.0.0.1:8091/preview/app.js | grep -nE 'setAdminGatedVisible|data-admin-gated'
