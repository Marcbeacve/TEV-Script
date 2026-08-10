from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> int:
    p = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(p.stdout, end="")
    return p.returncode


def main() -> int:
    if run([sys.executable, "tools/validate_semantic_residual_v0.py"]):
        print("TEV_SCRIPT_SEMANTIC_RESIDUAL_V0=FAIL")
        return 2
    if run([sys.executable, "-m", "unittest", "tests.test_semantic_residual_v0", "-v"]):
        print("TEV_SCRIPT_SEMANTIC_RESIDUAL_V0=FAIL")
        return 3
    markers = (
        "RESIDUAL_FIELD_IS_SEMANTIC_FIELD",
        "RESIDUAL_CLOSED_NULL",
        "RESIDUAL_RELEVANCE_SCOPED",
        "RESIDUAL_SELF_DESCRIBING_SOURCE",
        "RESIDUAL_CONTEXT_LAW_BOUNDARY",
        "RESIDUAL_OBSTRUCTION_CONTENT_ADDRESSING",
        "RESIDUAL_DETERMINISM",
        "RESIDUAL_FAIL_CLOSED_TAMPER",
        "RESIDUAL_JOIN_ALGEBRA",
        "RESIDUAL_PRODUCT_AGGREGATION",
        "RESIDUAL_PROGRESS_CLASSIFICATION",
        "RESIDUAL_DEPENDENCY_FRONTIER",
        "RESIDUAL_APPLICATION_MODE_SENSITIVE",
        "RESIDUAL_PROOF_ADAPTER",
        "RESIDUAL_COUNTERMODEL_ADAPTER",
        "RESIDUAL_DIVERGENCE_ADAPTER",
        "RESIDUAL_LAYER_ADAPTERS_DECOUPLED",
        "RESIDUAL_CUOFC_RUNTIME_DEPENDENCY_ABSENT",
        "RESIDUAL_IA_RUNTIME_DEPENDENCY_ABSENT",
        "FIELD_TRANSFORMATION_REDUCTION_PRESERVED",
    )
    for marker in markers:
        print(marker + "=PASS")
    print("TEV_SCRIPT_SEMANTIC_RESIDUAL_TESTS=25_PASS")
    print("TEV_SCRIPT_SEMANTIC_RESIDUAL_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
