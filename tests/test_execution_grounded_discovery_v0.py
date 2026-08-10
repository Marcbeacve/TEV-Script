from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ExecutionActivationReceiptV0
from tev_script.semantic_discovery_realization_v0 import (
    DiscoveryClaimV0,
    DiscoveryRealizationCycleV0,
    StructuralLawClaimV0,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_observation_v0 import (
    ExecutionObservationIssueV0,
    ExecutionObservationReceiptV0,
)
from tev_script.semantic_grounded_discovery_v0 import (
    ExecutionGroundedDiscoveryCycleV0,
    evaluate_execution_grounded_discovery_cycle,
    residual_from_execution_grounded_discovery,
)
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class ExecutionGroundedDiscoveryV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.assumption = h("law-assumption")
        self.regime = h("regime")
        self.transformation = h("transformation")
        self.boundary = h("boundary")
        self.source_law = StructuralLawClaimV0(
            "law.source",
            self.regime,
            self.transformation,
            self.boundary,
            h("falsifier-source"),
            EvidencePolicyV0(()).policy_hash,
            assumption_hashes=(self.assumption,),
        )
        self.rediscovered_law = StructuralLawClaimV0(
            "law.rediscovered",
            self.regime,
            self.transformation,
            self.boundary,
            h("falsifier-rediscovered"),
            EvidencePolicyV0(()).policy_hash,
            assumption_hashes=(self.assumption,),
        )
        self.realization_receipt = RealizationAdmissionReceiptV0(
            problem_hash=h("problem"),
            candidate_hash=h("candidate"),
            realization_hash=h("realization"),
            semantic_claim_hash=h("semantic-claim"),
            artifact_manifest_hash=h("manifest"),
            transformation_semantic_hash=self.transformation,
            transformation_regime_binding_hash=self.source_law.expected_realization_binding_hash,
            semantic_relation="EXACT_EQUIVALENT",
            regime_preservation_claim_hash=h("preservation"),
            resource_estimate_claim_hash=h("resource-estimate"),
            machine_hash=h("machine"),
            policy_hash=h("realization-policy"),
            regime_hash=self.regime,
            resource_catalog_hash=h("resource-catalog"),
            machine_compatibility_hash=h("machine-eval"),
            regime_evaluation_hash=h("regime-eval"),
            realization_evidence_evaluation_hash=h("realization-evidence"),
            regime_evidence_evaluation_hash=h("regime-evidence"),
            resource_evidence_evaluation_hash=h("resource-evidence"),
            issues=(),
        )
        self.activation = ExecutionActivationReceiptV0(
            h("activation-candidate"),
            h("activation-record"),
            self.realization_receipt.receipt_hash,
            self.realization_receipt.realization_hash,
            h("placement-evaluation"),
            h("machine-instance"),
            h("placement-context"),
            h("runtime-evaluation"),
            h("runtime-claim"),
            h("execution-context"),
            (),
        )
        self.observed_history = h("observed-history")
        self.observation = ExecutionObservationReceiptV0(
            h("observation-claim"),
            h("observation-record"),
            self.activation.receipt_hash,
            self.activation.execution_context_hash,
            self.observed_history,
            h("observation-evidence-evaluation"),
            (),
        )
        self.discovery_scope = h("discovery-scope")
        self.discovery_verifier = h("discovery-verifier")
        self.discovery_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "rediscovery",
                    ("EXHAUSTIVE",),
                    scope_hash=self.discovery_scope,
                    trusted_verifier_hashes=(self.discovery_verifier,),
                ),
            )
        )
        self.discovery_claim = DiscoveryClaimV0(
            h("experience-space"),
            h("observations"),
            h("interventions"),
            self.rediscovered_law.law_semantic_hash,
            h("discovery-context"),
            self.rediscovered_law.validity_boundary_hash,
            self.discovery_policy.policy_hash,
            assumption_hashes=self.rediscovered_law.assumption_hashes,
        )
        self.discovery_evidence = EvidenceItemV0(
            "e.rediscovery",
            self.discovery_claim.discovery_claim_hash,
            self.discovery_scope,
            "EXHAUSTIVE",
            verifier_hash=self.discovery_verifier,
            witness_hash=h("rediscovery-witness"),
            assumption_hashes=self.rediscovered_law.assumption_hashes,
        )
        self.epistemic_cycle = DiscoveryRealizationCycleV0(
            self.source_law.law_semantic_hash,
            self.realization_receipt.receipt_hash,
            self.observed_history,
            self.discovery_claim.discovery_claim_hash,
            self.rediscovered_law.law_semantic_hash,
        )
        self.grounded_cycle = ExecutionGroundedDiscoveryCycleV0(
            self.epistemic_cycle.cycle_hash,
            self.activation.receipt_hash,
            self.observation.receipt_hash,
        )

    def evaluate(self, grounded=None, **overrides):
        args = {
            "epistemic_cycle": self.epistemic_cycle,
            "source_law": self.source_law,
            "realization_receipt": self.realization_receipt,
            "activation_receipt": self.activation,
            "execution_observation_receipt": self.observation,
            "rediscovered_law": self.rediscovered_law,
            "rediscovery_claim": self.discovery_claim,
            "discovery_evidence_policy": self.discovery_policy,
            "evidence": (self.discovery_evidence,),
        }
        args.update(overrides)
        return evaluate_execution_grounded_discovery_cycle(
            grounded or self.grounded_cycle,
            **args,
        )

    def test_same_law_physical_round_trip_closes_only_through_receipt_chain(self):
        evaluation = self.evaluate()
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(evaluation.observed_history_hash, self.observation.observed_history_hash)
        self.assertEqual(parse_residual(residual_from_execution_grounded_discovery(evaluation)).status, "CLOSED")

    def test_arbitrary_history_cannot_be_injected_into_grounded_cycle(self):
        forged_epistemic = DiscoveryRealizationCycleV0(
            self.source_law.law_semantic_hash,
            self.realization_receipt.receipt_hash,
            h("forged-history"),
            self.discovery_claim.discovery_claim_hash,
            self.rediscovered_law.law_semantic_hash,
        )
        grounded = ExecutionGroundedDiscoveryCycleV0(
            forged_epistemic.cycle_hash,
            self.activation.receipt_hash,
            self.observation.receipt_hash,
        )
        evaluation = self.evaluate(grounded, epistemic_cycle=forged_epistemic)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("grounded.observed_history_mismatch", {item.kind for item in evaluation.issues})

    def test_observation_from_other_activation_rejects(self):
        other = ExecutionObservationReceiptV0(
            h("other-observation-claim"),
            h("other-observation-record"),
            h("other-activation"),
            self.activation.execution_context_hash,
            self.observed_history,
            h("observation-evidence-evaluation"),
            (),
        )
        grounded = ExecutionGroundedDiscoveryCycleV0(
            self.epistemic_cycle.cycle_hash,
            self.activation.receipt_hash,
            other.receipt_hash,
        )
        evaluation = self.evaluate(
            grounded,
            execution_observation_receipt=other,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("grounded.observation_activation_mismatch", {item.kind for item in evaluation.issues})

    def test_activation_from_other_realization_receipt_rejects(self):
        other_activation = ExecutionActivationReceiptV0(
            h("other-activation-candidate"),
            h("other-activation-record"),
            h("other-realization-receipt"),
            self.realization_receipt.realization_hash,
            h("placement-evaluation"),
            h("machine-instance"),
            h("placement-context"),
            h("runtime-evaluation"),
            h("runtime-claim"),
            self.activation.execution_context_hash,
            (),
        )
        observation = ExecutionObservationReceiptV0(
            h("observation-claim-other-activation"),
            h("observation-record-other-activation"),
            other_activation.receipt_hash,
            other_activation.execution_context_hash,
            self.observed_history,
            h("observation-evidence-evaluation"),
            (),
        )
        grounded = ExecutionGroundedDiscoveryCycleV0(
            self.epistemic_cycle.cycle_hash,
            other_activation.receipt_hash,
            observation.receipt_hash,
        )
        evaluation = self.evaluate(
            grounded,
            activation_receipt=other_activation,
            execution_observation_receipt=observation,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("grounded.activation_realization_receipt_mismatch", {item.kind for item in evaluation.issues})

    def test_open_execution_observation_propagates_proof_required(self):
        open_observation = ExecutionObservationReceiptV0(
            h("open-observation-claim"),
            h("open-observation-record"),
            self.activation.receipt_hash,
            self.activation.execution_context_hash,
            self.observed_history,
            h("observation-evidence-evaluation"),
            (
                ExecutionObservationIssueV0(
                    "observation.trace_required",
                    "PROOF_REQUIRED",
                    h("trace-obligation"),
                    {},
                ),
            ),
        )
        grounded = ExecutionGroundedDiscoveryCycleV0(
            self.epistemic_cycle.cycle_hash,
            self.activation.receipt_hash,
            open_observation.receipt_hash,
        )
        evaluation = self.evaluate(
            grounded,
            execution_observation_receipt=open_observation,
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("grounded.execution_observation_not_admitted", {item.kind for item in evaluation.issues})

    def test_rejected_observation_propagates_reject(self):
        rejected = ExecutionObservationReceiptV0(
            h("rejected-observation-claim"),
            h("rejected-observation-record"),
            self.activation.receipt_hash,
            self.activation.execution_context_hash,
            self.observed_history,
            h("observation-evidence-evaluation"),
            (
                ExecutionObservationIssueV0(
                    "observation.history_mismatch",
                    "REJECT",
                    h("history"),
                    {},
                ),
            ),
        )
        grounded = ExecutionGroundedDiscoveryCycleV0(
            self.epistemic_cycle.cycle_hash,
            self.activation.receipt_hash,
            rejected.receipt_hash,
        )
        evaluation = self.evaluate(grounded, execution_observation_receipt=rejected)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("grounded.execution_observation_not_admitted", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
