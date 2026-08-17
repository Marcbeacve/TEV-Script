from __future__ import annotations

import argparse
import json
from pathlib import Path

from tev_script.platform_completion import (
    validate_platform_completion,
    verify_platform_completion_receipt,
)

ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="validate-platform-completion")
    parser.add_argument("--fuzz-seed", type=int, default=31031)
    parser.add_argument("--fuzz-count", type=int, default=128)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    receipt = validate_platform_completion(
        ROOT,
        fuzz_seed=arguments.fuzz_seed,
        fuzz_count=arguments.fuzz_count,
    )
    verified = verify_platform_completion_receipt(receipt)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    print("PLATFORM_COMPLETION_RECEIPT_VERIFY=" + ("PASS" if verified else "FAIL"))
    return 0 if verified and receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
