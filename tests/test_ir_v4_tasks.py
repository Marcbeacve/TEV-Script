from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_pure import (
    TASK_CANCELLATION_POLICY_V4,
    TASK_JOIN_POLICY_V4,
    canonical_expression_v4,
    evaluate_pure_v4,
    validate_pure_v4,
)
from tev_script.ir_v4_values import build_type_table_v4


def table():
    return build_type_table_v4({
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
    })


def cint(value): return {"op":"CONST","type":"Int","value":{"$int":str(value)}}
def param(name): return {"op":"PARAM","name":name,"type":"Int"}
def plus(a,b): return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}

def scope(tasks, join, result_type="Int"):
    return {
        "op":"TASK_SCOPE",
        "result_type":result_type,
        "join_policy":TASK_JOIN_POLICY_V4,
        "cancellation_policy":TASK_CANCELLATION_POLICY_V4,
        "tasks":tasks,
        "join":join,
    }


class IrV4TaskScopeR1Tests(unittest.TestCase):
    def setUp(self): self.table=table()

    def test_fan_out_fan_in_evaluates_and_accounts_exact_steps(self):
        expr=scope([
            {"name":"a","type":"Int","body":plus(cint(1),cint(2))},
            {"name":"b","type":"Int","body":plus(cint(3),cint(4))},
        ],plus(param("a"),param("b")))
        validation=validate_pure_v4(expr,self.table)
        receipt=evaluate_pure_v4(expr,self.table)
        self.assertEqual(receipt.result_encoded,{"$int":"10"})
        self.assertEqual(receipt.evaluation_steps,validation.static_step_upper_bound)
        self.assertEqual(receipt.bounded_loop_iterations,0)

    def test_task_declaration_order_is_nonsemantic_and_canonicalized(self):
        first=scope([
            {"name":"b","type":"Int","body":cint(2)},
            {"name":"a","type":"Int","body":cint(1)},
        ],plus(param("a"),param("b")))
        second=scope([
            {"name":"a","type":"Int","body":cint(1)},
            {"name":"b","type":"Int","body":cint(2)},
        ],plus(param("a"),param("b")))
        self.assertEqual(canonical_expression_v4(first),canonical_expression_v4(second))
        self.assertEqual(validate_pure_v4(first,self.table).expression_hash,validate_pure_v4(second,self.table).expression_hash)

    def test_tasks_see_outer_environment_but_not_sibling_results(self):
        ok=scope([
            {"name":"a","type":"Int","body":plus(param("x"),cint(1))},
            {"name":"b","type":"Int","body":plus(param("x"),cint(2))},
        ],plus(param("a"),param("b")))
        receipt=evaluate_pure_v4(ok,self.table,[__import__('tev_script.ir_v4_pure',fromlist=['PureBindingV4']).PureBindingV4('x','Int',5)])
        self.assertEqual(receipt.result_encoded,{"$int":"13"})
        bad=scope([
            {"name":"a","type":"Int","body":cint(1)},
            {"name":"b","type":"Int","body":plus(param("a"),cint(1))},
        ],param("b"))
        with self.assertRaises(TevScriptError) as captured:
            validate_pure_v4(bad,self.table)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_IR_V4_PURE_PARAM')

    def test_join_can_read_outer_and_all_child_results(self):
        expr=scope([
            {"name":"a","type":"Int","body":cint(2)},
            {"name":"b","type":"Int","body":cint(3)},
        ],plus(plus(param("a"),param("b")),param("x")))
        PureBindingV4=__import__('tev_script.ir_v4_pure',fromlist=['PureBindingV4']).PureBindingV4
        receipt=evaluate_pure_v4(expr,self.table,[PureBindingV4('x','Int',4)])
        self.assertEqual(receipt.result_encoded,{"$int":"9"})

    def test_task_binding_cannot_shadow_outer_or_duplicate(self):
        shadow=scope([{"name":"x","type":"Int","body":cint(1)}],param("x"))
        with self.assertRaises(TevScriptError) as captured:
            validate_pure_v4(shadow,self.table,{"x":"Int"})
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_IR_V4_PURE_TASK_BINDING')
        duplicate=scope([
            {"name":"a","type":"Int","body":cint(1)},
            {"name":"a","type":"Int","body":cint(2)},
        ],param("a"))
        with self.assertRaises(TevScriptError) as captured:
            canonical_expression_v4(duplicate)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_IR_V4_PURE_TASK_BINDING')

    def test_task_and_join_types_are_exact(self):
        bad_task=scope([{"name":"a","type":"Text","body":cint(1)}],cint(0))
        with self.assertRaises(TevScriptError): validate_pure_v4(bad_task,self.table)
        bad_join=scope([{"name":"a","type":"Int","body":cint(1)}],cint(1),result_type="Text")
        with self.assertRaises(TevScriptError): validate_pure_v4(bad_join,self.table)

    def test_policies_are_semantic_and_forgery_fails_closed(self):
        expr=scope([{"name":"a","type":"Int","body":cint(1)}],param("a"))
        changed=copy.deepcopy(expr); changed['join_policy']='collect_results_v1'
        with self.assertRaises(TevScriptError) as captured: canonical_expression_v4(changed)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_IR_V4_PURE_TASK_POLICY')
        changed=copy.deepcopy(expr); changed['cancellation_policy']='none_v1'
        with self.assertRaises(TevScriptError): canonical_expression_v4(changed)

    def test_task_count_is_bounded(self):
        with self.assertRaises(TevScriptError): canonical_expression_v4(scope([],cint(0)))
        many=[{"name":f"t{i}","type":"Int","body":cint(i)} for i in range(65)]
        with self.assertRaises(TevScriptError) as captured: canonical_expression_v4(scope(many,cint(0)))
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_IR_V4_PURE_TASK_BOUND')

    def test_nested_scopes_remain_structured(self):
        inner=scope([
            {"name":"i1","type":"Int","body":cint(2)},
            {"name":"i2","type":"Int","body":cint(3)},
        ],plus(param("i1"),param("i2")))
        outer=scope([
            {"name":"nested","type":"Int","body":inner},
            {"name":"direct","type":"Int","body":cint(4)},
        ],plus(param("nested"),param("direct")))
        self.assertEqual(evaluate_pure_v4(outer,self.table).result_encoded,{"$int":"9"})


if __name__=='__main__': unittest.main()
