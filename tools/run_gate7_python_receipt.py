from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tev_script.canonical import canonical_json
from tev_script.conformance import run_conformance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    program = json.loads(Path(args.program).read_text(encoding="utf-8"))
    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))

    expected: bytes | None = None
    for index in range(args.repeat):
        receipt = run_conformance(program, scenario)
        data = (canonical_json(receipt) + "\n").encode("utf-8")
        if expected is None:
            expected = data
        elif data != expected:
            raise RuntimeError(f"PYTHON_REPLAY_DIVERGENCE run={index}")

    assert expected is not None
    Path(args.out).write_bytes(expected)
    print(f"GATE7_PYTHON_REPLAY_{args.repeat}=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
