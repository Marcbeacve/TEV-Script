from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_values import (
    ListValueV4,
    MapValueV4,
    RecordValueV4,
    SetValueV4,
    VariantValueV4,
    build_type_table_v4,
    decode_v4_value,
    encode_v4_value,
    v4_values_equal,
)


def _base_types() -> list[dict]:
    return [
        {"type_id": "Bool", "kind": "primitive"},
        {"type_id": "Int", "kind": "primitive"},
        {"type_id": "Rat", "kind": "primitive"},
        {"type_id": "Text", "kind": "primitive"},
        {"type_id": "Unit", "kind": "unit"},
        {"type_id": "Vec2", "kind": "primitive"},
        {"type_id": "Vec3", "kind": "primitive"},
    ]


def _program(*extra: dict, maximum_value_nesting: int = 128) -> dict:
    types = [*_base_types(), *extra]
    types.sort(key=lambda item: item["type_id"])
    return {
        "boundary": {"maximum_value_nesting": maximum_value_nesting},
        "types": types,
    }


def _rich_table():
    return build_type_table_v4(
        _program(
            {
                "type_id": "List<Int,3>",
                "kind": "list",
                "element_type": "Int",
                "capacity": 3,
                "order_policy": "sequence",
            },
            {
                "type_id": "Map<Text,Option<Int>,4>",
                "kind": "map",
                "key_type": "Text",
                "value_type": "Option<Int>",
                "capacity": 4,
                "order_policy": "canonical_key_bytes",
            },
            {"type_id": "Option<Int>", "kind": "option", "argument": "Int"},
            {
                "type_id": "Root.Bag",
                "kind": "record",
                "fields": [{"name": "items", "type": "List<Int,3>"}],
            },
            {
                "type_id": "Set<Root.Bag,4>",
                "kind": "set",
                "element_type": "Root.Bag",
                "capacity": 4,
                "order_policy": "canonical_value_bytes",
            },
        )
    )


class IrV4TypeTableTests(unittest.TestCase):
    def test_collection_descriptors_are_identity_bound(self):
        table = _rich_table()
        self.assertEqual(table.require("List<Int,3>").capacity, 3)
        self.assertEqual(table.require("Set<Root.Bag,4>").order_policy, "canonical_value_bytes")
        self.assertEqual(table.require("Map<Text,Option<Int>,4>").value_type, "Option<Int>")

    def test_wrong_policy_type_id_or_capacity_fails_closed(self):
        bad = [
            {
                "type_id": "List<Int,3>", "kind": "list", "element_type": "Int",
                "capacity": 3, "order_policy": "canonical_value_bytes",
            },
            {
                "type_id": "Set<Int,4>", "kind": "set", "element_type": "Int",
                "capacity": 3, "order_policy": "canonical_value_bytes",
            },
            {
                "type_id": "Map<Text,Int,0>", "kind": "map", "key_type": "Text",
                "value_type": "Int", "capacity": 0, "order_policy": "canonical_key_bytes",
            },
        ]
        for descriptor in bad:
            with self.subTest(descriptor=descriptor["type_id"]):
                with self.assertRaises(TevScriptError):
                    build_type_table_v4(_program(descriptor))

    def test_unit_nested_in_collection_is_rejected(self):
        descriptor = {
            "type_id": "List<Unit,2>", "kind": "list", "element_type": "Unit",
            "capacity": 2, "order_policy": "sequence",
        }
        with self.assertRaises(TevScriptError) as captured:
            build_type_table_v4(_program(descriptor))
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_CONTRACT")

    def test_shared_deep_dependency_cannot_bypass_type_nesting_limit(self):
        extras = []
        # Build an acyclic chain 127 constructed nodes deep. Root.Wrap adds two
        # additional layers through already-visited nodes; total > 128.
        for index in range(127):
            current = f"Root.A{index:03d}"
            child = "Int" if index == 126 else f"Root.A{index + 1:03d}"
            extras.append({
                "type_id": current,
                "kind": "record",
                "fields": [{"name": "next", "type": child}],
            })
        extras.append({
            "type_id": "Root.Wrap1",
            "kind": "record",
            "fields": [{"name": "next", "type": "Root.A000"}],
        })
        extras.append({
            "type_id": "Root.Wrap2",
            "kind": "record",
            "fields": [{"name": "next", "type": "Root.Wrap1"}],
        })
        with self.assertRaises(TevScriptError) as captured:
            build_type_table_v4(_program(*extras))
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_CONTRACT")
        self.assertIn("nesting exceeds 128", captured.exception.diagnostic.message)

    def test_recursive_record_through_collection_is_rejected(self):
        program = _program(
            {
                "type_id": "List<Root.Node,2>", "kind": "list", "element_type": "Root.Node",
                "capacity": 2, "order_policy": "sequence",
            },
            {
                "type_id": "Root.Node", "kind": "record",
                "fields": [{"name": "children", "type": "List<Root.Node,2>"}],
            },
        )
        with self.assertRaises(TevScriptError) as captured:
            build_type_table_v4(program)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_CONTRACT")
        self.assertIn("dependency cycle", captured.exception.diagnostic.message)


class IrV4CollectionCodecTests(unittest.TestCase):
    def setUp(self):
        self.table = _rich_table()

    def test_record_can_contain_list_roundtrip(self):
        value = RecordValueV4("Root.Bag", (("items", ListValueV4("List<Int,3>", (3, 1, 2))),))
        encoded = encode_v4_value("Root.Bag", value, self.table)
        self.assertEqual(
            encoded["$record"]["fields"][0]["value"],
            {"$list": {"type": "List<Int,3>", "items": [{"$int": "3"}, {"$int": "1"}, {"$int": "2"}]}},
        )
        decoded = decode_v4_value("Root.Bag", encoded, self.table)
        self.assertTrue(v4_values_equal("Root.Bag", value, decoded, self.table))

    def test_map_can_contain_option_and_is_insertion_order_independent(self):
        some = VariantValueV4("Option<Int>", "Some", 7)
        none = VariantValueV4("Option<Int>", "None")
        a = MapValueV4("Map<Text,Option<Int>,4>", (("b", none), ("a", some)))
        b = MapValueV4("Map<Text,Option<Int>,4>", (("a", some), ("b", none)))
        encoded_a = encode_v4_value(a.type_id, a, self.table)
        encoded_b = encode_v4_value(b.type_id, b, self.table)
        self.assertEqual(encoded_a, encoded_b)
        decoded = decode_v4_value(a.type_id, encoded_a, self.table)
        self.assertTrue(v4_values_equal(a.type_id, a, decoded, self.table))

    def test_set_of_records_is_insertion_order_independent(self):
        bag1 = RecordValueV4("Root.Bag", (("items", ListValueV4("List<Int,3>", (1,))),))
        bag2 = RecordValueV4("Root.Bag", (("items", ListValueV4("List<Int,3>", (2,))),))
        a = SetValueV4("Set<Root.Bag,4>", (bag2, bag1))
        b = SetValueV4("Set<Root.Bag,4>", (bag1, bag2))
        self.assertEqual(
            encode_v4_value(a.type_id, a, self.table),
            encode_v4_value(b.type_id, b, self.table),
        )

    def test_duplicate_set_values_and_map_keys_are_rejected(self):
        bag = RecordValueV4("Root.Bag", (("items", ListValueV4("List<Int,3>", (1,))),))
        with self.assertRaises(TevScriptError):
            encode_v4_value("Set<Root.Bag,4>", SetValueV4("Set<Root.Bag,4>", (bag, bag)), self.table)
        some = VariantValueV4("Option<Int>", "Some", 1)
        with self.assertRaises(TevScriptError):
            encode_v4_value(
                "Map<Text,Option<Int>,4>",
                MapValueV4("Map<Text,Option<Int>,4>", (("a", some), ("a", some))),
                self.table,
            )

    def test_capacity_overflow_is_rejected_at_value_boundary(self):
        with self.assertRaises(TevScriptError):
            encode_v4_value("List<Int,3>", ListValueV4("List<Int,3>", (1, 2, 3, 4)), self.table)

    def test_decode_rejects_noncanonical_set_and_map_order(self):
        bag1 = RecordValueV4("Root.Bag", (("items", ListValueV4("List<Int,3>", (1,))),))
        bag2 = RecordValueV4("Root.Bag", (("items", ListValueV4("List<Int,3>", (2,))),))
        canonical_set = encode_v4_value("Set<Root.Bag,4>", SetValueV4("Set<Root.Bag,4>", (bag1, bag2)), self.table)
        tampered_set = copy.deepcopy(canonical_set)
        tampered_set["$set"]["items"].reverse()
        if tampered_set != canonical_set:
            with self.assertRaises(TevScriptError):
                decode_v4_value("Set<Root.Bag,4>", tampered_set, self.table)

        some = VariantValueV4("Option<Int>", "Some", 1)
        canonical_map = encode_v4_value(
            "Map<Text,Option<Int>,4>",
            MapValueV4("Map<Text,Option<Int>,4>", (("a", some), ("b", some))),
            self.table,
        )
        tampered_map = copy.deepcopy(canonical_map)
        tampered_map["$map"]["entries"].reverse()
        with self.assertRaises(TevScriptError):
            decode_v4_value("Map<Text,Option<Int>,4>", tampered_map, self.table)

    def test_encoded_collection_type_tamper_is_rejected(self):
        encoded = encode_v4_value("List<Int,3>", ListValueV4("List<Int,3>", (1,)), self.table)
        encoded["$list"]["type"] = "List<Int,4>"
        with self.assertRaises(TevScriptError) as captured:
            decode_v4_value("List<Int,3>", encoded, self.table)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_VALUE_INVALID")

    def test_wrong_nested_type_fails_before_normalization(self):
        with self.assertRaises(TevScriptError):
            encode_v4_value("List<Int,3>", ListValueV4("List<Int,3>", (True,)), self.table)


if __name__ == "__main__":
    unittest.main()
