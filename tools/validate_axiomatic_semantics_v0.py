from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "TEV_SCRIPT_AXIOM_OBLIGATIONS_V0"

_REQUIRED = {
    "spec/TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0.md",
    "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json",
    "formal/lean/TEVScriptAxiomsV0.lean",
    "formal/smt/tev_script_axioms_theorems_v0.smt2",
    "formal/smt/tev_script_axioms_model_v0.smt2",
    "formal/smt/tev_script_axioms_negative_control_v0.smt2",
    "formal/tevprover/TEVScriptAxiomsV0.plan.json",
}

_CORRESPONDENCE = {
    "tev_script/semantic_kernel_v0.py": ("class SemanticFieldV0", "field_hash"),
    "tev_script/semantic_apply_v0.py": ("def apply_rule",),
    "tev_script/semantic_composition_theorem_v0.py": (
        "def prove_semantic_diamond",
        "PROOF_REQUIRED",
        "LAW_VIOLATION",
    ),
    "tev_script/semantic_residual_v0.py": ("Residual",),
    "tev_script/semantic_paraconsistent_v0.py": (
        "class FourValueV0",
        "\"BOTH\"",
        "PROOF_REQUIRED",
    ),
    "tev_script/semantic_realization_selection_v0.py": (
        "def evaluate_realization_selection",
        "PROOF_REQUIRED",
        "REJECT",
    ),
    "tev_script/semantic_realization_resolution_v0.py": (
        "SELECTED",
        "INDETERMINATE",
        "NO_ADMISSIBLE_REALIZATION",
    ),
    "tev_script/semantic_proof_boundary_v0.py": (
        "class ProofBoundaryWitnessV0",
        "verifier_hash",
        "scope_hash",
    ),
}


def validate(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    failures: list[str] = []

    for relative in sorted(_REQUIRED):
        if not (root / relative).is_file():
            failures.append(f"missing:{relative}")

    manifest_path = root / "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append("manifest:invalid_json")
            manifest = {}
        if manifest.get("schema") != SCHEMA:
            failures.append("manifest:schema")
        if manifest.get("status") != "AXIOMATIC_CANDIDATE":
            failures.append("manifest:status")
        if manifest.get("primitive_families") != ["Field", "Transformation"]:
            failures.append("manifest:primitive_families")
        meta = manifest.get("meta_logic")
        if not isinstance(meta, dict) or meta.get(
            "classical_explosion_applies_to_object_evidence"
        ) is not False:
            failures.append("manifest:meta_logic_boundary")

        formal = {
            row.get("id"): row
            for row in manifest.get("formal_sources", [])
            if isinstance(row, dict)
        }
        expected = {
            "LEAN_ABSTRACT_THEORY": ("lean", None, False),
            "Z3_THEOREMS": ("z3", "unsat", False),
            "Z3_NONCOLLAPSE_MODEL": ("z3", "sat", False),
            "Z3_SELECTION_NEGATIVE_CONTROL": ("z3", "unsat", True),
        }
        for key, (engine, outcome, negative) in expected.items():
            row = formal.get(key)
            if not isinstance(row, dict):
                failures.append(f"manifest:formal_missing:{key}")
                continue
            if row.get("engine") != engine:
                failures.append(f"manifest:engine:{key}")
            if outcome is not None and row.get("expected_outcome") != outcome:
                failures.append(f"manifest:outcome:{key}")
            if bool(row.get("negative_control", False)) is not negative:
                failures.append(f"manifest:negative_control:{key}")

        promotion = manifest.get("promotion")
        if not isinstance(promotion, dict) or promotion.get(
            "bind_to_system_canonical_index_before_formal_pass"
        ) is not False:
            failures.append("manifest:premature_authority_binding")

    lean = root / "formal/lean/TEVScriptAxiomsV0.lean"
    if lean.is_file():
        text = lean.read_text(encoding="utf-8")
        scrubbed = re.sub(r"/-.*?-/", "", text, flags=re.DOTALL)
        forbidden = re.compile(r"(?m)^\s*(axiom|admit|sorry)\b")
        if forbidden.search(scrubbed):
            failures.append("lean:admission_or_global_axiom")
        for token in (
            "structure Theory",
            "governed_compose_associative",
            "noAdmissible_no_selection",
            "tied_distinct_best_no_selection",
            "fourValue_negate_involutive",
            "metadata_noncollapse_same_semantics",
        ):
            if token not in text:
                failures.append(f"lean:missing:{token}")

    smt_expectations = {
        "formal/smt/tev_script_axioms_theorems_v0.smt2": 4,
        "formal/smt/tev_script_axioms_model_v0.smt2": 1,
        "formal/smt/tev_script_axioms_negative_control_v0.smt2": 1,
    }
    for relative, checks in smt_expectations.items():
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if text.count("(check-sat)") != checks:
            failures.append(f"smt:check_count:{relative}")

    for relative, tokens in _CORRESPONDENCE.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"correspondence:missing:{relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                failures.append(f"correspondence:{relative}:{token}")

    tevprover_plan = root / "formal/tevprover/TEVScriptAxiomsV0.plan.json"
    if tevprover_plan.is_file():
        try:
            plan = json.loads(tevprover_plan.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append("tevprover:invalid_json")
            plan = {}
        if plan.get("schema") != "TEV_SCRIPT_TEVPROVER_AXIOM_PLAN_V0":
            failures.append("tevprover:schema")
        if plan.get("status") != "PREPARED_NOT_EXECUTED":
            failures.append("tevprover:premature_execution_claim")
        if plan.get("semantic_authority") is not False:
            failures.append("tevprover:authority_inversion")

    historical = root / "CANONICAL_INDEX.json"
    if historical.is_file():
        text = historical.read_text(encoding="utf-8")
        if "TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0" in text:
            failures.append("historical_v1:axiom_candidate_leaked")

    return tuple(sorted(set(failures)))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures = validate(root)
    if failures:
        for failure in failures:
            print(f"TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0=FAIL:{failure}")
        return 1
    print("TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
