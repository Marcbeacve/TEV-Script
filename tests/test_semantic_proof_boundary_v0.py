from __future__ import annotations

import unittest

from tev_script.semantic_proof_boundary_v0 import (
    ProofBoundaryWitnessV0,
    VerifierTrustPolicyV0,
)


class ProofBoundaryV0Tests(unittest.TestCase):
    def test_trust_is_not_self_declared(self):
        witness = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "proved",
        )
        trusted = VerifierTrustPolicyV0(("b" * 64,))
        untrusted = VerifierTrustPolicyV0(("d" * 64,))
        self.assertTrue(
            trusted.accepts(
                witness,
                "c" * 64,
            )
        )
        self.assertFalse(
            untrusted.accepts(
                witness,
                "c" * 64,
            )
        )

    def test_sampled_and_revoked_are_not_strong(self):
        policy = VerifierTrustPolicyV0(("b" * 64,))
        sampled = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "sampled",
        )
        revoked = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "attested",
            "revoked",
        )
        self.assertFalse(
            policy.accepts(
                sampled,
                "c" * 64,
            )
        )
        self.assertFalse(
            policy.accepts(
                revoked,
                "c" * 64,
            )
        )

    def test_policy_is_canonical(self):
        policy = VerifierTrustPolicyV0(
            (
                "b" * 64,
                "a" * 64,
                "a" * 64,
            )
        )
        self.assertEqual(
            policy.trusted_verifier_hashes,
            (
                "a" * 64,
                "b" * 64,
            ),
        )


if __name__ == "__main__":
    unittest.main()
