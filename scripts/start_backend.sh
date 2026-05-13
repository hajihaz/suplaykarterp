#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f ".env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    export "$line"
  done < .env
fi

BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
UVICORN_LOOP="${UVICORN_LOOP:-asyncio}"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

if [ ! -x ".venv/bin/uvicorn" ]; then
  ./.venv/bin/pip install -r backend/requirements.txt
fi

source .venv/bin/activate
echo "Starting stable backend UI on http://${BACKEND_HOST}:${BACKEND_PORT}"
uvicorn app.main:app --app-dir backend --host "$BACKEND_HOST" --port "$BACKEND_PORT" --loop "$UVICORN_LOOP"
