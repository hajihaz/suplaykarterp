#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
PATCH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp "$PATCH_ROOT/backend/app/services/anthropic_client.py" "$APP_ROOT/backend/app/services/anthropic_client.py"
cp "$PATCH_ROOT/backend/app/services/response_builder.py" "$APP_ROOT/backend/app/services/response_builder.py"
cp "$PATCH_ROOT/preview/app.js" "$APP_ROOT/preview/app.js"

chown hajirp:hajirp \
  "$APP_ROOT/backend/app/services/anthropic_client.py" \
  "$APP_ROOT/backend/app/services/response_builder.py" \
  "$APP_ROOT/preview/app.js"

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - hajirp -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 6
echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo
echo "--- LOCAL CONVERSATION CHECK ---"
curl -fsS http://127.0.0.1:8091/preview/app.js | grep -nE 'conversation: "conversational"|humanizeMode'
