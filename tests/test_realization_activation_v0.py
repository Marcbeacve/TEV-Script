from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import (
    ExecutionActivationCandidateV0,
    evaluate_execution_activation,
    residual_from_execution_activation,
)
from tev_script.semantic_placement_v0 import PlacementContextV0, PlacementEvaluationV0, execution_context_hash
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0, RealizationIssueV0
from tev_script.semantic_residual_v0 import parse_residual
from tev_script.semantic_runtime_state_v0 import (
    RuntimeStateEvaluationV0,
    RuntimeStateIssueV0,
    RuntimeStateObservationV0,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


def realization_receipt(*, issues=()) -> RealizationAdmissionReceiptV0:
    return RealizationAdmissionReceiptV0(
        problem_hash=h("problem"),
        candidate_hash=h("candidate"),
        realization_hash=h("realization"),
        semantic_claim_hash=h("semantic-claim"),
        artifact_manifest_hash=h("manifest"),
        transformation_semantic_hash=h("transformation"),
        transformation_regime_binding_hash=h("binding"),
        semantic_relation="EXACT_EQUIVALENT",
        regime_preservation_claim_hash=h("preservation"),
        resource_estimate_claim_hash=h("resource-estimate"),
        machine_hash=h("machine-profile"),
        policy_hash=h("realization-policy"),
        regime_hash=h("regime"),
        resource_catalog_hash=h("resource-catalog"),
        machine_compatibility_hash=h("machine-evaluation"),
        regime_evaluation_hash=h("regime-evaluation"),
        realization_evidence_evaluation_hash=h("semantic-evidence"),
        regime_evidence_evaluation_hash=h("regime-evidence"),
        resource_evidence_evaluation_hash=h("resource-evidence"),
        issues=tuple(issues),
    )


class ExecutionActivationV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.receipt = realization_receipt()
        self.instance = h("machine-instance")
        self.placement_context = PlacementContextV0(
            self.instance,
            location_hash=h("location"),
            authority_domain_hash=h("authority"),
            fault_domain_hash=h("fault-domain"),
            communication_domain_hash=h("communication"),
        )
        self.placement_evaluation = PlacementEvaluationV0(
            h("placement-candidate"),
            h("placement-record"),
            self.receipt.receipt_hash,
            self.instance,
            self.placement_context.placement_context_hash,
            h("placement-policy"),
            h("instance-evidence-evaluation"),
            (),
        )
        self.runtime_observation = RuntimeStateObservationV0(
            self.instance,
            h("epoch"),
            "AVAILABLE",
            h("runtime-state"),
        )
        self.runtime_evaluation = RuntimeStateEvaluationV0(
            self.runtime_observation.runtime_state_claim_hash,
            self.runtime_observation.record_hash,
            h("runtime-policy"),
            h("runtime-evidence-evaluation"),
            (),
        )
        self.workload = h("workload")
        self.environment = h("environment")
        self.execution_context = execution_context_hash(
            realization_hash=self.receipt.realization_hash,
            machine_instance_hash=self.instance,
            placement_context_hash=self.placement_context.placement_context_hash,
            workload_hash=self.workload,
            environment_hash=self.environment,
        )

    def candidate(self, *, execution_context=None, provenance=None):
        return ExecutionActivationCandidateV0(
            self.receipt.receipt_hash,
            self.placement_evaluation.evaluation_hash,
            self.runtime_evaluation.evaluation_hash,
            self.runtime_observation.runtime_state_claim_hash,
            execution_context or self.execution_context,
            self.workload,
            self.environment,
            provenance={} if provenance is None else provenance,
        )

    def evaluate(self, candidate=None, **overrides):
        args = {
            "realization_receipt": self.receipt,
            "placement_evaluation": self.placement_evaluation,
            "placement_context": self.placement_context,
            "runtime_state_evaluation": self.runtime_evaluation,
            "runtime_state_observation": self.runtime_observation,
        }
        args.update(overrides)
        return evaluate_execution_activation(candidate or self.candidate(), **args)

    def test_all_admissions_same_instance_and_context_close_activation(self):
        receipt = self.evaluate()
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.execution_context_hash, self.execution_context)
        self.assertEqual(parse_residual(residual_from_execution_activation(receipt)).status, "CLOSED")

    def test_activation_provenance_is_record_not_activation_identity(self):
        left = self.candidate(provenance={"planner": "a"})
        right = self.candidate(provenance={"planner": "b"})
        self.assertEqual(left.activation_candidate_hash, right.activation_candidate_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_proof_required_runtime_state_propagates_as_open_activation(self):
        runtime = RuntimeStateEvaluationV0(
            self.runtime_observation.runtime_state_claim_hash,
            self.runtime_observation.record_hash,
            h("runtime-policy"),
            h("runtime-evidence-evaluation"),
            (RuntimeStateIssueV0("runtime.availability_unknown", "PROOF_REQUIRED", h("unknown"), {}),),
        )
        candidate = ExecutionActivationCandidateV0(
            self.receipt.receipt_hash,
            self.placement_evaluation.evaluation_hash,
            runtime.evaluation_hash,
            self.runtime_observation.runtime_state_claim_hash,
            self.execution_context,
            self.workload,
            self.environment,
        )
        result = self.evaluate(candidate, runtime_state_evaluation=runtime)
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("activation.runtime_state_not_admitted", {item.kind for item in result.issues})

    def test_rejected_realization_propagates_reject(self):
        rejected = realization_receipt(
            issues=(RealizationIssueV0("realization.failure", "REJECT", h("failure"), {}),)
        )
        placement = PlacementEvaluationV0(
            h("placement-candidate"),
            h("placement-record"),
            rejected.receipt_hash,
            self.instance,
            self.placement_context.placement_context_hash,
            h("placement-policy"),
            h("instance-evidence-evaluation"),
            (),
        )
        context = execution_context_hash(
            realization_hash=rejected.realization_hash,
            machine_instance_hash=self.instance,
            placement_context_hash=self.placement_context.placement_context_hash,
            workload_hash=self.workload,
            environment_hash=self.environment,
        )
        candidate = ExecutionActivationCandidateV0(
            rejected.receipt_hash,
            placement.evaluation_hash,
            self.runtime_evaluation.evaluation_hash,
            self.runtime_observation.runtime_state_claim_hash,
            context,
            self.workload,
            self.environment,
        )
        result = self.evaluate(candidate, realization_receipt=rejected, placement_evaluation=placement)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("activation.realization_not_admitted", {item.kind for item in result.issues})

    def test_runtime_state_from_other_instance_rejects(self):
        other_observation = RuntimeStateObservationV0(
            h("other-instance"),
            h("epoch"),
            "AVAILABLE",
            h("runtime-state"),
        )
        other_eval = RuntimeStateEvaluationV0(
            other_observation.runtime_state_claim_hash,
            other_observation.record_hash,
            h("runtime-policy"),
            h("runtime-evidence-evaluation"),
            (),
        )
        candidate = ExecutionActivationCandidateV0(
            self.receipt.receipt_hash,
            self.placement_evaluation.evaluation_hash,
            other_eval.evaluation_hash,
            other_observation.runtime_state_claim_hash,
            self.execution_context,
            self.workload,
            self.environment,
        )
        result = self.evaluate(
            candidate,
            runtime_state_evaluation=other_eval,
            runtime_state_observation=other_observation,
        )
        self.assertEqual(result.status, "REJECT")
        self.assertIn("activation.runtime_instance_mismatch", {item.kind for item in result.issues})

    def test_execution_context_cannot_be_forged(self):
        result = self.evaluate(self.candidate(execution_context=h("forged-context")))
        self.assertEqual(result.status, "REJECT")
        self.assertIn("activation.execution_context_mismatch", {item.kind for item in result.issues})

    def test_placement_context_object_must_match_admitted_placement(self):
        other = PlacementContextV0(
            self.instance,
            location_hash=h("other-location"),
            authority_domain_hash=h("authority"),
            fault_domain_hash=h("fault-domain"),
            communication_domain_hash=h("communication"),
        )
        result = self.evaluate(placement_context=other)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("activation.placement_context_mismatch", {item.kind for item in result.issues})


if __name__ == "__main__":
    unittest.main()
