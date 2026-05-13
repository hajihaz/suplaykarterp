#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
PATCH_ROOT="${1:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_ROOT/tmp/orchestration-ux-backups/$STAMP"
LOCAL_BASE_URL="${LOCAL_BASE_URL:-http://127.0.0.1:8091}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

if [ -z "$PATCH_ROOT" ] || [ ! -d "$PATCH_ROOT" ]; then
  die "usage: $0 /path/to/patch-root"
fi

files=(
  backend/app/db.py
  backend/app/main.py
  backend/app/schemas.py
  backend/app/core/security.py
  backend/app/routes/chat.py
  backend/app/routes/user_auth.py
  backend/app/services/anthropic_client.py
  backend/app/services/orchestration.py
  backend/app/services/response_builder.py
  backend/app/services/web_lookup.py
  preview/index.html
  preview/hajihaz-ui.css
  preview/hajihaz-ui.js
)

run_as_app_user() {
  if [ "$(id -u)" -eq 0 ]; then
    su - "$APP_USER" -c "$1"
  else
    bash -lc "$1"
  fi
}

echo "--- PREPARE ORCHESTRATION + UX BACKUP ---"
mkdir -p "$APP_ROOT/tmp" "$APP_ROOT/logs/app" "$BACKUP_DIR"
for file in "${files[@]}"; do
  source_path="$PATCH_ROOT/$file"
  target_path="$APP_ROOT/$file"
  [ -f "$source_path" ] || die "missing patch file: $source_path"
  if [ -e "$target_path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$file")"
    cp -a "$target_path" "$BACKUP_DIR/$file" || die "backup failed for $file"
  fi
done

cat >"$BACKUP_DIR/rollback_orchestration_ux.sh" <<ROLLBACK
#!/bin/bash
set -euo pipefail
APP_ROOT="\${APP_ROOT:-$APP_ROOT}"
BACKUP_DIR="$BACKUP_DIR"
for file in ${files[*]}; do
  if [ -f "\$BACKUP_DIR/\$file" ]; then
    mkdir -p "\$APP_ROOT/\$(dirname "\$file")"
    install -m 0644 "\$BACKUP_DIR/\$file" "\$APP_ROOT/\$file"
  fi
done
echo "rolled back orchestration + UX patch from \$BACKUP_DIR"
ROLLBACK
chmod +x "$BACKUP_DIR/rollback_orchestration_ux.sh"

echo "--- INSTALL ORCHESTRATION + UX PATCH ---"
for file in "${files[@]}"; do
  source_path="$PATCH_ROOT/$file"
  target_path="$APP_ROOT/$file"
  mkdir -p "$(dirname "$target_path")"
  install -m 0644 "$source_path" "$target_path" || die "install failed for $file"
done

if [ "$(id -u)" -eq 0 ]; then
  chown "$APP_USER:$APP_USER" \
    "$APP_ROOT/backend/app/db.py" \
    "$APP_ROOT/backend/app/main.py" \
    "$APP_ROOT/backend/app/schemas.py" \
    "$APP_ROOT/backend/app/core/security.py" \
    "$APP_ROOT/backend/app/routes/chat.py" \
    "$APP_ROOT/backend/app/routes/user_auth.py" \
    "$APP_ROOT/backend/app/services/anthropic_client.py" \
    "$APP_ROOT/backend/app/services/orchestration.py" \
    "$APP_ROOT/backend/app/services/response_builder.py" \
    "$APP_ROOT/backend/app/services/web_lookup.py" \
    "$APP_ROOT/preview/index.html" \
    "$APP_ROOT/preview/hajihaz-ui.css" \
    "$APP_ROOT/preview/hajihaz-ui.js" 2>/dev/null || true
  chown -R "$APP_USER:$APP_USER" "$APP_ROOT/tmp" "$APP_ROOT/logs" 2>/dev/null || true
fi

echo "--- PYTHON COMPILE CHECK ---"
run_as_app_user "cd '$APP_ROOT' && PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile backend/app/db.py backend/app/main.py backend/app/schemas.py backend/app/core/security.py backend/app/routes/chat.py backend/app/routes/user_auth.py backend/app/services/anthropic_client.py backend/app/services/orchestration.py backend/app/services/response_builder.py backend/app/services/web_lookup.py"

echo "--- RESTART APP ---"
pkill -f "uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091" 2>/dev/null || true
rm -f "$APP_ROOT/tmp/hajihaz.pid"
run_as_app_user "cd '$APP_ROOT' && nohup python3 -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8091 > '$APP_ROOT/logs/app/uvicorn.log' 2>&1 & echo \\\$! > '$APP_ROOT/tmp/hajihaz.pid'"

sleep 10

echo "--- HEALTH ---"
if ! curl -fsS "$LOCAL_BASE_URL/health"; then
  echo
  echo "--- UVICORN LOG ---"
  tail -n 120 "$APP_ROOT/logs/app/uvicorn.log" || true
  die "health check failed"
fi
echo

echo "--- CONTENT CHECK ---"
grep -n 'hajihaz-ui.css?v=20260512a' "$APP_ROOT/preview/index.html" || die "index does not reference patched stylesheet"
grep -n 'hajihaz-ui.js?v=20260512a' "$APP_ROOT/preview/index.html" || die "index does not reference patched script"
grep -n 'memory_enabled' "$APP_ROOT/preview/hajihaz-ui.js" || die "frontend memory toggle payload missing"
grep -n 'profileAvatarUpload' "$APP_ROOT/preview/hajihaz-ui.js" || die "frontend profile avatar upload missing"
grep -n 'USER_COLUMN_MIGRATIONS' "$APP_ROOT/backend/app/db.py" || die "user profile migrations missing"
grep -n 'build_route_plan' "$APP_ROOT/backend/app/routes/chat.py" || die "chat route is missing orchestration"
grep -n 'class ChatRoutePlan' "$APP_ROOT/backend/app/services/orchestration.py" || die "orchestration service missing"

echo "--- PM ROUTING SMOKE ---"
CHAT_JSON="$(curl -fsS "$LOCAL_BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"Who is the Prime Minister of India?","memory_enabled":true,"ai_mode":"auto"}')"
CHAT_JSON="$CHAT_JSON" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CHAT_JSON"])
answer = payload.get("answer", "")
blob = json.dumps(payload, ensure_ascii=False)
print("intent=" + str(payload.get("intent")))
print("source_strategy=" + str(payload.get("source_strategy")))
print("memory_confidence=" + str(payload.get("memory_confidence")))
print("answer=" + answer[:220])
if payload.get("intent") != "current_affairs":
    sys.exit("intent smoke failed")
if payload.get("source_strategy") != "web":
    sys.exit("source strategy smoke failed")
if float(payload.get("memory_confidence") or 0) != 0.0:
    sys.exit("memory confidence smoke failed")
if "RAJA MANICKAM" in blob.upper():
    sys.exit("memory leakage smoke failed")
if "narendra modi" not in answer.lower():
    sys.exit("current office holder smoke failed")
if "head of government" in answer.lower():
    sys.exit("generic office summary smoke failed")
if not answer.strip():
    sys.exit("empty answer smoke failed")
PY

echo "--- ENTITY ROUTING SMOKE ---"
CHAT_JSON="$(curl -fsS "$LOCAL_BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"who is narendra modi","memory_enabled":true,"ai_mode":"auto"}')"
CHAT_JSON="$CHAT_JSON" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CHAT_JSON"])
answer = payload.get("answer", "")
blob = json.dumps(payload, ensure_ascii=False).lower()
print("intent=" + str(payload.get("intent")))
print("source_strategy=" + str(payload.get("source_strategy")))
print("answer=" + answer[:220])
if payload.get("source_strategy") != "web":
    sys.exit("entity should route to web")
if float(payload.get("memory_confidence") or 0) != 0.0:
    sys.exit("entity memory confidence should be zero")
if "narendra" not in answer.lower() or "modi" not in answer.lower():
    sys.exit("entity answer missing Narendra Modi")
if any(term in blob for term in ("movie", "film", "box office", "trailer")):
    sys.exit("entity smoke leaked entertainment result")
PY

echo "--- PRESIDENT ROUTING SMOKE ---"
CHAT_JSON="$(curl -fsS "$LOCAL_BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"who is president of america","memory_enabled":true,"ai_mode":"auto"}')"
CHAT_JSON="$CHAT_JSON" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CHAT_JSON"])
answer = payload.get("answer", "")
blob = json.dumps(payload, ensure_ascii=False).lower()
print("intent=" + str(payload.get("intent")))
print("source_strategy=" + str(payload.get("source_strategy")))
print("answer=" + answer[:220])
if payload.get("source_strategy") != "web":
    sys.exit("president should route to web")
if "president" not in answer.lower() or "trump" not in answer.lower():
    sys.exit("president answer missing Donald Trump")
if any(term in blob for term in ("phil baker", "movie", "film")):
    sys.exit("president smoke leaked irrelevant entity")
PY

echo "--- TAMIL NADU NEWS SMOKE ---"
CHAT_JSON="$(curl -fsS "$LOCAL_BASE_URL/chat" \
  -H 'Content-Type: application/json' \
  -d '{"message":"top news in tamilnadu","memory_enabled":true,"ai_mode":"auto"}')"
CHAT_JSON="$CHAT_JSON" python3 - <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["CHAT_JSON"])
answer = payload.get("answer", "")
blob = json.dumps(payload, ensure_ascii=False).lower()
print("intent=" + str(payload.get("intent")))
print("source_strategy=" + str(payload.get("source_strategy")))
print("answer=" + answer[:220])
if payload.get("source_strategy") != "web":
    sys.exit("news should route to web")
if not answer.strip():
    sys.exit("news answer empty")
if any(term in blob for term in ("jyothika", "actress", "movie", "film")):
    sys.exit("news smoke leaked entertainment result")
PY

echo "--- UI SERVE CHECK ---"
curl -fsS "$LOCAL_BASE_URL/" | grep -q 'settingsPanel' || die "root UI settings panel missing"
curl -fsS "$LOCAL_BASE_URL/preview/hajihaz-ui.js?v=20260512a" | grep -q 'memory_enabled' || die "patched UI script not served"

echo "backup saved to $BACKUP_DIR"
echo "rollback command: APP_ROOT='$APP_ROOT' bash '$BACKUP_DIR/rollback_orchestration_ux.sh'"
echo "orchestration + UX patch deployed to $APP_ROOT"
