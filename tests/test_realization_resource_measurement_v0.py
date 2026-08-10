from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_resource_algebra_v0 import (
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceDimensionV0,
    ResourceVectorV0,
)
from tev_script.semantic_resource_measurement_v0 import (
    ResourceMeasurementClaimV0,
    ResourceMeasurementPolicyV0,
    ResourceMeasurementRecordV0,
    evaluate_resource_measurement,
    residual_from_resource_measurement,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def activation(*, issues=()) -> ExecutionActivationReceiptV0:
    return ExecutionActivationReceiptV0(
        h("activation-candidate"),
        h("activation-record"),
        h("realization-receipt"),
        h("realization"),
        h("placement-evaluation"),
        h("machine-instance"),
        h("placement-context"),
        h("runtime-evaluation"),
        h("runtime-claim"),
        h("execution-context"),
        tuple(issues),
    )


class ResourceMeasurementV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation()
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
            )
        )
        self.vector = ResourceVectorV0(
            (
                ResourceBoundV0.exact("latency", 7),
                ResourceBoundV0.exact("energy", 3),
            ),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        self.assumption = h("measurement-assumption")
        self.scope = h("measurement-scope")
        self.verifier = h("measurement-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "measurement",
                    ("ATTESTATION", "EMPIRICAL_OBSERVATION"),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = ResourceMeasurementPolicyV0(
            self.evidence_policy.policy_hash,
            accepted_assumption_hashes=(self.assumption,),
        )

    def claim(self, *, epoch="epoch-a", vector=None) -> ResourceMeasurementClaimV0:
        vector = vector or self.vector
        return ResourceMeasurementClaimV0(
            self.activation.receipt_hash,
            self.activation.realization_hash,
            self.activation.execution_context_hash,
            self.catalog.catalog_hash,
            vector.vector_hash,
            h(epoch),
            assumption_hashes=(self.assumption,),
        )

    def evidence(self, claim, *, evidence_id="e.measurement", status="ACTIVE") -> EvidenceItemV0:
        return EvidenceItemV0(
            evidence_id,
            claim.measurement_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("measurement-witness"),
            assumption_hashes=(self.assumption,),
            status=status,
        )

    def record(self, claim, evidence_hashes=(), *, observer="observer-a", detail=None):
        return ResourceMeasurementRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            tuple(evidence_hashes),
            observer_hash=h(observer),
            detail={} if detail is None else detail,
        )

    def evaluate(self, record, evidence=(), **overrides):
        args = {
            "activation_receipt": self.activation,
            "observed_resources": self.vector,
            "resource_catalog": self.catalog,
            "policy": self.policy,
            "evidence_policy": self.evidence_policy,
            "evidence": tuple(evidence),
        }
        args.update(overrides)
        return evaluate_resource_measurement(record, **args)

    def test_execution_bound_evidenced_measurement_passes(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        evaluation = self.evaluate(self.record(claim, (evidence.evidence_hash,)), (evidence,))
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(parse_residual(residual_from_resource_measurement(evaluation)).status, "CLOSED")

    def test_observer_and_detail_are_record_not_measurement_claim(self):
        claim = self.claim()
        left = self.record(claim, observer="observer-a", detail={"sensor": "a"})
        right = self.record(claim, observer="observer-b", detail={"sensor": "b"})
        self.assertEqual(left.claim.measurement_claim_hash, right.claim.measurement_claim_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_epoch_is_part_of_measurement_claim(self):
        self.assertNotEqual(self.claim(epoch="epoch-a").measurement_claim_hash, self.claim(epoch="epoch-b").measurement_claim_hash)

    def test_measurement_from_other_execution_context_rejects(self):
        claim = ResourceMeasurementClaimV0(
            self.activation.receipt_hash,
            self.activation.realization_hash,
            h("other-execution-context"),
            self.catalog.catalog_hash,
            self.vector.vector_hash,
            h("epoch"),
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        evaluation = self.evaluate(self.record(claim, (evidence.evidence_hash,)), (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("measurement.execution_context_mismatch", {item.kind for item in evaluation.issues})

    def test_resource_vector_and_catalog_are_exactly_bound(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        other_vector = ResourceVectorV0(
            (
                ResourceBoundV0.exact("latency", 8),
                ResourceBoundV0.exact("energy", 3),
            ),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        evaluation = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            observed_resources=other_vector,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("measurement.resource_vector_mismatch", {item.kind for item in evaluation.issues})

    def test_revocation_keeps_measurement_binding_but_reopens(self):
        claim = self.claim()
        active = self.evidence(claim, evidence_id="e.active", status="ACTIVE")
        revoked = self.evidence(claim, evidence_id="e.revoked", status="REVOKED")
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        record = self.record(claim, (active.evidence_hash,))
        self.assertEqual(self.evaluate(record, (active,)).status, "PASS")
        reopened = self.evaluate(record, (revoked,))
        self.assertEqual(reopened.status, "PROOF_REQUIRED")
        self.assertIn("measurement.evidence.inactive", {item.kind for item in reopened.issues})

    def test_positive_measurement_support_must_be_record_bound(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        evaluation = self.evaluate(self.record(claim), (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("measurement.evidence_unbound_support", {item.kind for item in evaluation.issues})

    def test_non_pass_activation_cannot_authorize_measurement(self):
        open_activation = activation(
            issues=(ActivationIssueV0("activation.runtime_state_not_admitted", "PROOF_REQUIRED", h("runtime"), {}),)
        )
        claim = ResourceMeasurementClaimV0(
            open_activation.receipt_hash,
            open_activation.realization_hash,
            open_activation.execution_context_hash,
            self.catalog.catalog_hash,
            self.vector.vector_hash,
            h("epoch"),
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        evaluation = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            activation_receipt=open_activation,
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("measurement.activation_not_admitted", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
