from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_dispatch_consumption_v0 import (
    DispatchConsumptionCommitReceiptV0,
    DispatchConsumptionIssueV0,
)
from tev_script.semantic_dispatch_observation_v0 import (
    DispatchObservationIssueV0,
    DispatchedExecutionObservationBindingV0,
    DispatchedExecutionObservationReceiptV0,
    evaluate_dispatched_execution_observation,
    residual_from_dispatched_execution_observation,
)
from tev_script.semantic_dispatch_v0 import (
    DispatchIssueV0,
    ExecutionDispatchReceiptV0,
    dispatch_consumption_domain_hash,
)
from tev_script.semantic_dispatched_grounded_discovery_v0 import (
    DispatchedGroundedDiscoveryV0,
    evaluate_dispatched_grounded_discovery,
    residual_from_dispatched_grounded_discovery,
)
from tev_script.semantic_execution_observation_v0 import (
    ExecutionObservationIssueV0,
    ExecutionObservationReceiptV0,
)
from tev_script.semantic_grounded_discovery_v0 import (
    ExecutionGroundedDiscoveryEvaluationV0,
    GroundedDiscoveryIssueV0,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def dispatch(*, issues=(), activation=None, context=None, request=None, authority_claim=None) -> ExecutionDispatchReceiptV0:
    request_hash = request or h("dispatch-request")
    return ExecutionDispatchReceiptV0(
        dispatch_candidate_hash=h("dispatch-candidate"),
        dispatch_record_hash=h("dispatch-record"),
        dispatch_request_hash=request_hash,
        dispatch_epoch_hash=h("dispatch-epoch"),
        activation_receipt_hash=activation or h("activation"),
        activation_validity_evaluation_hash=h("activation-validity-evaluation"),
        activation_authority_state_hash=h("activation-authority-state"),
        execution_authority_receipt_hash=h("execution-authority-receipt"),
        execution_authority_claim_hash=authority_claim or h("execution-authority-claim"),
        execution_authority_validity_evaluation_hash=h("execution-authority-validity-evaluation"),
        execution_authority_state_hash=h("execution-authority-state"),
        prepared_execution_receipt_hash=h("prepared-execution-receipt"),
        prepared_execution_claim_hash=h("prepared-execution-claim"),
        prepared_execution_validity_evaluation_hash=h("prepared-execution-validity-evaluation"),
        prepared_execution_authority_state_hash=h("prepared-execution-authority-state"),
        invocation_workload_hash=h("invocation-workload"),
        before_checkpoint_hash=h("before-checkpoint"),
        after_checkpoint_hash=h("after-checkpoint"),
        dispatch_consumption_domain_hash=dispatch_consumption_domain_hash(request_hash),
        realization_receipt_hash=h("realization-receipt"),
        realization_hash=h("realization"),
        execution_context_hash=context or h("execution-context"),
        machine_instance_hash=h("machine-instance"),
        placement_context_hash=h("placement-context"),
        runtime_state_claim_hash=h("runtime-claim"),
        issues=tuple(issues),
    )


def consumption(d: ExecutionDispatchReceiptV0, *, issues=(), request=None) -> DispatchConsumptionCommitReceiptV0:
    return DispatchConsumptionCommitReceiptV0(
        h("consumption-claim"),
        h("consumption-record"),
        h("consumption-transition"),
        d.receipt_hash,
        request or d.dispatch_request_hash,
        h("consumption-before"),
        h("consumption-after"),
        h("storage-authority"),
        h("consumption-epoch"),
        h("consumption-evidence-evaluation"),
        h("consumption-policy"),
        tuple(issues),
    )


def observation(*, issues=(), activation=None, context=None, history=None) -> ExecutionObservationReceiptV0:
    return ExecutionObservationReceiptV0(
        h("observation-claim"),
        h("observation-record"),
        activation or h("activation"),
        context or h("execution-context"),
        history or h("observed-history"),
        h("observation-evidence-evaluation"),
        tuple(issues),
    )


class DispatchObservationBindingV0Tests(unittest.TestCase):
    def evaluate(self, d, c, o):
        binding = DispatchedExecutionObservationBindingV0(
            d.receipt_hash,
            c.receipt_hash,
            o.receipt_hash,
        )
        return evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=d,
            dispatch_consumption_commit_receipt=c,
            execution_observation_receipt=o,
        )

    def test_matching_pass_receipts_bind_consumed_dispatch_to_observation(self):
        d = dispatch()
        c = consumption(d)
        o = observation()
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.dispatch_request_hash, d.dispatch_request_hash)
        self.assertEqual(receipt.dispatch_consumption_commit_receipt_hash, c.receipt_hash)
        self.assertEqual(receipt.consumption_after_state_hash, c.after_state_hash)
        self.assertEqual(receipt.realization_receipt_hash, d.realization_receipt_hash)
        self.assertEqual(parse_residual(residual_from_dispatched_execution_observation(receipt)).status, "CLOSED")

    def test_uncommitted_consumption_keeps_observation_open(self):
        d = dispatch()
        c = consumption(
            d,
            issues=(
                DispatchConsumptionIssueV0(
                    "dispatch_consumption.evidence.required",
                    "PROOF_REQUIRED",
                    h("cas"),
                    {},
                ),
            ),
        )
        o = observation()
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch_observation.consumption_not_committed", {item.kind for item in receipt.issues})

    def test_consumption_for_other_dispatch_request_rejects(self):
        d = dispatch()
        c = consumption(d, request=h("other-request"))
        o = observation()
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.consumption_request_mismatch", {item.kind for item in receipt.issues})

    def test_activation_mismatch_rejects(self):
        d = dispatch(activation=h("activation-a"))
        c = consumption(d)
        o = observation(activation=h("activation-b"))
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.activation_mismatch", {item.kind for item in receipt.issues})

    def test_execution_context_mismatch_rejects(self):
        d = dispatch(context=h("context-a"))
        c = consumption(d)
        o = observation(context=h("context-b"))
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.execution_context_mismatch", {item.kind for item in receipt.issues})

    def test_open_prepared_dispatch_propagates_proof_required(self):
        d = dispatch(
            issues=(
                DispatchIssueV0(
                    "dispatch.prepared_execution_not_current",
                    "PROOF_REQUIRED",
                    h("prepared-validity"),
                    {},
                ),
            )
        )
        c = consumption(d)
        o = observation()
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch_observation.dispatch_not_admitted", {item.kind for item in receipt.issues})

    def test_rejected_observation_propagates_reject(self):
        d = dispatch()
        c = consumption(d)
        o = observation(
            issues=(ExecutionObservationIssueV0("observation.history_mismatch", "REJECT", h("history"), {}),)
        )
        receipt = self.evaluate(d, c, o)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.observation_not_admitted", {item.kind for item in receipt.issues})


class DispatchedGroundedDiscoveryV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatch = dispatch()
        self.consumption = consumption(self.dispatch)
        self.observation = observation()
        binding = DispatchedExecutionObservationBindingV0(
            self.dispatch.receipt_hash,
            self.consumption.receipt_hash,
            self.observation.receipt_hash,
        )
        self.dispatched_observation = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=self.dispatch,
            dispatch_consumption_commit_receipt=self.consumption,
            execution_observation_receipt=self.observation,
        )
        self.grounded = ExecutionGroundedDiscoveryEvaluationV0(
            h("grounded-cycle"),
            h("epistemic-evaluation"),
            self.dispatch.activation_receipt_hash,
            self.observation.receipt_hash,
            self.dispatch.realization_receipt_hash,
            self.observation.observed_history_hash,
            (),
        )

    def cycle(self, grounded=None, dispatched=None):
        grounded = grounded or self.grounded
        dispatched = dispatched or self.dispatched_observation
        return DispatchedGroundedDiscoveryV0(
            grounded.evaluation_hash,
            dispatched.receipt_hash,
        )

    def evaluate(self, grounded=None, dispatched=None):
        grounded = grounded or self.grounded
        dispatched = dispatched or self.dispatched_observation
        return evaluate_dispatched_grounded_discovery(
            self.cycle(grounded, dispatched),
            grounded_discovery_evaluation=grounded,
            dispatched_execution_observation_receipt=dispatched,
        )

    def test_consumed_dispatch_identity_reaches_grounded_rediscovery(self):
        evaluation = self.evaluate()
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(evaluation.dispatch_request_hash, self.dispatch.dispatch_request_hash)
        self.assertEqual(evaluation.realization_hash, self.dispatch.realization_hash)
        self.assertEqual(evaluation.observed_history_hash, self.observation.observed_history_hash)
        self.assertEqual(parse_residual(residual_from_dispatched_grounded_discovery(evaluation)).status, "CLOSED")

    def mismatched_dispatched(self, *, observation_receipt=None, history=None, issues=()):
        return DispatchedExecutionObservationReceiptV0(
            self.dispatched_observation.binding_hash,
            self.dispatched_observation.dispatch_receipt_hash,
            self.dispatched_observation.dispatch_consumption_commit_receipt_hash,
            self.dispatched_observation.dispatch_request_hash,
            self.dispatched_observation.dispatch_epoch_hash,
            self.dispatched_observation.consumption_after_state_hash,
            self.dispatched_observation.consumption_storage_authority_hash,
            observation_receipt or self.dispatched_observation.execution_observation_receipt_hash,
            self.dispatched_observation.activation_receipt_hash,
            self.dispatched_observation.realization_receipt_hash,
            self.dispatched_observation.realization_hash,
            self.dispatched_observation.execution_context_hash,
            history or self.dispatched_observation.observed_history_hash,
            tuple(issues),
        )

    def test_different_execution_observation_receipt_rejects(self):
        evaluation = self.evaluate(
            dispatched=self.mismatched_dispatched(observation_receipt=h("other-observation-receipt"))
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("dispatched_grounded.execution_observation_receipt_mismatch", {item.kind for item in evaluation.issues})

    def test_history_mismatch_rejects(self):
        evaluation = self.evaluate(
            dispatched=self.mismatched_dispatched(history=h("other-history"))
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("dispatched_grounded.history_mismatch", {item.kind for item in evaluation.issues})

    def test_open_grounded_discovery_propagates_proof_required(self):
        grounded = ExecutionGroundedDiscoveryEvaluationV0(
            self.grounded.grounded_cycle_hash,
            self.grounded.epistemic_evaluation_hash,
            self.grounded.activation_receipt_hash,
            self.grounded.execution_observation_receipt_hash,
            self.grounded.realization_receipt_hash,
            self.grounded.observed_history_hash,
            (
                GroundedDiscoveryIssueV0(
                    "grounded.execution_observation_not_admitted",
                    "PROOF_REQUIRED",
                    h("observation"),
                    {},
                ),
            ),
        )
        evaluation = self.evaluate(grounded=grounded)
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("dispatched_grounded.grounded_discovery_not_admitted", {item.kind for item in evaluation.issues})

    def test_rejected_dispatch_observation_propagates_reject(self):
        dispatched = self.mismatched_dispatched(
            issues=(
                DispatchObservationIssueV0(
                    "dispatch_observation.execution_context_mismatch",
                    "REJECT",
                    h("context"),
                    {},
                ),
            )
        )
        evaluation = self.evaluate(dispatched=dispatched)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("dispatched_grounded.dispatch_observation_not_admitted", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
