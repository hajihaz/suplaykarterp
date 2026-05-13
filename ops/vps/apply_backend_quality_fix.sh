#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
PATCH_ROOT="${1:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_ROOT/tmp/backend-quality-backups/$STAMP"

if [ -z "$PATCH_ROOT" ] || [ ! -d "$PATCH_ROOT" ]; then
  echo "usage: $0 /path/to/patch-root"
  exit 1
fi

mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app" "$BACKUP_DIR"

for file in \
  backend/app/routes/chat.py \
  backend/app/services/response_builder.py \
  ops/vps/manage_hajihaz.sh
do
  if [ -f "$APP_ROOT/$file" ]; then
    install -m 0644 "$APP_ROOT/$file" "$BACKUP_DIR/$(basename "$file").bak"
  fi
done

install -m 0644 "$PATCH_ROOT/backend/app/routes/chat.py" "$APP_ROOT/backend/app/routes/chat.py"
install -m 0644 "$PATCH_ROOT/backend/app/services/response_builder.py" "$APP_ROOT/backend/app/services/response_builder.py"
install -m 0755 "$PATCH_ROOT/ops/vps/manage_hajihaz.sh" "$APP_ROOT/ops/vps/manage_hajihaz.sh"

if [ "$(id -u)" -eq 0 ]; then
  chown "$APP_USER:$APP_USER" \
    "$APP_ROOT/backend/app/routes/chat.py" \
    "$APP_ROOT/backend/app/services/response_builder.py" \
    "$APP_ROOT/ops/vps/manage_hajihaz.sh"
  chown -R "$APP_USER:$APP_USER" "$APP_ROOT/tmp" "$APP_ROOT/logs"
fi

if [ -f "$APP_ROOT/ops/vps/manage_hajihaz.sh" ]; then
  if [ "$(id -u)" -eq 0 ]; then
    su - "$APP_USER" -c "APP_ROOT='$APP_ROOT' bash '$APP_ROOT/ops/vps/manage_hajihaz.sh' restart"
  else
    APP_ROOT="$APP_ROOT" bash "$APP_ROOT/ops/vps/manage_hajihaz.sh" restart
  fi
else
  pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" || true
  su - "$APP_USER" -c "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \$! > '$APP_ROOT/tmp/hajihaz.pid'"
fi

sleep 6

echo '--- LOCAL HEALTH ---'
curl -fsS http://127.0.0.1:8091/health
echo
echo '--- PATCH CHECK ---'
grep -n "Give more details about" "$APP_ROOT/backend/app/services/response_builder.py"
grep -n "_infer_recent_knowledge_owned_entity" "$APP_ROOT/backend/app/services/response_builder.py"
grep -n "session_snapshot = get_chat_session" "$APP_ROOT/backend/app/routes/chat.py"
echo "backup saved to $BACKUP_DIR"
echo "backend quality fix deployed to $APP_ROOT"
