from __future__ import annotations

import subprocess
import sys

MODULES = (
    "tests.test_semantic_paraconsistent_closure_v0",
    "tests.test_semantic_liveness_closure_v0",
    "tests.test_semantic_causality_closure_v0",
    "tests.test_semantic_universality_closure_v0",
    "tests.test_semantic_composition_theorem_v0",
    "tests.test_semantic_proof_boundary_v0",
)


def main() -> int:
    closure = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            *MODULES,
        ],
        text=True,
    )
    if closure.returncode:
        return closure.returncode

    base = subprocess.run(
        [
            sys.executable,
            "tests/run_semantic_calculus_campaign.py",
        ],
        text=True,
    )
    if base.returncode:
        return base.returncode

    print("TEV_SCRIPT_SEMANTIC_FRONTIER_CLOSURE_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
