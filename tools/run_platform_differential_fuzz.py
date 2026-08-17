from __future__ import annotations

import argparse
import json
from pathlib import Path

from tev_script.platform_fuzz import run_differential_fuzz

ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run-platform-differential-fuzz")
    parser.add_argument("--seed", type=int, default=31031)
    parser.add_argument("--count", type=int, default=128)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    receipt = run_differential_fuzz(
        ROOT,
        seed=arguments.seed,
        count=arguments.count,
    )
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
