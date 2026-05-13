#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
BUNDLE_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp "$BUNDLE_ROOT/backend/requirements.txt" "$APP_ROOT/backend/requirements.txt"
cp "$BUNDLE_ROOT/backend/app/db.py" "$APP_ROOT/backend/app/db.py"
cp "$BUNDLE_ROOT/backend/app/schemas.py" "$APP_ROOT/backend/app/schemas.py"
cp "$BUNDLE_ROOT/backend/app/main.py" "$APP_ROOT/backend/app/main.py"
cp "$BUNDLE_ROOT/backend/app/core/config.py" "$APP_ROOT/backend/app/core/config.py"
cp "$BUNDLE_ROOT/backend/app/core/security.py" "$APP_ROOT/backend/app/core/security.py"
cp "$BUNDLE_ROOT/backend/app/routes/chat.py" "$APP_ROOT/backend/app/routes/chat.py"
cp "$BUNDLE_ROOT/backend/app/routes/user_auth.py" "$APP_ROOT/backend/app/routes/user_auth.py"
cp "$BUNDLE_ROOT/backend/app/services/conversations.py" "$APP_ROOT/backend/app/services/conversations.py"
cp "$BUNDLE_ROOT/backend/app/services/google_identity.py" "$APP_ROOT/backend/app/services/google_identity.py"
cp "$BUNDLE_ROOT/preview/index.html" "$APP_ROOT/preview/index.html"
cp "$BUNDLE_ROOT/preview/admin.html" "$APP_ROOT/preview/admin.html"
cp "$BUNDLE_ROOT/preview/app.js" "$APP_ROOT/preview/app.js"
cp "$BUNDLE_ROOT/preview/styles.css" "$APP_ROOT/preview/styles.css"

chown "$APP_USER":"$APP_USER" \
  "$APP_ROOT/backend/requirements.txt" \
  "$APP_ROOT/backend/app/db.py" \
  "$APP_ROOT/backend/app/schemas.py" \
  "$APP_ROOT/backend/app/main.py" \
  "$APP_ROOT/backend/app/core/config.py" \
  "$APP_ROOT/backend/app/core/security.py" \
  "$APP_ROOT/backend/app/routes/chat.py" \
  "$APP_ROOT/backend/app/routes/user_auth.py" \
  "$APP_ROOT/backend/app/services/conversations.py" \
  "$APP_ROOT/backend/app/services/google_identity.py" \
  "$APP_ROOT/preview/index.html" \
  "$APP_ROOT/preview/admin.html" \
  "$APP_ROOT/preview/app.js" \
  "$APP_ROOT/preview/styles.css"

if [ -x "$APP_ROOT/.venv/bin/pip" ]; then
  "$APP_ROOT/.venv/bin/pip" install -r "$APP_ROOT/backend/requirements.txt"
else
  python3 -m pip install --break-system-packages -r "$APP_ROOT/backend/requirements.txt"
fi

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - "$APP_USER" -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 6
echo "--- LOCAL HEALTH ---"
curl -fsS http://127.0.0.1:8091/health
echo
echo "--- GOOGLE CONFIG ---"
if [ -f "$APP_ROOT/.env" ] && grep -Eq '^GOOGLE_CLIENT_ID=.+$' "$APP_ROOT/.env"; then
  echo "Google client id configured"
else
  echo "Google client id not configured"
fi
echo "--- LOCAL USER AUTH CHECK ---"
curl -fsS http://127.0.0.1:8091/user-auth/config
echo
echo "--- LOCAL PREVIEW CHECK ---"
grep -nE 'Protected|adminEmailInput' "$APP_ROOT/preview/admin.html"
grep -nE 'chatGoogleButton|chatUserCard|CHAT_USER_TOKEN_KEY|/user-auth/google|/chat/sessions' "$APP_ROOT/preview/index.html" "$APP_ROOT/preview/app.js"
