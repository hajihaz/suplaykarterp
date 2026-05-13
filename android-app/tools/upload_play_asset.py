#!/usr/bin/env python3
import argparse
import base64
import mimetypes
import pathlib
import subprocess
import sys


def run_zsh(cmd: str) -> str:
    result = subprocess.run(
        ["/bin/zsh", "-lc", cmd],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise RuntimeError(message)
    return result.stdout.strip()


def escape_js_for_applescript(js: str) -> str:
    return js.replace("\\", "\\\\").replace('"', '\\"')


def run_js(js: str, expect_result: bool = False) -> str:
    escaped = escape_js_for_applescript(js)
    verb = "return do JavaScript" if expect_result else "do JavaScript"
    cmd = (
        "osascript "
        "-e 'tell application \"Safari\"' "
        f"-e '{verb} \"{escaped}\" in current tab of front window' "
        "-e 'end tell'"
    )
    return run_zsh(cmd)


def upload_asset(path: pathlib.Path, mime_type: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode()
    run_js("window.__playUploadB64 = String();")

    chunk_size = 1200
    for start in range(0, len(data), chunk_size):
        chunk = data[start : start + chunk_size]
        run_js(f'window.__playUploadB64 += "{chunk}";')

    final_js = (
        '(() => { '
        'const input = document.querySelector("input[type=file]"); '
        'if (input === null) return "NO_INPUT"; '
        'const bytes = Uint8Array.from(atob(window.__playUploadB64), c => c.charCodeAt(0)); '
        f'const file = new File([bytes], "{path.name}", {{ type: "{mime_type}" }}); '
        'const dt = new DataTransfer(); '
        'dt.items.add(file); '
        'input.files = dt.files; '
        'input.dispatchEvent(new Event("change", { bubbles: true })); '
        'return "SET:" + input.files.length + ":" + input.files[0].name + ":" + input.files[0].size; '
        '})()'
    )
    return run_js(final_js, expect_result=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--mime")
    args = parser.parse_args()

    path = pathlib.Path(args.path).expanduser().resolve()
    if not path.exists():
        print(f"Missing file: {path}", file=sys.stderr)
        return 1

    mime_type = args.mime or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    print(upload_asset(path, mime_type))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
