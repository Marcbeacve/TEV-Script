from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.generic_functions_v2 import GenericPureFunctionRegistryV2
from tev_script.generic_types_v2 import GenericRegistryV2
from tev_script.ir_v4_values import ListValueV4, MapValueV4


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


def _registries():
    types = GenericRegistryV2(_base_program())
    funcs = GenericPureFunctionRegistryV2(types)
    return types, funcs


def param(name: str, type_id: str):
    return {"op":"PARAM","name":name,"type":type_id}


class GenericPureFunctionV2Tests(unittest.TestCase):
    def test_identity_is_executable_for_multiple_exact_types(self) -> None:
        _types, funcs = _registries()
        template = funcs.register("Root", "identity", ("T",), (("x","T"),), "T", param("x","T"))
        int_inst = funcs.instantiate(template, ("Int",))
        text_inst = funcs.instantiate(template, ("Text",))
        self.assertNotEqual(int_inst.callable_id, text_inst.callable_id)
        self.assertEqual(funcs.call(int_inst, (7,)).result_encoded, {"$int":"7"})
        self.assertEqual(funcs.call(text_inst, ("hello",)).result_encoded, "hello")

    def test_append_generic_list_function_is_persistent_and_bounded(self) -> None:
        _types, funcs = _registries()
        body = {
            "op":"LIST_PUSH","collection_type":"List<T,4>",
            "collection":param("xs","List<T,4>"),"item":param("x","T"),
        }
        funcs.register("Root","append",("T",),(('xs','List<T,4>'),('x','T')),"List<T,4>",body)
        inst = funcs.instantiate("append",("Int",))
        original = ListValueV4("List<Int,4>",(1,2))
        receipt = funcs.call(inst,(original,3))
        self.assertEqual(receipt.result_encoded["$list"]["items"],[{"$int":"1"},{"$int":"2"},{"$int":"3"}])
        self.assertEqual(original.items,(1,2))
        with self.assertRaises(TevScriptError):
            funcs.call(inst,(ListValueV4("List<Int,4>",(1,2,3,4)),5))

    def test_generic_map_lookup_returns_exact_language_option(self) -> None:
        _types, funcs = _registries()
        body = {
            "op":"MAP_LOOKUP","collection_type":"Map<Text,V,4>","result_type":"Option<V>",
            "collection":param("m","Map<Text,V,4>"),"key":param("key","Text"),
        }
        funcs.register("Root","lookup",("V",),(('m','Map<Text,V,4>'),('key','Text')),"Option<V>",body)
        inst = funcs.instantiate("lookup",("Int",))
        mapping = MapValueV4("Map<Text,Int,4>",(("a",1),))
        found = funcs.call(inst,(mapping,"a"))
        missing = funcs.call(inst,(mapping,"z"))
        self.assertEqual(found.result_encoded,{"$option":{"type":"Option<Int>","variant":"Some","value":{"$int":"1"}}})
        self.assertEqual(missing.result_encoded,{"$option":{"type":"Option<Int>","variant":"None"}})

    def test_generic_function_can_construct_monomorphized_generic_record(self) -> None:
        types, funcs = _registries()
        types.register_record("Root","Box",("T",),(("value","T"),))
        body = {"op":"RECORD","type":"Box<T>","fields":[{"name":"value","expr":param("x","T")}]}
        funcs.register("Root","box",("T",),(('x','T'),),"Box<T>",body)
        inst = funcs.instantiate("box",("Int",))
        receipt = funcs.call(inst,(9,))
        self.assertTrue(receipt.result_type.startswith("Root.Box__g_"))
        self.assertEqual(receipt.result_encoded["$record"]["fields"][0]["value"],{"$int":"9"})

    def test_generic_for_fold_function_is_statically_bounded_and_executes(self) -> None:
        _types, funcs = _registries()
        body = {
            "op":"FOR_FOLD","collection_type":"List<T,4>","accumulator_name":"acc","accumulator_type":"List<T,4>",
            "bindings":[{"name":"item","type":"T"}],"collection":param("xs","List<T,4>"),
            "initial":{"op":"LIST","type":"List<T,4>","items":[]},
            "body":{"op":"LIST_PUSH","collection_type":"List<T,4>","collection":param("acc","List<T,4>"),"item":param("item","T")},
        }
        funcs.register("Root","copy",("T",),(('xs','List<T,4>'),),"List<T,4>",body,maximum_steps=100)
        inst = funcs.instantiate("copy",("Text",))
        self.assertLessEqual(inst.static_step_upper_bound,inst.maximum_steps)
        receipt = funcs.call(inst,(ListValueV4("List<Text,4>",("b","a")),))
        self.assertEqual(receipt.result_encoded["$list"]["items"],["b","a"])
        self.assertEqual(receipt.bounded_loop_iterations,2)

    def test_generic_match_unwrap_or_executes_option_elimination(self) -> None:
        _types, funcs = _registries()
        body={
            "op":"MATCH","subject_type":"Option<T>","result_type":"T","subject":param("value","Option<T>"),
            "arms":[
                {"variant":"Some","binding":{"name":"payload","type":"T"},"body":param("payload","T")},
                {"variant":"None","body":param("default","T")},
            ],
        }
        funcs.register("Root","unwrap_or",("T",),(('value','Option<T>'),('default','T')),"T",body)
        inst=funcs.instantiate("unwrap_or",("Int",))
        from tev_script.ir_v4_values import VariantValueV4
        some=VariantValueV4("Option<Int>","Some",7)
        none=VariantValueV4("Option<Int>","None")
        self.assertEqual(funcs.call(inst,(some,3)).result_encoded,{"$int":"7"})
        self.assertEqual(funcs.call(inst,(none,3)).result_encoded,{"$int":"3"})

    def test_static_budget_rejects_function_before_invocation(self) -> None:
        _types, funcs = _registries()
        body = {
            "op":"FOR_FOLD","collection_type":"List<T,4>","accumulator_name":"acc","accumulator_type":"List<T,4>",
            "bindings":[{"name":"item","type":"T"}],"collection":param("xs","List<T,4>"),
            "initial":{"op":"LIST","type":"List<T,4>","items":[]},
            "body":{"op":"LIST_PUSH","collection_type":"List<T,4>","collection":param("acc","List<T,4>"),"item":param("item","T")},
        }
        funcs.register("Root","copy",("T",),(('xs','List<T,4>'),),"List<T,4>",body,maximum_steps=10)
        with self.assertRaises(TevScriptError) as captured:
            funcs.instantiate("copy",("Int",))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_GENERIC_FUNCTION_BUDGET")

    def test_body_hash_is_part_of_template_and_callable_identity(self) -> None:
        types_a = GenericRegistryV2(_base_program()); funcs_a = GenericPureFunctionRegistryV2(types_a)
        types_b = GenericRegistryV2(_base_program()); funcs_b = GenericPureFunctionRegistryV2(types_b)
        a = funcs_a.register("Root","transform",("T",),(('x','T'),),"T",param("x","T"))
        body_b = {"op":"IF","result_type":"T","condition":{"op":"CONST","type":"Bool","value":True},"then":param("x","T"),"else":param("x","T")}
        b = funcs_b.register("Root","transform",("T",),(('x','T'),),"T",body_b)
        self.assertNotEqual(a.template_hash,b.template_hash)
        self.assertNotEqual(funcs_a.instantiate(a,("Int",)).callable_id,funcs_b.instantiate(b,("Int",)).callable_id)

    def test_type_parameter_alpha_renaming_is_identity_preserving(self) -> None:
        types_a = GenericRegistryV2(_base_program()); funcs_a = GenericPureFunctionRegistryV2(types_a)
        types_b = GenericRegistryV2(_base_program()); funcs_b = GenericPureFunctionRegistryV2(types_b)
        a = funcs_a.register("Root","identity",("T",),(('x','T'),),"T",param("x","T"))
        b = funcs_b.register("Root","identity",("U",),(('x','U'),),"U",param("x","U"))
        self.assertEqual(a.template_hash,b.template_hash)
        self.assertEqual(funcs_a.instantiate(a,("Int",)).callable_id,funcs_b.instantiate(b,("Int",)).callable_id)

    def test_generic_dependent_const_and_recursive_call_surface_are_closed(self) -> None:
        _types, funcs = _registries()
        with self.assertRaises(TevScriptError) as captured:
            funcs.register("Root","bad",("T",),(('x','T'),),"T",{"op":"CONST","type":"T","value":{"$int":"0"}})
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_GENERIC_FUNCTION_CONST_GENERIC")
        with self.assertRaises(TevScriptError):
            funcs.register("Root","recursive",("T",),(('x','T'),),"T",{"op":"CALL","function":"recursive","args":[param("x","T")]})

    def test_wrong_signature_or_undeclared_parameter_fails_at_instantiation(self) -> None:
        _types, funcs = _registries()
        funcs.register("Root","badreturn",("T",),(('x','T'),),"T",{"op":"CONST","type":"Int","value":{"$int":"1"}})
        with self.assertRaises(TevScriptError) as captured:
            funcs.instantiate("badreturn",("Text",))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_GENERIC_FUNCTION_RETURN")
        funcs.register("Root","missing",("T",),(('x','T'),),"T",param("y","T"))
        with self.assertRaises(TevScriptError): funcs.instantiate("missing",("Int",))

    def test_dependency_closure_is_stable_under_unrelated_type_addition(self) -> None:
        types, funcs = _registries()
        funcs.register("Root","identity",("T",),(('x','T'),),"T",param("x","T"))
        inst = funcs.instantiate("identity",("Int",))
        before = funcs.call(inst,(1,))
        types.register_record("Root","Unrelated",("U",),(("value","U"),))
        types.resolve_source_type("Unrelated<Text>")
        after = funcs.call(inst,(1,))
        self.assertEqual(inst.dependency_hash,inst.dependency_hash)
        self.assertEqual(before.result_hash,after.result_hash)
        self.assertNotEqual(before.type_table_hash,after.type_table_hash)

    def test_argument_and_instantiation_budgets_fail_closed(self) -> None:
        types = GenericRegistryV2(_base_program())
        funcs = GenericPureFunctionRegistryV2(types,max_instantiations=1)
        funcs.register("Root","identity",("T",),(('x','T'),),"T",param("x","T"))
        int_inst = funcs.instantiate("identity",("Int",))
        with self.assertRaises((TevScriptError,TypeError)):
            funcs.call(int_inst,("not-int",))
        with self.assertRaises(TevScriptError): funcs.instantiate("identity",("Text",))


if __name__ == "__main__":
    unittest.main()
