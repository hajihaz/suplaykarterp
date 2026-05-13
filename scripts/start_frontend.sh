#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
NODE_BIN="$ROOT_DIR/.tools/node-v20.20.2-darwin-arm64/bin"

if [ ! -x "$NODE_BIN/node" ]; then
  echo "Local Node runtime is missing at $NODE_BIN"
  exit 1
fi

if [ -f "$ROOT_DIR/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    export "$line"
  done < "$ROOT_DIR/.env"
fi

cd "$ROOT_DIR/frontend"
export PATH="$NODE_BIN:$PATH"
export HOSTNAME=127.0.0.1
export PORT=3000
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"

echo "Starting the optional Next.js frontend on http://127.0.0.1:3000"
echo "Stable local product UI: http://127.0.0.1:8000"

if [ ! -d "node_modules" ]; then
  npm install
fi

if [ ! -f ".next/BUILD_ID" ] || [ "$ROOT_DIR/.env" -nt ".next/BUILD_ID" ] || find app components lib public -type f -newer ".next/BUILD_ID" | grep -q .; then
  npm run build
fi

npm run start
