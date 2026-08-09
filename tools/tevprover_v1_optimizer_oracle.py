from __future__ import annotations

import argparse
import hashlib
import json
import os
from itertools import product
from pathlib import Path
import sys
from typing import Any, Iterable

try:
    from tools.v1_optimizer_oracle_contract import (
        OPTIMIZER_ORACLE_PASS_MARKER,
        OPTIMIZER_ORACLE_SCHEMA_V1,
        optimizer_oracle_receipt_line,
    )
except ModuleNotFoundError:
    from v1_optimizer_oracle_contract import (
        OPTIMIZER_ORACLE_PASS_MARKER,
        OPTIMIZER_ORACLE_SCHEMA_V1,
        optimizer_oracle_receipt_line,
    )

# Every carrier is strictly larger than the largest logical-cost witness (5),
# so cost components are represented exactly instead of only modulo p.
DEFAULT_MODULI = (7, 11, 13, 17, 19, 23, 29, 31)

FAMILIES: tuple[dict[str, Any], ...] = (
    {
        "name": "ADD_STATE_INT_CONST",
        "parameters": ("x", "c"),
        "logical_cost": 5,
        "operation": "add",
        "original_id": "add_state_original",
        "optimized_id": "add_state_optimized",
        "original_source": '''def add_state_original(x, c):
    state = x
    constant = c
    state = state + constant
    return state, 5, 0
''',
        "optimized_source": '''def add_state_optimized(x, c):
    return x + c, 5, 0
''',
    },
    {
        "name": "ADD_INT",
        "parameters": ("x", "y"),
        "logical_cost": 1,
        "operation": "add",
        "original_id": "add_int_original",
        "optimized_id": "add_int_optimized",
        "original_source": '''def add_int_original(x, y):
    left = x
    right = y
    result = left + right
    return result, 1, 0
''',
        "optimized_source": '''def add_int_optimized(x, y):
    return x + y, 1, 0
''',
    },
    {
        "name": "SUB_INT",
        "parameters": ("x", "y"),
        "logical_cost": 1,
        "operation": "sub",
        "original_id": "sub_int_original",
        "optimized_id": "sub_int_optimized",
        "original_source": '''def sub_int_original(x, y):
    left = x
    right = y
    result = left - right
    return result, 1, 0
''',
        "optimized_source": '''def sub_int_optimized(x, y):
    return x - y, 1, 0
''',
    },
    {
        "name": "MUL_INT",
        "parameters": ("x", "y"),
        "logical_cost": 1,
        "operation": "mul",
        "original_id": "mul_int_original",
        "optimized_id": "mul_int_optimized",
        "original_source": '''def mul_int_original(x, y):
    left = x
    right = y
    result = left * right
    return result, 1, 0
''',
        "optimized_source": '''def mul_int_optimized(x, y):
    return x * y, 1, 0
''',
    },
)


def _source_sha256(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _apply(operation: str, left: int, right: int, modulus: int) -> int:
    if operation == "add":
        return (left + right) % modulus
    if operation == "sub":
        return (left - right) % modulus
    if operation == "mul":
        return (left * right) % modulus
    raise AssertionError(operation)


def _points(family: dict[str, Any], modulus: int) -> list[dict[str, list[int]]]:
    cost = int(family["logical_cost"])
    operation = str(family["operation"])
    return [
        {
            "inputs": [left, right],
            "outputs": [_apply(operation, left, right, modulus), cost, 0],
        }
        for left, right in product(range(modulus), repeat=2)
    ]


def _program(
    *,
    function_name: str,
    source_text: str,
    parameters: tuple[str, ...],
    points: list[dict[str, list[int]]],
) -> dict[str, Any]:
    return {
        "source_text": source_text,
        "source_sha256": _source_sha256(source_text),
        "function_name": function_name,
        "parameters": list(parameters),
        "output_arity": 3,
        "points": points,
        # TEVProver's debugger is deliberately a non-executing independent
        # semantic consumer. Actual runtime implementation equivalence is a
        # separate TEV Script regression obligation.
        "target_code_executed": False,
    }


def _certificate(modulus: int, *, tamper_optimized: bool = False) -> dict[str, Any]:
    programs: dict[str, dict[str, Any]] = {}
    for family in FAMILIES:
        points = _points(family, modulus)
        optimized_points = [
            {"inputs": list(row["inputs"]), "outputs": list(row["outputs"])}
            for row in points
        ]
        if tamper_optimized:
            optimized_points[0]["outputs"][0] = (
                optimized_points[0]["outputs"][0] + 1
            ) % modulus
        parameters = tuple(str(value) for value in family["parameters"])
        original_id = str(family["original_id"])
        optimized_id = str(family["optimized_id"])
        programs[original_id] = _program(
            function_name=original_id,
            source_text=str(family["original_source"]),
            parameters=parameters,
            points=points,
        )
        programs[optimized_id] = _program(
            function_name=optimized_id,
            source_text=str(family["optimized_source"]),
            parameters=parameters,
            points=optimized_points,
        )
    return {"field_modulus": modulus, "programs": programs}


def _parse_moduli(raw: str) -> tuple[int, ...]:
    values = tuple(int(value.strip()) for value in raw.split(",") if value.strip())
    if not values:
        raise ValueError("at least one modulus is required")
    if len(values) != len(set(values)):
        raise ValueError("moduli must be unique")
    if any(value <= 5 for value in values):
        raise ValueError("every modulus must be > 5 so logical cost 5 is represented exactly")
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


def _rows_by_id(analysis: dict[str, Any], modulus: int) -> dict[str, dict[str, Any]]:
    rows = analysis.get("program_results")
    if not isinstance(rows, list) or len(rows) != 2 * len(FAMILIES):
        raise RuntimeError(f"unexpected TEVProver program results for modulus {modulus}")
    by_id = {
        str(row.get("program_id")): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("program_id"), str)
    }
    if len(by_id) != len(rows):
        raise RuntimeError(f"duplicate/malformed TEVProver program results for modulus {modulus}")
    return by_id


def _require_agreement(result: dict[str, Any], proof: dict[str, Any], modulus: int) -> tuple[dict[str, Any], dict[str, str]]:
    if result.get("status") != "accepted_by_kernel":
        raise RuntimeError(f"TEVProver rejected modulus {modulus}: {result}")
    analysis = proof.get("goal", {}).get("analysis")
    if not isinstance(analysis, dict):
        raise RuntimeError(f"TEVProver analysis missing for modulus {modulus}")
    if analysis.get("agreement_bool") is not True or analysis.get("mismatch_count") != 0:
        raise RuntimeError(
            f"optimizer equivalence failed for modulus {modulus}: "
            f"{analysis.get('first_counterexample')}"
        )
    by_id = _rows_by_id(analysis, modulus)
    table_hashes: dict[str, str] = {}
    for family in FAMILIES:
        original = by_id[str(family["original_id"])]
        optimized = by_id[str(family["optimized_id"])]
        for row in (original, optimized):
            if row.get("declared_table_sha256") != row.get("reference_table_sha256"):
                raise RuntimeError(
                    f"declared/reference mismatch for {row.get('program_id')} modulus {modulus}"
                )
        original_hash = str(original["reference_table_sha256"])
        optimized_hash = str(optimized["reference_table_sha256"])
        if original_hash != optimized_hash:
            raise RuntimeError(
                f"cross-program table mismatch for {family['name']} modulus {modulus}"
            )
        table_hashes[str(family["name"])] = original_hash
    return analysis, table_hashes


def _require_negative_detection(result: dict[str, Any], proof: dict[str, Any], modulus: int) -> dict[str, Any]:
    # A debugger disagreement is still a valid analysis object. The optimizer
    # gate requires the negative campaign to report all injected mismatches and
    # expose a concrete first counterexample.
    if result.get("status") != "accepted_by_kernel":
        raise RuntimeError(f"TEVProver negative-control analysis rejected for modulus {modulus}")
    analysis = proof.get("goal", {}).get("analysis")
    if not isinstance(analysis, dict):
        raise RuntimeError("negative-control analysis missing")
    if (
        analysis.get("agreement_bool") is not False
        or not isinstance(analysis.get("mismatch_count"), int)
        or int(analysis["mismatch_count"]) < len(FAMILIES)
        or not isinstance(analysis.get("first_counterexample"), dict)
    ):
        raise RuntimeError(f"TEVProver failed to detect optimizer tampering for modulus {modulus}")
    return analysis


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent TEVProver finite oracle for TEV Script V1 optimizer transformations"
    )
    parser.add_argument(
        "--tevprover-root",
        default=os.environ.get("TEVPROVER_ROOT", ""),
        help="Path to an optional TEVProver checkout (or set TEVPROVER_ROOT)",
    )
    parser.add_argument(
        "--moduli",
        default=",".join(str(value) for value in DEFAULT_MODULI),
        help="Comma-separated prime finite carriers, each > 5",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not args.tevprover_root:
        raise SystemExit("--tevprover-root or TEVPROVER_ROOT is required")

    moduli = _parse_moduli(args.moduli)
    tevprover_root, build_proof, verify, sha256_obj = _load_tevprover(Path(args.tevprover_root))

    receipts: list[dict[str, Any]] = []
    total_domain_points = 0
    for modulus in moduli:
        proof = build_proof(
            _certificate(modulus),
            claim_id=f"TEV_SCRIPT_V1_OPTIMIZER_EQUIVALENCE_MOD_{modulus}",
        )
        result = verify(proof)
        analysis, table_hashes = _require_agreement(result, proof, modulus)
        total_domain_points += int(analysis["total_domain_points"])

        negative_proof = build_proof(
            _certificate(modulus, tamper_optimized=True),
            claim_id=f"TEV_SCRIPT_V1_OPTIMIZER_NEGATIVE_MOD_{modulus}",
        )
        negative_result = verify(negative_proof)
        negative_analysis = _require_negative_detection(
            negative_result,
            negative_proof,
            modulus,
        )

        receipts.append(
            {
                "modulus": modulus,
                "proof_sha256": sha256_obj(proof),
                "dual_replay_sha256": analysis["dual_replay_sha256"],
                "domain_points": analysis["total_domain_points"],
                "agreement": True,
                "table_sha256_by_family": table_hashes,
                "negative_control_detected": True,
                "negative_mismatch_count": negative_analysis["mismatch_count"],
                "negative_first_counterexample": negative_analysis["first_counterexample"],
            }
        )

    receipt = {
        "schema": "TEV_SCRIPT_V1_TEVPROVER_OPTIMIZER_ORACLE_V2",
        "transformation_families": [str(family["name"]) for family in FAMILIES],
        "semantic_claim": "each_original_and_specialized_integer_path_agrees_on_each_selected_finite_carrier",
        "logical_cost_claim": "finite_programs_preserve_declared_logical_cost_and_zero_emission_witness",
        "moduli": list(moduli),
        "finite_program_points_verified": total_domain_points,
        "all_agree": True,
        "negative_controls_detected": True,
        "tevprover_root": str(tevprover_root),
        "family_source_sha256": {
            str(family["name"]): {
                "original": _source_sha256(str(family["original_source"])),
                "optimized": _source_sha256(str(family["optimized_source"])),
            }
            for family in FAMILIES
        },
        "receipts": receipts,
        "runtime_implementation_equivalence_proved": False,
        "universal_integer_equivalence_proved": False,
        "write_authority": False,
        "promotion_authority": False,
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print("TEV_SCRIPT_V1_TEVPROVER_OPTIMIZER_ORACLE=PASS")
    generic_receipt = {
        "schema": OPTIMIZER_ORACLE_SCHEMA_V1,
        "provider_id": "external.tevprover.finite-oracle.v1",
        "provider_kind": "external",
        "evidence_scope": "finite_selected_carriers",
        "semantic_claim": receipt["semantic_claim"],
        "transformation_families": receipt["transformation_families"],
        "moduli": receipt["moduli"],
        "finite_program_points_verified": receipt["finite_program_points_verified"],
        "all_agree": receipt["all_agree"],
        "negative_controls_detected": receipt["negative_controls_detected"],
        "provider_receipt_sha256": hashlib.sha256(
            json.dumps(
                receipt,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "runtime_implementation_equivalence_proved": False,
        "universal_integer_equivalence_proved": False,
        "write_authority": False,
        "promotion_authority": False,
    }
    print(optimizer_oracle_receipt_line(generic_receipt))
    print(OPTIMIZER_ORACLE_PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
