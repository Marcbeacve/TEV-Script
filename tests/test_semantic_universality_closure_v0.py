from __future__ import annotations

import unittest

from tev_script.semantic_proof_boundary_v0 import (
    ProofBoundaryWitnessV0,
    VerifierTrustPolicyV0,
)
from tev_script.semantic_universality_v0 import (
    THEOREM_SCOPE,
    CounterInstructionV0,
    CounterMachineStateV0,
    counter_step,
    embedded_counter_step,
    trace_universality_witness,
    validate_program,
    verify_step_embedding,
)


class UniversalityClosureV0Tests(unittest.TestCase):
    def test_literal_field_apply_embedding(self):
        program = (
            CounterInstructionV0(
                "INC",
                0,
                next_pc=1,
            ),
            CounterInstructionV0("HALT"),
        )
        state = CounterMachineStateV0(
            0,
            0,
            0,
        )
        self.assertEqual(
            embedded_counter_step(
                program,
                state,
            ),
            counter_step(
                program,
                state,
            ),
        )

    def test_invalid_jump_rejects(self):
        with self.assertRaises(ValueError):
            validate_program(
                (
                    CounterInstructionV0(
                        "INC",
                        0,
                        next_pc=9,
                    ),
                )
            )

    def test_embedding_exact_on_counter_samples(self):
        program = (
            CounterInstructionV0(
                "DECJZ",
                0,
                zero_pc=1,
                nonzero_pc=0,
            ),
            CounterInstructionV0("HALT"),
        )
        samples = tuple(
            CounterMachineStateV0(
                0,
                value,
                0,
            )
            for value in range(8)
        )
        self.assertTrue(
            verify_step_embedding(
                program,
                samples,
            )
        )

    def test_relative_universality_requires_trusted_source_theorem(self):
        witness = ProofBoundaryWitnessV0(
            "a" * 64,
            "b" * 64,
            THEOREM_SCOPE,
            "proved",
        )
        self.assertEqual(
            trace_universality_witness(
                True,
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("c" * 64,)
                ),
            ).status,
            "PROOF_REQUIRED",
        )
        self.assertEqual(
            trace_universality_witness(
                True,
                proof_witness=witness,
                trust_policy=VerifierTrustPolicyV0(
                    ("b" * 64,)
                ),
            ).status,
            "PASS_RELATIVE",
        )


if __name__ == "__main__":
    unittest.main()
