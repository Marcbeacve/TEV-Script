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
)
from tev_script.semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


class StructuralLawIdentityV0Tests(unittest.TestCase):
    def _policy(self):
        return EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "law-evidence",
                    ("PROOF", "EXHAUSTIVE"),
                    scope_hash=h("law-scope"),
                    trusted_verifier_hashes=(h("verifier"),),
                ),
            )
        )

    def _law(self, law_id: str, *, transformation=None, formulation=None, provenance=None):
        policy = self._policy()
        return StructuralLawClaimV0(
            law_id,
            h("regime"),
            transformation or h("transformation"),
            h("boundary"),
            h("falsifiers"),
            policy.policy_hash,
            assumption_hashes=(h("assumption"),),
            formulation_hash=formulation or h("formulation-" + law_id),
            provenance=provenance or {"source": law_id},
        )

    def test_display_name_formulation_and_provenance_do_not_define_law_semantics(self):
        left = self._law(
            "law.alpha",
            formulation=h("text-a"),
            provenance={"notation": "a"},
        )
        right = self._law(
            "law.beta",
            formulation=h("text-b"),
            provenance={"notation": "b"},
        )
        self.assertEqual(left.law_semantic_hash, right.law_semantic_hash)
        self.assertNotEqual(left.law_claim_hash, right.law_claim_hash)

    def test_boundary_and_transformation_are_semantic(self):
        base = self._law("law.base")
        other_transformation = self._law("law.other", transformation=h("different-transformation"))
        self.assertNotEqual(base.law_semantic_hash, other_transformation.law_semantic_hash)

        other_boundary = StructuralLawClaimV0(
            "law.boundary",
            h("regime"),
            h("transformation"),
            h("different-boundary"),
            h("falsifiers"),
            self._policy().policy_hash,
            assumption_hashes=(h("assumption"),),
        )
        self.assertNotEqual(base.law_semantic_hash, other_boundary.law_semantic_hash)

    def test_distinct_concrete_semantics_require_explicit_equivalence_claim(self):
        left = self._law("law.left")
        right = self._law("law.right", transformation=h("isomorphic-recoding"))
        eq_policy = EvidencePolicyV0(())
        claim = LawEquivalenceClaimV0(
            left.law_semantic_hash,
            right.law_semantic_hash,
            h("isomorphism-relation"),
            h("law-scope"),
            eq_policy.policy_hash,
        )
        reversed_claim = LawEquivalenceClaimV0(
            right.law_semantic_hash,
            left.law_semantic_hash,
            h("isomorphism-relation"),
            h("law-scope"),
            eq_policy.policy_hash,
        )
        self.assertEqual(claim.equivalence_claim_hash, reversed_claim.equivalence_claim_hash)
        self.assertEqual(claim.law_pair, reversed_claim.law_pair)

    def test_equivalence_claim_rejects_identical_hashes_as_redundant(self):
        law = self._law("law.same")
        with self.assertRaises(DiscoveryRealizationError):
            LawEquivalenceClaimV0(
                law.law_semantic_hash,
                law.law_semantic_hash,
                h("eq"),
                h("scope"),
                EvidencePolicyV0(()).policy_hash,
            )

    def test_model_compatibility_is_a_claim_not_an_implicit_truth(self):
        law = self._law("law.model")
        claim = ModelCompatibilityClaimV0(
            law.law_semantic_hash,
            h("generated-model"),
            h("regime"),
            h("boundary"),
            h("satisfies-relation"),
            EvidencePolicyV0(()).policy_hash,
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

    def _discovery_claim(self, law_hash: str):
        policy = self._discovery_policy()
        return DiscoveryClaimV0(
            h("experience-space"),
            h("observations"),
            h("interventions"),
            law_hash,
            h("discovery-context"),
            h("boundary"),
            policy.policy_hash,
            assumption_hashes=(h("assumption"),),
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

    def test_round_trip_passes_when_same_canonical_law_is_rediscovered_with_evidence(self):
        law_hash = h("law-semantic")
        claim = self._discovery_claim(law_hash)
        cycle = DiscoveryRealizationCycleV0(
            law_hash,
            h("realization-receipt"),
            h("observed-history"),
            claim.discovery_claim_hash,
            law_hash,
        )
        evaluation = evaluate_discovery_realization_cycle(
            cycle,
            rediscovery_claim=claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=(self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "PASS")

    def test_different_concrete_law_requires_governed_equivalence(self):
        source = h("law-source")
        rediscovered = h("law-recoded")
        claim = self._discovery_claim(rediscovered)
        cycle = DiscoveryRealizationCycleV0(
            source,
            h("realization-receipt"),
            h("observed-history"),
            claim.discovery_claim_hash,
            rediscovered,
        )
        evaluation = evaluate_discovery_realization_cycle(
            cycle,
            rediscovery_claim=claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=(self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("cycle.law_equivalence_required", {item.kind for item in evaluation.issues})

    def test_isomorphic_recode_round_trip_passes_only_with_equivalence_evidence(self):
        source = h("law-source")
        rediscovered = h("law-recoded")
        discovery_claim = self._discovery_claim(rediscovered)
        eq_policy = self._equivalence_policy()
        eq_claim = LawEquivalenceClaimV0(
            source,
            rediscovered,
            h("isomorphism"),
            h("equivalence-scope"),
            eq_policy.policy_hash,
        )
        cycle = DiscoveryRealizationCycleV0(
            source,
            h("realization-receipt"),
            h("observed-history"),
            discovery_claim.discovery_claim_hash,
            rediscovered,
            eq_claim.equivalence_claim_hash,
        )
        equivalence_evidence = EvidenceItemV0(
            "e.isomorphism",
            eq_claim.equivalence_claim_hash,
            h("equivalence-scope"),
            "PROOF",
            verifier_hash=h("equivalence-verifier"),
            witness_hash=h("isomorphism-witness"),
        )
        evaluation = evaluate_discovery_realization_cycle(
            cycle,
            rediscovery_claim=discovery_claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=(self._discovery_evidence(discovery_claim), equivalence_evidence),
            law_equivalence_claim=eq_claim,
            equivalence_evidence_policy=eq_policy,
        )
        self.assertEqual(evaluation.status, "PASS")

    def test_equivalence_claim_without_evidence_stays_open(self):
        source = h("law-source")
        rediscovered = h("law-recoded")
        discovery_claim = self._discovery_claim(rediscovered)
        eq_policy = self._equivalence_policy()
        eq_claim = LawEquivalenceClaimV0(
            source,
            rediscovered,
            h("isomorphism"),
            h("equivalence-scope"),
            eq_policy.policy_hash,
        )
        cycle = DiscoveryRealizationCycleV0(
            source,
            h("realization-receipt"),
            h("observed-history"),
            discovery_claim.discovery_claim_hash,
            rediscovered,
            eq_claim.equivalence_claim_hash,
        )
        evaluation = evaluate_discovery_realization_cycle(
            cycle,
            rediscovery_claim=discovery_claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=(self._discovery_evidence(discovery_claim),),
            law_equivalence_claim=eq_claim,
            equivalence_evidence_policy=eq_policy,
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("equivalence.evidence.required", {item.kind for item in evaluation.issues})

    def test_falsified_rediscovery_rejects_round_trip(self):
        law_hash = h("law-semantic")
        claim = self._discovery_claim(law_hash)
        cycle = DiscoveryRealizationCycleV0(
            law_hash,
            h("realization-receipt"),
            h("observed-history"),
            claim.discovery_claim_hash,
            law_hash,
        )
        good = self._discovery_evidence(claim)
        falsified = EvidenceItemV0(
            "e.rediscovery.counterexample",
            claim.discovery_claim_hash,
            h("counterexample-scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        evaluation = evaluate_discovery_realization_cycle(
            cycle,
            rediscovery_claim=claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=(good, falsified),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("discovery.evidence.falsified", {item.kind for item in evaluation.issues})

    def test_cycle_binding_mismatch_rejects_even_if_evidence_is_good(self):
        law_hash = h("law-semantic")
        claim = self._discovery_claim(law_hash)
        cycle = DiscoveryRealizationCycleV0(
            law_hash,
            h("realization-receipt"),
            h("observed-history"),
            h("wrong-discovery-claim"),
            law_hash,
        )
        evaluation = evaluate_discovery_realization_cycle(
            cycle,
            rediscovery_claim=claim,
            discovery_evidence_policy=self._discovery_policy(),
            evidence=(self._discovery_evidence(claim),),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("cycle.rediscovery_claim_mismatch", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
