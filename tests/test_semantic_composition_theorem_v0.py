from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_apply_v0 import (
    RuleOpV0,
    rule_field,
)
from tev_script.semantic_composition_theorem_v0 import (
    commit_scope_hash,
    composition_law_hash,
    physical_commit_composition,
    prove_finite_family_serializable,
    prove_semantic_diamond,
)
from tev_script.semantic_effects_v0 import (
    DomainLawV0,
    EffectAtomV0,
)
from tev_script.semantic_kernel_v0 import SemanticFieldV0
from tev_script.semantic_proof_boundary_v0 import (
    ProofBoundaryWitnessV0,
    VerifierTrustPolicyV0,
)

CONTEXT_HASH = canonical_hash({"center": "composition-test"})


class CompositionTheoremV0Tests(unittest.TestCase):
    @staticmethod
    def field():
        return SemanticFieldV0.build(
            (
                ("a", 1),
                ("b", 1),
                ("c", 1),
            ),
            (),
        )

    @staticmethod
    def put(relation: str, value: int):
        return rule_field(
            relation,
            (
                RuleOpV0(
                    "put",
                    {
                        "relation": relation,
                        "arguments": [value],
                    },
                ),
            ),
        )

    def test_law_context_is_content_bound(self):
        laws = {}
        law_hash = composition_law_hash(laws)
        self.assertEqual(
            prove_semantic_diamond(
                self.field(),
                self.put("a", 1),
                self.put("b", 2),
                laws=laws,
                context_hash=CONTEXT_HASH,
                law_hash=law_hash,
            ).status,
            "PASS",
        )
        self.assertEqual(
            prove_semantic_diamond(
                self.field(),
                self.put("a", 1),
                self.put("b", 2),
                laws=laws,
                context_hash=CONTEXT_HASH,
                law_hash="0" * 64,
            ).reason,
            "law_context_hash_mismatch",
        )

    def test_wildcard_remove_detects_latent_conflict(self):
        laws = {}
        law_hash = composition_law_hash(laws)
        remove = rule_field(
            "remove-a",
            (
                RuleOpV0(
                    "remove",
                    {"relation": "a"},
                ),
            ),
        )
        self.assertEqual(
            prove_semantic_diamond(
                self.field(),
                self.put("a", 1),
                remove,
                laws=laws,
                context_hash=CONTEXT_HASH,
                law_hash=law_hash,
            ).status,
            "REJECT",
        )

    def test_disjoint_external_resources_commute_under_complete_law(self):
        laws = {
            "external": DomainLawV0(
                "external",
                complete=True,
            )
        }
        law_hash = composition_law_hash(laws)
        left = rule_field(
            "A",
            (),
            (
                EffectAtomV0(
                    "external",
                    "file",
                    "write",
                    payload=("A",),
                ),
            ),
        )
        right = rule_field(
            "B",
            (),
            (
                EffectAtomV0(
                    "external",
                    "file",
                    "write",
                    payload=("B",),
                ),
            ),
        )
        self.assertEqual(
            prove_semantic_diamond(
                self.field(),
                left,
                right,
                laws=laws,
                context_hash=CONTEXT_HASH,
                law_hash=law_hash,
            ).status,
            "PASS",
        )

    def test_physical_commit_requires_trusted_scope_proof(self):
        laws = {}
        law_hash = composition_law_hash(laws)
        diamond = prove_semantic_diamond(
            self.field(),
            self.put("a", 1),
            self.put("b", 2),
            laws=laws,
            context_hash=CONTEXT_HASH,
            law_hash=law_hash,
        )
        scope_hash = commit_scope_hash(diamond)
        witness = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            scope_hash,
            "proved",
        )
        self.assertEqual(
            physical_commit_composition(
                diamond,
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("c" * 64,)
                ),
            ).status,
            "PROOF_REQUIRED",
        )
        self.assertEqual(
            physical_commit_composition(
                diamond,
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("b" * 64,)
                ),
            ).status,
            "PASS",
        )

    def test_finite_family_is_exhaustive_and_large_family_is_proof_bound(self):
        laws = {}
        law_hash = composition_law_hash(laws)
        rules = (
            self.put("a", 1),
            self.put("b", 2),
            self.put("c", 3),
        )
        self.assertEqual(
            prove_finite_family_serializable(
                self.field(),
                rules,
                laws=laws,
                context_hash=CONTEXT_HASH,
                law_hash=law_hash,
            ).status,
            "PASS",
        )

        large = tuple(
            rule_field(
                f"noop-{index}",
                (),
            )
            for index in range(7)
        )
        self.assertEqual(
            prove_finite_family_serializable(
                self.field(),
                large,
                laws=laws,
                context_hash=CONTEXT_HASH,
                law_hash=law_hash,
            ).status,
            "PROOF_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()
