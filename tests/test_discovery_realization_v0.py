from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_discovery_realization_v0 import (
    DiscoveryClaimV0,
    DiscoveryRealizationCycleV0,
    DiscoveryRealizationError,
    LawEquivalenceClaimV0,
    ModelCompatibilityClaimV0,
    StructuralLawClaimV0,
    evaluate_discovery_realization_cycle,
    residual_from_discovery_realization_cycle,
)
from tev_script.semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
)
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0, RealizationIssueV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class StructuralLawIdentityV0Tests(unittest.TestCase):
    def _law(
        self,
        law_id: str,
        *,
        regime=None,
        transformation=None,
        boundary=None,
        assumption=None,
        falsifier=None,
        formulation=None,
        provenance=None,
    ):
        return StructuralLawClaimV0(
            law_id,
            regime or h("regime"),
            transformation or h("transformation"),
            boundary or h("boundary"),
            falsifier or h("falsifiers"),
            EvidencePolicyV0(()).policy_hash,
            assumption_hashes=(assumption or h("assumption"),),
            formulation_hash=formulation or h("formulation-" + law_id),
            provenance=provenance or {"source": law_id},
        )

    def test_notation_provenance_and_falsification_profile_do_not_define_law_semantics(self):
        left = self._law(
            "law.alpha",
            falsifier=h("falsifier-a"),
            formulation=h("text-a"),
            provenance={"notation": "a"},
        )
        right = self._law(
            "law.beta",
            falsifier=h("falsifier-b"),
            formulation=h("text-b"),
            provenance={"notation": "b"},
        )
        self.assertEqual(left.law_semantic_hash, right.law_semantic_hash)
        self.assertNotEqual(left.law_claim_hash, right.law_claim_hash)

    def test_transformation_validity_boundary_regime_and_assumptions_are_semantic(self):
        base = self._law("law.base")
        variants = (
            self._law("law.t", transformation=h("other-transformation")),
            self._law("law.b", boundary=h("other-boundary")),
            self._law("law.r", regime=h("other-regime")),
            self._law("law.a", assumption=h("other-assumption")),
        )
        self.assertTrue(all(base.law_semantic_hash != item.law_semantic_hash for item in variants))

    def test_law_realization_scope_binds_boundary_and_assumptions(self):
        base = self._law("law.base")
        other_boundary = self._law("law.boundary", boundary=h("other-boundary"))
        other_assumption = self._law("law.assumption", assumption=h("other-assumption"))
        self.assertNotEqual(base.law_realization_scope_hash, other_boundary.law_realization_scope_hash)
        self.assertNotEqual(base.law_realization_scope_hash, other_assumption.law_realization_scope_hash)
        self.assertNotEqual(
            base.expected_realization_binding_hash,
            other_boundary.expected_realization_binding_hash,
        )

    def test_distinct_concrete_structures_need_explicit_equivalence_claim(self):
        left = self._law("law.left")
        right = self._law("law.right", transformation=h("isomorphic-recoding"))
        policy = EvidencePolicyV0(())
        claim = LawEquivalenceClaimV0(
            left.law_semantic_hash,
            right.law_semantic_hash,
            h("isomorphism-relation"),
            h("law-scope"),
            policy.policy_hash,
        )
        reverse = LawEquivalenceClaimV0(
            right.law_semantic_hash,
            left.law_semantic_hash,
            h("isomorphism-relation"),
            h("law-scope"),
            policy.policy_hash,
        )
        self.assertEqual(claim.equivalence_claim_hash, reverse.equivalence_claim_hash)
        self.assertEqual(claim.law_pair, reverse.law_pair)

    def test_equivalence_claim_is_not_used_for_identical_semantic_hashes(self):
        law = self._law("law.same")
        with self.assertRaises(DiscoveryRealizationError):
            LawEquivalenceClaimV0(
                law.law_semantic_hash,
                law.law_semantic_hash,
                h("eq"),
                h("scope"),
                EvidencePolicyV0(()).policy_hash,
            )

    def test_model_compatibility_remains_a_separate_claim(self):
        law = self._law("law.model")
        claim = ModelCompatibilityClaimV0(
            law.law_semantic_hash,
            h("generated-model"),
            law.regime_hash,
            law.validity_boundary_hash,
            h("satisfies-relation"),
            EvidencePolicyV0(()).policy_hash,
            assumption_hashes=law.assumption_hashes,
        )
        self.assertEqual(len(claim.compatibility_claim_hash), 64)


class DiscoveryRealizationCycleV0Tests(unittest.TestCase):
    def _discovery_policy(self):
        return EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "rediscovery",
                    ("EXHAUSTIVE",),
                    scope_hash=h("discovery-scope"),
                    trusted_verifier_hashes=(h("discovery-verifier"),),
                ),
            )
        )

    def _equivalence_policy(self):
        return EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "law-equivalence",
                    ("PROOF",),
                    scope_hash=h("equivalence-scope"),
                    trusted_verifier_hashes=(h("equivalence-verifier"),),
                ),
            )
        )

    def _law(
        self,
        *,
        law_id="law.cycle",
        transformation=None,
        regime=None,
        boundary=None,
        assumption=None,
    ):
        return StructuralLawClaimV0(
            law_id,
            regime or h("cycle-regime"),
            transformation or h("cycle-transformation"),
            boundary or h("boundary"),
            h("falsifiers-" + law_id),
            EvidencePolicyV0(()).policy_hash,
            assumption_hashes=(assumption or h("assumption"),),
        )

    def _receipt(
        self,
        law: StructuralLawClaimV0,
        *,
        issues=(),
        transformation=None,
        regime=None,
        binding=None,
    ):
        return RealizationAdmissionReceiptV0(
            h("problem"),
            h("candidate"),
            h("realization"),
            h("semantic-claim"),
            transformation or law.transformation_semantic_hash,
            binding or law.expected_realization_binding_hash,
            "EXACT_EQUIVALENT",
            h("preservation-claim"),
            h("resource-estimate-claim"),
            h("machine"),
            h("policy"),
            regime or law.regime_hash,
            h("resource-catalog"),
            h("machine-compatibility"),
            h("regime-evaluation"),
            h("semantic-evidence-evaluation"),
            h("regime-evidence-evaluation"),
            h("resource-evidence-evaluation"),
            tuple(issues),
        )

    def _discovery_claim(
        self,
        law: StructuralLawClaimV0,
        *,
        boundary=None,
        assumptions=None,
        candidate_hash=None,
    ):
        policy = self._discovery_policy()
        return DiscoveryClaimV0(
            h("experience-space"),
            h("observations"),
            h("interventions"),
            candidate_hash or law.law_semantic_hash,
            h("discovery-context"),
            boundary or law.validity_boundary_hash,
            policy.policy_hash,
            assumption_hashes=(
                law.assumption_hashes if assumptions is None else tuple(assumptions)
            ),
        )

    def _discovery_evidence(self, claim: DiscoveryClaimV0, *, status="ACTIVE"):
        return EvidenceItemV0(
            "e.rediscovery." + status.lower(),
            claim.discovery_claim_hash,
            h("discovery-scope"),
            "EXHAUSTIVE",
            verifier_hash=h("discovery-verifier"),
            witness_hash=h("rediscovery-witness-" + status.lower()),
            status=status,
        )

    def _cycle(self, source_law, receipt, claim, rediscovered_law, *, equivalence_hash=""):
        return DiscoveryRealizationCycleV0(
            source_law.law_semantic_hash,
            receipt.receipt_hash,
            h("observed-history"),
            claim.discovery_claim_hash,
            rediscovered_law.law_semantic_hash,
            equivalence_hash,
        )

    def _evaluate(
        self,
        cycle,
        source_law,
        receipt,
        rediscovered_law,
        claim,
        evidence,
        **kwargs,
    ):
        return evaluate_discovery_realization_cycle(
            cycle,
            source_law=source_law,
            realization_receipt=receipt,
            rediscovered_law=rediscovered_law,
            rediscovery_claim=claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=evidence,
            **kwargs,
        )

    def test_same_law_round_trip_passes_only_with_admitted_scoped_realization_and_evidence(self):
        law = self._law()
        receipt = self._receipt(law)
        claim = self._discovery_claim(law)
        cycle = self._cycle(law, receipt, claim, law)
        evaluation = self._evaluate(
            cycle,
            law,
            receipt,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(
            parse_residual(residual_from_discovery_realization_cycle(evaluation)).status,
            "CLOSED",
        )

    def test_non_pass_realization_cannot_enter_successful_round_trip(self):
        law = self._law()
        receipt = self._receipt(
            law,
            issues=(RealizationIssueV0("machine.operation_missing", "REJECT", h("op"), {}),),
        )
        claim = self._discovery_claim(law)
        evaluation = self._evaluate(
            self._cycle(law, receipt, claim, law),
            law,
            receipt,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("cycle.realization_not_admitted", {item.kind for item in evaluation.issues})

    def test_realization_must_match_source_law_transformation_regime_and_scope(self):
        law = self._law()
        claim = self._discovery_claim(law)

        wrong_t = self._receipt(law, transformation=h("other-transformation"))
        evaluation = self._evaluate(
            self._cycle(law, wrong_t, claim, law),
            law,
            wrong_t,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertIn("cycle.realization_transformation_mismatch", {item.kind for item in evaluation.issues})

        wrong_r = self._receipt(law, regime=h("other-regime"))
        evaluation = self._evaluate(
            self._cycle(law, wrong_r, claim, law),
            law,
            wrong_r,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertIn("cycle.realization_regime_mismatch", {item.kind for item in evaluation.issues})

        wrong_scope = self._receipt(law, binding=h("wrong-binding"))
        evaluation = self._evaluate(
            self._cycle(law, wrong_scope, claim, law),
            law,
            wrong_scope,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertIn("cycle.realization_scope_mismatch", {item.kind for item in evaluation.issues})

    def test_rediscovery_claim_must_match_rediscovered_law_boundary_and_assumptions(self):
        law = self._law()
        receipt = self._receipt(law)

        bad_boundary = self._discovery_claim(law, boundary=h("wrong-boundary"))
        evaluation = self._evaluate(
            self._cycle(law, receipt, bad_boundary, law),
            law,
            receipt,
            law,
            bad_boundary,
            (self._discovery_evidence(bad_boundary),),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("cycle.rediscovery_boundary_mismatch", {item.kind for item in evaluation.issues})

        bad_assumptions = self._discovery_claim(law, assumptions=(h("wrong-assumption"),))
        evaluation = self._evaluate(
            self._cycle(law, receipt, bad_assumptions, law),
            law,
            receipt,
            law,
            bad_assumptions,
            (self._discovery_evidence(bad_assumptions),),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("cycle.rediscovery_assumption_mismatch", {item.kind for item in evaluation.issues})

    def test_rediscovery_claim_cannot_label_a_different_law_hash(self):
        law = self._law()
        receipt = self._receipt(law)
        claim = self._discovery_claim(law, candidate_hash=h("different-law"))
        cycle = DiscoveryRealizationCycleV0(
            law.law_semantic_hash,
            receipt.receipt_hash,
            h("observed-history"),
            claim.discovery_claim_hash,
            law.law_semantic_hash,
        )
        evaluation = self._evaluate(
            cycle,
            law,
            receipt,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("cycle.rediscovery_claim_law_mismatch", {item.kind for item in evaluation.issues})

    def test_different_concrete_law_stays_open_without_equivalence_claim(self):
        source = self._law(law_id="law.source")
        rediscovered = self._law(
            law_id="law.recoded",
            transformation=h("law-recoded-transformation"),
        )
        receipt = self._receipt(source)
        claim = self._discovery_claim(rediscovered)
        evaluation = self._evaluate(
            self._cycle(source, receipt, claim, rediscovered),
            source,
            receipt,
            rediscovered,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("cycle.law_equivalence_required", {item.kind for item in evaluation.issues})

    def test_isomorphic_recode_needs_explicit_equivalence_evidence(self):
        source = self._law(law_id="law.source")
        rediscovered = self._law(
            law_id="law.recoded",
            transformation=h("law-recoded-transformation"),
        )
        receipt = self._receipt(source)
        claim = self._discovery_claim(rediscovered)
        eq_policy = self._equivalence_policy()
        eq_claim = LawEquivalenceClaimV0(
            source.law_semantic_hash,
            rediscovered.law_semantic_hash,
            h("isomorphism"),
            h("equivalence-scope"),
            eq_policy.policy_hash,
        )
        cycle = self._cycle(
            source,
            receipt,
            claim,
            rediscovered,
            equivalence_hash=eq_claim.equivalence_claim_hash,
        )

        without_eq_evidence = self._evaluate(
            cycle,
            source,
            receipt,
            rediscovered,
            claim,
            (self._discovery_evidence(claim),),
            law_equivalence_claim=eq_claim,
            equivalence_evidence_policy=eq_policy,
        )
        self.assertEqual(without_eq_evidence.status, "PROOF_REQUIRED")
        self.assertIn(
            "equivalence.evidence.required",
            {item.kind for item in without_eq_evidence.issues},
        )

        eq_evidence = EvidenceItemV0(
            "e.isomorphism",
            eq_claim.equivalence_claim_hash,
            h("equivalence-scope"),
            "PROOF",
            verifier_hash=h("equivalence-verifier"),
            witness_hash=h("isomorphism-witness"),
        )
        closed = self._evaluate(
            cycle,
            source,
            receipt,
            rediscovered,
            claim,
            (self._discovery_evidence(claim), eq_evidence),
            law_equivalence_claim=eq_claim,
            equivalence_evidence_policy=eq_policy,
        )
        self.assertEqual(closed.status, "PASS")

    def test_falsified_rediscovery_rejects_round_trip(self):
        law = self._law()
        receipt = self._receipt(law)
        claim = self._discovery_claim(law)
        falsified = EvidenceItemV0(
            "e.rediscovery.counterexample",
            claim.discovery_claim_hash,
            h("counterexample-scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        evaluation = self._evaluate(
            self._cycle(law, receipt, claim, law),
            law,
            receipt,
            law,
            claim,
            (self._discovery_evidence(claim), falsified),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("discovery.evidence.falsified", {item.kind for item in evaluation.issues})

    def test_cycle_binding_mismatch_is_reject_and_open_residual(self):
        law = self._law()
        receipt = self._receipt(law)
        claim = self._discovery_claim(law)
        cycle = DiscoveryRealizationCycleV0(
            law.law_semantic_hash,
            receipt.receipt_hash,
            h("observed-history"),
            h("wrong-discovery-claim"),
            law.law_semantic_hash,
        )
        evaluation = self._evaluate(
            cycle,
            law,
            receipt,
            law,
            claim,
            (self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("cycle.rediscovery_claim_mismatch", {item.kind for item in evaluation.issues})
        self.assertEqual(
            parse_residual(residual_from_discovery_realization_cycle(evaluation)).status,
            "OPEN",
        )


if __name__ == "__main__":
    unittest.main()
