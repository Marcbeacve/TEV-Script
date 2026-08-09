from __future__ import annotations

import argparse
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable

# Keep every carrier strictly above the largest logical-cost witness (7), and
# keep the largest per-program domain within TEVProver's 4096-point limit.
DEFAULT_MODULI = (11, 13, 17, 19, 23, 29, 31)

ORIGINAL_SOURCE = '''def original(x, flag):
    state = x
    if flag == 1:
        state = state + 1
        cost = 7
    else:
        cost = 3
    return state, cost, 0
'''

OPTIMIZED_SOURCE = '''def optimized(x, flag):
    if flag == 1:
        return x + 1, 7, 0
    else:
        return x, 3, 0
'''


def _source_sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _points(modulus: int) -> list[dict[str, list[int]]]:
    rows: list[dict[str, list[int]]] = []
    for x, flag in product(range(modulus), repeat=2):
        enabled = flag == 1
        rows.append(
            {
                "inputs": [x, flag],
                "outputs": [
                    (x + 1) % modulus if enabled else x,
                    7 if enabled else 3,
                    0,
                ],
            }
        )
    return rows


def _program(
    function_name: str,
    source_text: str,
    points: list[dict[str, list[int]]],
) -> dict[str, Any]:
    return {
        "source_text": source_text,
        "source_sha256": _source_sha256(source_text),
        "function_name": function_name,
        "parameters": ["x", "flag"],
        "output_arity": 3,
        "points": points,
        "target_code_executed": False,
    }


def _certificate(modulus: int, *, tamper: bool = False) -> dict[str, Any]:
    original_points = _points(modulus)
    optimized_points = [
        {"inputs": list(row["inputs"]), "outputs": list(row["outputs"])}
        for row in original_points
    ]
    if tamper:
        optimized_points[0]["outputs"][0] = (
            optimized_points[0]["outputs"][0] + 1
        ) % modulus
    return {
        "field_modulus": modulus,
        "programs": {
            "original": _program("original", ORIGINAL_SOURCE, original_points),
            "optimized": _program("optimized", OPTIMIZED_SOURCE, optimized_points),
        },
    }


def _parse_moduli(raw: str) -> tuple[int, ...]:
    values = tuple(int(value.strip()) for value in raw.split(",") if value.strip())
    if not values or len(values) != len(set(values)):
        raise ValueError("moduli must be a non-empty unique list")
    if any(value <= 7 for value in values):
        raise ValueError("every modulus must be > 7 so logical costs 7 and 3 remain exact")
    if any(value * value > 4096 for value in values):
        raise ValueError("carrier exceeds TEVProver per-program point budget")
    return values


def _load_tevprover(root: Path):
    resolved = root.expanduser().resolve()
    if not (resolved / "kernel" / "checker.py").is_file():
        raise RuntimeError(f"TEVProver root is invalid: {resolved}")
    sys.path.insert(0, str(resolved))
    try:
        from kernel.causal_authority import (  # type: ignore[import-not-found]
            build_finite_dual_semantic_program_table_proof,
        )
        from kernel.checker import tevprover_verify  # type: ignore[import-not-found]
        from kernel.lnu_contracts import sha256_obj  # type: ignore[import-not-found]
    except Exception:
        sys.path.pop(0)
        raise
    return resolved, build_finite_dual_semantic_program_table_proof, tevprover_verify, sha256_obj


def _analysis(proof: dict[str, Any]) -> dict[str, Any]:
    value = proof.get("goal", {}).get("analysis")
    if not isinstance(value, dict):
        raise RuntimeError("TEVProver analysis missing")
    return value


def _require_agreement(result: dict[str, Any], proof: dict[str, Any], modulus: int) -> dict[str, Any]:
    if result.get("status") != "accepted_by_kernel":
        raise RuntimeError(f"TEVProver rejected modulus {modulus}: {result}")
    analysis = _analysis(proof)
    if analysis.get("agreement_bool") is not True or analysis.get("mismatch_count") != 0:
        raise RuntimeError(
            f"branch fast-path disagreement modulus={modulus} "
            f"counterexample={analysis.get('first_counterexample')}"
        )
    rows = analysis.get("program_results")
    if not isinstance(rows, list) or len(rows) != 2:
        raise RuntimeError("unexpected TEVProver program result shape")
    reference_hashes = {
        row.get("reference_table_sha256")
        for row in rows
        if isinstance(row, dict)
    }
    declared_hashes = {
        row.get("declared_table_sha256")
        for row in rows
        if isinstance(row, dict)
    }
    if len(reference_hashes) != 1 or reference_hashes != declared_hashes:
        raise RuntimeError("cross-program table identity failed")
    return analysis


def _require_negative(result: dict[str, Any], proof: dict[str, Any], modulus: int) -> dict[str, Any]:
    if result.get("status") != "accepted_by_kernel":
        raise RuntimeError(f"negative analysis rejected modulus={modulus}")
    analysis = _analysis(proof)
    if (
        analysis.get("agreement_bool") is not False
        or not isinstance(analysis.get("mismatch_count"), int)
        or int(analysis["mismatch_count"]) < 1
        or not isinstance(analysis.get("first_counterexample"), dict)
    ):
        raise RuntimeError(f"negative control not detected modulus={modulus}")
    return analysis


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="TEVProver finite oracle for TEV Script guarded Bool branch fast path"
    )
    parser.add_argument(
        "--tevprover-root",
        default=os.environ.get("TEVPROVER_ROOT", ""),
    )
    parser.add_argument(
        "--moduli",
        default=",".join(str(value) for value in DEFAULT_MODULI),
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.tevprover_root:
        raise SystemExit("--tevprover-root or TEVPROVER_ROOT is required")

    moduli = _parse_moduli(args.moduli)
    root, build_proof, verify, sha256_obj = _load_tevprover(Path(args.tevprover_root))
    receipts: list[dict[str, Any]] = []
    total_points = 0

    for modulus in moduli:
        proof = build_proof(
            _certificate(modulus),
            claim_id=f"TEV_SCRIPT_V1_BOOL_GUARD_FAST_EQ_MOD_{modulus}",
        )
        result = verify(proof)
        analysis = _require_agreement(result, proof, modulus)
        total_points += int(analysis["total_domain_points"])

        negative_proof = build_proof(
            _certificate(modulus, tamper=True),
            claim_id=f"TEV_SCRIPT_V1_BOOL_GUARD_FAST_NEG_MOD_{modulus}",
        )
        negative_result = verify(negative_proof)
        negative = _require_negative(negative_result, negative_proof, modulus)

        receipts.append(
            {
                "modulus": modulus,
                "domain_points": analysis["total_domain_points"],
                "proof_sha256": sha256_obj(proof),
                "dual_replay_sha256": analysis["dual_replay_sha256"],
                "table_sha256": analysis["program_results"][0]["reference_table_sha256"],
                "negative_first_counterexample": negative["first_counterexample"],
            }
        )

    receipt = {
        "schema": "TEV_SCRIPT_V1_TEVPROVER_BOOL_GUARD_FAST_ORACLE_V1",
        "transformation": "BOOL_GUARD_ADD_STATE_INT_CONST",
        "semantic_claim": "if_flag_then_x_plus_one_else_x_matches_closed_fast_profile_on_selected_finite_carriers",
        "logical_cost_claim": "true_path_cost_7_and_false_path_cost_3_are_preserved_on_selected_carriers",
        "moduli": list(moduli),
        "finite_program_points_verified": total_points,
        "all_agree": True,
        "negative_controls_detected": True,
        "tevprover_root": str(root),
        "runtime_implementation_equivalence_proved": False,
        "universal_integer_equivalence_proved": False,
        "write_authority": False,
        "promotion_authority": False,
        "receipts": receipts,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("TEV_SCRIPT_V1_TEVPROVER_BOOL_GUARD_FAST_ORACLE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
