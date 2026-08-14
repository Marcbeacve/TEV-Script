from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_collections import (
    collection_length,
    list_get,
    list_items,
    list_push,
    list_set,
    map_entries,
    map_lookup,
    map_put,
    set_add,
    set_contains,
    set_items,
)
from tev_script.ir_v4_values import (
    ListValueV4,
    MapValueV4,
    SetValueV4,
    VariantValueV4,
    build_type_table_v4,
    encode_v4_value,
)


def _table():
    types = [
        {"type_id":"Bool","kind":"primitive"},
        {"type_id":"Int","kind":"primitive"},
        {"type_id":"List<Int,2>","kind":"list","element_type":"Int","capacity":2,"order_policy":"sequence"},
        {"type_id":"Map<Text,Option<Int>,2>","kind":"map","key_type":"Text","value_type":"Option<Int>","capacity":2,"order_policy":"canonical_key_bytes"},
        {"type_id":"Option<Int>","kind":"option","argument":"Int"},
        {"type_id":"Rat","kind":"primitive"},
        {"type_id":"Set<Int,2>","kind":"set","element_type":"Int","capacity":2,"order_policy":"canonical_value_bytes"},
        {"type_id":"Text","kind":"primitive"},
        {"type_id":"Unit","kind":"unit"},
        {"type_id":"Vec2","kind":"primitive"},
        {"type_id":"Vec3","kind":"primitive"},
    ]
    types.sort(key=lambda x:x["type_id"])
    return build_type_table_v4({"boundary":{"maximum_value_nesting":128},"types":types})


class IrV4CollectionOperationsTests(unittest.TestCase):
    def setUp(self):
        self.table=_table()

    def test_list_operations_are_persistent_bounded_and_typed(self):
        a=ListValueV4("List<Int,2>")
        b=list_push(a,1,self.table)
        c=list_push(b,2,self.table)
        self.assertEqual(a.items,())
        self.assertEqual(c.items,(1,2))
        self.assertEqual(list_get(c,1,self.table),2)
        d=list_set(c,0,9,self.table)
        self.assertEqual(d.items,(9,2)); self.assertEqual(c.items,(1,2))
        self.assertEqual(list_items(c,self.table),(1,2))
        self.assertEqual(collection_length(c,self.table),2)
        with self.assertRaises(TevScriptError): list_push(c,3,self.table)
        with self.assertRaises(TevScriptError): list_get(c,2,self.table)
        with self.assertRaises(TevScriptError): list_set(c,0,True,self.table)

    def test_set_is_idempotent_and_iteration_is_canonical_not_insertion_order(self):
        a=SetValueV4("Set<Int,2>")
        b=set_add(a,2,self.table)
        c=set_add(b,10,self.table)
        d=set_add(c,2,self.table)
        self.assertIs(c,d)
        self.assertTrue(set_contains(c,2,self.table)); self.assertFalse(set_contains(c,7,self.table))
        # TEV canonical wire bytes order $int "10" before $int "2".
        self.assertEqual(set_items(c,self.table),(10,2))
        self.assertEqual(collection_length(c,self.table),2)
        with self.assertRaises(TevScriptError): set_add(c,3,self.table)
        with self.assertRaises(TevScriptError): set_add(c,True,self.table)

    def test_map_update_lookup_and_iteration_have_explicit_presence_and_canonical_order(self):
        none=VariantValueV4("Option<Int>","None")
        some=VariantValueV4("Option<Int>","Some",4)
        a=MapValueV4("Map<Text,Option<Int>,2>")
        b=map_put(a,"b",none,self.table)
        c=map_put(b,"a",some,self.table)
        self.assertEqual(a.entries,())
        found=map_lookup(c,"a",self.table)
        missing=map_lookup(c,"z",self.table)
        self.assertTrue(found.found); self.assertEqual(found.value,some)
        self.assertFalse(missing.found)
        self.assertEqual(tuple(key for key,_ in map_entries(c,self.table)),("a","b"))
        self.assertEqual(collection_length(c,self.table),2)
        updated=map_put(c,"a",VariantValueV4("Option<Int>","Some",9),self.table)
        self.assertEqual(map_lookup(updated,"a",self.table).value.payload,9)
        self.assertEqual(map_lookup(c,"a",self.table).value.payload,4)
        with self.assertRaises(TevScriptError): map_put(c,"c",some,self.table)
        with self.assertRaises(TevScriptError): map_put(c,1,some,self.table)

    def test_semantically_equal_set_and_map_orders_encode_identically(self):
        set_a=SetValueV4("Set<Int,2>",(2,10))
        set_b=SetValueV4("Set<Int,2>",(10,2))
        self.assertEqual(encode_v4_value(set_a.type_id,set_a,self.table),encode_v4_value(set_b.type_id,set_b,self.table))
        none=VariantValueV4("Option<Int>","None")
        map_a=MapValueV4("Map<Text,Option<Int>,2>",(("b",none),("a",none)))
        map_b=MapValueV4("Map<Text,Option<Int>,2>",(("a",none),("b",none)))
        self.assertEqual(encode_v4_value(map_a.type_id,map_a,self.table),encode_v4_value(map_b.type_id,map_b,self.table))


if __name__ == "__main__": unittest.main()
