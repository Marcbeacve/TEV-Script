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

ALLOWED_ABSOLUTE_IMPORT_ROOTS = frozenset(
    {"__future__", "dataclasses", "fractions", "re", "typing"}
)
FORBIDDEN_HOST_IMPORT_ROOTS = frozenset(
    {"os", "platform", "subprocess", "socket", "psutil", "torch", "cpuinfo"}
)
FORBIDDEN_TOKENS = ("nvidia", "cuda", "rocm", "tevprover", "ia_tev", "ia-tev")

TOKEN_GATES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "R0_HISTORICAL_RECEIPT_VALIDITY",
        "tev_script/semantic_receipt_validity_v0.py",
        ("VALID", "REVOKED", "SUPERSEDED", "UNKNOWN", "validation_epoch_hash", "authority_state_hash"),
    ),
    (
        "R0_EXECUTION_REQUEST_NOT_FREE_NONCE",
        "tev_script/semantic_execution_request_v0.py",
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
    ),
    (
        "R0_CAUSAL_LEAST_AUTHORITY_BRIDGE",
        "tev_script/semantic_execution_authority_v0.py",
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
    ),
    (
        "R0_PREPARED_EXECUTION_REVALIDATED",
        "tev_script/semantic_prepared_execution_v0.py",
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
    ),
    (
        "R0_DELIVERY_PLAN_DERIVED_BEFORE_DISPATCH",
        "tev_script/semantic_delivery_plan_v0.py",
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
    ),
    (
        "R0_JIT_DISPATCH_FIVE_CURRENT_BOUNDARIES",
        "tev_script/semantic_dispatch_v0.py",
        (
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
            "dispatch_consumption_domain_hash(candidate.dispatch_request_hash)",
            "dispatch consumption domain not derived from request identity",
            "dispatch.execution_request_not_current",
            "dispatch.execution_authority_not_current",
            "dispatch.prepared_execution_not_current",
            "dispatch.delivery_plan_not_current",
            "dispatch.request_workload_mismatch",
            "dispatch.delivery_plan_guarantee_mismatch",
        ),
    ),
    (
        "R0_DISPATCH_CONSUMPTION_REQUEST_SCOPED_CAS",
        "tev_script/semantic_dispatch_consumption_v0.py",
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
    ),
    (
        "R0_DELIVERY_GUARANTEE_NOT_OVERCLAIMED",
        "tev_script/semantic_delivery_guarantee_v0.py",
        (
            "AT_MOST_ONCE_DISPATCH",
            "EXACTLY_ONCE_COMMIT",
            "DURABLE_EXACTLY_ONCE_COMMIT",
            "delivery_plan_receipt_hash",
            "delivery.requested_guarantee_mismatch",
            "delivery.atomic_commit_witness_required",
            "delivery.atomic_claim_plan_mismatch",
            "delivery.atomic_claim_participant_manifest_mismatch",
            "delivery.atomic_claim_coordinator_mismatch",
            "delivery.atomic_claim_domain_mismatch",
            "delivery.effect_not_exactly_once_capable",
            "delivery.effect_not_durably_recoverable",
            "delivery.atomic_commit_not_durable",
            "prepare_commit_abort",
            "commit_total_after_prepare",
            "durable_recovery",
        ),
    ),
    (
        "R0_CAUSAL_COMMIT_OUTCOME_OBSERVED",
        "tev_script/semantic_commit_outcome_v0.py",
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
    ),
    (
        "R0_DELIVERY_SUPPORT_SATISFACTION_SEPARATED",
        "tev_script/semantic_delivery_satisfaction_v0.py",
        (
            "DeliverySatisfactionReceiptV0",
            "causal_commit_outcome_receipt",
            "delivery_satisfaction.commit_outcome_required",
            "delivery_satisfaction.commit_not_committed",
            "delivery_satisfaction.outcome_dispatch_mismatch",
            "delivery_satisfaction.guarantee_not_admitted",
        ),
    ),
    (
        "R0_SEARCH_COVERAGE_SCOPE",
        "tev_script/semantic_realization_search_v0.py",
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
    ),
    (
        "R0_CONSUMED_DISPATCH_OBSERVATION_BOUND",
        "tev_script/semantic_dispatch_observation_v0.py",
        (
            "dispatch_consumption_commit_receipt_hash",
            "consumption_after_state_hash",
            "consumption_storage_authority_hash",
            "dispatch_observation.consumption_not_committed",
            "dispatch_observation.consumption_request_mismatch",
        ),
    ),
    (
        "R0_DISPATCHED_DISCOVERY_CHAIN",
        "tev_script/semantic_dispatched_grounded_discovery_v0.py",
        ("dispatch_request_hash", "observed_history_hash", "realization_hash"),
    ),
    (
        "R0_RESOURCE_MEASUREMENT_CONTEXT_BOUND",
        "tev_script/semantic_resource_measurement_v0.py",
        ("measurement_epoch_hash", "execution_context_hash", "observed_resource_vector_hash", "evidence_policy_hash"),
    ),
    (
        "R0_CALIBRATION_VALIDITY_VERDICT_SEPARATED",
        "tev_script/semantic_resource_calibration_v0.py",
        ("def status(self) -> str", '"status": self.status', 'if self.status != "PASS"', 'verdict = "INCONCLUSIVE"'),
    ),
    (
        "R0_SELECTION_RULES_AND_PROBLEM_BINDING",
        "tev_script/semantic_realization_selection_v0.py",
        ("PARETO_MEMBER", "LEXICOGRAPHIC_MIN", "receipt.problem_hash != problem.realization_problem_hash", "selection.receipt_realization_problem_mismatch"),
    ),
    (
        "R0_EMPIRICAL_COST_MODEL",
        "tev_script/semantic_cost_model_v0.py",
        ("EmpiricalCostModelV0", "CostModelAdmissionReceiptV0", "empirical_envelope", "measurement_claim_hashes", "execution_context_hash"),
    ),
    (
        "R0_COST_MODEL_APPEND_ONLY_LINEAGE",
        "tev_script/semantic_cost_model_update_v0.py",
        ("parent_model_hash", "successor_model_hash", "new_measurement_claim_hashes", "successor_basis_mismatch", "measurement_already_in_parent"),
    ),
    (
        "R0_COST_PREDICTION_FAIL_CLOSED",
        "tev_script/semantic_cost_prediction_v0.py",
        ("cost_prediction.context_unseen", "EMPIRICAL_ENVELOPE", "EMPIRICAL_OBSERVATION", "model_admission.receipt_hash"),
    ),
)


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

    for marker, path_text, tokens in TOKEN_GATES:
        source = (ROOT / path_text).read_text(encoding="utf-8")
        missing = tuple(token for token in tokens if token not in source)
        if missing:
            return fail(f"{marker}:missing=" + ",".join(missing))
        print(marker + "=PASS")

    print("R0_EXTENDED_LONG_VALIDATION_DEFERRED=PASS")
    print("REALIZATION_R0_EXTENDED_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
