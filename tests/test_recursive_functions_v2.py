from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.generic_types_v2 import GenericRegistryV2
from tev_script.ir_v4_pure import evaluate_pure_v4
from tev_script.ir_v4_values import ListValueV4
from tev_script.recursive_functions_v2 import RecursivePureFunctionRegistryV2


def _base_program():
    return {
        "boundary":{"maximum_value_nesting":32},
        "types":[
            {"type_id":"Bool","kind":"primitive"},
            {"type_id":"Int","kind":"primitive"},
            {"type_id":"Rat","kind":"primitive"},
            {"type_id":"Text","kind":"primitive"},
            {"type_id":"Unit","kind":"unit"},
            {"type_id":"Vec2","kind":"primitive"},
            {"type_id":"Vec3","kind":"primitive"},
        ],
    }


def cint(value: int):
    return {"op":"CONST","type":"Int","value":{"$int":str(value)}}


def param(name: str, type_id: str):
    return {"op":"PARAM","name":name,"type":type_id}


def sub(left, right):
    return {"op":"BINARY","operator":"MINUS","left_type":"Int","right_type":"Int","result_type":"Int","left":left,"right":right}


def eq(left, right):
    return {"op":"BINARY","operator":"EQEQ","left_type":"Int","right_type":"Int","result_type":"Bool","left":left,"right":right}


def factorial_body(measure_expr=None):
    n=param("n","Int")
    next_n=sub(n,cint(1)) if measure_expr is None else measure_expr
    recursive={"op":"SELF_CALL","arguments":[next_n]}
    return {
        "op":"IF","result_type":"Int",
        "condition":eq(n,cint(0)),
        "then":cint(1),
        "else":{"op":"BINARY","operator":"STAR","left_type":"Int","right_type":"Int","result_type":"Int","left":n,"right":recursive},
    }


class RecursivePureFunctionV2Tests(unittest.TestCase):
    def _registry(self):
        types=GenericRegistryV2(_base_program())
        return types,RecursivePureFunctionRegistryV2(types)

    def test_factorial_non_tail_recursion_executes_with_strict_decrease(self) -> None:
        _types,rec=self._registry()
        template=rec.register(
            "Root","factorial",(),(("n","Int"),),"Int",factorial_body(),
            measure_parameter="n",max_depth=8,maximum_steps=10000,
        )
        inst=rec.instantiate(template)
        receipt=rec.call(inst,(5,))
        self.assertEqual(receipt.result_encoded,{"$int":"120"})
        self.assertEqual(receipt.recursion_calls,5)
        self.assertEqual(receipt.maximum_observed_depth,5)
        self.assertLessEqual(receipt.evaluation_steps,inst.recursive_static_step_upper_bound)

    def test_base_case_at_zero_performs_no_recursive_call(self) -> None:
        _types,rec=self._registry()
        rec.register("Root","factorial",(),(("n","Int"),),"Int",factorial_body(),measure_parameter="n",max_depth=8)
        receipt=rec.call_recursive("factorial",(),(0,))
        self.assertEqual(receipt.result_encoded,{"$int":"1"})
        self.assertEqual(receipt.recursion_calls,0)
        self.assertEqual(receipt.maximum_observed_depth,0)

    def test_non_decreasing_measure_is_rejected_at_self_call_boundary(self) -> None:
        _types,rec=self._registry()
        rec.register(
            "Root","bad",(),(("n","Int"),),"Int",factorial_body(param("n","Int")),
            measure_parameter="n",max_depth=8,
        )
        with self.assertRaises(TevScriptError) as captured:
            rec.call_recursive("bad",(),(3,))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_MEASURE_NOT_DECREASING")

    def test_negative_initial_measure_is_rejected(self) -> None:
        _types,rec=self._registry()
        rec.register("Root","factorial",(),(("n","Int"),),"Int",factorial_body(),measure_parameter="n",max_depth=8)
        with self.assertRaises(TevScriptError) as captured:
            rec.call_recursive("factorial",(),(-1,))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_MEASURE")

    def test_depth_exhaustion_fails_closed_without_partial_result(self) -> None:
        _types,rec=self._registry()
        rec.register(
            "Root","factorial",(),(("n","Int"),),"Int",factorial_body(),
            measure_parameter="n",max_depth=3,maximum_steps=10000,
        )
        with self.assertRaises(TevScriptError) as captured:
            rec.call_recursive("factorial",(),(5,))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_DEPTH_EXHAUSTED")

    def test_max_depth_is_part_of_template_and_callable_identity(self) -> None:
        types_a=GenericRegistryV2(_base_program()); a=RecursivePureFunctionRegistryV2(types_a)
        types_b=GenericRegistryV2(_base_program()); b=RecursivePureFunctionRegistryV2(types_b)
        ta=a.register("Root","factorial",(),(("n","Int"),),"Int",factorial_body(),measure_parameter="n",max_depth=4)
        tb=b.register("Root","factorial",(),(("n","Int"),),"Int",factorial_body(),measure_parameter="n",max_depth=8)
        self.assertNotEqual(ta.template_hash,tb.template_hash)
        self.assertNotEqual(a.instantiate(ta).callable_id,b.instantiate(tb).callable_id)

    def test_two_static_self_calls_are_rejected_in_r1(self) -> None:
        _types,rec=self._registry()
        n=param("n","Int"); next_n=sub(n,cint(1))
        fib_like={
            "op":"IF","result_type":"Int","condition":eq(n,cint(0)),"then":cint(1),
            "else":{"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int",
                    "left":{"op":"SELF_CALL","arguments":[next_n]},"right":{"op":"SELF_CALL","arguments":[next_n]}},
        }
        with self.assertRaises(TevScriptError) as captured:
            rec.register("Root","fib_like",(),(("n","Int"),),"Int",fib_like,measure_parameter="n",max_depth=8)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_CALL_SITE")

    def test_self_call_inside_loop_is_rejected(self) -> None:
        types,rec=self._registry()
        types.materialize_resolved_type(types.resolve_source_type("List<Int,4>"))
        body={
            "op":"FOR_FOLD","collection_type":"List<Int,4>","accumulator_name":"acc","accumulator_type":"Int",
            "bindings":[{"name":"x","type":"Int"}],"collection":param("xs","List<Int,4>"),"initial":param("n","Int"),
            "body":{"op":"SELF_CALL","arguments":[sub(param("acc","Int"),cint(1)),param("xs","List<Int,4>")]},
        }
        with self.assertRaises(TevScriptError) as captured:
            rec.register("Root","loop_rec",(),(("n","Int"),("xs","List<Int,4>")),"Int",body,measure_parameter="n",max_depth=8)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_LOOP")

    def test_self_call_inside_condition_is_rejected(self) -> None:
        _types,rec=self._registry()
        body={
            "op":"IF","result_type":"Int",
            "condition":{"op":"BINARY","operator":"EQEQ","left_type":"Int","right_type":"Int","result_type":"Bool",
                         "left":{"op":"SELF_CALL","arguments":[sub(param("n","Int"),cint(1))]},"right":cint(0)},
            "then":cint(1),"else":cint(2),
        }
        with self.assertRaises(TevScriptError) as captured:
            rec.register("Root","cond_rec",(),(("n","Int"),),"Int",body,measure_parameter="n",max_depth=8)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_CONDITION")

    def test_nested_self_call_argument_is_rejected(self) -> None:
        _types,rec=self._registry()
        nested={"op":"SELF_CALL","arguments":[{"op":"SELF_CALL","arguments":[sub(param("n","Int"),cint(1))]}]}
        body={"op":"IF","result_type":"Int","condition":eq(param("n","Int"),cint(0)),"then":cint(0),"else":nested}
        with self.assertRaises(TevScriptError) as captured:
            rec.register("Root","nested",(),(("n","Int"),),"Int",body,measure_parameter="n",max_depth=8)
        self.assertIn(captured.exception.diagnostic.code,{"TEVS_V2_RECURSION_CALL_SITE","TEVS_V2_RECURSION_ARGUMENT"})

    def test_measure_parameter_must_instantiate_to_int(self) -> None:
        _types,rec=self._registry()
        body={"op":"IF","result_type":"T","condition":{"op":"CONST","type":"Bool","value":True},"then":param("n","T"),"else":{"op":"SELF_CALL","arguments":[param("n","T")]}}
        rec.register("Root","generic_measure",("T",),(("n","T"),),"T",body,measure_parameter="n",max_depth=4)
        with self.assertRaises(TevScriptError) as captured:
            rec.instantiate("generic_measure",("Text",))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_MEASURE")

    def test_generic_recursive_countdown_builds_bounded_list(self) -> None:
        _types,rec=self._registry()
        n=param("n","Int"); x=param("x","T")
        body={
            "op":"IF","result_type":"List<T,4>","condition":eq(n,cint(0)),
            "then":{"op":"LIST","type":"List<T,4>","items":[]},
            "else":{"op":"LIST_PUSH","collection_type":"List<T,4>",
                    "collection":{"op":"SELF_CALL","arguments":[sub(n,cint(1)),x]},"item":x},
        }
        rec.register(
            "Root","repeat",("T",),(("n","Int"),("x","T")),"List<T,4>",body,
            measure_parameter="n",max_depth=4,maximum_steps=10000,
        )
        inst=rec.instantiate("repeat",("Text",))
        receipt=rec.call(inst,(3,"a"))
        self.assertEqual(receipt.result_encoded["$list"]["items"],["a","a","a"])
        self.assertEqual(receipt.recursion_calls,3)
        with self.assertRaises(TevScriptError):
            rec.call(inst,(5,"a"))

    def test_recursive_static_budget_is_checked_before_call(self) -> None:
        _types,rec=self._registry()
        rec.register(
            "Root","factorial",(),(("n","Int"),),"Int",factorial_body(),
            measure_parameter="n",max_depth=32,maximum_steps=64,
        )
        with self.assertRaises(TevScriptError) as captured:
            rec.instantiate("factorial")
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_RECURSION_STATIC_BUDGET")

    def test_pure_kernel_rejects_self_call_without_recursive_authority(self) -> None:
        types=GenericRegistryV2(_base_program())
        with self.assertRaises(TevScriptError) as captured:
            evaluate_pure_v4({"op":"SELF_CALL","arguments":[cint(0)]},types.table)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_RECURSION_CONTEXT")


if __name__ == "__main__":
    unittest.main()
