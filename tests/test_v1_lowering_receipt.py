from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.lowering_ir_v2_linked_v1 import lower_linked_program_v1_to_ir_v2
from tev_script.lowering_receipt_v1 import (
    build_ir_v2_lowering_receipt,
    verify_ir_v2_lowering_receipt,
)
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]


def build(source: str):
    plan = link_v1_sources([SourceInputV1("receipt.tevs", source.encode())])
    linked = emit_linked_program_v1(analyze_v1_static_semantics(plan))
    target = lower_linked_program_v1_to_ir_v2(linked)
    return linked, target, build_ir_v2_lowering_receipt(linked, target)


class V1LoweringReceiptTests(unittest.TestCase):
    def test_receipt_binds_source_and_target(self) -> None:
        source, target, bundle = build(
            'script Root version "1.0.0"; '
            'fn twice(x: Int) -> Int = x * 2; '
            'entity E { state x: Int = 1; on update { x = twice(x); } }'
        )
        verify_ir_v2_lowering_receipt(bundle.receipt, source, target)
        self.assertEqual(
            bundle.receipt["source"]["semantic_hash"], source.semantic_hash
        )
        self.assertEqual(
            bundle.receipt["target"]["semantic_hash"], target.ir["semantic_hash"]
        )

    def test_receipt_schema_validates(self) -> None:
        try:
            import jsonschema
        except ImportError as exc:
            raise unittest.SkipTest("jsonschema dependency unavailable") from exc
        _source, _target, bundle = build(
            'script Root version "1.0.0"; entity E { on start { return; } }'
        )
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_lowering_receipt_v1.schema.json").read_text()
        )
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(bundle.receipt)

    def test_tampered_receipt_hash_is_rejected(self) -> None:
        source, target, bundle = build(
            'script Root version "1.0.0"; entity E { state x: Int = 0; on update { x = x + 1; } }'
        )
        tampered = copy.deepcopy(bundle.receipt)
        tampered["receipt_hash"] = "0" * 64
        with self.assertRaises(TevScriptError) as captured:
            verify_ir_v2_lowering_receipt(tampered, source, target)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_LOWER_RECEIPT_HASH")

    def test_receipt_cannot_be_reused_for_different_source(self) -> None:
        source_a, target_a, bundle = build(
            'script Root version "1.0.0"; entity E { state x: Int = 1; on start { return; } }'
        )
        source_b, _target_b, _bundle_b = build(
            'script Root version "1.0.0"; entity E { state x: Int = 2; on start { return; } }'
        )
        with self.assertRaises(TevScriptError):
            verify_ir_v2_lowering_receipt(bundle.receipt, source_b, target_a)
        verify_ir_v2_lowering_receipt(bundle.receipt, source_a, target_a)

    def test_receipt_canonical_bytes_are_deterministic(self) -> None:
        left = build(
            'script Root version "1.0.0"; entity E { state x: Int = 1 + 1; on start { return; } }'
        )[2]
        right = build(
            'script Root version "1.0.0"; entity E { state x: Int = 2; on start { return; } }'
        )[2]
        self.assertEqual(left.canonical_json, right.canonical_json)
        self.assertEqual(left.receipt_hash, right.receipt_hash)


if __name__ == "__main__":
    unittest.main()
