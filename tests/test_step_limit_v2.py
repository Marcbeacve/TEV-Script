from __future__ import annotations

import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import canonical_program_ir_v4_bytes, export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2
from tev_script.task_scheduler_v2 import BoundedThreadTaskStrategyV2


class StepLimitV2Tests(unittest.TestCase):
    def test_exact_child_step_bound_succeeds(self):
        source='script StepExact version "2.0.0"; entry main:Int=within_steps 3 do 1+2;'
        compiled,_=compile_and_run_program_v2(source)
        receipt=run_program_ir_v4_pure(export_program_ir_v4_pure(compiled))
        self.assertEqual(receipt.result_encoded,{"$int":"3"})
        self.assertEqual(receipt.evaluation_steps,4)

    def test_one_step_below_required_fails_closed(self):
        source='script StepTooSmall version "2.0.0"; entry main:Int=within_steps 2 do 1+2;'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(ir)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_BUDGET")

    def test_step_limit_is_semantic_identity(self):
        a=compile_program_v2('script StepIdentity version "2.0.0"; entry main:Int=within_steps 3 do 1+2;')
        b=compile_program_v2('script StepIdentity version "2.0.0"; entry main:Int=within_steps 4 do 1+2;')
        self.assertNotEqual(a.semantic_hash,b.semantic_hash)
        self.assertNotEqual(a.entry.entry_hash,b.entry.entry_hash)
        ia=export_program_ir_v4_pure(a); ib=export_program_ir_v4_pure(b)
        self.assertNotEqual(ia["program_ir_hash"],ib["program_ir_hash"])
        self.assertEqual(run_program_ir_v4_pure(ia).result_encoded,run_program_ir_v4_pure(ib).result_encoded)

    def test_invalid_source_limits_fail_closed(self):
        for raw in ("0","1.5","1000001"):
            source=f'script StepInvalid version "2.0.0"; entry main:Int=within_steps {raw} do 1;'
            with self.assertRaises(TevScriptError) as captured:
                compile_program_v2(source)
            self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_STEP_LIMIT")

    def test_step_limit_preserves_type_contract(self):
        source='script StepType version "2.0.0"; entry main:Text=within_steps 3 do 1+2;'
        with self.assertRaises(TevScriptError):
            compile_program_v2(source)

    def test_program_ir_detached_roundtrip_preserves_limit(self):
        source='script StepPortable version "2.0.0"; entry main:Int=within_steps 3 do 1+2;'
        compiled,_=compile_and_run_program_v2(source)
        ir=export_program_ir_v4_pure(compiled)
        detached=json.loads(canonical_program_ir_v4_bytes(ir).decode("utf-8"))
        self.assertEqual(detached["entry"]["body"]["op"],"STEP_LIMIT")
        self.assertEqual(detached["entry"]["body"]["maximum_steps"],3)
        actual=run_program_ir_v4_pure(detached)
        reference=run_program_ir_v4_pure(ir)
        self.assertEqual(actual.receipt_hash,reference.receipt_hash)
        self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)

    def test_step_limit_wraps_task_dag_with_scheduler_independent_receipt(self):
        source='''
        script StepDag version "2.0.0";
        fn square(x:Int)->Int=x*x;
        entry main:Int=within_steps 100 do task scope {
            spawn a:Int=square(3);
            spawn b:Int=square(4);
            spawn c:Int=await a + await b;
            return await c;
        };
        '''
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        reference=run_program_ir_v4_pure(ir)
        self.assertEqual(reference.result_encoded,{"$int":"25"})
        self.assertEqual(ir["entry"]["body"]["op"],"STEP_LIMIT")
        self.assertEqual(ir["entry"]["body"]["body"]["op"],"TASK_DAG")
        for workers in (1,2,4):
            actual=run_program_ir_v4_pure(ir,task_strategy=BoundedThreadTaskStrategyV2(workers))
            self.assertEqual(actual.receipt_hash,reference.receipt_hash)
            self.assertEqual(actual.evaluation_receipt_hash,reference.evaluation_receipt_hash)
            self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)

    def test_insufficient_task_dag_limit_fails_identically_for_all_worker_counts(self):
        source='''
        script StepDagFail version "2.0.0";
        entry main:Int=within_steps 1 do task scope {
            spawn a:Int=1;
            spawn b:Int=2;
            return await a + await b;
        };
        '''
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        for strategy in (None,BoundedThreadTaskStrategyV2(1),BoundedThreadTaskStrategyV2(2),BoundedThreadTaskStrategyV2(4)):
            with self.assertRaises(TevScriptError) as captured:
                run_program_ir_v4_pure(ir,task_strategy=strategy)
            self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_BUDGET")


if __name__=="__main__": unittest.main()
