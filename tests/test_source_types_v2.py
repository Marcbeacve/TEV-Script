from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_types_v2 import (
    collection_iteration_bound,
    parse_type_ref_v2,
    resolve_type_ref_v2,
)


class SourceTypeSyntaxV2Tests(unittest.TestCase):
    def test_nested_collection_type_is_parsed_and_resolved_canonically(self):
        ref=parse_type_ref_v2("Map<Text, List<Option<Int>,32>, 128>")
        resolved=resolve_type_ref_v2(ref)
        self.assertEqual(resolved.type_id,"Map<Text,List<Option<Int>,32>,128>")
        self.assertEqual(resolved.collection_capacity,128)
        self.assertEqual(collection_iteration_bound(resolved),128)

    def test_nominal_type_resolution_flows_through_collection(self):
        ref=parse_type_ref_v2("Set<Local.Point,64>")
        resolved=resolve_type_ref_v2(ref,lambda name: "world.Point" if name=="Local.Point" else "")
        self.assertEqual(resolved.type_id,"Set<world.Point,64>")

    def test_option_and_result_remain_compatible_in_v2_type_algebra(self):
        resolved=resolve_type_ref_v2(parse_type_ref_v2("Result<Option<Int>,Text>"))
        self.assertEqual(resolved.type_id,"Result<Option<Int>,Text>")

    def test_collection_capacity_is_part_of_identity(self):
        a=resolve_type_ref_v2(parse_type_ref_v2("List<Int,4>"))
        b=resolve_type_ref_v2(parse_type_ref_v2("List<Int,8>"))
        self.assertNotEqual(a.type_id,b.type_id)

    def test_unit_is_not_storable_in_collection(self):
        with self.assertRaises(TevScriptError):
            resolve_type_ref_v2(parse_type_ref_v2("List<Unit,2>"))

    def test_non_collection_has_no_iteration_bound(self):
        with self.assertRaises(TevScriptError):
            collection_iteration_bound(resolve_type_ref_v2(parse_type_ref_v2("Int")))

    def test_user_generic_is_fail_closed_until_declaration_system_exists(self):
        with self.assertRaises(TevScriptError) as captured:
            parse_type_ref_v2("Box<Int>")
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_USER_GENERIC_NOT_DECLARED")

    def test_bad_arity_capacity_and_tokens_fail_closed(self):
        cases=(
            "Option",
            "Result<Int>",
            "List<Int,0>",
            "List<Int,4097>",
            "Map<Text,Int>",
            "Map<Text,Int,2,3>",
            "List<Int,-1>",
            "List<Int,2>>",
        )
        for text in cases:
            with self.subTest(text=text):
                with self.assertRaises(TevScriptError):
                    parse_type_ref_v2(text)

    def test_whitespace_is_surface_only(self):
        compact=resolve_type_ref_v2(parse_type_ref_v2("Map<Text,List<Int,2>,4>"))
        spaced=resolve_type_ref_v2(parse_type_ref_v2("  Map < Text , List < Int , 2 > , 4 >  "))
        self.assertEqual(compact,spaced)


if __name__ == "__main__": unittest.main()
