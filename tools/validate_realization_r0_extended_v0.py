from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MODULES = (
    "tev_script/semantic_commit_outcome_v0.py",
    "tev_script/semantic_cost_model_v0.py",
    "tev_script/semantic_cost_model_update_v0.py",
    "tev_script/semantic_cost_prediction_v0.py",
    "tev_script/semantic_delivery_guarantee_v0.py",
    "tev_script/semantic_delivery_plan_v0.py",
    "tev_script/semantic_delivery_satisfaction_v0.py",
    "tev_script/semantic_dispatch_consumption_v0.py",
    "tev_script/semantic_dispatch_v0.py",
    "tev_script/semantic_dispatch_observation_v0.py",
    "tev_script/semantic_dispatched_grounded_discovery_v0.py",
    "tev_script/semantic_execution_authority_v0.py",
    "tev_script/semantic_execution_request_v0.py",
    "tev_script/semantic_prepared_execution_v0.py",
    "tev_script/semantic_receipt_validity_v0.py",
    "tev_script/semantic_realization_search_v0.py",
    "tev_script/semantic_realization_selection_v0.py",
    "tev_script/semantic_resource_calibration_v0.py",
    "tev_script/semantic_resource_measurement_v0.py",
)
TESTS = (
    "tests/test_commit_outcome_v0.py",
    "tests/test_delivery_guarantee_v0.py",
    "tests/test_delivery_plan_v0.py",
    "tests/test_delivery_satisfaction_v0.py",
    "tests/test_dispatch_consumption_v0.py",
    "tests/test_execution_request_v0.py",
    "tests/test_prepared_execution_v0.py",
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


def require_tokens(source: str, tokens: tuple[str, ...], detail: str) -> tuple[bool, str]:
    missing = tuple(token for token in tokens if token not in source)
    if missing:
        return False, detail + ":" + ",".join(missing)
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
    request = (ROOT / "tev_script" / "semantic_execution_request_v0.py").read_text(encoding="utf-8")
    dispatch = (ROOT / "tev_script" / "semantic_dispatch_v0.py").read_text(encoding="utf-8")
    consumption = (ROOT / "tev_script" / "semantic_dispatch_consumption_v0.py").read_text(encoding="utf-8")
    execution_authority = (ROOT / "tev_script" / "semantic_execution_authority_v0.py").read_text(encoding="utf-8")
    prepared_execution = (ROOT / "tev_script" / "semantic_prepared_execution_v0.py").read_text(encoding="utf-8")
    delivery_plan = (ROOT / "tev_script" / "semantic_delivery_plan_v0.py").read_text(encoding="utf-8")
    delivery = (ROOT / "tev_script" / "semantic_delivery_guarantee_v0.py").read_text(encoding="utf-8")
    commit_outcome = (ROOT / "tev_script" / "semantic_commit_outcome_v0.py").read_text(encoding="utf-8")
    satisfaction = (ROOT / "tev_script" / "semantic_delivery_satisfaction_v0.py").read_text(encoding="utf-8")
    search = (ROOT / "tev_script" / "semantic_realization_search_v0.py").read_text(encoding="utf-8")
    dispatched_observation = (ROOT / "tev_script" / "semantic_dispatch_observation_v0.py").read_text(encoding="utf-8")
    dispatched_grounded = (ROOT / "tev_script" / "semantic_dispatched_grounded_discovery_v0.py").read_text(encoding="utf-8")
    measurement = (ROOT / "tev_script" / "semantic_resource_measurement_v0.py").read_text(encoding="utf-8")
    calibration = (ROOT / "tev_script" / "semantic_resource_calibration_v0.py").read_text(encoding="utf-8")
    selection = (ROOT / "tev_script" / "semantic_realization_selection_v0.py").read_text(encoding="utf-8")
    cost_model = (ROOT / "tev_script" / "semantic_cost_model_v0.py").read_text(encoding="utf-8")
    cost_update = (ROOT / "tev_script" / "semantic_cost_model_update_v0.py").read_text(encoding="utf-8")
    cost_prediction = (ROOT / "tev_script" / "semantic_cost_prediction_v0.py").read_text(encoding="utf-8")

    ok, detail = require_tokens(
        validity,
        ("VALID", "REVOKED", "SUPERSEDED", "UNKNOWN", "validation_epoch_hash", "authority_state_hash"),
        "historical receipt validity surface incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_HISTORICAL_RECEIPT_VALIDITY=PASS")

    ok, detail = require_tokens(
        request,
        (
            "ExecutionIntentV0",
            "ExecutionRequestV0",
            "ExecutionRequestAdmissionReceiptV0",
            "INTENT_SINGLETON",
            "OCCURRENCE_SCOPED",
            "request.requester_untrusted",
            "request.delivery_guarantee_not_allowed",
            "request.evidence_policy_empty",
        ),
        "execution request/intention boundary incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_EXECUTION_REQUEST_NOT_FREE_NONCE=PASS")

    ok, detail = require_tokens(
        prepared_execution,
        (
            "causal_invocation_workload_hash",
            "verify_prepared_refinement",
            "prepared_execution.workload_mismatch",
            "prepared_execution.refinement_revalidation_mismatch",
            "prepared_execution.prepared_refinement_not_admitted",
            "before_checkpoint_hash",
            "after_checkpoint_hash",
            "execution_authority_receipt_hash",
            "activation_candidate.activation_candidate_hash",
        ),
        "prepared causal invocation binding incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_PREPARED_EXECUTION_REVALIDATED=PASS")

    ok, detail = require_tokens(
        delivery_plan,
        (
            "DeliveryParticipantManifestV0",
            "derive_delivery_participant_manifest",
            "DISPATCH_LEDGER",
            "RUNTIME_STATE_COMMIT",
            "EXTERNAL_EFFECT",
            "delivery_plan.participant_manifest_not_derived",
            "delivery_plan.requested_guarantee_mismatch",
            "prepare_commit_abort",
            "commit_total_after_prepare",
            "trusted_coordinator_hashes",
        ),
        "pre-dispatch delivery plan boundary incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_DELIVERY_PLAN_DERIVED_BEFORE_DISPATCH=PASS")

    ok, detail = require_tokens(
        dispatch,
        (
            "dispatch_request_hash",
            "dispatch_epoch_hash",
            "EXECUTION_REQUEST_RECEIPT_CONTRACT_HASH_V0",
            "ACTIVATION_RECEIPT_CONTRACT_HASH_V0",
            "AUTHORITY_RECEIPT_CONTRACT_HASH_V0",
            "PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0",
            "DELIVERY_PLAN_RECEIPT_CONTRACT_HASH_V0",
            "execution_request_receipt_hash",
            "execution_authority_receipt_hash",
            "prepared_execution_receipt_hash",
            "delivery_plan_receipt_hash",
            "delivery_participant_manifest_hash",
            "invocation_workload_hash",
            "before_checkpoint_hash",
            "after_checkpoint_hash",
            "dispatch_consumption_domain_hash(candidate.dispatch_request_hash)",
            "dispatch consumption domain not derived from request identity",
            "dispatch.execution_request_not_current",
            "dispatch.execution_authority_not_current",
            "dispatch.prepared_execution_not_current",
            "dispatch.delivery_plan_not_current",
            "dispatch.request_workload_mismatch",
            "dispatch.delivery_plan_guarantee_mismatch",
        ),
        "just-in-time five-boundary dispatch surface incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_JIT_DISPATCH_FIVE_CURRENT_BOUNDARIES=PASS")

    ok, detail = require_tokens(
        consumption,
        (
            "DispatchConsumptionStateV0",
            "DispatchConsumptionAttemptV0",
            "dispatch_consumption.replay",
            "dispatch_consumption.request_domain_mismatch",
            "dispatch_consumption.ledger_domain_mismatch",
            "dispatch_receipt.dispatch_consumption_domain_hash",
            "before_state_hash",
            "after_state_hash",
            "trusted_storage_authority_hashes",
            "dispatch_consumption.storage_authority_untrusted",
            "dispatch_consumption.evidence_policy_empty",
        ),
        "request-scoped one-shot dispatch consumption/CAS surface incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_DISPATCH_CONSUMPTION_REQUEST_SCOPED_CAS=PASS")

    ok, detail = require_tokens(
        execution_authority,
        (
            "TransformationProgramBindingClaimV0",
            "ReactionContractV1",
            "ReactionFootprintV1",
            "CapabilityLawCatalogV1",
            "RefinementReceiptV1",
            "verify_structural_refinement",
            "authority.structural_refinement_not_admitted",
            "authority.refinement_not_admitted",
            "authority.law_catalog_incomplete",
            "authority.binding_scope_mismatch",
            "allowed_effectful_realization_relations",
            "authority.effectful_realization_relation_not_allowed",
            "binding_evidence_policy",
        ),
        "causal least-authority realization bridge incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_CAUSAL_LEAST_AUTHORITY_BRIDGE=PASS")

    ok, detail = require_tokens(
        delivery,
        (
            "AT_MOST_ONCE_DISPATCH",
            "EXACTLY_ONCE_COMMIT",
            "DURABLE_EXACTLY_ONCE_COMMIT",
            "delivery_plan_receipt_hash",
            "delivery.requested_guarantee_mismatch",
            "delivery.atomic_commit_witness_required",
            "delivery.atomic_claim_plan_mismatch",
            "delivery.atomic_claim_manifest_mismatch",
            "delivery.atomic_claim_coordinator_plan_mismatch",
            "delivery.atomic_claim_domain_plan_mismatch",
            "delivery.effect_not_exactly_once_capable",
            "delivery.effect_not_durably_recoverable",
            "delivery.atomic_commit_not_durable",
            "trusted_coordinator_hashes",
            "prepare_commit_abort",
            "commit_total_after_prepare",
            "durable_recovery",
        ),
        "delivery guarantee support/plan continuity incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_DELIVERY_GUARANTEE_NOT_OVERCLAIMED=PASS")

    ok, detail = require_tokens(
        commit_outcome,
        (
            "commit_result_field",
            "residual_from_commit_result_v1",
            "ExecutionObservationClaimV0",
            "commit_outcome.observed_result_field_mismatch",
            "commit_outcome.causal_result_invalid",
            "commit_outcome.result_prepared_reaction_mismatch",
            "commit_outcome.committed_effect_count_mismatch",
            "commit_status",
        ),
        "observed causal commit outcome binding incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_CAUSAL_COMMIT_OUTCOME_OBSERVED=PASS")

    ok, detail = require_tokens(
        satisfaction,
        (
            "DeliverySatisfactionReceiptV0",
            "causal_commit_outcome_receipt",
            "delivery_satisfaction.commit_outcome_required",
            "delivery_satisfaction.commit_not_committed",
            "delivery_satisfaction.outcome_dispatch_mismatch",
            "delivery_satisfaction.guarantee_not_admitted",
        ),
        "retrospective delivery satisfaction boundary incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_DELIVERY_SUPPORT_SATISFACTION_SEPARATED=PASS")

    ok, detail = require_tokens(
        search,
        (
            "HEURISTIC",
            "BOUNDED",
            "EXHAUSTIVE",
            "CANDIDATE_SET",
            "BOUNDED_SEARCH_SPACE",
            "EXHAUSTIVE_SEARCH_SPACE",
            "search.receipt_realization_problem_mismatch",
            "planning.candidate_universe_mismatch",
        ),
        "search coverage/planning scope surface incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_SEARCH_COVERAGE_SCOPE=PASS")

    ok, detail = require_tokens(
        dispatched_observation,
        (
            "dispatch_consumption_commit_receipt_hash",
            "consumption_after_state_hash",
            "consumption_storage_authority_hash",
            "dispatch_observation.consumption_not_committed",
            "dispatch_observation.consumption_request_mismatch",
        ),
        "consumed dispatch-to-observation binding incomplete",
    )
    if not ok:
        return fail(detail)
    if "dispatch_request_hash" not in dispatched_grounded or "observed_history_hash" not in dispatched_grounded:
        return fail("dispatch-to-grounded-discovery chain incomplete")
    print("R0_CONSUMED_DISPATCH_TO_DISCOVERY_CHAIN=PASS")

    ok, detail = require_tokens(
        measurement,
        ("measurement_epoch_hash", "execution_context_hash", "observed_resource_vector_hash", "evidence_policy_hash"),
        "resource measurement binding incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_RESOURCE_MEASUREMENT_CONTEXT_BOUND=PASS")

    ok, detail = require_tokens(
        selection,
        (
            "PARETO_MEMBER",
            "LEXICOGRAPHIC_MIN",
            "receipt.problem_hash != problem.realization_problem_hash",
            "selection.receipt_realization_problem_mismatch",
        ),
        "verifiable selection/problem binding incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_SELECTION_RULES_AND_PROBLEM_BINDING=PASS")

    ok, detail = require_tokens(
        calibration,
        ("def status(self) -> str", '"status": self.status', 'if self.status != "PASS"', 'verdict = "INCONCLUSIVE"'),
        "calibration validity/verdict separation incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_CALIBRATION_VALIDITY_VERDICT_SEPARATED=PASS")

    ok, detail = require_tokens(
        cost_model,
        ("EmpiricalCostModelV0", "CostModelAdmissionReceiptV0", "empirical_envelope", "measurement_claim_hashes", "execution_context_hash"),
        "empirical cost model surface incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_EMPIRICAL_COST_MODEL=PASS")

    ok, detail = require_tokens(
        cost_update,
        ("parent_model_hash", "successor_model_hash", "new_measurement_claim_hashes", "successor_basis_mismatch", "measurement_already_in_parent"),
        "cost model append-only lineage incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_COST_MODEL_APPEND_ONLY_LINEAGE=PASS")

    ok, detail = require_tokens(
        cost_prediction,
        ("cost_prediction.context_unseen", "EMPIRICAL_ENVELOPE", "EMPIRICAL_OBSERVATION", "model_admission.receipt_hash"),
        "cost prediction fail-closed projection incomplete",
    )
    if not ok:
        return fail(detail)
    print("R0_COST_PREDICTION_FAIL_CLOSED=PASS")

    print("R0_EXTENDED_LONG_VALIDATION_DEFERRED=PASS")
    print("REALIZATION_R0_EXTENDED_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
