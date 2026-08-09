from __future__ import annotations

import copy
import json
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v3_validation import validate_program_ir_v3
from tev_script.ir_v3_values import (
    RecordValueV3,
    VariantValueV3,
    build_type_table_v3,
    decode_v3_value,
    encode_v3_value,
    v3_values_equal,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text()
)


def _mutate(program: dict, mutation: dict) -> dict:
    result = copy.deepcopy(program)
    operation = mutation["operation"]
    if operation == "set":
        parent = result
        for segment in mutation["path"][:-1]:
            parent = parent[segment]
        parent[mutation["path"][-1]] = copy.deepcopy(mutation["value"])
    elif operation == "swap":
        target = result
        for segment in mutation["path"]:
            target = target[segment]
        target[mutation["left"]], target[mutation["right"]] = (
            target[mutation["right"]],
            target[mutation["left"]],
        )
    else:
        raise AssertionError(operation)
    return result


class IrV3ProgramValidatorTests(unittest.TestCase):
    def test_portable_positive_program_validates(self) -> None:
        program = copy.deepcopy(CASES["valid_program"])
        table = validate_program_ir_v3(
            program,
            expected_source_semantic_hash="1" * 64,
        )
        self.assertEqual(table.require("Root.Pair").kind, "record")
        self.assertEqual(table.require("Option<Int>").argument, "Int")
        self.assertEqual(table.require("Result<Int,Text>").err_type, "Text")

    def test_portable_negative_mutations_fail_with_expected_category(self) -> None:
        for mutation in CASES["negative_mutations"]:
            with self.subTest(case=mutation["id"]):
                program = _mutate(CASES["valid_program"], mutation)
                with self.assertRaises(TevScriptError) as captured:
                    validate_program_ir_v3(program)
                self.assertEqual(captured.exception.diagnostic.code, mutation["code"])

    def test_source_semantic_hash_binding_is_checked_independently(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            validate_program_ir_v3(
                copy.deepcopy(CASES["valid_program"]),
                expected_source_semantic_hash="2" * 64,
            )
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_SOURCE_HASH")

    def test_schema_accepts_the_portable_positive_program_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency unavailable")
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_program_ir_v3.schema.json").read_text()
        )
        jsonschema.Draft202012Validator(schema).validate(CASES["valid_program"])


class IrV3ValueCodecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.program = copy.deepcopy(CASES["valid_program"])
        self.table = build_type_table_v3(self.program)

    def test_record_roundtrip_uses_canonical_descriptor_order(self) -> None:
        value = RecordValueV3(
            "Root.Pair",
            (("b", Fraction(3, 2)), ("a", 7)),
        )
        encoded = encode_v3_value("Root.Pair", value, self.table)
        self.assertEqual(
            encoded,
            {
                "$record": {
                    "type": "Root.Pair",
                    "fields": [
                        {"name": "a", "value": {"$int": "7"}},
                        {"name": "b", "value": {"$rat": ["3", "2"]}},
                    ],
                }
            },
        )
        decoded = decode_v3_value("Root.Pair", encoded, self.table)
        self.assertTrue(v3_values_equal("Root.Pair", decoded, RecordValueV3("Root.Pair", (("a", 7), ("b", Fraction(3, 2)))), self.table))

    def test_option_result_and_enum_roundtrip(self) -> None:
        values = (
            ("Root.Kind", VariantValueV3("Root.Kind", "B")),
            ("Option<Int>", VariantValueV3("Option<Int>", "None")),
            ("Option<Int>", VariantValueV3("Option<Int>", "Some", 9)),
            ("Result<Int,Text>", VariantValueV3("Result<Int,Text>", "Ok", 3)),
            ("Result<Int,Text>", VariantValueV3("Result<Int,Text>", "Err", "bad")),
        )
        for type_id, value in values:
            with self.subTest(type_id=type_id, variant=value.variant):
                encoded = encode_v3_value(type_id, value, self.table)
                decoded = decode_v3_value(type_id, encoded, self.table)
                self.assertTrue(v3_values_equal(type_id, value, decoded, self.table))

    def test_vec2_and_vec3_preserve_v02_external_encoding(self) -> None:
        vec2 = encode_v3_value("Vec2", (Fraction(1, 2), Fraction(-3, 1)), self.table)
        vec3 = encode_v3_value("Vec3", (0, Fraction(1, 3), 2), self.table)
        self.assertEqual(
            vec2,
            [{"$rat": ["1", "2"]}, {"$rat": ["-3", "1"]}],
        )
        self.assertEqual(
            vec3,
            [{"$rat": ["0", "1"]}, {"$rat": ["1", "3"]}, {"$rat": ["2", "1"]}],
        )

    def test_composite_encoded_type_tampering_is_rejected(self) -> None:
        encoded = encode_v3_value(
            "Option<Int>",
            VariantValueV3("Option<Int>", "Some", 1),
            self.table,
        )
        encoded["$option"]["type"] = "Option<Rat>"
        with self.assertRaises(TevScriptError) as captured:
            decode_v3_value("Option<Int>", encoded, self.table)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_VALUE_INVALID")


class IrV3TypeTableTests(unittest.TestCase):
    def test_record_cycle_through_option_is_rejected(self) -> None:
        program = {
            "boundary": {"maximum_value_nesting": 128},
            "types": [
                {"type_id":"Bool","kind":"primitive"},
                {"type_id":"Int","kind":"primitive"},
                {"type_id":"Option<Root.Node>","kind":"option","argument":"Root.Node"},
                {"type_id":"Rat","kind":"primitive"},
                {"type_id":"Root.Node","kind":"record","fields":[{"name":"next","type":"Option<Root.Node>"}]},
                {"type_id":"Text","kind":"primitive"},
                {"type_id":"Unit","kind":"unit"},
                {"type_id":"Vec2","kind":"primitive"},
                {"type_id":"Vec3","kind":"primitive"},
            ],
        }
        with self.assertRaises(TevScriptError) as captured:
            build_type_table_v3(program)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_CONTRACT")
        self.assertIn("recursive record dependency", captured.exception.diagnostic.message)

    def test_nested_unit_is_rejected(self) -> None:
        program = {
            "boundary": {"maximum_value_nesting": 128},
            "types": [
                {"type_id":"Bool","kind":"primitive"},
                {"type_id":"Int","kind":"primitive"},
                {"type_id":"Option<Unit>","kind":"option","argument":"Unit"},
                {"type_id":"Rat","kind":"primitive"},
                {"type_id":"Text","kind":"primitive"},
                {"type_id":"Unit","kind":"unit"},
                {"type_id":"Vec2","kind":"primitive"},
                {"type_id":"Vec3","kind":"primitive"},
            ],
        }
        with self.assertRaises(TevScriptError) as captured:
            build_type_table_v3(program)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_CONTRACT")


if __name__ == "__main__":
    unittest.main()
