from __future__ import annotations

import argparse
import json
from pathlib import Path

from tev_script.platform_completion import EXPECTED_GATES, validate_platform_completion

ROOT = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py")
    parser.add_argument("--fuzz-seed", type=int, default=31031)
    parser.add_argument("--fuzz-count", type=int, default=128)
    parser.add_argument("--receipt", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    receipt = validate_platform_completion(
        ROOT,
        fuzz_seed=arguments.fuzz_seed,
        fuzz_count=arguments.fuzz_count,
    )
    if arguments.receipt is not None:
        arguments.receipt.parent.mkdir(parents=True, exist_ok=True)
        arguments.receipt.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            + "\n",
            encoding="utf-8",
        )
    for gate in sorted(EXPECTED_GATES):
        print(f"{gate}={receipt['gates'].get(gate, {}).get('status', 'FAIL')}")
    print(f"PLATFORM_COMPLETION={receipt['platform_completion']}")
    print(f"PLATFORM_COMPLETION_RECEIPT_SHA256={receipt['receipt_sha256']}")
    if receipt.get("source_commit"):
        print(f"SOURCE_COMMIT={receipt['source_commit']}")
    if receipt.get("source_tree"):
        print(f"SOURCE_TREE={receipt['source_tree']}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
