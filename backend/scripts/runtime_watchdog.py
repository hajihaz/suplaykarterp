from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.services.operations import prune_operational_data, run_watchdog_checks  # noqa: E402


def main() -> int:
    payload = {
        "metrics": run_watchdog_checks(),
        "pruned": prune_operational_data(),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
