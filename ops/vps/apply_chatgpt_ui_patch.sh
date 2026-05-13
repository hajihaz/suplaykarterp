#!/bin/bash
set -uo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_USER="${APP_USER:-hajirp}"
PATCH_ROOT="${1:-}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_DIR="$APP_ROOT/tmp/chatgpt-ui-backups/$STAMP"
LOCAL_BASE_URL="${LOCAL_BASE_URL:-http://127.0.0.1:8091}"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

if [ -z "$PATCH_ROOT" ] || [ ! -d "$PATCH_ROOT" ]; then
  die "usage: $0 /path/to/patch-root"
fi

files=(
  preview/admin.html
  preview/app.js
  preview/index.html
  preview/hajihaz-ui.css
  preview/hajihaz-ui.js
  preview/styles.css
)

echo "--- PREPARE UI BACKUP ---"
mkdir -p "$BACKUP_DIR"
for file in "${files[@]}"; do
  source_path="$PATCH_ROOT/$file"
  target_path="$APP_ROOT/$file"
  [ -f "$source_path" ] || die "missing patch file: $source_path"
  if [ -e "$target_path" ]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$file")"
    cp -a "$target_path" "$BACKUP_DIR/$file" || die "backup failed for $file"
  fi
done

echo "--- INSTALL CHATGPT-STYLE UI ---"
for file in "${files[@]}"; do
  source_path="$PATCH_ROOT/$file"
  target_path="$APP_ROOT/$file"
  mkdir -p "$(dirname "$target_path")" || die "could not create target dir for $file"
  install -m 0644 "$source_path" "$target_path" || die "install failed for $file"
done

if [ "$(id -u)" -eq 0 ]; then
  chown -R "$APP_USER:$APP_USER" "$APP_ROOT/preview" "$APP_ROOT/tmp" 2>/dev/null || true
fi

cat >"$BACKUP_DIR/rollback_chatgpt_ui.sh" <<ROLLBACK
#!/bin/bash
set -uo pipefail
APP_ROOT="\${APP_ROOT:-$APP_ROOT}"
BACKUP_DIR="$BACKUP_DIR"
for file in preview/admin.html preview/app.js preview/index.html preview/hajihaz-ui.css preview/hajihaz-ui.js preview/styles.css; do
  if [ -f "\$BACKUP_DIR/\$file" ]; then
    mkdir -p "\$APP_ROOT/\$(dirname "\$file")"
    install -m 0644 "\$BACKUP_DIR/\$file" "\$APP_ROOT/\$file"
  fi
done
echo "rolled back UI from \$BACKUP_DIR"
ROLLBACK
chmod +x "$BACKUP_DIR/rollback_chatgpt_ui.sh"

echo "--- INSTALLED FILE CHECK ---"
ls -lh \
  "$APP_ROOT/preview/admin.html" \
  "$APP_ROOT/preview/app.js" \
  "$APP_ROOT/preview/index.html" \
  "$APP_ROOT/preview/hajihaz-ui.css" \
  "$APP_ROOT/preview/hajihaz-ui.js" \
  "$APP_ROOT/preview/styles.css" || die "installed file check failed"

echo "--- CONTENT CHECK ---"
grep -n -m1 'hajihaz-ui.css' "$APP_ROOT/preview/index.html" || die "index does not reference new stylesheet"
grep -n -m1 'hajihaz-ui.js' "$APP_ROOT/preview/index.html" || die "index does not reference new script"
grep -n -m1 'hh-app' "$APP_ROOT/preview/index.html" || die "new app shell marker missing"
grep -n -m1 'STORAGE_KEY = "hajihaz-ui-state-v2"' "$APP_ROOT/preview/hajihaz-ui.js" || die "new UI state marker missing"
grep -n -m1 'admin-body' "$APP_ROOT/preview/admin.html" || die "admin page does not use the dark admin shell"
grep -n -m1 'HajiHaz AI Admin' "$APP_ROOT/preview/admin.html" || die "admin page title marker missing"
grep -n -m1 'body.admin-body' "$APP_ROOT/preview/styles.css" || die "admin stylesheet marker missing"
grep -n -m1 'function setRuntimePulseAlert' "$APP_ROOT/preview/app.js" || die "admin runtime alert helper missing"

echo "--- APP HEALTH CHECK ---"
if curl -fsS "$LOCAL_BASE_URL/health"; then
  echo
else
  echo "health warning: app did not answer $LOCAL_BASE_URL/health"
fi

echo "--- ROOT UI CHECK ---"
if curl -fsS "$LOCAL_BASE_URL/" | grep -q 'hajihaz-ui.css'; then
  echo "root page references new stylesheet"
else
  echo "root check warning: new stylesheet reference not found"
fi
if curl -fsS "$LOCAL_BASE_URL/preview/hajihaz-ui.js" | grep -q 'hajihaz-ui-state-v2'; then
  echo "new frontend script is served"
else
  echo "script check warning: new frontend script marker not found"
fi
if curl -fsS "$LOCAL_BASE_URL/admin" | grep -q 'admin-body'; then
  echo "admin page references dark admin shell"
else
  echo "admin check warning: dark admin shell marker not found"
fi

echo "backup saved to $BACKUP_DIR"
echo "rollback command: APP_ROOT='$APP_ROOT' bash '$BACKUP_DIR/rollback_chatgpt_ui.sh'"
echo "chatgpt-style UI deployed to $APP_ROOT"
