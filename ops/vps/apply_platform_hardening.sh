#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
PATCH_ROOT="${1:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_ROOT/tmp/platform-hardening-backups/$STAMP"
LOCAL_HEALTH_URL="${LOCAL_HEALTH_URL:-http://127.0.0.1:8091/health}"

if [ -z "$PATCH_ROOT" ] || [ ! -d "$PATCH_ROOT" ]; then
  echo "usage: $0 /path/to/patch-root"
  exit 1
fi

changed_files=(
  README.md
  backend/requirements.txt
  backend/app/core/config.py
  backend/app/core/security.py
  backend/app/core/rate_limit.py
  backend/app/main.py
  backend/app/routes/admin.py
  backend/app/routes/auth.py
  backend/app/routes/chat.py
  backend/app/routes/user_auth.py
  backend/app/schemas.py
  backend/app/services/anthropic_client.py
  backend/app/services/ingestion.py
  backend/app/services/response_builder.py
  docs/production-architecture.md
  ops/vps/deploy_release.sh
  ops/vps/manage_hajihaz.sh
  preview/admin.html
  preview/app.js
  preview/favicon.svg
  preview/hajihaz-ui.js
  preview/index.html
  preview/new-ui.html
  preview/privacy-policy.html
)

echo "--- PREPARE BACKUP ---"
mkdir -p "$BACKUP_DIR"
for file in "${changed_files[@]}"; do
  if [ -e "$APP_ROOT/$file" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$file")"
    cp -a "$APP_ROOT/$file" "$BACKUP_DIR/$file"
  fi
done
if [ -f "$APP_ROOT/.env" ]; then
  cp -a "$APP_ROOT/.env" "$BACKUP_DIR/.env"
fi
if [ -f "$APP_ROOT/backend/data/hajihaz.db" ]; then
  mkdir -p "$BACKUP_DIR/backend/data"
  cp -a "$APP_ROOT/backend/data/hajihaz.db" "$BACKUP_DIR/backend/data/hajihaz.db"
fi

cat >"$BACKUP_DIR/rollback_platform_hardening.sh" <<ROLLBACK
#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="\${APP_ROOT:-$APP_ROOT}"
APP_USER="\${APP_USER:-$APP_USER}"
BACKUP_DIR="$BACKUP_DIR"
rsync -a "\$BACKUP_DIR"/ "\$APP_ROOT"/
if [ "\$(id -u)" -eq 0 ]; then
  chown -R "\$APP_USER:\$APP_USER" "\$APP_ROOT/backend" "\$APP_ROOT/preview" "\$APP_ROOT/ops" "\$APP_ROOT/docs" "\$APP_ROOT/tmp" "\$APP_ROOT/logs" 2>/dev/null || true
  su - "\$APP_USER" -c "APP_ROOT='\$APP_ROOT' bash '\$APP_ROOT/ops/vps/manage_hajihaz.sh' restart"
else
  APP_ROOT="\$APP_ROOT" bash "\$APP_ROOT/ops/vps/manage_hajihaz.sh" restart
fi
curl -fsS http://127.0.0.1:8091/health
echo
echo "rollback restored from \$BACKUP_DIR"
ROLLBACK
chmod +x "$BACKUP_DIR/rollback_platform_hardening.sh"

echo "--- INSTALL FILES ---"
for file in "${changed_files[@]}"; do
  if [ -e "$PATCH_ROOT/$file" ]; then
    mkdir -p "$APP_ROOT/$(dirname "$file")"
    if [ -x "$PATCH_ROOT/$file" ]; then
      install -m 0755 "$PATCH_ROOT/$file" "$APP_ROOT/$file"
    else
      install -m 0644 "$PATCH_ROOT/$file" "$APP_ROOT/$file"
    fi
  fi
done

echo "--- HARDEN ENV ---"
APP_ROOT="$APP_ROOT" python3 - <<'PY'
from pathlib import Path
import os
import secrets

app_root = Path(os.environ["APP_ROOT"])
env_path = app_root / ".env"
existing_lines = env_path.read_text().splitlines() if env_path.exists() else []
values = {}
order = []
for line in existing_lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        order.append((None, line))
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    values[key] = value.strip()
    order.append((key, None))

forced = {
    "APP_ENV": "production",
    "PUBLIC_BASE_URL": "https://hajihazai.allbeesolutions.com",
    "CORS_ORIGINS": "https://hajihazai.allbeesolutions.com",
    "AUTH_COOKIE_SECURE": "true",
    "AUTH_COOKIE_SAMESITE": "lax",
    "RATE_LIMIT_ENABLED": "true",
}
values.update(forced)
if not values.get("SECRET_KEY") or values.get("SECRET_KEY") == "dev-secret-key":
    values["SECRET_KEY"] = secrets.token_urlsafe(48)

seen = set()
output = []
for key, raw_line in order:
    if key is None:
        output.append(raw_line)
        continue
    if key in seen:
        continue
    output.append(f"{key}={values[key]}")
    seen.add(key)
for key in values:
    if key not in seen:
        output.append(f"{key}={values[key]}")
env_path.write_text("\n".join(output).rstrip() + "\n")
PY

if [ "$(id -u)" -eq 0 ]; then
  chown "$APP_USER:$APP_USER" "$APP_ROOT/.env" 2>/dev/null || true
  chown -R "$APP_USER:$APP_USER" "$APP_ROOT/backend" "$APP_ROOT/preview" "$APP_ROOT/ops" "$APP_ROOT/docs" "$APP_ROOT/tmp" "$APP_ROOT/logs" 2>/dev/null || true
fi

echo "--- DEPENDENCIES ---"
if [ -f "$APP_ROOT/backend/requirements.txt" ]; then
  if [ -x "$APP_ROOT/.venv/bin/pip" ]; then
    timeout 180 "$APP_ROOT/.venv/bin/pip" install -r "$APP_ROOT/backend/requirements.txt" || echo "dependency install warning: venv pip failed or timed out; runtime fallback remains available"
  else
    timeout 180 python3 -m pip install --break-system-packages -r "$APP_ROOT/backend/requirements.txt" || echo "dependency install warning: system pip failed or timed out; runtime fallback remains available"
  fi
fi

echo "--- COMPILE CHECK ---"
su - "$APP_USER" -c "cd '$APP_ROOT' && PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile backend/app/core/security.py backend/app/core/config.py backend/app/core/rate_limit.py backend/app/main.py backend/app/services/ingestion.py backend/app/services/anthropic_client.py backend/app/routes/auth.py backend/app/routes/user_auth.py backend/app/routes/admin.py"

echo "--- RESTART ---"
if [ "$(id -u)" -eq 0 ]; then
  su - "$APP_USER" -c "APP_ROOT='$APP_ROOT' bash '$APP_ROOT/ops/vps/manage_hajihaz.sh' restart"
else
  APP_ROOT="$APP_ROOT" bash "$APP_ROOT/ops/vps/manage_hajihaz.sh" restart
fi

sleep 8

echo "--- HEALTH ---"
curl -fsS "$LOCAL_HEALTH_URL"
echo

echo "--- LOCAL SMOKE ---"
curl -fsS http://127.0.0.1:8091/robots.txt | head -n 3
curl -fsS http://127.0.0.1:8091/favicon.ico >/dev/null
curl -fsS -X POST http://127.0.0.1:8091/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello macha"}' | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("mode"), data.get("answer","")[:80])'
admin_status="$(curl -sS -o /tmp/hajihaz-admin-stats.out -w '%{http_code}' http://127.0.0.1:8091/admin/stats)"
runtime_status="$(curl -sS -o /tmp/hajihaz-runtime-pulse.out -w '%{http_code}' http://127.0.0.1:8091/admin/runtime-pulse)"
openapi_status="$(curl -sS -o /tmp/hajihaz-openapi.out -w '%{http_code}' http://127.0.0.1:8091/openapi.json)"
echo "admin_stats_no_auth=$admin_status"
echo "runtime_pulse_no_auth=$runtime_status"
echo "openapi_status=$openapi_status"
if [ "$admin_status" != "401" ] || [ "$runtime_status" != "401" ] || [ "$openapi_status" != "404" ]; then
  echo "smoke check failed: expected admin/runtime 401 and openapi 404"
  echo "rollback command: APP_ROOT='$APP_ROOT' bash '$BACKUP_DIR/rollback_platform_hardening.sh'"
  exit 1
fi

echo "--- SSRF GUARD CHECK ---"
su - "$APP_USER" -c "cd '$APP_ROOT' && PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import asyncio
from app.services.ingestion import import_documents_from_url

async def main():
    try:
        await import_documents_from_url('http://127.0.0.1/private')
    except ValueError as exc:
        print('ssrf_blocked=' + str(exc)[:80])
    else:
        raise SystemExit('ssrf guard failed')

asyncio.run(main())
PY"

echo "--- SECURITY HEADER CHECK ---"
curl -sSI http://127.0.0.1:8091/health | grep -Ei 'content-security-policy|x-content-type-options|referrer-policy|permissions-policy|cross-origin-opener-policy|strict-transport-security' || true

echo "backup saved to $BACKUP_DIR"
echo "rollback command: APP_ROOT='$APP_ROOT' bash '$BACKUP_DIR/rollback_platform_hardening.sh'"
echo "platform hardening deployed to $APP_ROOT"
