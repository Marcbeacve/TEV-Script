from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_values import ListValueV4, MapValueV4, RecordValueV4, SetValueV4, VariantValueV4
from tev_script.source_collection_literals_v2 import parse_contextual_literal_v2
from tev_script.source_for_in_v2 import parse_for_in_header_v2, plan_for_in_v2

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


class SourceForInV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def test_list_for_in_has_static_capacity_bound_and_sequence_order(self) -> None:
        value = parse_contextual_literal_v2("[3,1,2]", "List<Int,4>", self.table).value
        plan = plan_for_in_v2(parse_for_in_header_v2("for x in xs"), value, self.table)
        self.assertEqual(plan.binding_types, ("Int",))
        self.assertEqual(plan.maximum_iterations, 4)
        self.assertEqual(plan.actual_iterations, 3)
        self.assertEqual(plan.rows, ((3,), (1,), (2,)))
        self.assertEqual(plan.order_policy, "sequence")

    def test_set_for_in_is_canonical_not_insertion_order(self) -> None:
        a = parse_contextual_literal_v2('set{"b","a"}', "Set<Text,4>", self.table).value
        b = parse_contextual_literal_v2('set{"a","b"}', "Set<Text,4>", self.table).value
        header = parse_for_in_header_v2("for item in values")
        pa = plan_for_in_v2(header, a, self.table)
        pb = plan_for_in_v2(header, b, self.table)
        self.assertEqual(pa.rows, pb.rows)
        self.assertEqual(pa.witness_hash, pb.witness_hash)
        self.assertEqual(pa.maximum_iterations, 4)

    def test_map_for_in_requires_two_bindings_and_uses_canonical_key_order(self) -> None:
        value = parse_contextual_literal_v2('map{"b": Some(2), "a": None}', "Map<Text,Option<Int>,4>", self.table).value
        plan = plan_for_in_v2(parse_for_in_header_v2("for (key, value) in readings"), value, self.table)
        self.assertEqual(plan.binding_types, ("Text", "Option<Int>"))
        self.assertEqual(tuple(row[0] for row in plan.rows), ("a", "b"))
        with self.assertRaises(TevScriptError):
            plan_for_in_v2(parse_for_in_header_v2("for item in readings"), value, self.table)

    def test_binding_arity_and_duplicate_binding_fail_closed(self) -> None:
        value = parse_contextual_literal_v2("[1]", "List<Int,4>", self.table).value
        with self.assertRaises(TevScriptError):
            plan_for_in_v2(parse_for_in_header_v2("for (x, y) in xs"), value, self.table)
        with self.assertRaises(TevScriptError):
            parse_for_in_header_v2("for (x, x) in xs")

    def test_non_collection_source_fails_closed(self) -> None:
        record = parse_contextual_literal_v2('Bag(values=[], colors=set{})', "Root.Bag", self.table).value
        with self.assertRaises(TevScriptError):
            plan_for_in_v2(parse_for_in_header_v2("for x in bag"), record, self.table)  # type: ignore[arg-type]

    def test_header_is_format_insensitive_but_not_grammar_ambiguous(self) -> None:
        self.assertEqual(parse_for_in_header_v2("  for ( k , v ) in data  ").bindings, ("k", "v"))
        for bad in ["for x data", "while x in data", "for x,y in data", "for () in data"]:
            with self.subTest(bad=bad):
                with self.assertRaises(TevScriptError):
                    parse_for_in_header_v2(bad)


if __name__ == "__main__":
    unittest.main()
