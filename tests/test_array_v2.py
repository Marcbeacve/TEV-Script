from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.generic_functions_v2 import GenericPureFunctionRegistryV2
from tev_script.generic_types_v2 import GenericRegistryV2
from tev_script.ir_v4_collections import array_get, array_items, array_set, collection_length, list_push
from tev_script.ir_v4_pure import evaluate_pure_v4, hash_type_table_v4, validate_pure_v4
from tev_script.ir_v4_values import ArrayValueV4, ListValueV4, build_type_table_v4, decode_v4_value, encode_v4_value, v4_values_equal
from tev_script.source_collection_literals_v2 import parse_contextual_literal_v2
from tev_script.source_for_in_v2 import parse_for_in_header_v2, plan_for_in_v2
from tev_script.source_types_v2 import parse_type_ref_v2, resolve_type_ref_v2


def _base_types():
    return [
        {"type_id":"Array<Int,3>","kind":"array","element_type":"Int","length":3,"order_policy":"sequence"},
        {"type_id":"Array<Int,4>","kind":"array","element_type":"Int","length":4,"order_policy":"sequence"},
        {"type_id":"Bool","kind":"primitive"},
        {"type_id":"Int","kind":"primitive"},
        {"type_id":"List<Int,4>","kind":"list","element_type":"Int","capacity":4,"order_policy":"sequence"},
        {"type_id":"Rat","kind":"primitive"},
        {"type_id":"Text","kind":"primitive"},
        {"type_id":"Unit","kind":"unit"},
        {"type_id":"Vec2","kind":"primitive"},
        {"type_id":"Vec3","kind":"primitive"},
    ]


def _table():
    return build_type_table_v4({"boundary":{"maximum_value_nesting":32},"types":_base_types()})


def _program():
    return {"boundary":{"maximum_value_nesting":32},"types":[item for item in _base_types() if not item["type_id"].startswith("Array<") and not item["type_id"].startswith("List<")]}


def cint(value:int):
    return {"op":"CONST","type":"Int","value":{"$int":str(value)}}


def param(name:str,type_id:str):
    return {"op":"PARAM","name":name,"type":type_id}


class ArrayV4ValueTests(unittest.TestCase):
    def setUp(self): self.table=_table()

    def test_array_descriptor_binds_kind_element_length_and_sequence_policy(self):
        d=self.table.require("Array<Int,4>")
        self.assertEqual(d.kind,"array")
        self.assertEqual(d.element_type,"Int")
        self.assertEqual(d.length,4)
        self.assertIsNone(d.capacity)
        self.assertEqual(d.order_policy,"sequence")
        self.assertNotEqual(hash_type_table_v4(self.table),hash_type_table_v4(build_type_table_v4({"boundary":{"maximum_value_nesting":32},"types":[item for item in _base_types() if item["type_id"]!="Array<Int,4>"]})))

    def test_array_roundtrip_uses_distinct_array_wire_format(self):
        value=ArrayValueV4("Array<Int,4>",(1,2,3,4))
        encoded=encode_v4_value("Array<Int,4>",value,self.table)
        self.assertEqual(encoded,{"$array":{"type":"Array<Int,4>","items":[{"$int":"1"},{"$int":"2"},{"$int":"3"},{"$int":"4"}]}})
        self.assertEqual(decode_v4_value("Array<Int,4>",encoded,self.table),value)
        with self.assertRaises(TevScriptError): decode_v4_value("List<Int,4>",encoded,self.table)

    def test_array_requires_exact_length_both_short_and_long(self):
        for items in ((1,2,3),(1,2,3,4,5)):
            with self.subTest(items=items):
                with self.assertRaises(TevScriptError):
                    encode_v4_value("Array<Int,4>",ArrayValueV4("Array<Int,4>",items),self.table)
        # The exact same short payload remains legal as a bounded List.
        encoded=encode_v4_value("List<Int,4>",ListValueV4("List<Int,4>",(1,2,3)),self.table)
        self.assertEqual(len(encoded["$list"]["items"]),3)

    def test_array_structural_equality_is_exact_and_never_list_equality(self):
        a=ArrayValueV4("Array<Int,4>",(1,2,3,4))
        b=ArrayValueV4("Array<Int,4>",(1,2,3,4))
        c=ArrayValueV4("Array<Int,4>",(1,2,3,9))
        self.assertTrue(v4_values_equal("Array<Int,4>",a,b,self.table))
        self.assertFalse(v4_values_equal("Array<Int,4>",a,c,self.table))
        self.assertFalse(v4_values_equal("Array<Int,4>",a,ListValueV4("List<Int,4>",(1,2,3,4)),self.table))

    def test_descriptor_cannot_smuggle_array_as_capacity_or_wrong_policy(self):
        base=[item for item in _base_types() if item["type_id"]!="Array<Int,4>"]
        bads=[
            {"type_id":"Array<Int,4>","kind":"array","element_type":"Int","capacity":4,"order_policy":"sequence"},
            {"type_id":"Array<Int,4>","kind":"array","element_type":"Int","length":3,"order_policy":"sequence"},
            {"type_id":"Array<Int,4>","kind":"array","element_type":"Int","length":4,"order_policy":"canonical_value_bytes"},
        ]
        for bad in bads:
            with self.subTest(bad=bad):
                with self.assertRaises(TevScriptError):
                    build_type_table_v4({"boundary":{"maximum_value_nesting":32},"types":sorted([*base,bad],key=lambda x:x["type_id"])})


class ArrayV4OperationsTests(unittest.TestCase):
    def setUp(self): self.table=_table(); self.value=ArrayValueV4("Array<Int,4>",(1,2,3,4))

    def test_array_get_set_len_and_items_are_exact_and_persistent(self):
        self.assertEqual(array_get(self.value,2,self.table),3)
        changed=array_set(self.value,2,9,self.table)
        self.assertEqual(changed.items,(1,2,9,4))
        self.assertEqual(self.value.items,(1,2,3,4))
        self.assertEqual(array_items(changed,self.table),(1,2,9,4))
        self.assertEqual(collection_length(changed,self.table),4)

    def test_array_index_and_item_type_fail_closed(self):
        for index in (-1,4,True):
            with self.subTest(index=index):
                with self.assertRaises(TevScriptError): array_get(self.value,index,self.table)
        with self.assertRaises(TevScriptError): array_set(self.value,0,"bad",self.table)

    def test_list_push_cannot_be_reused_as_array_push(self):
        with self.assertRaises(TevScriptError):
            list_push(self.value,5,self.table)  # type: ignore[arg-type]


class ArraySourceV2Tests(unittest.TestCase):
    def setUp(self): self.table=_table()

    def test_source_type_resolves_array_length_not_list_capacity(self):
        array=resolve_type_ref_v2(parse_type_ref_v2("Array<Int,4>"))
        listing=resolve_type_ref_v2(parse_type_ref_v2("List<Int,4>"))
        self.assertEqual(array.kind,"array")
        self.assertEqual(array.array_length,4)
        self.assertIsNone(array.collection_capacity)
        self.assertEqual(listing.collection_capacity,4)
        self.assertIsNone(listing.array_length)
        self.assertNotEqual(array.type_id,listing.type_id)

    def test_contextual_bracket_literal_distinguishes_array_from_list(self):
        array=parse_contextual_literal_v2("[1,2,3,4]","Array<Int,4>",self.table)
        listing=parse_contextual_literal_v2("[1,2,3]","List<Int,4>",self.table)
        self.assertIsInstance(array.value,ArrayValueV4)
        self.assertIsInstance(listing.value,ListValueV4)
        with self.assertRaises(TevScriptError): parse_contextual_literal_v2("[1,2,3]","Array<Int,4>",self.table)
        with self.assertRaises(TevScriptError): parse_contextual_literal_v2("[]","Array<Int,4>",self.table)

    def test_array_for_in_has_exact_static_and_actual_iteration_count(self):
        value=parse_contextual_literal_v2("[3,1,2,4]","Array<Int,4>",self.table).value
        plan=plan_for_in_v2(parse_for_in_header_v2("for x in xs"),value,self.table)
        self.assertEqual(plan.binding_types,("Int",))
        self.assertEqual(plan.maximum_iterations,4)
        self.assertEqual(plan.actual_iterations,4)
        self.assertEqual(plan.order_policy,"sequence")
        self.assertEqual(plan.rows,((3,),(1,),(2,),(4,)))


class ArrayPureKernelTests(unittest.TestCase):
    def setUp(self): self.table=_table()

    def _array(self): return {"op":"ARRAY","type":"Array<Int,4>","items":[cint(1),cint(2),cint(3),cint(4)]}

    def test_array_constructor_get_set_and_len_execute(self):
        changed={"op":"ARRAY_SET","collection_type":"Array<Int,4>","collection":self._array(),"index":cint(1),"item":cint(9)}
        get={"op":"ARRAY_GET","collection_type":"Array<Int,4>","result_type":"Int","collection":changed,"index":cint(1)}
        self.assertEqual(evaluate_pure_v4(get,self.table).result_encoded,{"$int":"9"})
        self.assertEqual(evaluate_pure_v4({"op":"LEN","collection_type":"Array<Int,4>","collection":changed},self.table).result_encoded,{"$int":"4"})

    def test_pure_array_constructor_requires_exact_length_statically(self):
        short={"op":"ARRAY","type":"Array<Int,4>","items":[cint(1),cint(2),cint(3)]}
        with self.assertRaises(TevScriptError): validate_pure_v4(short,self.table)
        with self.assertRaises(TevScriptError): evaluate_pure_v4(short,self.table)

    def test_list_push_opcode_rejects_array_kind(self):
        expr={"op":"LIST_PUSH","collection_type":"Array<Int,4>","collection":self._array(),"item":cint(5)}
        with self.assertRaises(TevScriptError): validate_pure_v4(expr,self.table)

    def test_pure_binary_equality_accepts_arrays_of_same_exact_type(self):
        left=self._array()
        right={"op":"ARRAY","type":"Array<Int,4>","items":[cint(1),cint(2),cint(3),cint(4)]}
        expr={"op":"BINARY","operator":"EQEQ","left_type":"Array<Int,4>","right_type":"Array<Int,4>","result_type":"Bool","left":left,"right":right}
        self.assertTrue(evaluate_pure_v4(expr,self.table).result_encoded)

    def test_array_for_fold_uses_exact_length_as_static_loop_bound(self):
        expr={
            "op":"FOR_FOLD","collection_type":"Array<Int,4>","accumulator_name":"acc","accumulator_type":"Int",
            "bindings":[{"name":"x","type":"Int"}],"collection":self._array(),"initial":cint(0),
            "body":{"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":param("acc","Int"),"right":param("x","Int")},
        }
        validation=validate_pure_v4(expr,self.table)
        receipt=evaluate_pure_v4(expr,self.table)
        self.assertEqual(receipt.result_encoded,{"$int":"10"})
        self.assertEqual(receipt.bounded_loop_iterations,4)
        self.assertGreaterEqual(validation.bounded_loop_iteration_upper_bound,4)


class ArrayGenericV2Tests(unittest.TestCase):
    def test_generic_record_can_materialize_array_field(self):
        types=GenericRegistryV2(_program())
        types.register_record("Root","Fixed",("T",),(("values","Array<T,3>"),))
        resolved=types.resolve_source_type("Fixed<Int>")
        record=types.table.require(resolved.type_id)
        array_type=dict(record.fields)["values"]
        self.assertEqual(array_type,"Array<Int,3>")
        descriptor=types.table.require(array_type)
        self.assertEqual(descriptor.kind,"array")
        self.assertEqual(descriptor.length,3)

    def test_generic_pure_function_reads_array_without_list_semantics(self):
        types=GenericRegistryV2(_program()); funcs=GenericPureFunctionRegistryV2(types)
        body={"op":"ARRAY_GET","collection_type":"Array<T,3>","result_type":"T","collection":param("xs","Array<T,3>"),"index":cint(1)}
        funcs.register("Root","middle",("T",),(('xs','Array<T,3>'),),"T",body)
        inst=funcs.instantiate("middle",("Int",))
        value=ArrayValueV4("Array<Int,3>",(4,9,7))
        self.assertEqual(funcs.call(inst,(value,)).result_encoded,{"$int":"9"})
        with self.assertRaises((TevScriptError,TypeError)):
            funcs.call(inst,(ListValueV4("List<Int,4>",(4,9,7)),))


if __name__=="__main__": unittest.main()
