from __future__ import annotations
from dataclasses import replace
import unittest

from tev_script.source_semantic_process_v3 import compile_semantic_process_v3
from tev_script.translation_validation_v3 import (
    source_to_ir_validation_field,
    validate_source_to_ir_v3,
    verify_source_to_ir_validation,
)

SOURCE = '''
process Door version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["closed"];
fact opened = door.state ["open"];
field actual = [closed];
transform open effects 1111111111111111111111111111111111111111111111111111111111111111 resources 2222222222222222222222222222222222222222222222222222222222222222 remove [closed] add [opened];
label start = apply open done;
label done = halt;
entry start;
'''

class TranslationValidationV3Tests(unittest.TestCase):
    def test_compiler_output_is_independently_admitted(self) -> None:
        candidate = compile_semantic_process_v3(SOURCE)
        receipt = validate_source_to_ir_v3(SOURCE, candidate)
        self.assertEqual(receipt.status, "PASS")
        self.assertTrue(receipt.admission_authority)
        self.assertFalse(receipt.promotion_authority)
        self.assertTrue(verify_source_to_ir_validation(SOURCE, candidate, receipt))

    def test_valid_but_wrong_ir_is_rejected(self) -> None:
        other = compile_semantic_process_v3(SOURCE.replace("quantum_steps 4", "quantum_steps 5"))
        receipt = validate_source_to_ir_v3(SOURCE, other)
        self.assertEqual(receipt.status, "REJECT")
        self.assertTrue(verify_source_to_ir_validation(SOURCE, other, receipt))

    def test_receipt_tamper_is_rejected(self) -> None:
        candidate = compile_semantic_process_v3(SOURCE)
        receipt = validate_source_to_ir_v3(SOURCE, candidate)
        self.assertFalse(verify_source_to_ir_validation(SOURCE, candidate, replace(receipt, status="REJECT")))

    def test_receipt_lowers_to_existing_field_basis(self) -> None:
        candidate = compile_semantic_process_v3(SOURCE)
        receipt = validate_source_to_ir_v3(SOURCE, candidate)
        field = source_to_ir_validation_field(receipt)
        self.assertEqual({fact.relation for fact in field.facts}, {"tev.proof.source_to_ir"})
        self.assertEqual(field.profile, "proof_validation")

if __name__ == "__main__": unittest.main()
