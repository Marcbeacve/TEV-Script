from __future__ import annotations

import json
from pathlib import Path

from tev_script.platform_conformance import run_platform_conformance

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    receipt = run_platform_conformance(ROOT)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
