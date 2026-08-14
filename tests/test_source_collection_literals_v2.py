from __future__ import annotations

import unittest
from fractions import Fraction

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_values import ListValueV4, MapValueV4, RecordValueV4, SetValueV4, VariantValueV4
from tev_script.source_collection_literals_v2 import parse_contextual_literal_v2

def _table():
    from tev_script.ir_v4_values import build_type_table_v4
    types = [
        {"type_id":"Bool","kind":"primitive"},
        {"type_id":"Int","kind":"primitive"},
        {"type_id":"List<Int,4>","kind":"list","element_type":"Int","capacity":4,"order_policy":"sequence"},
        {"type_id":"Map<Text,Option<Int>,4>","kind":"map","key_type":"Text","value_type":"Option<Int>","capacity":4,"order_policy":"canonical_key_bytes"},
        {"type_id":"Option<Int>","kind":"option","argument":"Int"},
        {"type_id":"Rat","kind":"primitive"},
        {"type_id":"Root.Bag","kind":"record","fields":[{"name":"colors","type":"Set<Root.Color,4>"},{"name":"values","type":"List<Int,4>"}]},
        {"type_id":"Root.Color","kind":"enum","variants":["Blue","Red"]},
        {"type_id":"Set<Root.Color,4>","kind":"set","element_type":"Root.Color","capacity":4,"order_policy":"canonical_value_bytes"},
        {"type_id":"Set<Text,4>","kind":"set","element_type":"Text","capacity":4,"order_policy":"canonical_value_bytes"},
        {"type_id":"Text","kind":"primitive"},
        {"type_id":"Unit","kind":"unit"},
        {"type_id":"Vec2","kind":"primitive"},
        {"type_id":"Vec3","kind":"primitive"},
    ]
    return build_type_table_v4({"boundary":{"maximum_value_nesting":16},"types":types})


class SourceCollectionLiteralV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def test_list_literal_uses_expected_capacity_without_inference(self) -> None:
        parsed = parse_contextual_literal_v2("[1, 2, -3]", "List<Int,4>", self.table)
        self.assertEqual(parsed.type_id, "List<Int,4>")
        self.assertEqual(parsed.value, ListValueV4("List<Int,4>", (1, 2, -3)))
        self.assertEqual(parsed.encoded["$list"]["type"], "List<Int,4>")

    def test_empty_collection_is_valid_only_because_context_supplies_identity(self) -> None:
        parsed = parse_contextual_literal_v2("[]", "List<Int,4>", self.table)
        self.assertEqual(parsed.value.items, ())
        with self.assertRaises(TevScriptError):
            parse_contextual_literal_v2("[]", "", self.table)

    def test_set_literal_is_order_independent_and_hash_stable(self) -> None:
        a = parse_contextual_literal_v2("set{Root.Color::Red, Root.Color::Blue}", "Set<Root.Color,4>", self.table)
        b = parse_contextual_literal_v2("set{Color::Blue, Color::Red}", "Set<Root.Color,4>", self.table)
        self.assertEqual(a.encoded, b.encoded)
        self.assertEqual(a.semantic_hash, b.semantic_hash)

    def test_map_literal_is_contextual_recursive_and_canonical(self) -> None:
        a = parse_contextual_literal_v2('map{"b": Some(2), "a": None}', "Map<Text,Option<Int>,4>", self.table)
        b = parse_contextual_literal_v2('map{"a": None, "b": Some(2)}', "Map<Text,Option<Int>,4>", self.table)
        self.assertIsInstance(a.value, MapValueV4)
        self.assertEqual(a.encoded, b.encoded)
        self.assertEqual(a.semantic_hash, b.semantic_hash)
        self.assertEqual([row["key"] for row in a.encoded["$map"]["entries"]], ["a", "b"])

    def test_record_can_embed_collection_literals_in_arbitrary_surface_field_order(self) -> None:
        text = 'Bag(values=[1,2], colors=set{Color::Red})'
        parsed = parse_contextual_literal_v2(text, "Root.Bag", self.table)
        self.assertIsInstance(parsed.value, RecordValueV4)
        self.assertEqual([f["name"] for f in parsed.encoded["$record"]["fields"]], ["colors", "values"])

    def test_scalar_and_vector_values_follow_expected_types(self) -> None:
        rat = parse_contextual_literal_v2("1.25", "Rat", self.table)
        vec = parse_contextual_literal_v2("vec2(1, -0.5)", "Vec2", self.table)
        self.assertEqual(rat.value, Fraction(5, 4))
        self.assertEqual(vec.value, (Fraction(1, 1), Fraction(-1, 2)))

    def test_overflow_duplicate_and_wrong_nested_type_fail_closed(self) -> None:
        for text, type_id in [
            ("[1,2,3,4,5]", "List<Int,4>"),
            ('set{"a","a"}', "Set<Text,4>"),
            ('map{"a": Some("bad")}', "Map<Text,Option<Int>,4>"),
        ]:
            with self.subTest(text=text):
                with self.assertRaises(TevScriptError):
                    parse_contextual_literal_v2(text, type_id, self.table)

    def test_nominal_tamper_and_trailing_tokens_fail_closed(self) -> None:
        for text, type_id in [
            ("Other::Red", "Root.Color"),
            ("[1] garbage", "List<Int,4>"),
            ("Bag(values=[1])", "Root.Bag"),
        ]:
            with self.subTest(text=text):
                with self.assertRaises(TevScriptError):
                    parse_contextual_literal_v2(text, type_id, self.table)


if __name__ == "__main__":
    unittest.main()
