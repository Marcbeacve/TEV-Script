from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
)
from tev_script.semantic_realization_composition_v0 import (
    RealizationCompositionClaimV0,
    RealizationCompositionPolicyV0,
    RealizationCompositionRecordV0,
    evaluate_realization_composition,
    residual_from_realization_composition,
)
from tev_script.semantic_realization_v0 import (
    RealizationAdmissionReceiptV0,
    RealizationIssueV0,
)
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
    def setUp(self):
        self.left = receipt("left")
        self.right = receipt("right")
        self.scope = h("composition-scope")
        self.verifier = h("composition-verifier")
        self.assumption = h("composition-assumption")
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
            h("target-transformation"),
            h("target-binding"),
            (self.left.receipt_hash, self.right.receipt_hash),
            h("composition-relation"),
            self.scope,
            assumption_hashes=(self.assumption,),
        )

    def evidence(self, *, status="ACTIVE", assumptions=None):
        return EvidenceItemV0(
            "e.composition." + status.lower(),
            self.claim.composition_claim_hash,
            self.scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("composition-witness-" + status.lower()),
            assumption_hashes=(
                (self.assumption,) if assumptions is None else tuple(assumptions)
            ),
            status=status,
        )

    def record(self, evidence_hashes=()):
        return RealizationCompositionRecordV0(
            self.claim,
            self.evidence_policy.policy_hash,
            tuple(evidence_hashes),
            provenance={"producer": "test"},
        )

    def evaluate(self, record, evidence=(), receipts=None, policy=None):
        return evaluate_realization_composition(
            record,
            policy=policy or self.policy,
            evidence_policy=self.evidence_policy,
            component_receipts=(self.left, self.right) if receipts is None else receipts,
            evidence=evidence,
        )

    def test_pass_components_do_not_imply_pass_composition(self):
        evaluation = self.evaluate(self.record())
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("composition.evidence.required", {x.kind for x in evaluation.issues})
        self.assertEqual(
            parse_residual(residual_from_realization_composition(evaluation)).status,
            "OPEN",
        )

    def test_composition_closes_only_with_bound_evidence(self):
        evidence = self.evidence()
        evaluation = self.evaluate(self.record((evidence.evidence_hash,)), (evidence,))
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(
            parse_residual(residual_from_realization_composition(evaluation)).status,
            "CLOSED",
        )

    def test_non_admitted_component_rejects_composition_even_with_proof(self):
        bad = receipt("bad", rejected=True)
        claim = RealizationCompositionClaimV0(
            h("target-transformation"),
            h("target-binding"),
            (self.left.receipt_hash, bad.receipt_hash),
            h("composition-relation"),
            self.scope,
            assumption_hashes=(self.assumption,),
        )
        evidence = EvidenceItemV0(
            "e.composition.bad",
            claim.composition_claim_hash,
            self.scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("bad-proof"),
            assumption_hashes=(self.assumption,),
        )
        record = RealizationCompositionRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        evaluation = evaluate_realization_composition(
            record,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            component_receipts=(self.left, bad),
            evidence=(evidence,),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.component_not_admitted", {x.kind for x in evaluation.issues})

    def test_component_receipt_multiset_is_exact(self):
        evidence = self.evidence()
        evaluation = self.evaluate(
            self.record((evidence.evidence_hash,)),
            (evidence,),
            receipts=(self.left,),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn(
            "composition.component_receipt_set_mismatch",
            {x.kind for x in evaluation.issues},
        )

    def test_duplicate_component_use_preserves_multiplicity(self):
        claim = RealizationCompositionClaimV0(
            h("target-transformation"),
            h("target-binding"),
            (self.left.receipt_hash, self.left.receipt_hash),
            h("composition-relation-duplicate"),
            self.scope,
            assumption_hashes=(self.assumption,),
        )
        evidence = EvidenceItemV0(
            "e.composition.duplicate",
            claim.composition_claim_hash,
            self.scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("duplicate-proof"),
            assumption_hashes=(self.assumption,),
        )
        record = RealizationCompositionRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        evaluation = evaluate_realization_composition(
            record,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            component_receipts=(self.left, self.left),
            evidence=(evidence,),
        )
        self.assertEqual(evaluation.status, "PASS")

    def test_positive_composition_support_must_be_record_bound(self):
        evidence = self.evidence()
        evaluation = self.evaluate(self.record(), (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn(
            "composition.evidence_unbound_support",
            {x.kind for x in evaluation.issues},
        )

    def test_composition_assumption_is_policy_governed(self):
        evidence = self.evidence()
        strict_policy = RealizationCompositionPolicyV0(self.evidence_policy.policy_hash, ())
        evaluation = self.evaluate(
            self.record((evidence.evidence_hash,)),
            (evidence,),
            policy=strict_policy,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn(
            "composition.assumption_not_accepted",
            {x.kind for x in evaluation.issues},
        )

    def test_falsified_composition_claim_rejects_even_if_other_proof_exists(self):
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
            self.record((good.evidence_hash,)),
            (good, falsified),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("composition.evidence.falsified", {x.kind for x in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
