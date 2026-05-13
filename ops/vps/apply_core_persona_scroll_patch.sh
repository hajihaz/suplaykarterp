#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
PATCH_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp "$PATCH_ROOT/backend/app/db.py" "$APP_ROOT/backend/app/db.py"
cp "$PATCH_ROOT/backend/app/schemas.py" "$APP_ROOT/backend/app/schemas.py"
cp "$PATCH_ROOT/backend/app/routes/admin.py" "$APP_ROOT/backend/app/routes/admin.py"
cp "$PATCH_ROOT/backend/app/services/rag.py" "$APP_ROOT/backend/app/services/rag.py"
cp "$PATCH_ROOT/preview/admin.html" "$APP_ROOT/preview/admin.html"
cp "$PATCH_ROOT/preview/app.js" "$APP_ROOT/preview/app.js"
cp "$PATCH_ROOT/preview/styles.css" "$APP_ROOT/preview/styles.css"

chown "$APP_USER":"$APP_USER" \
  "$APP_ROOT/backend/app/db.py" \
  "$APP_ROOT/backend/app/schemas.py" \
  "$APP_ROOT/backend/app/routes/admin.py" \
  "$APP_ROOT/backend/app/services/rag.py" \
  "$APP_ROOT/preview/admin.html" \
  "$APP_ROOT/preview/app.js" \
  "$APP_ROOT/preview/styles.css"

echo "--- FILE CHECK ---"
rg -n "scrollConversationIntoView|scrollToConversation|data-toggle-core-persona|core_persona: corePersonaInput.checked|Core persona source|adminCorePersonaInput|persona-badge|toggle-card" \
  "$APP_ROOT/preview/app.js" \
  "$APP_ROOT/preview/admin.html" \
  "$APP_ROOT/preview/styles.css"

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - "$APP_USER" -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 6

echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo

echo "--- LOCAL APP.JS CHECK ---"
curl -fsS http://127.0.0.1:8091/preview/app.js | rg -n "scrollConversationIntoView|scrollToConversation|data-toggle-core-persona|core_persona: corePersonaInput.checked"

echo "--- LOCAL ADMIN.HTML CHECK ---"
curl -fsS http://127.0.0.1:8091/preview/admin.html | rg -n "Core persona source|adminCorePersonaInput"
