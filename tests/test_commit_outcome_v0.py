from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.causal_model_v1 import CommitResultV1, PreparedReactionV1
from tev_script.semantic_causal_bridge_v0 import commit_result_field, residual_from_commit_result_v1
from tev_script.semantic_commit_outcome_v0 import (
    CausalCommitOutcomeClaimV0,
    evaluate_causal_commit_outcome,
    residual_from_causal_commit_outcome,
)
from tev_script.semantic_delivery_plan_v0 import DeliveryPlanReceiptV0
from tev_script.semantic_dispatch_consumption_v0 import DispatchConsumptionCommitReceiptV0
from tev_script.semantic_dispatch_v0 import ExecutionDispatchReceiptV0, dispatch_consumption_domain_hash
from tev_script.semantic_execution_observation_v0 import ExecutionObservationClaimV0, ExecutionObservationReceiptV0
from tev_script.semantic_prepared_execution_v0 import PreparedExecutionReceiptV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def prepared_reaction() -> PreparedReactionV1:
    before = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "marker": "before"}
    after = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "marker": "after"}
    return PreparedReactionV1(
        h("program"),
        h("source"),
        h("contract"),
        h("catalog"),
        h("prepared-refinement"),
        h("footprint"),
        "entity.main",
        "start",
        (),
        before,
        canonical_hash(before),
        after,
        canonical_hash(after),
        (),
        ({"index": 0, "capability_id": "motor.set", "arguments": []},),
        (),
        "transactional",
        ("test-prepared",),
    )


def prepared_execution(reaction: PreparedReactionV1) -> PreparedExecutionReceiptV0:
    return PreparedExecutionReceiptV0(
        prepared_execution_claim_hash=h("prepared-execution-claim"),
        activation_receipt_hash=h("activation"),
        execution_authority_receipt_hash=h("execution-authority"),
        realization_receipt_hash=h("realization-receipt"),
        realization_hash=h("realization"),
        execution_context_hash=h("execution-context"),
        invocation_workload_hash=h("workload"),
        prepared_reaction_hash=reaction.prepared_reaction_hash,
        prepared_refinement_receipt_hash=reaction.refinement_receipt_hash,
        before_checkpoint_hash=reaction.before_checkpoint_hash,
        after_checkpoint_hash=reaction.after_checkpoint_hash,
        program_semantic_hash=reaction.program_semantic_hash,
        reaction_contract_hash=reaction.contract_hash,
        reaction_footprint_hash=reaction.footprint_hash,
        law_catalog_hash=reaction.law_catalog_hash,
        issues=(),
    )


def delivery_plan(prepared: PreparedExecutionReceiptV0) -> DeliveryPlanReceiptV0:
    return DeliveryPlanReceiptV0(
        plan_claim_hash=h("delivery-plan-claim"),
        execution_request_receipt_hash=h("execution-request-receipt"),
        prepared_execution_receipt_hash=prepared.receipt_hash,
        participant_manifest_hash=h("participant-manifest"),
        requested_guarantee="EXACTLY_ONCE_COMMIT",
        coordinator_hash=h("coordinator"),
        atomic_commit_domain_hash=h("atomic-domain"),
        evidence_evaluation_hash=h("delivery-plan-evidence"),
        policy_hash=h("delivery-plan-policy"),
        issues=(),
    )


def dispatch(prepared: PreparedExecutionReceiptV0, plan: DeliveryPlanReceiptV0) -> ExecutionDispatchReceiptV0:
    request = h("execution-request")
    return ExecutionDispatchReceiptV0(
        dispatch_candidate_hash=h("dispatch-candidate"),
        dispatch_record_hash=h("dispatch-record"),
        dispatch_request_hash=request,
        dispatch_epoch_hash=h("dispatch-epoch"),
        execution_request_receipt_hash=plan.execution_request_receipt_hash,
        execution_request_intent_hash=h("execution-intent"),
        execution_request_validity_evaluation_hash=h("execution-request-validity"),
        execution_request_authority_state_hash=h("execution-request-state"),
        requester_principal_hash=h("requester"),
        purpose_hash=h("purpose"),
        requested_delivery_guarantee=plan.requested_guarantee,
        idempotency_scope="OCCURRENCE_SCOPED",
        activation_receipt_hash=prepared.activation_receipt_hash,
        activation_validity_evaluation_hash=h("activation-validity"),
        activation_authority_state_hash=h("activation-state"),
        execution_authority_receipt_hash=prepared.execution_authority_receipt_hash,
        execution_authority_claim_hash=h("execution-authority-claim"),
        execution_authority_validity_evaluation_hash=h("execution-authority-validity"),
        execution_authority_state_hash=h("execution-authority-state"),
        prepared_execution_receipt_hash=prepared.receipt_hash,
        prepared_execution_claim_hash=prepared.prepared_execution_claim_hash,
        prepared_execution_validity_evaluation_hash=h("prepared-validity"),
        prepared_execution_authority_state_hash=h("prepared-state"),
        delivery_plan_receipt_hash=plan.receipt_hash,
        delivery_plan_claim_hash=plan.plan_claim_hash,
        delivery_plan_validity_evaluation_hash=h("delivery-plan-validity"),
        delivery_plan_authority_state_hash=h("delivery-plan-state"),
        delivery_participant_manifest_hash=plan.participant_manifest_hash,
        delivery_coordinator_hash=plan.coordinator_hash,
        delivery_atomic_commit_domain_hash=plan.atomic_commit_domain_hash,
        invocation_workload_hash=prepared.invocation_workload_hash,
        before_checkpoint_hash=prepared.before_checkpoint_hash,
        after_checkpoint_hash=prepared.after_checkpoint_hash,
        dispatch_consumption_domain_hash=dispatch_consumption_domain_hash(request),
        realization_receipt_hash=prepared.realization_receipt_hash,
        realization_hash=prepared.realization_hash,
        execution_context_hash=prepared.execution_context_hash,
        machine_instance_hash=h("machine-instance"),
        placement_context_hash=h("placement-context"),
        runtime_state_claim_hash=h("runtime-state"),
        issues=(),
    )


def consumption(d: ExecutionDispatchReceiptV0) -> DispatchConsumptionCommitReceiptV0:
    return DispatchConsumptionCommitReceiptV0(
        h("consumption-claim"),
        h("consumption-record"),
        h("consumption-transition"),
        d.receipt_hash,
        d.dispatch_request_hash,
        h("ledger-before"),
        h("ledger-after"),
        h("storage-authority"),
        h("consumption-epoch"),
        h("consumption-evidence"),
        h("consumption-policy"),
        (),
    )


def observation(
    d: ExecutionDispatchReceiptV0,
    result: CommitResultV1,
    *,
    result_hash: str | None = None,
) -> tuple[ExecutionObservationClaimV0, ExecutionObservationReceiptV0]:
    result_field = commit_result_field(result)
    residual_field = residual_from_commit_result_v1(result)
    claim = ExecutionObservationClaimV0(
        d.activation_receipt_hash,
        d.execution_context_hash,
        result_hash or result_field.field_hash,
        residual_field.field_hash,
        h("observed-history"),
        h("trace"),
    )
    receipt = ExecutionObservationReceiptV0(
        claim.observation_claim_hash,
        h("observation-record"),
        d.activation_receipt_hash,
        d.execution_context_hash,
        claim.observed_history_hash,
        h("observation-evidence"),
        (),
    )
    return claim, receipt


class CausalCommitOutcomeV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.reaction = prepared_reaction()
        self.prepared = prepared_execution(self.reaction)
        self.plan = delivery_plan(self.prepared)
        self.dispatch = dispatch(self.prepared, self.plan)
        self.consumption = consumption(self.dispatch)

    def evaluate(self, result: CommitResultV1, *, observation_result_hash=None):
        obs_claim, obs_receipt = observation(
            self.dispatch,
            result,
            result_hash=observation_result_hash,
        )
        claim = CausalCommitOutcomeClaimV0(
            self.dispatch.receipt_hash,
            self.consumption.receipt_hash,
            self.plan.receipt_hash,
            self.prepared.receipt_hash,
            obs_receipt.receipt_hash,
            commit_result_field(result).field_hash,
        )
        return evaluate_causal_commit_outcome(
            claim,
            dispatch_receipt=self.dispatch,
            consumption_commit_receipt=self.consumption,
            delivery_plan_receipt=self.plan,
            prepared_execution_receipt=self.prepared,
            prepared_reaction=self.reaction,
            execution_observation_claim=obs_claim,
            execution_observation_receipt=obs_receipt,
            commit_result=result,
        )

    def test_authentic_committed_outcome_closes_and_is_marked_committed(self):
        result = CommitResultV1(
            "COMMITTED",
            self.reaction.prepared_reaction_hash,
            True,
            False,
            1,
            self.reaction.emitted_events,
        )
        receipt = self.evaluate(result)
        self.assertEqual(receipt.status, "PASS")
        self.assertTrue(receipt.committed)
        self.assertEqual(receipt.commit_status, "COMMITTED")
        self.assertEqual(receipt.expected_effects, 1)
        self.assertEqual(parse_residual(residual_from_causal_commit_outcome(receipt)).status, "CLOSED")

    def test_authentic_abort_is_valid_outcome_but_not_commit_success(self):
        result = CommitResultV1(
            "ABORTED",
            self.reaction.prepared_reaction_hash,
            False,
            False,
            0,
            self.reaction.emitted_events,
            "prepare:failure",
        )
        receipt = self.evaluate(result)
        self.assertEqual(receipt.status, "PASS")
        self.assertFalse(receipt.committed)
        self.assertEqual(receipt.commit_status, "ABORTED")

    def test_observation_cannot_authenticate_different_commit_result_field(self):
        result = CommitResultV1(
            "COMMITTED",
            self.reaction.prepared_reaction_hash,
            True,
            False,
            1,
            self.reaction.emitted_events,
        )
        receipt = self.evaluate(result, observation_result_hash=h("other-result-field"))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("commit_outcome.observed_result_field_mismatch", {item.kind for item in receipt.issues})

    def test_commit_result_for_other_prepared_reaction_is_rejected(self):
        result = CommitResultV1(
            "ABORTED",
            h("other-prepared-reaction"),
            False,
            False,
            0,
            (),
        )
        receipt = self.evaluate(result)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("commit_outcome.result_prepared_reaction_mismatch", {item.kind for item in receipt.issues})

    def test_committed_result_must_cover_all_prepared_external_effects(self):
        result = CommitResultV1(
            "COMMITTED",
            self.reaction.prepared_reaction_hash,
            True,
            False,
            0,
            self.reaction.emitted_events,
        )
        receipt = self.evaluate(result)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("commit_outcome.committed_effect_count_mismatch", {item.kind for item in receipt.issues})

    def test_internally_inconsistent_commit_flags_are_rejected(self):
        result = CommitResultV1(
            "COMMITTED",
            self.reaction.prepared_reaction_hash,
            False,
            False,
            1,
            self.reaction.emitted_events,
        )
        result_field = commit_result_field(result)
        claim = ExecutionObservationClaimV0(
            self.dispatch.activation_receipt_hash,
            self.dispatch.execution_context_hash,
            result_field.field_hash,
            h("synthetic-invalid-residual"),
            h("observed-history"),
        )
        observation_receipt = ExecutionObservationReceiptV0(
            claim.observation_claim_hash,
            h("observation-record-invalid"),
            self.dispatch.activation_receipt_hash,
            self.dispatch.execution_context_hash,
            claim.observed_history_hash,
            h("observation-evidence-invalid"),
            (),
        )
        outcome_claim = CausalCommitOutcomeClaimV0(
            self.dispatch.receipt_hash,
            self.consumption.receipt_hash,
            self.plan.receipt_hash,
            self.prepared.receipt_hash,
            observation_receipt.receipt_hash,
            result_field.field_hash,
        )
        receipt = evaluate_causal_commit_outcome(
            outcome_claim,
            dispatch_receipt=self.dispatch,
            consumption_commit_receipt=self.consumption,
            delivery_plan_receipt=self.plan,
            prepared_execution_receipt=self.prepared,
            prepared_reaction=self.reaction,
            execution_observation_claim=claim,
            execution_observation_receipt=observation_receipt,
            commit_result=result,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("commit_outcome.causal_result_invalid", {item.kind for item in receipt.issues})


if __name__ == "__main__":
    unittest.main()
