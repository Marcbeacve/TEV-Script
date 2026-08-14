import unittest

from tev_script.diagnostics import TevScriptError
from fractions import Fraction

from tev_script.semantic_collections_v2 import CollectionTypeV2, ListValueV2, MapValueV2, SetValueV2


class CollectionV2Tests(unittest.TestCase):
    def test_type_identity_binds_capacity_and_order_policy(self):
        self.assertEqual(CollectionTypeV2("list", 2, element_type="Int").type_id, "List<Int,2>")
        self.assertNotEqual(CollectionTypeV2("list", 2, element_type="Int").type_id, CollectionTypeV2("list", 4, element_type="Int").type_id)
        with self.assertRaises(TevScriptError):
            CollectionTypeV2("map", 4, key_type="Text", value_type="Int", order_policy="sequence")

    def test_list_is_persistent_and_bounded(self):
        t = CollectionTypeV2("list", 2, element_type="Int")
        a = ListValueV2(t)
        b = a.append(1)
        c = b.append(2)
        self.assertEqual(a.items, ())
        self.assertEqual(c.items, (1, 2))
        self.assertEqual(c.get(1), 2)
        self.assertEqual(c.set(0, 9).items, (9, 2))
        self.assertEqual(c.items, (1, 2))
        with self.assertRaises(TevScriptError): c.append(3)
        with self.assertRaises(TevScriptError): c.get(2)

    def test_set_canonicalizes_and_is_idempotent(self):
        t = CollectionTypeV2("set", 3, element_type="Text", order_policy="canonical_value_bytes")
        a = SetValueV2(t, ("b", "a"))
        b = a.add("a")
        self.assertEqual(a.items, ("a", "b"))
        self.assertIs(a, b)
        self.assertTrue(a.contains("b"))
        self.assertEqual(a.canonical(), SetValueV2(t, ("a", "b")).canonical())

    def test_set_rejects_duplicate_constructor_values(self):
        t = CollectionTypeV2("set", 3, element_type="Int", order_policy="canonical_value_bytes")
        with self.assertRaises(TevScriptError): SetValueV2(t, (1, 1))

    def test_map_is_insertion_order_independent(self):
        t = CollectionTypeV2("map", 4, key_type="Text", value_type="Int", order_policy="canonical_key_bytes")
        a = MapValueV2(t, (("b", 2), ("a", 1)))
        b = MapValueV2(t, (("a", 1), ("b", 2)))
        self.assertEqual(a.entries, b.entries)
        self.assertEqual(a.canonical(), b.canonical())
        self.assertEqual(a.lookup("a").value, 1)
        self.assertTrue(a.lookup("a").found)
        self.assertFalse(a.lookup("z").found)

    def test_map_key_and_value_types_are_enforced_on_every_path(self):
        t = CollectionTypeV2("map", 2, key_type="Text", value_type="Int", order_policy="canonical_key_bytes")
        with self.assertRaises(TevScriptError): MapValueV2(t, ((1, 2),))
        with self.assertRaises(TevScriptError): MapValueV2(t).put("a", True)
        m = MapValueV2(t).put("a", 1)
        with self.assertRaises(TevScriptError): m.lookup(1)

    def test_map_put_updates_without_mutating_prior_value(self):
        t = CollectionTypeV2("map", 2, key_type="Text", value_type="Int", order_policy="canonical_key_bytes")
        a = MapValueV2(t).put("b", 2).put("a", 1)
        b = a.put("a", 7)
        self.assertEqual(b.lookup("a").value, 7)
        self.assertEqual(a.lookup("a").value, 1)
        with self.assertRaises(TevScriptError): b.put("c", 3)

    def test_values_use_tev_typed_canonical_encoding(self):
        ints = CollectionTypeV2("set", 3, element_type="Int", order_policy="canonical_value_bytes")
        self.assertEqual(SetValueV2(ints, (10, 2)).items, (10, 2))  # ordered by canonical $int bytes, not numeric host order
        with self.assertRaises(TevScriptError): SetValueV2(ints).add(True)
        rats = CollectionTypeV2("list", 2, element_type="Rat")
        self.assertEqual(ListValueV2(rats).append(Fraction(2, 4)).items, (Fraction(1, 2),))

    def test_unknown_or_host_native_value_type_is_rejected(self):
        t = CollectionTypeV2("list", 2, element_type="Opaque")
        with self.assertRaises(TevScriptError): ListValueV2(t).append(object())

    def test_descriptor_negative_cases(self):
        with self.assertRaises(TevScriptError): CollectionTypeV2("list", 0, element_type="Int")
        with self.assertRaises(TevScriptError): CollectionTypeV2("map", 2, key_type="Text", value_type=None, order_policy="canonical_key_bytes")
        with self.assertRaises(TevScriptError): CollectionTypeV2("tree", 2, element_type="Int")


if __name__ == "__main__":
    unittest.main()
