from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import semantic_field
from tev_script.program_ir_v4 import export_program_ir_v4_pure
from tev_script.source_program_v2 import compile_program_v2
from tev_script.program_ir_v5_total import (
    LANGUAGE_VERSION_V31,
    PROFILE_TOTAL_CORE,
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    TotalCoreUnitV1,
    VerifiedProofAdmissionV1,
    canonical_total_core_program_bytes,
    total_core_program_to_mapping,
    validate_total_core_program,
)


HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEX_D = "d" * 64


class ProgramIRV5TotalCoreTests(unittest.TestCase):
    PURE_SOURCE = (
        'script Calc version "2.0.0"; '
        'fn add1(x:Int)->Int=x+1; '
        'entry main:Int=add1(4);'
    )

    def pure_ir(self) -> dict:
        return export_program_ir_v4_pure(compile_program_v2(self.PURE_SOURCE))

    def unit(self) -> TotalCoreUnitV1:
        return TotalCoreUnitV1.build("Calc", "pure", self.pure_ir())

    def program(self, *, units=None, proofs=()) -> TotalCoreProgramV1:
        unit = self.unit()
        actual_units = (unit,) if units is None else tuple(units)
        instructions = (
            TotalCoreInstructionV1.invoke_v4(
                unit_hash=unit.unit_hash,
                result_relation="tev.total.result",
                next_pc=1,
            ),
            TotalCoreInstructionV1.halt(),
        )
        return TotalCoreProgramV1.build(
            program_id="Demo",
            source_semantic_hash=HEX_B,
            initial_field=semantic_field((), profile="actual"),
            transformations=(),
            v4_units=actual_units,
            proof_admissions=tuple(proofs),
            instructions=instructions,
            entry_pc=0,
            quantum_step_limit=8,
            authority_hash=HEX_A,
        )

    def test_v4_pure_unit_preserves_exact_program_hash(self) -> None:
        ir = self.pure_ir()
        unit = TotalCoreUnitV1.build("Calc", "pure", ir)
        self.assertEqual(unit.program_ir_hash, ir["program_ir_hash"])
        self.assertEqual(unit.profile, "pure")
        self.assertEqual(unit.unit_id, "Calc")
        self.assertEqual(len(unit.unit_hash), 64)

    def test_unit_profile_must_match_v4_schema(self) -> None:
        with self.assertRaises(TevScriptError):
            TotalCoreUnitV1.build("Calc", "recursive", self.pure_ir())

    def test_tampered_embedded_v4_program_hash_is_rejected(self) -> None:
        ir = self.pure_ir()
        ir["program_ir_hash"] = HEX_D
        with self.assertRaises(TevScriptError):
            TotalCoreUnitV1.build("Calc", "pure", ir)

    def test_verified_proof_admission_is_content_addressed(self) -> None:
        admission = VerifiedProofAdmissionV1.build(
            requirement_hash=HEX_A,
            verification_receipt_hash=HEX_B,
            verifier_identity_hash=HEX_C,
            authority_hash=HEX_D,
        )
        self.assertEqual(admission.status, "VERIFIED")
        self.assertEqual(len(admission.admission_hash), 64)
        rebuilt = VerifiedProofAdmissionV1.build(
            requirement_hash=HEX_A,
            verification_receipt_hash=HEX_B,
            verifier_identity_hash=HEX_C,
            authority_hash=HEX_D,
        )
        self.assertEqual(admission, rebuilt)

    def test_proof_admission_requires_lowercase_sha256_fields(self) -> None:
        with self.assertRaises(TevScriptError):
            VerifiedProofAdmissionV1.build(
                requirement_hash="A" * 64,
                verification_receipt_hash=HEX_B,
                verifier_identity_hash=HEX_C,
                authority_hash=HEX_D,
            )

    def test_invoke_v4_requires_stable_result_relation(self) -> None:
        unit = self.unit()
        with self.assertRaises(TevScriptError):
            TotalCoreInstructionV1.invoke_v4(
                unit_hash=unit.unit_hash,
                result_relation="not a relation",
                next_pc=1,
            )

    def test_program_has_v31_total_core_identity_and_roundtrips(self) -> None:
        program = self.program()
        self.assertEqual(program.language_version, LANGUAGE_VERSION_V31)
        self.assertEqual(program.profile, PROFILE_TOTAL_CORE)
        self.assertEqual(len(program.program_hash), 64)
        mapping = total_core_program_to_mapping(program)
        validated = validate_total_core_program(mapping)
        self.assertEqual(validated, program)
        self.assertEqual(
            canonical_total_core_program_bytes(mapping),
            canonical_total_core_program_bytes(program),
        )

    def test_duplicate_unit_id_is_rejected(self) -> None:
        first = self.unit()
        other_ir = export_program_ir_v4_pure(
            compile_program_v2(
                'script Other version "2.0.0"; '
                'fn f(x:Int)->Int=x+2; entry main:Int=f(4);'
            )
        )
        second = TotalCoreUnitV1.build("Calc", "pure", other_ir)
        with self.assertRaises(TevScriptError):
            self.program(units=(first, second))

    def test_tampered_outer_program_hash_is_rejected(self) -> None:
        program = self.program()
        mapping = copy.deepcopy(total_core_program_to_mapping(program))
        mapping["program_hash"] = HEX_D
        with self.assertRaises(TevScriptError):
            validate_total_core_program(mapping)


if __name__ == "__main__":
    unittest.main()
