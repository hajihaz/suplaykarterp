from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.services.monitoring import configure_logging, record_alert, record_health_check  # noqa: E402


def probe(url: str) -> tuple[bool, str]:
    request = Request(url, headers={"user-agent": "HajiHazAI-Uptime/1.0"})
    try:
        with urlopen(request, timeout=6) as response:
            body = response.read().decode("utf-8", errors="ignore")
            payload = json.loads(body)
            ok = response.status == 200 and payload.get("status") == "ok"
            detail = f"url={url} http={response.status} app={payload.get('app', 'unknown')}"
            return ok, detail
    except HTTPError as exc:
        return False, f"url={url} http={exc.code}"
    except (URLError, TimeoutError) as exc:
        return False, f"url={url} error={exc}"
    except json.JSONDecodeError:
        return False, f"url={url} error=invalid_json"


def main() -> int:
    configure_logging()
    target_url = os.getenv("HAJIHAZ_UPTIME_URL", "http://127.0.0.1:8091/health").strip()
    ok, detail = probe(target_url)
    record_health_check("uptime_probe", ok, detail)
    if not ok:
        record_alert("error", "Uptime probe failed", detail, source="uptime_probe")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
