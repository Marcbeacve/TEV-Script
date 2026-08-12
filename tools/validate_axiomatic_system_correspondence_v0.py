from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SURFACE_TOKENS: dict[str, tuple[str, ...]] = {
    "C0_SEMANTIC_IDENTITY_SEPARATION": (
        "tev_script/system_api_v0.py",
        "do_not_use_backend_identity_as_semantic_identity",
    ),
    "C0_COST_IS_SEPARATE_EVIDENCE": (
        "tev_script/semantic_cost_model_v0.py",
        "realization_hash",
        "resource_catalog_hash",
        "measurement_claim_hashes",
    ),
    "C1_EXPLICIT_EFFECT_BOUNDARY": (
        "AGENTS.md",
        "No implicit physical effect is permitted",
        "explicit capability",
    ),
    "C1_EFFECT_LAWS_FAIL_CLOSED": (
        "tev_script/semantic_effects_v0.py",
        "missing_domain_law",
        "noncommuting:",
    ),
    "C2_EXACT_RATIONAL_DOMAIN": (
        "tev_script/values.py",
        "from fractions import Fraction",
        "\"$rat\"",
        "rational must be normalized",
    ),
    "C2_EXPLICIT_HOST_CONVERSION": (
        "AGENTS.md",
        "rational arithmetic remains exact",
        "host capability",
    ),
    "C3_FAIL_CLOSED": (
        "AGENTS.md",
        "Missing capabilities",
        "exhausted budgets",
        "malformed IR",
        "hash mismatches",
        "fail closed",
    ),
    "C4_PROOF_SCOPE_BINDING": (
        "tev_script/semantic_proof_boundary_v0.py",
        "proof_hash",
        "verifier_hash",
        "scope_hash",
    ),
    "C5_AUTHORITY_SEPARATION": (
        "tools/validate_system_integration_v0.py",
        "FORBIDDEN_AUTHORITY_TOKENS",
        "SYSTEM_API_NO_CONSUMER_OR_EXTERNAL_AUTHORITY",
    ),
    "C6_EXACT_ARTIFACT_BINDING": (
        "tev_script/system_integration_receipt_v0.py",
        "expected_system_api_contract_hash",
        "expected_distribution_artifact_sha256",
        "expected_receipt_hash",
    ),
    "C7_BOUNDED_REASONING_HONESTY": (
        "tev_script/semantic_paraconsistent_v0.py",
        "max_atoms",
        "\"PROOF_REQUIRED\"",
        "\"valuation_space_bound\"",
    ),
    "C8_HASH_BINDING_NOT_SOLE_TRUTH": (
        "tev_script/system_integration_receipt_v0.py",
        "verification",
        "canonical_hash(body)",
    ),
}

EXPECTED_REPOTALK_TASKS = {
    "LEAN_ABSTRACT_THEORY": ("lean", None, False),
    "Z3_THEOREMS": ("z3", "unsat", False),
    "Z3_NONCOLLAPSE_MODEL": ("z3", "sat", False),
    "Z3_SELECTION_NEGATIVE_CONTROL": ("z3", "unsat", True),
}


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require(condition: bool, failures: list[str], detail: str) -> None:
    if not condition:
        failures.append(detail)


def _check_surfaces(failures: list[str]) -> None:
    for invariant, row in SURFACE_TOKENS.items():
        relative, *tokens = row
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"{invariant}:missing:{relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            _require(
                token in text,
                failures,
                f"{invariant}:missing_token:{token}",
            )


def _check_repotalk_campaign(failures: list[str]) -> None:
    path = ROOT / "formal/repotalk/TEVScriptAxiomsV0.campaign.json"
    if not path.is_file():
        failures.append("repotalk:campaign_missing")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    _require(
        data.get("schema") == "TEV_SCRIPT_REPOTALK_FORMAL_CAMPAIGN_V0",
        failures,
        "repotalk:schema",
    )
    _require(
        data.get("status") == "PREPARED_NOT_EXECUTED",
        failures,
        "repotalk:status",
    )
    _require(
        data.get("tool") == "repotalk_formal_verify",
        failures,
        "repotalk:tool",
    )
    _require(
        data.get("expected_head_sha_runtime_required") is True,
        failures,
        "repotalk:exact_head",
    )
    tasks = {
        row.get("id"): row
        for row in data.get("tasks", [])
        if isinstance(row, dict)
    }
    _require(
        set(tasks) == set(EXPECTED_REPOTALK_TASKS),
        failures,
        "repotalk:task_set",
    )
    for task_id, (engine, outcome, negative) in EXPECTED_REPOTALK_TASKS.items():
        row = tasks.get(task_id, {})
        _require(
            row.get("engine") == engine,
            failures,
            f"repotalk:{task_id}:engine",
        )
        _require(
            row.get("expected_outcome") == outcome,
            failures,
            f"repotalk:{task_id}:outcome",
        )
        _require(
            row.get("negative_control") is negative,
            failures,
            f"repotalk:{task_id}:negative",
        )
        source = row.get("source_path")
        _require(
            isinstance(source, str) and (ROOT / source).is_file(),
            failures,
            f"repotalk:{task_id}:source",
        )


def _check_operation(
    operation: object,
    elements: list[str],
    failures: list[str],
    index: int,
) -> None:
    if not isinstance(operation, dict):
        failures.append(f"tevprover:operation:{index}:shape")
        return
    arity = operation.get("arity")
    _require(
        type(arity) is int and 0 <= arity <= 3,
        failures,
        f"tevprover:operation:{index}:arity",
    )
    _require(
        operation.get("total") is True,
        failures,
        f"tevprover:operation:{index}:total",
    )
    _require(
        operation.get("closed") is True,
        failures,
        f"tevprover:operation:{index}:closed",
    )
    if type(arity) is not int:
        return
    table = operation.get("table")
    if not isinstance(table, list):
        failures.append(f"tevprover:operation:{index}:table")
        return
    _require(
        len(table) == len(elements) ** arity,
        failures,
        f"tevprover:operation:{index}:total_table",
    )
    seen: set[tuple[str, ...]] = set()
    carrier = set(elements)
    for entry in table:
        if not isinstance(entry, dict) or set(entry) != {"args", "result"}:
            failures.append(f"tevprover:operation:{index}:entry")
            continue
        args = entry.get("args")
        result = entry.get("result")
        if not isinstance(args, list):
            failures.append(f"tevprover:operation:{index}:args")
            continue
        _require(
            len(args) == arity and all(item in carrier for item in args),
            failures,
            f"tevprover:operation:{index}:arg_carrier",
        )
        _require(
            result in carrier,
            failures,
            f"tevprover:operation:{index}:result_carrier",
        )
        key = tuple(str(item) for item in args)
        _require(
            key not in seen,
            failures,
            f"tevprover:operation:{index}:duplicate_args",
        )
        seen.add(key)


def _check_tevprover(failures: list[str]) -> None:
    proof_path = ROOT / "formal/tevprover/TEVScriptFourValueV0.proof.json"
    plan_path = ROOT / "formal/tevprover/TEVScriptAxiomsV0.plan.json"
    if not proof_path.is_file() or not plan_path.is_file():
        failures.append("tevprover:materialization_missing")
        return
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    _require(
        proof.get("schema") == "TEVPROOF_OBJECT_V1",
        failures,
        "tevprover:proof_schema",
    )
    _require(
        proof.get("frame") == "TEV_NATIVE_EXACT_FINITE",
        failures,
        "tevprover:frame",
    )
    _require(
        proof.get("continuum_shadow") is False,
        failures,
        "tevprover:continuum_shadow",
    )
    goal = proof.get("goal")
    _require(
        isinstance(goal, dict) and goal.get("kind") == "finite_relation_graph",
        failures,
        "tevprover:goal_kind",
    )
    certificate = proof.get("module_rule_certificate")
    expected_cert = {
        "schema": "TEVPROVER_L4_CHECKER_CERTIFICATE_V2",
        "module_id": "finite_relation_graph",
        "rule_id": "finite_relation_graph_validate",
        "rule_kind": "registered_exact_checker_rule",
        "checker_version": "RELATION_GRAPH_L4_V2",
        "application": {
            "rule_id": "finite_relation_graph_validate",
            "goal_kind": "finite_relation_graph",
        },
        "truth_authority_bool": False,
        "write_authority_bool": False,
    }
    _require(
        certificate == expected_cert,
        failures,
        "tevprover:certificate",
    )

    witness = proof.get("witness")
    if not isinstance(witness, dict):
        failures.append("tevprover:witness")
        return
    elements = witness.get("elements")
    if not isinstance(elements, list) or not all(
        isinstance(item, str) for item in elements
    ):
        failures.append("tevprover:elements")
        return
    _require(
        witness.get("kind") == "finite_carrier"
        and witness.get("finite") is True
        and witness.get("size") == len(elements)
        and len(set(elements)) == len(elements),
        failures,
        "tevprover:finite_carrier",
    )
    _require(
        witness.get("elements_sha256") == canonical_sha256(elements),
        failures,
        "tevprover:elements_hash",
    )
    operations = witness.get("operations")
    if not isinstance(operations, list):
        failures.append("tevprover:operations")
        operations = []
    for index, operation in enumerate(operations):
        _check_operation(operation, elements, failures, index)
    _require(
        witness.get("operations_sha256") == canonical_sha256(operations),
        failures,
        "tevprover:operations_hash",
    )
    witness_clone = dict(witness)
    declared_witness_hash = witness_clone.pop("witness_sha256", None)
    _require(
        declared_witness_hash == canonical_sha256(witness_clone),
        failures,
        "tevprover:witness_hash",
    )

    graph = goal.get("graph") if isinstance(goal, dict) else None
    if not isinstance(graph, dict):
        failures.append("tevprover:graph")
        return
    _require(
        graph.get("carrier") == witness.get("carrier")
        and graph.get("nodes") == elements,
        failures,
        "tevprover:graph_carrier",
    )
    graph_clone = dict(graph)
    declared_graph_hash = graph_clone.pop("graph_sha256", None)
    _require(
        declared_graph_hash == canonical_sha256(graph_clone),
        failures,
        "tevprover:graph_hash",
    )
    _require(
        any(
            isinstance(step, dict)
            and step.get("rule") == "finite_relation_graph_validate"
            and step.get("output") == goal
            for step in proof.get("steps", [])
        ),
        failures,
        "tevprover:bound_step",
    )
    proof_hash = canonical_sha256(proof)
    obligations = {
        row.get("id"): row
        for row in plan.get("obligations", [])
        if isinstance(row, dict)
    }
    tvp0 = obligations.get("TVP0_FOUR_VALUE_FINITE_CARRIER", {})
    _require(
        tvp0.get("status") == "MATERIALIZED_NOT_EXECUTED",
        failures,
        "tevprover:tvp0_status",
    )
    _require(
        tvp0.get("proof_object_sha256") == proof_hash,
        failures,
        "tevprover:proof_hash_binding",
    )
    _require(
        plan.get("semantic_authority") is False,
        failures,
        "tevprover:authority",
    )


def validate() -> tuple[str, ...]:
    failures: list[str] = []
    _check_surfaces(failures)
    _check_repotalk_campaign(failures)
    _check_tevprover(failures)

    historical = ROOT / "CANONICAL_INDEX.json"
    system = ROOT / "spec/TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json"
    for path in (historical, system):
        if path.is_file():
            _require(
                "TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0"
                not in path.read_text(encoding="utf-8"),
                failures,
                f"authority:premature_binding:{path.name}",
            )
    return tuple(sorted(set(failures)))


def main() -> int:
    failures = validate()
    if failures:
        for failure in failures:
            print(
                "TEV_SCRIPT_AXIOMATIC_SYSTEM_CORRESPONDENCE_V0=FAIL:"
                + failure
            )
        return 1
    print("TEV_SCRIPT_AXIOMATIC_SYSTEM_CORRESPONDENCE_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
