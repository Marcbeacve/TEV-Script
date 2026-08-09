from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.lowering_ir_v3_linked_v1 import lower_linked_program_v1_to_ir_v3
from tev_script.lowering_receipt_v2 import (
    build_ir_v3_lowering_receipt,
    verify_ir_v3_lowering_receipt,
)
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]


def compile_pair(source_text: str):
    plan = link_v1_sources([SourceInputV1("root.tevs", source_text.encode())])
    linked = emit_linked_program_v1(analyze_v1_static_semantics(plan))
    target = lower_linked_program_v1_to_ir_v3(linked)
    return linked, target


class V1IrV3LoweringReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = '''script Root version "1.0.0";
record Pair { a: Int; b: Rat; }
entity E {
  state pair: Pair = Pair(a = 1, b = 2);
  state opt: Option<Int> = Some(3);
  on update {
    match opt {
      Some(value) => { pair = Pair(a = value, b = value); }
      None => { pair = Pair(a = 0, b = 0); }
    }
  }
}
'''
        self.linked, self.target = compile_pair(self.source)

    def test_receipt_binds_exact_source_and_ir_v3_target(self) -> None:
        receipt = build_ir_v3_lowering_receipt(self.linked, self.target)
        verify_ir_v3_lowering_receipt(receipt.receipt, self.linked, self.target)
        self.assertEqual(receipt.receipt["source"]["semantic_hash"], self.linked.semantic_hash)
        self.assertEqual(receipt.receipt["target"]["source_semantic_hash"], self.linked.semantic_hash)
        self.assertEqual(receipt.receipt["target"]["semantic_hash"], self.target.ir["semantic_hash"])
        self.assertTrue(all(receipt.receipt["proof_obligations"].values()))

    def test_receipt_schema_accepts_canonical_receipt_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency unavailable")
        receipt = build_ir_v3_lowering_receipt(self.linked, self.target)
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_lowering_receipt_v2.schema.json").read_text()
        )
        jsonschema.Draft202012Validator(schema).validate(receipt.receipt)

    def test_receipt_hash_tamper_fails(self) -> None:
        receipt = build_ir_v3_lowering_receipt(self.linked, self.target)
        tampered = copy.deepcopy(receipt.receipt)
        tampered["proof_obligations"]["algebraic_value_types_preserved"] = False
        with self.assertRaises(TevScriptError) as captured:
            verify_ir_v3_lowering_receipt(tampered, self.linked, self.target)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_IRV3_RECEIPT_HASH")

    def test_receipt_cannot_be_reused_for_another_linked_program(self) -> None:
        receipt = build_ir_v3_lowering_receipt(self.linked, self.target)
        other_source = self.source.replace("Some(3)", "Some(4)")
        other_linked, other_target = compile_pair(other_source)
        self.assertNotEqual(other_linked.semantic_hash, self.linked.semantic_hash)
        with self.assertRaises(TevScriptError):
            verify_ir_v3_lowering_receipt(receipt.receipt, other_linked, other_target)

    def test_target_bundle_with_wrong_embedded_source_hash_fails_before_receipt(self) -> None:
        from tev_script.lowering_ir_v3_linked_v1 import LinkedV1IrV3Bundle
        tampered_ir = copy.deepcopy(self.target.ir)
        tampered_ir["source_semantic_hash"] = "0" * 64
        tampered = LinkedV1IrV3Bundle(
            tampered_ir,
            self.target.canonical_json,
            self.target.linked_semantic_hash,
        )
        with self.assertRaises(TevScriptError):
            build_ir_v3_lowering_receipt(self.linked, tampered)


if __name__ == "__main__":
    unittest.main()
