#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
PATCH_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp "$PATCH_ROOT/backend/app/services/response_builder.py" "$APP_ROOT/backend/app/services/response_builder.py"
chown hajirp:hajirp "$APP_ROOT/backend/app/services/response_builder.py"

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - hajirp -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 6
echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo
echo "--- LOCAL WEB FORMAT CHECK ---"
grep -nE "_build_clean_web_answer|Here’s the short answer|Why that answer is likely right" "$APP_ROOT/backend/app/services/response_builder.py" || true
