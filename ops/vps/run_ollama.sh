#!/bin/bash
set -euo pipefail

HOME_DIR="${HOME:-/home/hhaiapp}"
OLLAMA_HOME="${OLLAMA_HOME:-$HOME_DIR/ollama}"
OLLAMA_BIN="${OLLAMA_BIN:-$OLLAMA_HOME/bin/ollama}"
PID_FILE="${OLLAMA_PID_FILE:-$HOME_DIR/tmp/ollama.pid}"
LOG_FILE="${OLLAMA_LOG_FILE:-$HOME_DIR/logs/ollama.log}"
HOST_VALUE="${OLLAMA_HOST:-127.0.0.1:11434}"

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    exit 0
  fi
fi

export OLLAMA_HOST="$HOST_VALUE"
nohup "$OLLAMA_BIN" serve >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"
