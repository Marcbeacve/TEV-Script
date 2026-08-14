from __future__ import annotations

import unittest
from fractions import Fraction

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_pure import PureBindingV4, canonical_expression_v4, evaluate_pure_v4, hash_type_table_v4, validate_pure_v4
from tev_script.ir_v4_values import ListValueV4, MapValueV4, RecordValueV4, SetValueV4, VariantValueV4, build_type_table_v4


def _table(*, map_value_type: str = "Int"):
    types = [
        {"type_id":"Bool","kind":"primitive"},
        {"type_id":"Int","kind":"primitive"},
        {"type_id":"List<Int,4>","kind":"list","element_type":"Int","capacity":4,"order_policy":"sequence"},
        {"type_id":f"Map<Text,{map_value_type},4>","kind":"map","key_type":"Text","value_type":map_value_type,"capacity":4,"order_policy":"canonical_key_bytes"},
        {"type_id":f"Option<{map_value_type}>","kind":"option","argument":map_value_type},
        {"type_id":"Option<Int>","kind":"option","argument":"Int"},
        {"type_id":"Rat","kind":"primitive"},
        {"type_id":"Result<Int,Text>","kind":"result","ok_type":"Int","err_type":"Text"},
        {"type_id":"Root.Kind","kind":"enum","variants":["A","B"]},
        {"type_id":"Root.Pair","kind":"record","fields":[{"name":"a","type":"Int"},{"name":"b","type":"Rat"}]},
        {"type_id":"Set<Int,4>","kind":"set","element_type":"Int","capacity":4,"order_policy":"canonical_value_bytes"},
        {"type_id":"Text","kind":"primitive"},
        {"type_id":"Unit","kind":"unit"},
        {"type_id":"Vec2","kind":"primitive"},
        {"type_id":"Vec3","kind":"primitive"},
    ]
    # Avoid duplicate Option<Int> when map_value_type is Int.
    unique = {item["type_id"]: item for item in types}
    return build_type_table_v4({"boundary":{"maximum_value_nesting":32},"types":[unique[k] for k in sorted(unique)]})


def cint(value: int):
    return {"op":"CONST","type":"Int","value":{"$int":str(value)}}


def crat(n: int, d: int = 1):
    return {"op":"CONST","type":"Rat","value":{"$rat":[str(n),str(d)]}}


def ctext(value: str):
    return {"op":"CONST","type":"Text","value":value}


def param(name: str, type_id: str):
    return {"op":"PARAM","name":name,"type":type_id}


def plus(left, right, lt="Int", rt="Int", result="Int"):
    return {"op":"BINARY","operator":"PLUS","left_type":lt,"right_type":rt,"result_type":result,"left":left,"right":right}


class IrV4PurePrimitiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def test_exact_arithmetic_and_numeric_widening_match_v1_contract(self) -> None:
        integer = evaluate_pure_v4(plus(cint(2), cint(3)), self.table)
        rational = evaluate_pure_v4(plus(cint(2), crat(1,2), "Int", "Rat", "Rat"), self.table)
        division = evaluate_pure_v4({"op":"BINARY","operator":"SLASH","left_type":"Int","right_type":"Int","result_type":"Rat","left":cint(3),"right":cint(2)}, self.table)
        self.assertEqual(integer.result_encoded, {"$int":"5"})
        self.assertEqual(rational.result_encoded, {"$rat":["5","2"]})
        self.assertEqual(division.result_encoded, {"$rat":["3","2"]})

    def test_vectors_boolean_logic_comparison_and_equality(self) -> None:
        vec = {"op":"CONST","type":"Vec2","value":[{"$rat":["1","1"]},{"$rat":["2","1"]}]}
        scale = {"op":"BINARY","operator":"STAR","left_type":"Vec2","right_type":"Int","result_type":"Vec2","left":vec,"right":cint(3)}
        eq = {"op":"BINARY","operator":"EQEQ","left_type":"Int","right_type":"Rat","result_type":"Bool","left":cint(1),"right":crat(1)}
        cond = {"op":"BINARY","operator":"LT","left_type":"Int","right_type":"Rat","result_type":"Bool","left":cint(1),"right":crat(3,2)}
        self.assertEqual(evaluate_pure_v4(scale,self.table).result_encoded,[{"$rat":["3","1"]},{"$rat":["6","1"]}])
        self.assertTrue(evaluate_pure_v4(eq,self.table).result_encoded)
        self.assertTrue(evaluate_pure_v4(cond,self.table).result_encoded)

    def test_divide_zero_and_forged_operator_contract_fail_closed(self) -> None:
        with self.assertRaises(TevScriptError) as captured:
            evaluate_pure_v4({"op":"BINARY","operator":"SLASH","left_type":"Int","right_type":"Int","result_type":"Rat","left":cint(1),"right":cint(0)},self.table)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_DIVIDE_ZERO")
        with self.assertRaises(TevScriptError):
            evaluate_pure_v4({"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Text","left":cint(1),"right":cint(2)},self.table)

    def test_let_if_and_parameter_typing_are_pure_and_exact(self) -> None:
        expr={
            "op":"LET","name":"y","type":"Int","result_type":"Int","value":cint(4),
            "body":{"op":"IF","result_type":"Int","condition":{"op":"BINARY","operator":"GT","left_type":"Int","right_type":"Int","result_type":"Bool","left":param("x","Int"),"right":cint(0)},"then":plus(param("x","Int"),param("y","Int")),"else":cint(0)},
        }
        receipt=evaluate_pure_v4(expr,self.table,[PureBindingV4("x","Int",3)])
        self.assertEqual(receipt.result_encoded,{"$int":"7"})
        with self.assertRaises(TevScriptError):
            evaluate_pure_v4(expr,self.table,[PureBindingV4("x","Rat",Fraction(3,1))])


class IrV4PureAlgebraicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def test_record_field_order_is_canonical_in_expression_identity(self) -> None:
        left={"op":"RECORD","type":"Root.Pair","fields":[{"name":"b","expr":crat(3,2)},{"name":"a","expr":cint(7)}]}
        right={"op":"RECORD","type":"Root.Pair","fields":[{"name":"a","expr":cint(7)},{"name":"b","expr":crat(3,2)}]}
        a=evaluate_pure_v4(left,self.table); b=evaluate_pure_v4(right,self.table)
        self.assertEqual(a.expression_hash,b.expression_hash)
        field={"op":"FIELD","record_type":"Root.Pair","field":"b","result_type":"Rat","record":left}
        self.assertEqual(evaluate_pure_v4(field,self.table).result_encoded,{"$rat":["3","2"]})

    def test_option_variant_construction_is_typed(self) -> None:
        some={"op":"VARIANT","type":"Option<Int>","variant":"Some","payload":cint(9)}
        none={"op":"VARIANT","type":"Option<Int>","variant":"None"}
        self.assertEqual(evaluate_pure_v4(some,self.table).result_encoded,{"$option":{"type":"Option<Int>","variant":"Some","value":{"$int":"9"}}})
        self.assertEqual(evaluate_pure_v4(none,self.table).result_encoded,{"$option":{"type":"Option<Int>","variant":"None"}})
        with self.assertRaises(TevScriptError):
            evaluate_pure_v4({"op":"VARIANT","type":"Option<Int>","variant":"Some","payload":ctext("bad")},self.table)


class IrV4PureMatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def _option_match(self, subject):
        return {
            "op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":subject,
            "arms":[
                {"variant":"Some","binding":{"name":"value","type":"Int"},"body":param("value","Int")},
                {"variant":"None","body":cint(-1)},
            ],
        }

    def test_option_match_eliminates_some_and_none_exactly(self) -> None:
        some={"op":"VARIANT","type":"Option<Int>","variant":"Some","payload":cint(7)}
        none={"op":"VARIANT","type":"Option<Int>","variant":"None"}
        self.assertEqual(evaluate_pure_v4(self._option_match(some),self.table).result_encoded,{"$int":"7"})
        self.assertEqual(evaluate_pure_v4(self._option_match(none),self.table).result_encoded,{"$int":"-1"})

    def test_result_and_enum_match_are_exhaustive_and_typed(self) -> None:
        ok={"op":"VARIANT","type":"Result<Int,Text>","variant":"Ok","payload":cint(4)}
        result_match={
            "op":"MATCH","subject_type":"Result<Int,Text>","result_type":"Int","subject":ok,
            "arms":[
                {"variant":"Err","binding":{"name":"error","type":"Text"},"body":cint(-1)},
                {"variant":"Ok","binding":{"name":"value","type":"Int"},"body":param("value","Int")},
            ],
        }
        enum_subject={"op":"VARIANT","type":"Root.Kind","variant":"B"}
        enum_match={
            "op":"MATCH","subject_type":"Root.Kind","result_type":"Int","subject":enum_subject,
            "arms":[{"variant":"B","body":cint(2)},{"variant":"A","body":cint(1)}],
        }
        self.assertEqual(evaluate_pure_v4(result_match,self.table).result_encoded,{"$int":"4"})
        self.assertEqual(evaluate_pure_v4(enum_match,self.table).result_encoded,{"$int":"2"})

    def test_match_arm_order_is_not_semantic_identity(self) -> None:
        subject={"op":"VARIANT","type":"Option<Int>","variant":"Some","payload":cint(1)}
        a=self._option_match(subject)
        b=dict(a); b["arms"]=list(reversed(a["arms"]))
        ca=canonical_expression_v4(a); cb=canonical_expression_v4(b)
        self.assertEqual(ca,cb)
        self.assertEqual(validate_pure_v4(ca,self.table).expression_hash,validate_pure_v4(cb,self.table).expression_hash)

    def test_match_is_lazy_and_does_not_evaluate_unselected_arm(self) -> None:
        some={"op":"VARIANT","type":"Option<Int>","variant":"Some","payload":cint(9)}
        divide_zero={"op":"BINARY","operator":"SLASH","left_type":"Int","right_type":"Int","result_type":"Rat","left":cint(1),"right":cint(0)}
        expr={
            "op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":some,
            "arms":[
                {"variant":"Some","binding":{"name":"value","type":"Int"},"body":param("value","Int")},
                {"variant":"None","body":{"op":"LET","name":"x","type":"Rat","result_type":"Int","value":divide_zero,"body":cint(-1)}},
            ],
        }
        self.assertEqual(evaluate_pure_v4(expr,self.table).result_encoded,{"$int":"9"})

    def test_nonexhaustive_duplicate_or_mistyped_match_fails_closed(self) -> None:
        subject={"op":"VARIANT","type":"Option<Int>","variant":"None"}
        cases=[
            {"op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":subject,"arms":[{"variant":"None","body":cint(0)}]},
            {"op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":subject,"arms":[{"variant":"None","body":cint(0)},{"variant":"None","body":cint(1)}]},
            {"op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":subject,"arms":[{"variant":"None","body":cint(0)},{"variant":"Some","binding":{"name":"x","type":"Text"},"body":cint(1)}]},
            {"op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":subject,"arms":[{"variant":"None","binding":{"name":"x","type":"Int"},"body":cint(0)},{"variant":"Some","binding":{"name":"v","type":"Int"},"body":cint(1)}]},
        ]
        for expr in cases:
            with self.subTest(expr=expr):
                with self.assertRaises(TevScriptError):
                    validate_pure_v4(expr,self.table)

    def test_match_binding_cannot_shadow_existing_environment(self) -> None:
        subject={"op":"VARIANT","type":"Option<Int>","variant":"Some","payload":cint(2)}
        expr={
            "op":"MATCH","subject_type":"Option<Int>","result_type":"Int","subject":subject,
            "arms":[{"variant":"None","body":cint(0)},{"variant":"Some","binding":{"name":"x","type":"Int"},"body":param("x","Int")}],
        }
        with self.assertRaises(TevScriptError):
            validate_pure_v4(expr,self.table,{"x":"Int"})


class IrV4PureCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def test_dynamic_list_operations_are_persistent_and_typed(self) -> None:
        base={"op":"LIST","type":"List<Int,4>","items":[cint(1),cint(2)]}
        pushed={"op":"LIST_PUSH","collection_type":"List<Int,4>","collection":base,"item":cint(3)}
        changed={"op":"LIST_SET","collection_type":"List<Int,4>","collection":pushed,"index":cint(0),"item":cint(9)}
        get={"op":"LIST_GET","collection_type":"List<Int,4>","result_type":"Int","collection":changed,"index":cint(0)}
        self.assertEqual(evaluate_pure_v4(get,self.table).result_encoded,{"$int":"9"})
        self.assertEqual(evaluate_pure_v4({"op":"LEN","collection_type":"List<Int,4>","collection":changed},self.table).result_encoded,{"$int":"3"})
        self.assertEqual(evaluate_pure_v4(base,self.table).result_encoded["$list"]["items"],[{"$int":"1"},{"$int":"2"}])

    def test_set_is_canonical_and_contains_is_pure(self) -> None:
        a={"op":"SET","type":"Set<Int,4>","items":[cint(2),cint(1)]}
        b={"op":"SET","type":"Set<Int,4>","items":[cint(1),cint(2)]}
        self.assertEqual(evaluate_pure_v4(a,self.table).result_encoded,evaluate_pure_v4(b,self.table).result_encoded)
        contains={"op":"SET_CONTAINS","collection_type":"Set<Int,4>","collection":a,"item":cint(2)}
        self.assertTrue(evaluate_pure_v4(contains,self.table).result_encoded)

    def test_map_lookup_returns_language_option_not_host_sentinel(self) -> None:
        map_type="Map<Text,Int,4>"
        mapping={"op":"MAP","type":map_type,"entries":[{"key":ctext("b"),"value":cint(2)},{"key":ctext("a"),"value":cint(1)}]}
        found={"op":"MAP_LOOKUP","collection_type":map_type,"result_type":"Option<Int>","collection":mapping,"key":ctext("a")}
        missing={"op":"MAP_LOOKUP","collection_type":map_type,"result_type":"Option<Int>","collection":mapping,"key":ctext("z")}
        self.assertEqual(evaluate_pure_v4(found,self.table).result_encoded,{"$option":{"type":"Option<Int>","variant":"Some","value":{"$int":"1"}}})
        self.assertEqual(evaluate_pure_v4(missing,self.table).result_encoded,{"$option":{"type":"Option<Int>","variant":"None"}})

    def test_collection_overflow_and_wrong_index_type_fail_closed(self) -> None:
        too_many={"op":"LIST","type":"List<Int,4>","items":[cint(i) for i in range(5)]}
        with self.assertRaises(TevScriptError): evaluate_pure_v4(too_many,self.table)
        with self.assertRaises(TevScriptError):
            evaluate_pure_v4({"op":"LIST_GET","collection_type":"List<Int,4>","result_type":"Int","collection":{"op":"LIST","type":"List<Int,4>","items":[cint(1)]},"index":crat(0)},self.table)


class IrV4PureWhileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def _increment_until(self, target: int, maximum: int, initial: int = 0):
        return {
            "op":"WHILE_FOLD",
            "accumulator_name":"x",
            "accumulator_type":"Int",
            "maximum_iterations":maximum,
            "initial":cint(initial),
            "condition":{
                "op":"BINARY","operator":"LT","left_type":"Int","right_type":"Int","result_type":"Bool",
                "left":param("x","Int"),"right":cint(target),
            },
            "body":plus(param("x","Int"),cint(1)),
        }

    def test_while_fold_terminates_exactly_at_declared_bound(self) -> None:
        expr=self._increment_until(3,3)
        validation=validate_pure_v4(expr,self.table)
        receipt=evaluate_pure_v4(expr,self.table)
        self.assertEqual(receipt.result_encoded,{"$int":"3"})
        self.assertEqual(receipt.bounded_loop_iterations,3)
        self.assertEqual(receipt.static_step_upper_bound,validation.static_step_upper_bound)
        self.assertLessEqual(receipt.evaluation_steps,receipt.static_step_upper_bound)

    def test_while_fold_fails_closed_when_condition_remains_true_at_bound(self) -> None:
        expr=self._increment_until(3,2)
        with self.assertRaises(TevScriptError) as captured:
            evaluate_pure_v4(expr,self.table)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_WHILE_BOUND")

    def test_while_fold_zero_runtime_iterations_when_condition_is_initially_false(self) -> None:
        expr=self._increment_until(3,8,initial=4)
        receipt=evaluate_pure_v4(expr,self.table)
        self.assertEqual(receipt.result_encoded,{"$int":"4"})
        self.assertEqual(receipt.bounded_loop_iterations,0)

    def test_while_bound_is_semantic_identity(self) -> None:
        two=canonical_expression_v4(self._increment_until(3,2))
        three=canonical_expression_v4(self._increment_until(3,3))
        self.assertNotEqual(two,three)
        self.assertNotEqual(validate_pure_v4(two,self.table).expression_hash,validate_pure_v4(three,self.table).expression_hash)

    def test_while_static_contract_rejects_bad_condition_or_body_type(self) -> None:
        bad_condition={
            "op":"WHILE_FOLD","accumulator_name":"x","accumulator_type":"Int","maximum_iterations":4,
            "initial":cint(0),"condition":param("x","Int"),"body":plus(param("x","Int"),cint(1)),
        }
        bad_body={
            "op":"WHILE_FOLD","accumulator_name":"x","accumulator_type":"Int","maximum_iterations":4,
            "initial":cint(0),
            "condition":{"op":"BINARY","operator":"LT","left_type":"Int","right_type":"Int","result_type":"Bool","left":param("x","Int"),"right":cint(3)},
            "body":ctext("bad"),
        }
        for expr in (bad_condition,bad_body):
            with self.subTest(expr=expr):
                with self.assertRaises(TevScriptError): validate_pure_v4(expr,self.table)

    def test_while_bound_range_is_fail_closed(self) -> None:
        for maximum in (0,4097,True):
            expr=self._increment_until(1,1)
            expr["maximum_iterations"]=maximum
            with self.subTest(maximum=maximum):
                with self.assertRaises(TevScriptError): canonical_expression_v4(expr)

    def test_while_static_step_upper_bound_prevents_underbudget_execution(self) -> None:
        expr=self._increment_until(3,3)
        validation=validate_pure_v4(expr,self.table)
        self.assertGreater(validation.static_step_upper_bound,0)
        with self.assertRaises(TevScriptError) as captured:
            evaluate_pure_v4(expr,self.table,maximum_steps=validation.static_step_upper_bound-1)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_BUDGET")


class IrV4PureFoldAndIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.table = _table()

    def _sum_fold(self, collection_expr):
        return {
            "op":"FOR_FOLD","collection_type":"List<Int,4>","accumulator_name":"acc","accumulator_type":"Int","bindings":[{"name":"x","type":"Int"}],
            "collection":collection_expr,"initial":cint(0),"body":plus(param("acc","Int"),param("x","Int")),
        }

    def test_for_fold_executes_bounded_functional_loop(self) -> None:
        expr=self._sum_fold({"op":"LIST","type":"List<Int,4>","items":[cint(1),cint(2),cint(3)]})
        receipt=evaluate_pure_v4(expr,self.table)
        self.assertEqual(receipt.result_encoded,{"$int":"6"})
        self.assertEqual(receipt.bounded_loop_iterations,3)
        self.assertGreater(receipt.evaluation_steps,3)

    def test_set_and_map_fold_use_canonical_iteration_order(self) -> None:
        set_a={"op":"SET","type":"Set<Int,4>","items":[cint(2),cint(1)]}
        set_b={"op":"SET","type":"Set<Int,4>","items":[cint(1),cint(2)]}
        fold=lambda set_expr:{"op":"FOR_FOLD","collection_type":"Set<Int,4>","accumulator_name":"acc","accumulator_type":"Int","bindings":[{"name":"x","type":"Int"}],"collection":set_expr,"initial":cint(0),"body":plus(param("acc","Int"),param("x","Int"))}
        self.assertEqual(evaluate_pure_v4(fold(set_a),self.table).result_hash,evaluate_pure_v4(fold(set_b),self.table).result_hash)
        map_type="Map<Text,Int,4>"
        mapping={"op":"MAP","type":map_type,"entries":[{"key":ctext("b"),"value":cint(2)},{"key":ctext("a"),"value":cint(1)}]}
        map_fold={"op":"FOR_FOLD","collection_type":map_type,"accumulator_name":"acc","accumulator_type":"Int","bindings":[{"name":"k","type":"Text"},{"name":"v","type":"Int"}],"collection":mapping,"initial":cint(0),"body":plus(param("acc","Int"),param("v","Int"))}
        self.assertEqual(evaluate_pure_v4(map_fold,self.table).result_encoded,{"$int":"3"})

    def test_evaluation_budget_cuts_off_large_fold(self) -> None:
        expr=self._sum_fold({"op":"LIST","type":"List<Int,4>","items":[cint(1),cint(2),cint(3)]})
        with self.assertRaises(TevScriptError) as captured:
            evaluate_pure_v4(expr,self.table,maximum_steps=5)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_BUDGET")

    def test_environment_order_is_not_identity_and_values_are_hash_bound(self) -> None:
        expr=plus(param("x","Int"),param("y","Int"))
        a=evaluate_pure_v4(expr,self.table,[PureBindingV4("x","Int",1),PureBindingV4("y","Int",2)])
        b=evaluate_pure_v4(expr,self.table,[PureBindingV4("y","Int",2),PureBindingV4("x","Int",1)])
        c=evaluate_pure_v4(expr,self.table,[PureBindingV4("x","Int",1),PureBindingV4("y","Int",3)])
        self.assertEqual(a.environment_hash,b.environment_hash)
        self.assertEqual(a.receipt_hash,b.receipt_hash)
        self.assertNotEqual(a.environment_hash,c.environment_hash)

    def test_type_table_hash_is_part_of_receipt_identity(self) -> None:
        int_table=_table(map_value_type="Int")
        text_table=_table(map_value_type="Text")
        self.assertNotEqual(hash_type_table_v4(int_table),hash_type_table_v4(text_table))
        int_map={"op":"MAP","type":"Map<Text,Int,4>","entries":[]}
        text_map={"op":"MAP","type":"Map<Text,Text,4>","entries":[]}
        int_lookup={"op":"MAP_LOOKUP","collection_type":"Map<Text,Int,4>","result_type":"Option<Int>","collection":int_map,"key":ctext("z")}
        text_lookup={"op":"MAP_LOOKUP","collection_type":"Map<Text,Text,4>","result_type":"Option<Text>","collection":text_map,"key":ctext("z")}
        a=evaluate_pure_v4(int_lookup,int_table); b=evaluate_pure_v4(text_lookup,text_table)
        self.assertNotEqual(a.type_table_hash,b.type_table_hash)
        self.assertNotEqual(a.receipt_hash,b.receipt_hash)

    def test_unknown_ops_non_json_expression_and_host_values_are_rejected(self) -> None:
        with self.assertRaises(TevScriptError): canonical_expression_v4({"op":"NETWORK_CALL"})
        with self.assertRaises(TevScriptError): canonical_expression_v4({"op":"CONST","type":"Int","value":object()})
        with self.assertRaises(TevScriptError): evaluate_pure_v4(param("x","Int"),self.table,[PureBindingV4("x","Int",object())])


if __name__ == "__main__":
    unittest.main()
