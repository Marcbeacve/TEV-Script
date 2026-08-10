from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_realization_composition_v0 import (
    RealizationCompositionClaimV0,
    RealizationCompositionPolicyV0,
    RealizationCompositionRecordV0,
    evaluate_realization_composition,
    residual_from_realization_composition,
)
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0, RealizationIssueV0
from tev_script.semantic_regime_v0 import TransformationRegimeBindingV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def receipt(label: str, *, rejected: bool = False) -> RealizationAdmissionReceiptV0:
    issues = (
        (RealizationIssueV0("component.failure", "REJECT", h(label + ".failure"), {}),)
        if rejected
        else ()
    )
    return RealizationAdmissionReceiptV0(
        problem_hash=h(label + ".problem"),
        candidate_hash=h(label + ".candidate"),
        realization_hash=h(label + ".realization"),
        semantic_claim_hash=h(label + ".claim"),
        artifact_manifest_hash=h(label + ".manifest"),
        transformation_semantic_hash=h(label + ".transformation"),
        transformation_regime_binding_hash=h(label + ".binding"),
        semantic_relation="EXACT_EQUIVALENT",
        regime_preservation_claim_hash=h(label + ".preservation"),
        resource_estimate_claim_hash=h(label + ".resource-estimate"),
        machine_hash=h(label + ".machine"),
        policy_hash=h(label + ".policy"),
        regime_hash=h(label + ".regime"),
        resource_catalog_hash=h(label + ".resource-catalog"),
        machine_compatibility_hash=h(label + ".machine-eval"),
        regime_evaluation_hash=h(label + ".regime-eval"),
        realization_evidence_evaluation_hash=h(label + ".realization-evidence"),
        regime_evidence_evaluation_hash=h(label + ".regime-evidence"),
        resource_evidence_evaluation_hash=h(label + ".resource-evidence"),
        issues=issues,
    )


class RealizationCompositionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.left = receipt("left")
        self.right = receipt("right")
        self.scope = h("composition-scope")
        self.verifier = h("composition-verifier")
        self.assumption = h("composition-assumption")
        self.target_binding = TransformationRegimeBindingV0(
            h("target-transformation"),
            h("target-regime"),
            self.scope,
        )
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "composition-proof",
                    ("PROOF",),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = RealizationCompositionPolicyV0(
            self.evidence_policy.policy_hash,
            accepted_assumption_hashes=(self.assumption,),
        )
        self.claim = RealizationCompositionClaimV0(
            self.target_binding.transformation_semantic_hash,
            self.target_binding.binding_hash,
            (self.left.receipt_hash, self.right.receipt_hash),
            h("composition-relation"),
            self.scope,
            assumption_hashes=(self.assumption,),
        )

    def evidence(self, claim=None, *, status="ACTIVE", assumptions=None):
        claim = claim or self.claim
        return EvidenceItemV0(
            "e.composition." + status.lower(),
            claim.composition_claim_hash,
            self.scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("composition-witness-" + status.lower()),
            assumption_hashes=(self.assumption,) if assumptions is None else tuple(assumptions),
            status=status,
        )

    def record(self, claim=None, evidence_hashes=()):
        return RealizationCompositionRecordV0(
            claim or self.claim,
            self.evidence_policy.policy_hash,
            tuple(evidence_hashes),
            provenance={"producer": "test"},
        )

    def evaluate(self, record, evidence=(), receipts=None, policy=None, target_binding=None):
        return evaluate_realization_composition(
            record,
            target_binding=target_binding or self.target_binding,
            policy=policy or self.policy,
            evidence_policy=self.evidence_policy,
            component_receipts=(self.left, self.right) if receipts is None else receipts,
            evidence=evidence,
        )

    def test_pass_components_do_not_imply_pass_composition(self):
        evaluation = self.evaluate(self.record())
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("composition.evidence.required", {x.kind for x in evaluation.issues})
        self.assertEqual(parse_residual(residual_from_realization_composition(evaluation)).status, "OPEN")

    def test_composition_closes_only_with_bound_evidence(self):
        evidence = self.evidence()
        evaluation = self.evaluate(self.record(evidence_hashes=(evidence.evidence_hash,)), (evidence,))
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(parse_residual(residual_from_realization_composition(evaluation)).status, "CLOSED")

    def test_target_binding_is_not_a_free_hash(self):
        evidence = self.evidence()
        wrong_binding = TransformationRegimeBindingV0(
            self.target_binding.transformation_semantic_hash,
            h("other-regime"),
            self.scope,
        )
        evaluation = self.evaluate(
            self.record(evidence_hashes=(evidence.evidence_hash,)),
            (evidence,),
            target_binding=wrong_binding,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.target_binding_mismatch", {x.kind for x in evaluation.issues})

    def test_scope_widening_rejects_even_with_valid_proof_for_narrow_scope(self):
        evidence = self.evidence()
        wider = TransformationRegimeBindingV0(
            self.target_binding.transformation_semantic_hash,
            self.target_binding.regime_hash,
            h("wider-scope"),
        )
        evaluation = self.evaluate(
            self.record(evidence_hashes=(evidence.evidence_hash,)),
            (evidence,),
            target_binding=wider,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.target_scope_mismatch", {x.kind for x in evaluation.issues})

    def test_non_admitted_component_rejects_even_with_composition_proof(self):
        bad = receipt("bad", rejected=True)
        claim = RealizationCompositionClaimV0(
            self.target_binding.transformation_semantic_hash,
            self.target_binding.binding_hash,
            (self.left.receipt_hash, bad.receipt_hash),
            h("composition-relation"),
            self.scope,
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        record = self.record(claim, (evidence.evidence_hash,))
        evaluation = self.evaluate(record, (evidence,), receipts=(self.left, bad))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.component_not_admitted", {x.kind for x in evaluation.issues})

    def test_component_receipt_multiset_is_exact(self):
        evidence = self.evidence()
        evaluation = self.evaluate(
            self.record(evidence_hashes=(evidence.evidence_hash,)),
            (evidence,),
            receipts=(self.left,),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.component_receipt_set_mismatch", {x.kind for x in evaluation.issues})

    def test_duplicate_component_use_preserves_multiplicity(self):
        claim = RealizationCompositionClaimV0(
            self.target_binding.transformation_semantic_hash,
            self.target_binding.binding_hash,
            (self.left.receipt_hash, self.left.receipt_hash),
            h("composition-relation-duplicate"),
            self.scope,
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        evaluation = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            receipts=(self.left, self.left),
        )
        self.assertEqual(evaluation.status, "PASS")

    def test_positive_support_must_be_record_bound(self):
        evidence = self.evidence()
        evaluation = self.evaluate(self.record(), (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.evidence_unbound_support", {x.kind for x in evaluation.issues})

    def test_composition_assumption_is_policy_governed(self):
        evidence = self.evidence()
        strict = RealizationCompositionPolicyV0(self.evidence_policy.policy_hash, ())
        evaluation = self.evaluate(
            self.record(evidence_hashes=(evidence.evidence_hash,)),
            (evidence,),
            policy=strict,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.assumption_not_accepted", {x.kind for x in evaluation.issues})

    def test_falsified_composition_claim_rejects_even_if_proof_exists(self):
        good = self.evidence()
        falsified = EvidenceItemV0(
            "e.composition.counterexample",
            self.claim.composition_claim_hash,
            h("counterexample-scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("composition-counterexample"),
            status="FALSIFIED",
        )
        evaluation = self.evaluate(
            self.record(evidence_hashes=(good.evidence_hash,)),
            (good, falsified),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.evidence.falsified", {x.kind for x in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
