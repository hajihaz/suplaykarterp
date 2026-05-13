#!/bin/bash
set -euo pipefail

echo "== Host audit =="
hostname
date -u

echo
echo "== Listening ports =="
ss -tulpn || true

echo
echo "== Firewall =="
if command -v ufw >/dev/null 2>&1; then
  ufw status verbose || true
else
  echo "ufw not installed"
fi

echo
echo "== Disk usage =="
df -h

echo
echo "== App process =="
ps -ef | grep -E "uvicorn|ollama" | grep -v grep || true

echo
echo "== User cron =="
crontab -l || true

echo
echo "== User systemd timers =="
systemctl --user list-timers --all || true

echo
echo "== Env placeholders =="
if [ -f "$HOME/htdocs/hajihaz.82.29.160.39.sslip.io/.env" ]; then
  grep -E "SECRET_KEY=|ADMIN_PASSWORD=|ALERT_WEBHOOK_URL=|ALERT_EMAIL_HOST=|PUBLIC_BASE_URL=|OCR_ENABLED=" "$HOME/htdocs/hajihaz.82.29.160.39.sslip.io/.env" | sed 's/=.*/=<redacted>/'
else
  echo ".env not found in app root"
fi
