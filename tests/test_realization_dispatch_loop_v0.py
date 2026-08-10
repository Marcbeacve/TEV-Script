from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_dispatch_observation_v0 import (
    DispatchObservationIssueV0,
    DispatchedExecutionObservationBindingV0,
    DispatchedExecutionObservationReceiptV0,
    evaluate_dispatched_execution_observation,
    residual_from_dispatched_execution_observation,
)
from tev_script.semantic_dispatch_v0 import DispatchIssueV0, ExecutionDispatchReceiptV0
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


def dispatch(*, issues=(), activation=None, context=None) -> ExecutionDispatchReceiptV0:
    return ExecutionDispatchReceiptV0(
        h("dispatch-candidate"),
        h("dispatch-record"),
        h("dispatch-request"),
        h("dispatch-epoch"),
        activation or h("activation"),
        h("activation-validity-evaluation"),
        h("activation-authority-state"),
        h("execution-authority-receipt"),
        h("execution-authority-validity-evaluation"),
        h("execution-authority-state"),
        h("realization-receipt"),
        h("realization"),
        context or h("execution-context"),
        h("machine-instance"),
        h("placement-context"),
        h("runtime-claim"),
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
    def test_matching_pass_receipts_bind_dispatch_to_observation(self):
        d = dispatch()
        o = observation()
        binding = DispatchedExecutionObservationBindingV0(d.receipt_hash, o.receipt_hash)
        receipt = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=d,
            execution_observation_receipt=o,
        )
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.dispatch_request_hash, d.dispatch_request_hash)
        self.assertEqual(receipt.realization_receipt_hash, d.realization_receipt_hash)
        self.assertEqual(parse_residual(residual_from_dispatched_execution_observation(receipt)).status, "CLOSED")

    def test_activation_mismatch_rejects(self):
        d = dispatch(activation=h("activation-a"))
        o = observation(activation=h("activation-b"))
        binding = DispatchedExecutionObservationBindingV0(d.receipt_hash, o.receipt_hash)
        receipt = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=d,
            execution_observation_receipt=o,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.activation_mismatch", {item.kind for item in receipt.issues})

    def test_execution_context_mismatch_rejects(self):
        d = dispatch(context=h("context-a"))
        o = observation(context=h("context-b"))
        binding = DispatchedExecutionObservationBindingV0(d.receipt_hash, o.receipt_hash)
        receipt = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=d,
            execution_observation_receipt=o,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.execution_context_mismatch", {item.kind for item in receipt.issues})

    def test_open_dispatch_propagates_proof_required(self):
        d = dispatch(
            issues=(DispatchIssueV0("dispatch.execution_authority_not_current", "PROOF_REQUIRED", h("authority-validity"), {}),)
        )
        o = observation()
        binding = DispatchedExecutionObservationBindingV0(d.receipt_hash, o.receipt_hash)
        receipt = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=d,
            execution_observation_receipt=o,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch_observation.dispatch_not_admitted", {item.kind for item in receipt.issues})

    def test_rejected_observation_propagates_reject(self):
        d = dispatch()
        o = observation(
            issues=(ExecutionObservationIssueV0("observation.history_mismatch", "REJECT", h("history"), {}),)
        )
        binding = DispatchedExecutionObservationBindingV0(d.receipt_hash, o.receipt_hash)
        receipt = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=d,
            execution_observation_receipt=o,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_observation.observation_not_admitted", {item.kind for item in receipt.issues})


class DispatchedGroundedDiscoveryV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatch = dispatch()
        self.observation = observation()
        binding = DispatchedExecutionObservationBindingV0(
            self.dispatch.receipt_hash,
            self.observation.receipt_hash,
        )
        self.dispatched_observation = evaluate_dispatched_execution_observation(
            binding,
            dispatch_receipt=self.dispatch,
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

    def test_dispatch_identity_reaches_grounded_rediscovery(self):
        evaluation = self.evaluate()
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(evaluation.dispatch_request_hash, self.dispatch.dispatch_request_hash)
        self.assertEqual(evaluation.realization_hash, self.dispatch.realization_hash)
        self.assertEqual(evaluation.observed_history_hash, self.observation.observed_history_hash)
        self.assertEqual(parse_residual(residual_from_dispatched_grounded_discovery(evaluation)).status, "CLOSED")

    def test_different_execution_observation_receipt_rejects(self):
        mismatched = DispatchedExecutionObservationReceiptV0(
            self.dispatched_observation.binding_hash,
            self.dispatched_observation.dispatch_receipt_hash,
            self.dispatched_observation.dispatch_request_hash,
            self.dispatched_observation.dispatch_epoch_hash,
            h("other-observation-receipt"),
            self.dispatched_observation.activation_receipt_hash,
            self.dispatched_observation.realization_receipt_hash,
            self.dispatched_observation.realization_hash,
            self.dispatched_observation.execution_context_hash,
            self.dispatched_observation.observed_history_hash,
            (),
        )
        evaluation = self.evaluate(dispatched=mismatched)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("dispatched_grounded.execution_observation_receipt_mismatch", {item.kind for item in evaluation.issues})

    def test_history_mismatch_rejects(self):
        mismatched = DispatchedExecutionObservationReceiptV0(
            self.dispatched_observation.binding_hash,
            self.dispatched_observation.dispatch_receipt_hash,
            self.dispatched_observation.dispatch_request_hash,
            self.dispatched_observation.dispatch_epoch_hash,
            self.dispatched_observation.execution_observation_receipt_hash,
            self.dispatched_observation.activation_receipt_hash,
            self.dispatched_observation.realization_receipt_hash,
            self.dispatched_observation.realization_hash,
            self.dispatched_observation.execution_context_hash,
            h("other-history"),
            (),
        )
        evaluation = self.evaluate(dispatched=mismatched)
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
        dispatched = DispatchedExecutionObservationReceiptV0(
            self.dispatched_observation.binding_hash,
            self.dispatched_observation.dispatch_receipt_hash,
            self.dispatched_observation.dispatch_request_hash,
            self.dispatched_observation.dispatch_epoch_hash,
            self.dispatched_observation.execution_observation_receipt_hash,
            self.dispatched_observation.activation_receipt_hash,
            self.dispatched_observation.realization_receipt_hash,
            self.dispatched_observation.realization_hash,
            self.dispatched_observation.execution_context_hash,
            self.dispatched_observation.observed_history_hash,
            (
                DispatchObservationIssueV0(
                    "dispatch_observation.execution_context_mismatch",
                    "REJECT",
                    h("context"),
                    {},
                ),
            ),
        )
        evaluation = self.evaluate(dispatched=dispatched)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("dispatched_grounded.dispatch_observation_not_admitted", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
