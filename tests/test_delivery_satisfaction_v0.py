from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_commit_outcome_v0 import CausalCommitOutcomeReceiptV0
from tev_script.semantic_delivery_guarantee_v0 import (
    DeliveryGuaranteeIssueV0,
    DeliveryGuaranteeReceiptV0,
)
from tev_script.semantic_delivery_satisfaction_v0 import (
    DeliverySatisfactionClaimV0,
    evaluate_delivery_satisfaction,
    residual_from_delivery_satisfaction,
)
from tev_script.semantic_dispatch_v0 import ExecutionDispatchReceiptV0, dispatch_consumption_domain_hash
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def dispatch(guarantee: str) -> ExecutionDispatchReceiptV0:
    request = h("request-" + guarantee)
    coordinator = "" if guarantee == "AT_MOST_ONCE_DISPATCH" else h("coordinator")
    atomic_domain = "" if guarantee == "AT_MOST_ONCE_DISPATCH" else h("atomic-domain")
    return ExecutionDispatchReceiptV0(
        dispatch_candidate_hash=h("dispatch-candidate-" + guarantee),
        dispatch_record_hash=h("dispatch-record-" + guarantee),
        dispatch_request_hash=request,
        dispatch_epoch_hash=h("dispatch-epoch"),
        execution_request_receipt_hash=h("execution-request-receipt"),
        execution_request_intent_hash=h("execution-intent"),
        execution_request_validity_evaluation_hash=h("request-validity"),
        execution_request_authority_state_hash=h("request-state"),
        requester_principal_hash=h("requester"),
        purpose_hash=h("purpose"),
        requested_delivery_guarantee=guarantee,
        idempotency_scope="OCCURRENCE_SCOPED",
        activation_receipt_hash=h("activation"),
        activation_validity_evaluation_hash=h("activation-validity"),
        activation_authority_state_hash=h("activation-state"),
        execution_authority_receipt_hash=h("execution-authority"),
        execution_authority_claim_hash=h("execution-authority-claim"),
        execution_authority_validity_evaluation_hash=h("execution-authority-validity"),
        execution_authority_state_hash=h("execution-authority-state"),
        prepared_execution_receipt_hash=h("prepared-execution"),
        prepared_execution_claim_hash=h("prepared-claim"),
        prepared_execution_validity_evaluation_hash=h("prepared-validity"),
        prepared_execution_authority_state_hash=h("prepared-state"),
        delivery_plan_receipt_hash=h("delivery-plan"),
        delivery_plan_claim_hash=h("delivery-plan-claim"),
        delivery_plan_validity_evaluation_hash=h("delivery-plan-validity"),
        delivery_plan_authority_state_hash=h("delivery-plan-state"),
        delivery_participant_manifest_hash=h("participant-manifest"),
        delivery_coordinator_hash=coordinator,
        delivery_atomic_commit_domain_hash=atomic_domain,
        invocation_workload_hash=h("workload"),
        before_checkpoint_hash=h("before"),
        after_checkpoint_hash=h("after"),
        dispatch_consumption_domain_hash=dispatch_consumption_domain_hash(request),
        realization_receipt_hash=h("realization-receipt"),
        realization_hash=h("realization"),
        execution_context_hash=h("execution-context"),
        machine_instance_hash=h("machine-instance"),
        placement_context_hash=h("placement"),
        runtime_state_claim_hash=h("runtime-state"),
        issues=(),
    )


def guarantee_receipt(d: ExecutionDispatchReceiptV0, *, issues=()) -> DeliveryGuaranteeReceiptV0:
    return DeliveryGuaranteeReceiptV0(
        delivery_claim_hash=h("delivery-claim-" + d.requested_delivery_guarantee),
        requested_guarantee=d.requested_delivery_guarantee,
        dispatch_receipt_hash=d.receipt_hash,
        delivery_plan_receipt_hash=d.delivery_plan_receipt_hash,
        dispatch_consumption_commit_receipt_hash=h("consumption-receipt"),
        prepared_execution_receipt_hash=d.prepared_execution_receipt_hash,
        atomic_delivery_claim_hash="" if d.requested_delivery_guarantee == "AT_MOST_ONCE_DISPATCH" else h("atomic-claim"),
        atomic_evidence_evaluation_hash="" if d.requested_delivery_guarantee == "AT_MOST_ONCE_DISPATCH" else h("atomic-evidence"),
        policy_hash=h("delivery-policy"),
        issues=tuple(issues),
    )


def outcome(d: ExecutionDispatchReceiptV0, g: DeliveryGuaranteeReceiptV0, status: str, *, issues=()) -> CausalCommitOutcomeReceiptV0:
    if status == "COMMITTED":
        state_committed, external_partial, committed_effects = True, False, 1
    elif status == "ABORTED":
        state_committed, external_partial, committed_effects = False, False, 0
    else:
        state_committed, external_partial, committed_effects = False, True, 1
    return CausalCommitOutcomeReceiptV0(
        outcome_claim_hash=h("outcome-claim-" + status),
        dispatch_receipt_hash=d.receipt_hash,
        dispatch_consumption_commit_receipt_hash=g.dispatch_consumption_commit_receipt_hash,
        delivery_plan_receipt_hash=g.delivery_plan_receipt_hash,
        prepared_execution_receipt_hash=g.prepared_execution_receipt_hash,
        execution_observation_receipt_hash=h("observation-receipt-" + status),
        causal_commit_result_field_hash=h("commit-result-field-" + status),
        causal_commit_residual_field_hash=h("commit-residual-field-" + status),
        prepared_reaction_hash=h("prepared-reaction"),
        commit_status=status,
        state_committed=state_committed,
        external_partial=external_partial,
        committed_effects=committed_effects,
        expected_effects=1,
        issues=tuple(issues),
    )


class DeliverySatisfactionV0Tests(unittest.TestCase):
    def test_at_most_once_satisfaction_does_not_require_successful_commit(self):
        d = dispatch("AT_MOST_ONCE_DISPATCH")
        g = guarantee_receipt(d)
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
        )
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.commit_status, "")
        self.assertEqual(parse_residual(residual_from_delivery_satisfaction(receipt)).status, "CLOSED")

    def test_exactly_once_requires_authentic_committed_outcome(self):
        d = dispatch("EXACTLY_ONCE_COMMIT")
        g = guarantee_receipt(d)
        o = outcome(d, g, "COMMITTED")
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee, o.receipt_hash)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
            causal_commit_outcome_receipt=o,
        )
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.commit_status, "COMMITTED")

    def test_exactly_once_without_outcome_stays_open(self):
        d = dispatch("EXACTLY_ONCE_COMMIT")
        g = guarantee_receipt(d)
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("delivery_satisfaction.commit_outcome_required", {item.kind for item in receipt.issues})

    def test_authentic_abort_does_not_satisfy_exactly_once_commit(self):
        d = dispatch("EXACTLY_ONCE_COMMIT")
        g = guarantee_receipt(d)
        o = outcome(d, g, "ABORTED")
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee, o.receipt_hash)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
            causal_commit_outcome_receipt=o,
        )
        self.assertEqual(o.status, "PASS")
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery_satisfaction.commit_not_committed", {item.kind for item in receipt.issues})

    def test_external_partial_never_satisfies_exactly_once_commit(self):
        d = dispatch("EXACTLY_ONCE_COMMIT")
        g = guarantee_receipt(d)
        o = outcome(d, g, "EXTERNAL_PARTIAL")
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee, o.receipt_hash)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
            causal_commit_outcome_receipt=o,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery_satisfaction.commit_not_committed", {item.kind for item in receipt.issues})

    def test_outcome_from_other_dispatch_is_rejected(self):
        d = dispatch("EXACTLY_ONCE_COMMIT")
        g = guarantee_receipt(d)
        o = outcome(d, g, "COMMITTED")
        foreign = CausalCommitOutcomeReceiptV0(
            outcome_claim_hash=o.outcome_claim_hash,
            dispatch_receipt_hash=h("foreign-dispatch"),
            dispatch_consumption_commit_receipt_hash=o.dispatch_consumption_commit_receipt_hash,
            delivery_plan_receipt_hash=o.delivery_plan_receipt_hash,
            prepared_execution_receipt_hash=o.prepared_execution_receipt_hash,
            execution_observation_receipt_hash=o.execution_observation_receipt_hash,
            causal_commit_result_field_hash=o.causal_commit_result_field_hash,
            causal_commit_residual_field_hash=o.causal_commit_residual_field_hash,
            prepared_reaction_hash=o.prepared_reaction_hash,
            commit_status=o.commit_status,
            state_committed=o.state_committed,
            external_partial=o.external_partial,
            committed_effects=o.committed_effects,
            expected_effects=o.expected_effects,
            issues=(),
        )
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee, foreign.receipt_hash)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
            causal_commit_outcome_receipt=foreign,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery_satisfaction.outcome_dispatch_mismatch", {item.kind for item in receipt.issues})

    def test_open_guarantee_cannot_be_satisfied(self):
        d = dispatch("EXACTLY_ONCE_COMMIT")
        g = guarantee_receipt(
            d,
            issues=(DeliveryGuaranteeIssueV0("delivery.atomic_commit_witness_required", "PROOF_REQUIRED", h("atomic"), {}),),
        )
        o = outcome(d, g, "COMMITTED")
        claim = DeliverySatisfactionClaimV0(g.receipt_hash, d.receipt_hash, g.requested_guarantee, o.receipt_hash)
        receipt = evaluate_delivery_satisfaction(
            claim,
            delivery_guarantee_receipt=g,
            dispatch_receipt=d,
            causal_commit_outcome_receipt=o,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("delivery_satisfaction.guarantee_not_admitted", {item.kind for item in receipt.issues})


if __name__ == "__main__":
    unittest.main()
