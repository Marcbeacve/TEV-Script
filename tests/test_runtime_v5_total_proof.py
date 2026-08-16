from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import field_fact, field_transformation, semantic_field
from tev_script.program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    VerifiedProofAdmissionV1,
)
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum


AUTHORITY = "a" * 64
SOURCE = "b" * 64
REQUIREMENT = "c" * 64
VERIFICATION_RECEIPT = "d" * 64
VERIFIER = "e" * 64
OTHER_AUTHORITY = "f" * 64


class RuntimeV5TotalCoreProofAdmissionTests(unittest.TestCase):
    def transformation(self):
        fact = field_fact("tev.proof.accepted", ({"value": "verified"},))
        return field_transformation(
            transformation_id="proof.gated.transition",
            add_facts=(fact,),
            effect_set_hash="1" * 64,
            resource_vector_hash="2" * 64,
            proof_requirement_hashes=(REQUIREMENT,),
        )

    def admission(self, *, authority_hash: str = AUTHORITY):
        return VerifiedProofAdmissionV1.build(
            requirement_hash=REQUIREMENT,
            verification_receipt_hash=VERIFICATION_RECEIPT,
            verifier_identity_hash=VERIFIER,
            authority_hash=authority_hash,
        )

    def program(self, *, admissions):
        transformation = self.transformation()
        return TotalCoreProgramV1.build(
            program_id="ProofOpen",
            source_semantic_hash=SOURCE,
            initial_field=semantic_field((), profile="actual"),
            transformations=(transformation,),
            v4_units=(),
            proof_admissions=tuple(admissions),
            instructions=(
                TotalCoreInstructionV1.apply(
                    transformation.transformation_hash,
                    next_pc=1,
                ),
                TotalCoreInstructionV1.halt(),
            ),
            entry_pc=0,
            quantum_step_limit=4,
            authority_hash=AUTHORITY,
        )

    def test_exact_verified_admission_executes_proof_open_apply(self) -> None:
        program = self.program(admissions=(self.admission(),))
        original = program.transformations[0]

        result = run_total_core_quantum(
            program,
            initial_total_core_checkpoint(program),
        )

        self.assertEqual(result.status, "HALTED")
        self.assertEqual(result.steps_used, 2)
        self.assertTrue(
            any(fact.relation == "tev.proof.accepted" for fact in result.field.facts)
        )
        self.assertEqual(
            program.transformations[0].transformation_hash,
            original.transformation_hash,
        )
        self.assertEqual(
            program.transformations[0].proof_requirement_hashes,
            (REQUIREMENT,),
        )

    def test_missing_admission_is_rejected_before_runtime(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            self.program(admissions=())
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V31_TOTAL_PROOF_REQUIRED",
        )

    def test_admission_authority_mismatch_is_rejected_before_runtime(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            self.program(admissions=(self.admission(authority_hash=OTHER_AUTHORITY),))
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V31_TOTAL_PROOF_AUTHORITY",
        )


if __name__ == "__main__":
    unittest.main()
