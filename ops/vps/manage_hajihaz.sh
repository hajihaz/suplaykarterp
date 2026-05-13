#!/bin/bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/home/hajirp/hajihaz-app}"
APP_PID_FILE="${APP_PID_FILE:-$APP_ROOT/tmp/hajihaz.pid}"
APP_LOG_FILE="${APP_LOG_FILE:-$APP_ROOT/logs/app/uvicorn.log}"
OLLAMA_CMD="${OLLAMA_CMD:-$HOME/ollama/bin/ollama}"
HOST_VALUE="${HOST_VALUE:-127.0.0.1}"
PORT_VALUE="${PORT_VALUE:-8091}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:${PORT_VALUE}/health}"
APP_RUN_PATTERN="uvicorn app.main:app --app-dir backend --host ${HOST_VALUE} --port ${PORT_VALUE}"

if [ -n "${PYTHON_CMD:-}" ]; then
  PYTHON_CMD="$PYTHON_CMD"
elif [ -f "$APP_ROOT/.venv/pyvenv.cfg" ] && [ -x "$APP_ROOT/.venv/bin/python" ] && "$APP_ROOT/.venv/bin/python" -m uvicorn --version >/dev/null 2>&1; then
  PYTHON_CMD="$APP_ROOT/.venv/bin/python"
else
  PYTHON_CMD="python3"
fi

start_app() {
  mkdir -p "$(dirname "$APP_PID_FILE")" "$(dirname "$APP_LOG_FILE")"
  if [ -f "$APP_PID_FILE" ] && kill -0 "$(cat "$APP_PID_FILE")" 2>/dev/null; then
    echo "app already running"
    return 0
  fi
  rm -f "$APP_PID_FILE"
  cd "$APP_ROOT"
  if [ -x "$PYTHON_CMD" ]; then
    PYTHON_BIN="$PYTHON_CMD"
  elif command -v "$PYTHON_CMD" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$PYTHON_CMD")"
  else
    echo "python not found at $PYTHON_CMD"
    exit 1
  fi
  if ! "$PYTHON_BIN" -m uvicorn --version >/dev/null 2>&1; then
    echo "uvicorn module not available for $PYTHON_BIN"
    exit 1
  fi
  nohup "$PYTHON_BIN" -m uvicorn app.main:app --app-dir backend --host "$HOST_VALUE" --port "$PORT_VALUE" >"$APP_LOG_FILE" 2>&1 &
  echo $! >"$APP_PID_FILE"
  echo "started app pid $(cat "$APP_PID_FILE")"
}

stop_app() {
  PID="$(cat "$APP_PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    sleep 2
  fi
  pkill -f "$APP_RUN_PATTERN" 2>/dev/null || true
  rm -f "$APP_PID_FILE"
  echo "stopped app"
}

status_app() {
  if [ -f "$APP_PID_FILE" ] && kill -0 "$(cat "$APP_PID_FILE")" 2>/dev/null; then
    echo "app running pid $(cat "$APP_PID_FILE")"
  else
    echo "app stopped"
  fi
}

health_app() {
  curl -fsS "$HEALTH_URL"
}

watchdog_app() {
  cd "$APP_ROOT"
  "$PYTHON_CMD" backend/scripts/runtime_watchdog.py
}

maintenance_app() {
  cd "$APP_ROOT"
  "$PYTHON_CMD" backend/scripts/ops_maintenance.py scheduled
}

start_ollama() {
  nohup "$APP_ROOT/run_ollama.sh" >/dev/null 2>&1 &
  echo "ollama bootstrap triggered"
}

status_all() {
  status_app
  pgrep -af ollama || true
}

case "${1:-status}" in
  start) start_app ;;
  stop) stop_app ;;
  restart) stop_app; start_app ;;
  status) status_app ;;
  status-all) status_all ;;
  health) health_app ;;
  watchdog) watchdog_app ;;
  maintenance) maintenance_app ;;
  start-ollama) start_ollama ;;
  *)
    echo "usage: $0 {start|stop|restart|status|status-all|health|watchdog|maintenance|start-ollama}"
    exit 1
    ;;
esac
