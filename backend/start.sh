#!/bin/sh
set -eu

HOST="${BACKEND_HOST:-0.0.0.0}"
PORT_VALUE="${PORT:-${BACKEND_PORT:-8000}}"

exec uvicorn app.main:app --app-dir backend --host "$HOST" --port "$PORT_VALUE"

