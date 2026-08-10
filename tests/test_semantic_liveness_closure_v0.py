from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_liveness_v0 import (
    FiniteTransitionSystemV0,
    finite_fair_eventually,
    general_liveness,
    verify_lasso_witness,
)
from tev_script.semantic_proof_boundary_v0 import (
    ProofBoundaryWitnessV0,
    VerifierTrustPolicyV0,
)


class LivenessClosureV0Tests(unittest.TestCase):
    def test_non_goal_deadlock_is_failure(self):
        system = FiniteTransitionSystemV0(
            ("s0", "dead", "goal"),
            "s0",
            (
                ("s0", "dead"),
                ("s0", "goal"),
                ("goal", "goal"),
            ),
        )
        result = finite_fair_eventually(
            system,
            ("goal",),
        )
        self.assertEqual(
            result.reason,
            "non_goal_deadlock",
        )

    def test_fair_cycle_rejects_and_unfair_cycle_can_be_excluded(self):
        system = FiniteTransitionSystemV0(
            ("s0", "spin", "goal"),
            "s0",
            (
                ("s0", "spin"),
                ("spin", "spin"),
                ("s0", "goal"),
                ("goal", "goal"),
            ),
        )
        self.assertEqual(
            finite_fair_eventually(
                system,
                ("goal",),
                (("spin", "goal"),),
            ).status,
            "REJECT",
        )
        self.assertEqual(
            finite_fair_eventually(
                system,
                ("goal",),
                (("goal",),),
            ).status,
            "PASS",
        )

    def test_empty_justice_set_is_invalid(self):
        system = FiniteTransitionSystemV0(
            ("s0",),
            "s0",
            (("s0", "s0"),),
        )
        with self.assertRaises(ValueError):
            finite_fair_eventually(
                system,
                (),
                ((),),
            )

    def test_valid_lasso_witness(self):
        system = FiniteTransitionSystemV0(
            ("s0", "a", "b"),
            "s0",
            (
                ("s0", "a"),
                ("a", "b"),
                ("b", "a"),
            ),
        )
        self.assertEqual(
            verify_lasso_witness(
                system,
                ("s0",),
                ("a", "b"),
                (("a",),),
            ).status,
            "PASS",
        )

    def test_general_liveness_requires_trusted_scope_proof(self):
        scope_hash = canonical_hash(
            {"property": "infinite_liveness"}
        )
        witness = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            scope_hash,
            "proved",
        )
        self.assertEqual(
            general_liveness(
                scope_hash=scope_hash,
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("c" * 64,)
                ),
            ).status,
            "PROOF_REQUIRED",
        )
        self.assertEqual(
            general_liveness(
                scope_hash=scope_hash,
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("b" * 64,)
                ),
            ).status,
            "PASS",
        )


if __name__ == "__main__":
    unittest.main()
