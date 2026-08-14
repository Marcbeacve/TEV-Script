from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.generic_types_v2 import GenericRegistryV2


def _base_program():
    return {
        "boundary": {"maximum_value_nesting": 32},
        "types": [
            {"type_id":"Bool","kind":"primitive"},
            {"type_id":"Int","kind":"primitive"},
            {"type_id":"Rat","kind":"primitive"},
            {"type_id":"Text","kind":"primitive"},
            {"type_id":"Unit","kind":"unit"},
            {"type_id":"Vec2","kind":"primitive"},
            {"type_id":"Vec3","kind":"primitive"},
        ],
    }


class GenericTypesV2Tests(unittest.TestCase):
    def test_basic_box_monomorphizes_to_hash_bound_nominal_record(self) -> None:
        registry = GenericRegistryV2(_base_program())
        template = registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        resolved = registry.resolve_source_type("Box<Int>")
        self.assertEqual(resolved.kind, "user_generic")
        self.assertTrue(resolved.type_id.startswith("Root.Box__g_"))
        inst = registry.instantiate(template, ("Int",))
        self.assertEqual(inst.runtime_type_id, resolved.type_id)
        self.assertEqual(len(inst.template_hash), 64)
        self.assertEqual(len(inst.instantiation_hash), 64)
        descriptor = registry.table.require(inst.runtime_type_id)
        self.assertEqual(descriptor.kind, "record")
        self.assertEqual(descriptor.fields, (("value", "Int"),))

    def test_same_instantiation_is_cached_and_surface_whitespace_is_irrelevant(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        a = registry.resolve_source_type("Box<Int>")
        b = registry.resolve_source_type("  Box < Int >  ")
        self.assertEqual(a.type_id, b.type_id)
        self.assertEqual(registry.instantiation_count, 1)

    def test_different_type_arguments_produce_different_runtime_nominals(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        int_box = registry.resolve_source_type("Box<Int>")
        text_box = registry.resolve_source_type("Box<Text>")
        self.assertNotEqual(int_box.type_id, text_box.type_id)
        self.assertEqual(registry.instantiation_count, 2)

    def test_template_identity_changes_runtime_id_when_semantics_change(self) -> None:
        left = GenericRegistryV2(_base_program())
        right = GenericRegistryV2(_base_program())
        a = left.register_record("Root", "Box", ("T",), (("value", "T"),))
        b = right.register_record("Root", "Box", ("T",), (("value", "Option<T>"),))
        self.assertNotEqual(a.template_hash, b.template_hash)
        self.assertNotEqual(left.resolve_source_type("Box<Int>").type_id, right.resolve_source_type("Box<Int>").type_id)

    def test_parameter_alpha_renaming_preserves_template_and_instantiation_identity(self) -> None:
        left = GenericRegistryV2(_base_program())
        right = GenericRegistryV2(_base_program())
        a = left.register_record("Root", "Box", ("T",), (("value", "List<T,4>"),))
        b = right.register_record("Root", "Box", ("U",), (("value", "List<U,4>"),))
        self.assertEqual(a.template_hash, b.template_hash)
        self.assertEqual(left.resolve_source_type("Box<Int>").type_id, right.resolve_source_type("Box<Int>").type_id)

    def test_constructed_field_types_are_materialized_into_v4(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Bucket", ("T",), (("items", "List<Option<T>,4>"),))
        resolved = registry.resolve_source_type("Bucket<Int>")
        descriptor = registry.table.require(resolved.type_id)
        self.assertEqual(descriptor.fields[0][1], "List<Option<Int>,4>")
        self.assertEqual(registry.table.require("Option<Int>").kind, "option")
        self.assertEqual(registry.table.require("List<Option<Int>,4>").capacity, 4)

    def test_nested_user_generic_application_is_monomorphized_recursively(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        registry.register_record("Root", "Pair", ("A", "B"), (("left", "A"), ("right", "B")))
        resolved = registry.resolve_source_type("Pair<Box<Int>,Text>")
        pair = registry.table.require(resolved.type_id)
        left_type = dict(pair.fields)["left"]
        self.assertTrue(left_type.startswith("Root.Box__g_"))
        self.assertEqual(registry.table.require(left_type).fields, (("value", "Int"),))

    def test_materialize_source_type_closes_nested_generic_arguments_leaf_first(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        resolved = registry.materialize_source_type("Box<Option<Int>>")
        self.assertEqual(registry.table.require("Option<Int>").kind, "option")
        box = registry.table.require(resolved.type_id)
        self.assertEqual(box.fields, (("value", "Option<Int>"),))

    def test_template_field_can_reference_an_earlier_generic(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        registry.register_record("Root", "Wrapper", ("T",), (("box", "Box<T>"),))
        wrapper = registry.resolve_source_type("Wrapper<Int>")
        box_type = dict(registry.table.require(wrapper.type_id).fields)["box"]
        self.assertTrue(box_type.startswith("Root.Box__g_"))

    def test_recursive_generic_instantiation_fails_closed_without_poisoning_registry(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Node", ("T",), (("next", "Option<Node<T>>"),))
        before = registry.type_descriptors()
        with self.assertRaises(TevScriptError) as captured:
            registry.resolve_source_type("Node<Int>")
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_GENERIC_RECURSION")
        self.assertEqual(registry.type_descriptors(), before)
        self.assertEqual(registry.instantiation_count, 0)

    def test_unit_substitution_fails_v4_storability_and_rolls_back(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        before = registry.type_descriptors()
        with self.assertRaises(TevScriptError):
            registry.resolve_source_type("Box<Unit>")
        self.assertEqual(registry.type_descriptors(), before)
        self.assertEqual(registry.instantiation_count, 0)

    def test_instantiation_budget_is_bounded(self) -> None:
        registry = GenericRegistryV2(_base_program(), max_instantiations=2)
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        registry.resolve_source_type("Box<Int>")
        registry.resolve_source_type("Box<Text>")
        with self.assertRaises(TevScriptError) as captured:
            registry.resolve_source_type("Box<Rat>")
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_GENERIC_BUDGET")

    def test_generic_record_literal_lowers_directly_from_source_type_context(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        parsed = registry.parse_literal("Box<Int>", "Box(value=7)")
        self.assertTrue(parsed.type_id.startswith("Root.Box__g_"))
        self.assertEqual(parsed.encoded["$record"]["fields"][0]["value"], {"$int": "7"})

    def test_generic_literal_can_embed_collection_and_nested_generic_values(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        registry.register_record("Root", "Bucket", ("T",), (("items", "List<T,4>"),))
        registry.register_record("Root", "Wrapper", ("T",), (("box", "Box<T>"),))
        bucket = registry.parse_literal("Bucket<Int>", "Bucket(items=[1,2,3])")
        wrapper = registry.parse_literal("Wrapper<Int>", "Wrapper(box=Box(value=9))")
        self.assertEqual(bucket.encoded["$record"]["fields"][0]["value"]["$list"]["items"][1], {"$int": "2"})
        inner = wrapper.encoded["$record"]["fields"][0]["value"]
        self.assertIn("$record", inner)

    def test_generic_constructor_alias_is_context_bound_and_tamper_rejected(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        a = registry.parse_literal("Box<Int>", "Box(value=1)")
        b = registry.parse_literal("Root.Box<Int>", "Root.Box(value=1)")
        self.assertEqual(a.semantic_hash, b.semantic_hash)
        with self.assertRaises(TevScriptError):
            registry.parse_literal("Box<Int>", "Other(value=1)")

    def test_undeclared_or_wrong_arity_generic_remains_fail_closed(self) -> None:
        registry = GenericRegistryV2(_base_program())
        registry.register_record("Root", "Box", ("T",), (("value", "T"),))
        for source in ("Unknown<Int>", "Box<Int,Text>", "Box<>"):
            with self.subTest(source=source):
                with self.assertRaises(TevScriptError):
                    registry.resolve_source_type(source)


if __name__ == "__main__":
    unittest.main()
