#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
BUNDLE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp "$BUNDLE_ROOT/backend/app/db.py" "$APP_ROOT/backend/app/db.py"
cp "$BUNDLE_ROOT/backend/app/schemas.py" "$APP_ROOT/backend/app/schemas.py"
cp "$BUNDLE_ROOT/backend/app/routes/chat.py" "$APP_ROOT/backend/app/routes/chat.py"
cp "$BUNDLE_ROOT/backend/app/services/conversations.py" "$APP_ROOT/backend/app/services/conversations.py"
cp "$BUNDLE_ROOT/preview/index.html" "$APP_ROOT/preview/index.html"
cp "$BUNDLE_ROOT/preview/app.js" "$APP_ROOT/preview/app.js"
cp "$BUNDLE_ROOT/preview/styles.css" "$APP_ROOT/preview/styles.css"

chown "$APP_USER":"$APP_USER" \
  "$APP_ROOT/backend/app/db.py" \
  "$APP_ROOT/backend/app/schemas.py" \
  "$APP_ROOT/backend/app/routes/chat.py" \
  "$APP_ROOT/backend/app/services/conversations.py" \
  "$APP_ROOT/preview/index.html" \
  "$APP_ROOT/preview/app.js" \
  "$APP_ROOT/preview/styles.css"

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - "$APP_USER" -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"
sleep 6

echo '--- LOCAL HEALTH ---'
curl -fsS http://127.0.0.1:8091/health
echo
echo '--- FILE CHECK ---'
grep -n "CREATE TABLE IF NOT EXISTS chat_sessions" "$APP_ROOT/backend/app/db.py"
grep -n "session_id" "$APP_ROOT/backend/app/routes/chat.py" | head -n 5
grep -n "CHAT_SESSION_KEY" "$APP_ROOT/preview/app.js"
grep -n "chatNewThreadButton" "$APP_ROOT/preview/index.html"
