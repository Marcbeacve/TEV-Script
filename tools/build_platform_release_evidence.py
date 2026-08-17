from __future__ import annotations

import json
from pathlib import Path

from tev_script.platform_release import validate_platform_release
from tev_script.platform_release_receipt import verify_platform_release_receipt

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    receipt = validate_platform_release(ROOT)
    verified = verify_platform_release_receipt(receipt)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    print("PLATFORM_RELEASE_RECEIPT_VERIFY=" + ("PASS" if verified else "FAIL"))
    return 0 if verified and receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
