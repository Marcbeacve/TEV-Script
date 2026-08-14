from __future__ import annotations

import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import canonical_program_ir_v4_bytes, export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2
from tev_script.task_scheduler_v2 import BoundedThreadTaskStrategyV2


class TaskDagV2Tests(unittest.TestCase):
    SOURCE='''
    script TaskDag version "2.0.0";
    fn square(x:Int)->Int=x*x;
    entry main:Int=task scope {
        spawn a:Int=square(3);
        spawn b:Int=square(4);
        spawn c:Int=await a + await b;
        return await c;
    };
    '''

    def test_source_dag_executes_dependencies(self):
        compiled,receipt=compile_and_run_program_v2(self.SOURCE)
        self.assertEqual(receipt.result_encoded,{"$int":"25"})
        ir=export_program_ir_v4_pure(compiled)
        body=ir["entry"]["body"]
        self.assertEqual(body["op"],"TASK_DAG")
        self.assertEqual([(t["name"],t["dependencies"]) for t in body["tasks"]],[("a",[]),("b",[]),("c",["a","b"])])

    def test_spawn_declaration_order_is_nonsemantic(self):
        alternate=self.SOURCE.replace(
            'spawn a:Int=square(3);\n        spawn b:Int=square(4);\n        spawn c:Int=await a + await b;',
            'spawn c:Int=await a + await b;\n        spawn b:Int=square(4);\n        spawn a:Int=square(3);',
        )
        a,ar=compile_and_run_program_v2(self.SOURCE)
        b,br=compile_and_run_program_v2(alternate)
        self.assertEqual(a.semantic_hash,b.semantic_hash)
        self.assertEqual(a.entry.entry_hash,b.entry.entry_hash)
        self.assertEqual(ar.receipt_hash,br.receipt_hash)

    def test_task_result_requires_await(self):
        bad=self.SOURCE.replace('return await c;','return c;')
        with self.assertRaises(TevScriptError) as captured: compile_program_v2(bad)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_NAME")

    def test_await_unknown_task_fails_closed(self):
        bad=self.SOURCE.replace('return await c;','return await missing;')
        with self.assertRaises(TevScriptError) as captured: compile_program_v2(bad)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_TASK_AWAIT")

    def test_self_and_mutual_cycles_fail_closed(self):
        self_cycle='script Cycle version "2.0.0"; entry main:Int=task scope { spawn a:Int=await a; return await a; };'
        with self.assertRaises(TevScriptError): compile_program_v2(self_cycle)
        mutual='script Cycle2 version "2.0.0"; entry main:Int=task scope { spawn a:Int=await b; spawn b:Int=await a; return await a; };'
        with self.assertRaises(TevScriptError) as captured: compile_program_v2(mutual)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_TASK_DAG_CYCLE")

    def test_task_name_cannot_shadow_outer_value(self):
        source='script Shadow version "2.0.0"; fn f(a:Int)->Int=task scope { spawn a:Int=1; return await a; }; entry main:Int=f(2);'
        with self.assertRaises(TevScriptError) as captured: compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_TASK_DAG_BINDING")

    def test_nested_task_scope_is_rejected_in_r1(self):
        source='script NestedDag version "2.0.0"; entry main:Int=task scope { spawn a:Int=task scope { spawn b:Int=1; return await b; }; return await a; };'
        with self.assertRaises(TevScriptError) as captured: compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_TASK_DAG_NESTING")

    def test_await_task_outside_scope_is_rejected(self):
        source='script LooseAwait version "2.0.0"; entry main:Int=await x;'
        with self.assertRaises(TevScriptError) as captured: compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_TASK_AWAIT")

    def test_program_ir_detached_roundtrip(self):
        compiled,source_receipt=compile_and_run_program_v2(self.SOURCE)
        ir=export_program_ir_v4_pure(compiled)
        detached=json.loads(canonical_program_ir_v4_bytes(ir).decode("utf-8"))
        portable=run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_encoded,source_receipt.result_encoded)
        self.assertEqual(portable.result_hash,source_receipt.result_hash)
        self.assertEqual(detached["entry"]["body"]["op"],"TASK_DAG")

    def test_workers_1_2_4_preserve_exact_receipt(self):
        compiled,_=compile_and_run_program_v2(self.SOURCE)
        ir=export_program_ir_v4_pure(compiled)
        reference=run_program_ir_v4_pure(ir)
        for workers in (1,2,4):
            actual=run_program_ir_v4_pure(ir,task_strategy=BoundedThreadTaskStrategyV2(workers))
            self.assertEqual(actual.receipt_hash,reference.receipt_hash)
            self.assertEqual(actual.evaluation_receipt_hash,reference.evaluation_receipt_hash)
            self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)

    def test_scheduler_observes_canonical_topological_waves(self):
        compiled,_=compile_and_run_program_v2(self.SOURCE)
        ir=export_program_ir_v4_pure(compiled)
        class RecordingStrategy:
            def __init__(self): self.waves=[]
            def run(self,tasks,evaluate_child):
                self.waves.append(tuple(str(task["name"]) for task in tasks))
                return tuple(evaluate_child(task) for task in tasks)
        strategy=RecordingStrategy()
        result=run_program_ir_v4_pure(ir,task_strategy=strategy)
        self.assertEqual(result.result_encoded,{"$int":"25"})
        self.assertEqual(strategy.waves,[("a","b"),("c",)])


if __name__=="__main__": unittest.main()
