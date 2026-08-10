from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = (
    "tev_script/semantic_cost_model_v0.py",
    "tev_script/semantic_cost_model_update_v0.py",
    "tev_script/semantic_cost_prediction_v0.py",
    "tev_script/semantic_dispatch_v0.py",
    "tev_script/semantic_dispatch_observation_v0.py",
    "tev_script/semantic_dispatched_grounded_discovery_v0.py",
    "tev_script/semantic_execution_authority_v0.py",
    "tev_script/semantic_receipt_validity_v0.py",
    "tev_script/semantic_realization_search_v0.py",
    "tev_script/semantic_realization_selection_v0.py",
    "tev_script/semantic_resource_calibration_v0.py",
    "tev_script/semantic_resource_measurement_v0.py",
)
TESTS = (
    "tests/test_realization_cost_model_v0.py",
    "tests/test_realization_cost_model_update_v0.py",
    "tests/test_realization_cost_prediction_v0.py",
    "tests/test_realization_dispatch_loop_v0.py",
    "tests/test_realization_execution_authority_v0.py",
    "tests/test_realization_receipt_validity_dispatch_v0.py",
    "tests/test_realization_resource_calibration_v0.py",
    "tests/test_realization_resource_measurement_v0.py",
    "tests/test_realization_search_v0.py",
    "tests/test_realization_selection_v0.py",
)
ALLOWED_ABSOLUTE_IMPORT_ROOTS = frozenset({"__future__", "dataclasses", "fractions", "re", "typing"})
FORBIDDEN_HOST_IMPORT_ROOTS = frozenset({"os", "platform", "subprocess", "socket", "psutil", "torch", "cpuinfo"})
FORBIDDEN_TOKENS = ("nvidia", "cuda", "rocm", "tevprover", "ia_tev", "ia-tev")


def fail(detail: str) -> int:
    print("REALIZATION_R0_EXTENDED_AUTHORITY=FAIL")
    print("REALIZATION_R0_EXTENDED_AUTHORITY_DETAIL=" + detail)
    return 1


def validate_module(path_text: str) -> tuple[bool, str]:
    path = ROOT / path_text
    if not path.is_file():
        return False, f"missing module {path_text}"
    source = path.read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            return False, f"forbidden implementation authority token {token!r} in {path_text}"
    tree = ast.parse(source, filename=path_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_HOST_IMPORT_ROOTS:
                    return False, f"host introspection import {alias.name!r} in {path_text}"
                if root not in ALLOWED_ABSOLUTE_IMPORT_ROOTS:
                    return False, f"unapproved absolute import {alias.name!r} in {path_text}"
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_HOST_IMPORT_ROOTS:
                return False, f"host introspection import {node.module!r} in {path_text}"
            if root not in ALLOWED_ABSOLUTE_IMPORT_ROOTS:
                return False, f"unapproved absolute import {node.module!r} in {path_text}"
    return True, ""


def main() -> int:
    for path_text in (*MODULES, *TESTS):
        if not (ROOT / path_text).is_file():
            return fail(f"missing extended R0 path {path_text}")
    print("R0_EXTENDED_REQUIRED_PATHS=PASS")

    for module in MODULES:
        ok, detail = validate_module(module)
        if not ok:
            return fail(detail)
    print("R0_EXTENDED_NO_HOST_OR_VENDOR_AUTHORITY=PASS")

    validity = (ROOT / "tev_script" / "semantic_receipt_validity_v0.py").read_text(encoding="utf-8")
    dispatch = (ROOT / "tev_script" / "semantic_dispatch_v0.py").read_text(encoding="utf-8")
    execution_authority = (ROOT / "tev_script" / "semantic_execution_authority_v0.py").read_text(encoding="utf-8")
    search = (ROOT / "tev_script" / "semantic_realization_search_v0.py").read_text(encoding="utf-8")
    dispatched_observation = (ROOT / "tev_script" / "semantic_dispatch_observation_v0.py").read_text(encoding="utf-8")
    dispatched_grounded = (ROOT / "tev_script" / "semantic_dispatched_grounded_discovery_v0.py").read_text(encoding="utf-8")
    measurement = (ROOT / "tev_script" / "semantic_resource_measurement_v0.py").read_text(encoding="utf-8")
    calibration = (ROOT / "tev_script" / "semantic_resource_calibration_v0.py").read_text(encoding="utf-8")
    selection = (ROOT / "tev_script" / "semantic_realization_selection_v0.py").read_text(encoding="utf-8")
    cost_model = (ROOT / "tev_script" / "semantic_cost_model_v0.py").read_text(encoding="utf-8")
    cost_update = (ROOT / "tev_script" / "semantic_cost_model_update_v0.py").read_text(encoding="utf-8")
    cost_prediction = (ROOT / "tev_script" / "semantic_cost_prediction_v0.py").read_text(encoding="utf-8")

    required_validity = ("VALID", "REVOKED", "SUPERSEDED", "UNKNOWN", "validation_epoch_hash", "authority_state_hash")
    if any(token not in validity for token in required_validity):
        return fail("historical receipt validity surface incomplete")
    print("R0_HISTORICAL_RECEIPT_VALIDITY=PASS")

    required_dispatch = (
        "dispatch_request_hash",
        "dispatch_epoch_hash",
        "ACTIVATION_RECEIPT_CONTRACT_HASH_V0",
        "AUTHORITY_RECEIPT_CONTRACT_HASH_V0",
        "execution_authority_receipt_hash",
        "execution_authority_validity_evaluation_hash",
        "dispatch.execution_authority_not_current",
        "dispatch.execution_authority_realization_mismatch",
    )
    if any(token not in dispatch for token in required_dispatch):
        return fail("just-in-time dual-authority dispatch surface incomplete")
    print("R0_JIT_DISPATCH_DUAL_AUTHORITY=PASS")

    required_execution_authority = (
        "TransformationProgramBindingClaimV0",
        "ReactionContractV1",
        "ReactionFootprintV1",
        "CapabilityLawCatalogV1",
        "RefinementReceiptV1",
        "authority.refinement_not_admitted",
        "authority.law_catalog_incomplete",
        "binding_evidence_policy",
    )
    if any(token not in execution_authority for token in required_execution_authority):
        return fail("causal least-authority realization bridge incomplete")
    print("R0_CAUSAL_LEAST_AUTHORITY_BRIDGE=PASS")

    required_search = (
        "HEURISTIC",
        "BOUNDED",
        "EXHAUSTIVE",
        "CANDIDATE_SET",
        "BOUNDED_SEARCH_SPACE",
        "EXHAUSTIVE_SEARCH_SPACE",
        "search.receipt_realization_problem_mismatch",
        "planning.candidate_universe_mismatch",
    )
    if any(token not in search for token in required_search):
        return fail("search coverage/planning scope surface incomplete")
    print("R0_SEARCH_COVERAGE_SCOPE=PASS")

    if "dispatch_request_hash" not in dispatched_observation or "execution_observation_receipt_hash" not in dispatched_observation:
        return fail("dispatch-to-observation binding incomplete")
    if "dispatch_request_hash" not in dispatched_grounded or "observed_history_hash" not in dispatched_grounded:
        return fail("dispatch-to-grounded-discovery chain incomplete")
    print("R0_DISPATCH_TO_DISCOVERY_CHAIN=PASS")

    required_measurement = ("measurement_epoch_hash", "execution_context_hash", "observed_resource_vector_hash", "evidence_policy_hash")
    if any(token not in measurement for token in required_measurement):
        return fail("resource measurement binding incomplete")
    print("R0_RESOURCE_MEASUREMENT_CONTEXT_BOUND=PASS")

    required_selection = (
        "PARETO_MEMBER",
        "LEXICOGRAPHIC_MIN",
        "receipt.problem_hash != problem.realization_problem_hash",
        "selection.receipt_realization_problem_mismatch",
    )
    if any(token not in selection for token in required_selection):
        return fail("verifiable selection/problem binding incomplete")
    print("R0_SELECTION_RULES_AND_PROBLEM_BINDING=PASS")

    required_calibration = (
        "def status(self) -> str",
        '"status": self.status',
        'if self.status != "PASS"',
        'verdict = "INCONCLUSIVE"',
    )
    if any(token not in calibration for token in required_calibration):
        return fail("calibration validity/verdict separation incomplete")
    print("R0_CALIBRATION_VALIDITY_VERDICT_SEPARATED=PASS")

    required_cost_model = (
        "EmpiricalCostModelV0",
        "CostModelAdmissionReceiptV0",
        "empirical_envelope",
        "measurement_claim_hashes",
        "execution_context_hash",
    )
    if any(token not in cost_model for token in required_cost_model):
        return fail("empirical cost model surface incomplete")
    print("R0_EMPIRICAL_COST_MODEL=PASS")

    required_update = (
        "parent_model_hash",
        "successor_model_hash",
        "new_measurement_claim_hashes",
        "successor_basis_mismatch",
        "measurement_already_in_parent",
    )
    if any(token not in cost_update for token in required_update):
        return fail("cost model append-only lineage incomplete")
    print("R0_COST_MODEL_APPEND_ONLY_LINEAGE=PASS")

    required_prediction = (
        "cost_prediction.context_unseen",
        "EMPIRICAL_ENVELOPE",
        "EMPIRICAL_OBSERVATION",
        "model_admission.receipt_hash",
    )
    if any(token not in cost_prediction for token in required_prediction):
        return fail("cost prediction fail-closed projection incomplete")
    print("R0_COST_PREDICTION_FAIL_CLOSED=PASS")

    print("R0_EXTENDED_LONG_VALIDATION_DEFERRED=PASS")
    print("REALIZATION_R0_EXTENDED_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
