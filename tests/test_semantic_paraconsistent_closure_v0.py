from __future__ import annotations

import unittest

from tev_script.semantic_epistemic_v0 import evidence_field
from tev_script.semantic_paraconsistent_v0 import (
    FourValueV0,
    RevisionPolicyV0,
    finite_entails,
    four_value_of,
    revised_four_value,
)


class ParaconsistentClosureV0Tests(unittest.TestCase):
    def test_contradiction_does_not_explode(self):
        result = finite_entails(
            (
                "p",
                ("not", "p"),
            ),
            "q",
            ("p", "q"),
        )
        self.assertEqual(
            result.status,
            "REJECT",
        )
        self.assertTrue(result.countermodel)

    def test_valid_four_valued_entailment(self):
        result = finite_entails(
            ("p",),
            ("or", "p", "q"),
            ("p", "q"),
        )
        self.assertEqual(result.status, "PASS")

    def test_large_valuation_space_is_proof_bound(self):
        result = finite_entails(
            (),
            "a",
            tuple("abcdefgh"),
            max_atoms=7,
        )
        self.assertEqual(
            result.status,
            "PROOF_REQUIRED",
        )

    def test_revision_is_policy_bound_and_content_addressed(self):
        evidence = evidence_field(
            (
                (
                    "e1",
                    "p",
                    "support",
                    "cameraA",
                    1,
                    1,
                    "",
                    "active",
                ),
                (
                    "e2",
                    "p",
                    "refute",
                    "cameraB",
                    1,
                    2,
                    "",
                    "active",
                ),
            )
        )
        policy = RevisionPolicyV0(
            "prefer-camera-b",
            ("cameraB", "cameraA"),
        )
        self.assertEqual(
            four_value_of(evidence, "p").name,
            "BOTH",
        )
        self.assertEqual(
            revised_four_value(
                evidence,
                "p",
                policy,
            ).name,
            "FALSE_ONLY",
        )
        self.assertEqual(
            policy.policy_hash,
            RevisionPolicyV0(
                "prefer-camera-b",
                ("cameraB", "cameraA"),
            ).policy_hash,
        )

    def test_double_negation_for_all_four_values(self):
        values = [
            FourValueV0(support, refute)
            for support in (False, True)
            for refute in (False, True)
        ]
        for value in values:
            self.assertEqual(
                value.negate().negate(),
                value,
            )


if __name__ == "__main__":
    unittest.main()
