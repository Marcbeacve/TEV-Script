from __future__ import annotations

import json
import unittest
from pathlib import Path

from tev_script.canonical import canonical_hash, canonical_json
from tev_script.diagnostics import TevScriptError
from tev_script.json_io import parse_strict_json
from tev_script.values import decode_typed_value, encode_typed_value

ROOT = Path(__file__).resolve().parents[1]


class CanonicalTests(unittest.TestCase):
    def test_normative_vectors(self) -> None:
        document = json.loads(
            (ROOT / "conformance" / "canonical.vectors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(document["profile"], "TEV_CANONICAL_JSON_V1")
        for vector in document["vectors"]:
            with self.subTest(vector=vector["id"]):
                self.assertEqual(canonical_json(vector["value"]), vector["canonical"])
                self.assertEqual(canonical_hash(vector["value"]), vector["sha256"])

    def test_structural_integer_outside_safe_range_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "portable safe range"):
            canonical_json(2**53)

    def test_strict_json_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(TevScriptError, "TEVS_JSON_DUPLICATE_KEY"):
            parse_strict_json('{"a":1,"a":2}')

    def test_strict_json_rejects_floats(self) -> None:
        with self.assertRaisesRegex(TevScriptError, "TEVS_JSON_FLOAT_FORBIDDEN"):
            parse_strict_json('{"a":1.0}')

    def test_strict_json_rejects_out_of_range_structural_integer(self) -> None:
        with self.assertRaisesRegex(TevScriptError, "TEVS_JSON_NUMBER_RANGE"):
            parse_strict_json('{"a":9007199254740992}')

    def test_strict_json_rejects_negative_zero(self) -> None:
        with self.assertRaisesRegex(TevScriptError, "TEVS_JSON_NEGATIVE_ZERO"):
            parse_strict_json('{"a":-0}')

    def test_strict_json_accepts_tagged_large_integer(self) -> None:
        self.assertEqual(
            parse_strict_json('{"value":{"$int":"9007199254740992"}}'),
            {"value": {"$int": "9007199254740992"}},
        )


    def test_non_string_object_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(TypeError, "keys must be strings"):
            canonical_json({1: "forbidden"})

    def test_noncanonical_semantic_integer_is_rejected(self) -> None:
        for text in ("+1", "01", "-0"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(TevScriptError, "TEVS_RUNTIME_INT"):
                    decode_typed_value("Int", {"$int": text})

    def test_lossy_python_numeric_values_are_rejected(self) -> None:
        with self.assertRaises(TypeError):
            encode_typed_value("Int", 1.0)
        with self.assertRaises(TypeError):
            encode_typed_value("Rat", 0.5)


if __name__ == "__main__":
    unittest.main()
