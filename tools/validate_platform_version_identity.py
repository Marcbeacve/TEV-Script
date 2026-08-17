from __future__ import annotations

import json
from pathlib import Path

from tev_script.platform_versioning import validate_current_version_identity

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    receipt = validate_current_version_identity(ROOT)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
