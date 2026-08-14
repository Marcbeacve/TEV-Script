from __future__ import annotations

import threading
import time
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_pure import TaskChildEvaluationV4, TypedValueV4, evaluate_pure_v4
from tev_script.ir_v4_values import build_type_table_v4
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2
from tev_script.task_scheduler_v2 import BoundedThreadTaskStrategyV2


def _table():
    return build_type_table_v4({
        "boundary":{"maximum_value_nesting":16},
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


def cint(value:int):
    return {"op":"CONST","type":"Int","value":{"$int":str(value)}}


def plus(a,b):
    return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}


def scope(a,b):
    return {
        "op":"TASK_SCOPE",
        "result_type":"Int",
        "join_policy":"all_success_v1",
        "cancellation_policy":"cancel_siblings_on_failure_v1",
        "tasks":[{"name":"a","type":"Int","body":a},{"name":"b","type":"Int","body":b}],
        "join":plus({"op":"PARAM","name":"a","type":"Int"},{"op":"PARAM","name":"b","type":"Int"}),
    }


class TaskSchedulerV2Tests(unittest.TestCase):
    def test_worker_count_is_operational_not_semantic(self):
        expr=scope(plus(cint(1),cint(2)),plus(cint(3),cint(4)))
        reference=evaluate_pure_v4(expr,_table())
        for workers in (1,2,4):
            actual=evaluate_pure_v4(expr,_table(),task_strategy=BoundedThreadTaskStrategyV2(workers))
            self.assertEqual(actual.receipt_hash,reference.receipt_hash)
            self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)
            self.assertEqual(actual.result_encoded,{"$int":"10"})

    def test_nested_scopes_preserve_reference_receipt(self):
        expr=scope(scope(cint(1),cint(2)),scope(cint(3),cint(4)))
        reference=evaluate_pure_v4(expr,_table())
        actual=evaluate_pure_v4(expr,_table(),task_strategy=BoundedThreadTaskStrategyV2(4))
        self.assertEqual(actual.receipt_hash,reference.receipt_hash)
        self.assertEqual(actual.result_encoded,{"$int":"10"})

    def test_program_ir_receipt_is_scheduler_independent(self):
        source='script SchedulerDemo version "2.0.0"; entry main:Int=await all(a:Int=1+2,b:Int=3+4)=>a+b;'
        compiled,_=compile_and_run_program_v2(source)
        ir=export_program_ir_v4_pure(compiled)
        reference=run_program_ir_v4_pure(ir)
        actual=run_program_ir_v4_pure(ir,task_strategy=BoundedThreadTaskStrategyV2(4))
        self.assertEqual(actual.receipt_hash,reference.receipt_hash)
        self.assertEqual(actual.evaluation_receipt_hash,reference.evaluation_receipt_hash)
        self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)

    def test_two_workers_are_physically_concurrent(self):
        strategy=BoundedThreadTaskStrategyV2(2)
        barrier=threading.Barrier(2)
        lock=threading.Lock()
        thread_ids=set()
        def evaluate(task):
            with lock:
                thread_ids.add(threading.get_ident())
            barrier.wait(timeout=2)
            return TaskChildEvaluationV4(str(task["name"]),TypedValueV4("Int",1),1,0)
        result=strategy.run(({"name":"a"},{"name":"b"}),evaluate)
        self.assertEqual(len(result),2)
        self.assertEqual(len(thread_ids),2)

    def test_failure_selection_uses_canonical_task_order(self):
        strategy=BoundedThreadTaskStrategyV2(2)
        def evaluate(task):
            if task["name"]=="a":
                time.sleep(0.03)
                raise TevScriptError("TEVS_TEST_CANONICAL_A","a")
            raise TevScriptError("TEVS_TEST_FAST_B","b")
        with self.assertRaises(TevScriptError) as captured:
            strategy.run(({"name":"a"},{"name":"b"}),evaluate)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_TEST_CANONICAL_A")

    def test_invalid_strategy_results_and_worker_bounds_fail_closed(self):
        for workers in (0,65):
            with self.assertRaises(TevScriptError):
                BoundedThreadTaskStrategyV2(workers)
        class Broken:
            def run(self,tasks,evaluate_child):
                return (evaluate_child(tasks[0]),)
        with self.assertRaises(TevScriptError) as captured:
            evaluate_pure_v4(scope(cint(1),cint(2)),_table(),task_strategy=Broken())
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_TASK_STRATEGY")


if __name__=="__main__": unittest.main()
