#!/bin/zsh
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <asset-path> [mime-type]" >&2
  exit 1
fi

asset_path="$1"
mime_type="${2:-image/png}"
asset_name="$(basename "$asset_path")"

if [[ ! -f "$asset_path" ]]; then
  echo "missing file: $asset_path" >&2
  exit 1
fi

b64="$(base64 < "$asset_path" | tr -d '\n')"
chunk_size=500

run_js() {
  local js="$1"
  osascript \
    -e 'tell application "Safari"' \
    -e "do JavaScript \"$js\" in current tab of front window" \
    -e 'end tell' >/dev/null
}

run_js "window.__playUploadB64 = String();"

local_start=1
local_end=${#b64}
while (( local_start <= local_end )); do
  chunk="${b64[local_start,local_start+chunk_size-1]}"
  run_js "window.__playUploadB64 += \\\"$chunk\\\";"
  (( local_start += chunk_size ))
done

final_js="(() => { const input = document.querySelector(\\\"input[type=file]\\\"); if (input === null) return \\\"NO_INPUT\\\"; const bytes = Uint8Array.from(atob(window.__playUploadB64), c => c.charCodeAt(0)); const file = new File([bytes], \\\"$asset_name\\\", { type: \\\"$mime_type\\\" }); const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files; input.dispatchEvent(new Event(\\\"change\\\", { bubbles: true })); return \\\"SET:\\\" + input.files.length + \\\":\\\" + input.files[0].name + \\\":\\\" + input.files[0].size; })()"

osascript \
  -e 'tell application "Safari"' \
  -e "return do JavaScript \"$final_js\" in current tab of front window" \
  -e 'end tell'
