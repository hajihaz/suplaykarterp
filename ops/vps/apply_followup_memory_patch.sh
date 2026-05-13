#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app"

cp /tmp/hajihaz-followup-memory/backend/app/routes/chat.py "$APP_ROOT/backend/app/routes/chat.py"
cp /tmp/hajihaz-followup-memory/backend/app/schemas.py "$APP_ROOT/backend/app/schemas.py"
cp /tmp/hajihaz-followup-memory/backend/app/services/anthropic_client.py "$APP_ROOT/backend/app/services/anthropic_client.py"
cp /tmp/hajihaz-followup-memory/backend/app/services/response_builder.py "$APP_ROOT/backend/app/services/response_builder.py"
cp /tmp/hajihaz-followup-memory/preview/app.js "$APP_ROOT/preview/app.js"
cp /tmp/hajihaz-followup-memory/preview/styles.css "$APP_ROOT/preview/styles.css"

chown hajirp:hajirp \
  "$APP_ROOT/backend/app/routes/chat.py" \
  "$APP_ROOT/backend/app/schemas.py" \
  "$APP_ROOT/backend/app/services/anthropic_client.py" \
  "$APP_ROOT/backend/app/services/response_builder.py" \
  "$APP_ROOT/preview/app.js" \
  "$APP_ROOT/preview/styles.css"

pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
su - hajirp -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 6
echo '--- LOCAL HEALTH ---'
curl -fsS http://127.0.0.1:8091/health
echo
echo '--- LOCAL CHAT.JS CHECK ---'
curl -fsS http://127.0.0.1:8091/preview/app.js | grep -nE 'chatHistory|history: requestHistory|citation-kind'
echo '--- LOCAL CHAT ROUTE CHECK ---'
grep -nE 'expand_prompt_with_history|history = \\[turn.model_dump' "$APP_ROOT/backend/app/routes/chat.py"
