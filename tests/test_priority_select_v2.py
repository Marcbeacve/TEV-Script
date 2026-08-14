from __future__ import annotations

import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import canonical_program_ir_v4_bytes, export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2
from tev_script.task_scheduler_v2 import BoundedThreadTaskStrategyV2


class PrioritySelectV2Tests(unittest.TestCase):
    def test_first_candidate_within_budget_wins(self):
        source='script SelectFirst version "2.0.0"; entry main:Int=select first_within { within_steps 3 do 1+2; within_steps 3 do 4+5; };'
        compiled,_=compile_and_run_program_v2(source)
        ir=export_program_ir_v4_pure(compiled)
        receipt=run_program_ir_v4_pure(ir)
        self.assertEqual(receipt.result_encoded,{"$int":"3"})
        self.assertEqual(receipt.evaluation_steps,4)

    def test_first_budget_exhaustion_falls_back_to_second(self):
        source='script SelectFallback version "2.0.0"; entry main:Int=select first_within { within_steps 2 do 1+2; within_steps 3 do 4+5; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        receipt=run_program_ir_v4_pure(ir)
        self.assertEqual(receipt.result_encoded,{"$int":"9"})
        self.assertEqual(receipt.evaluation_steps,7)

    def test_priority_order_is_semantic_identity(self):
        left='script SelectIdentity version "2.0.0"; entry main:Int=select first_within { within_steps 3 do 1+2; within_steps 3 do 4+5; };'
        right='script SelectIdentity version "2.0.0"; entry main:Int=select first_within { within_steps 3 do 4+5; within_steps 3 do 1+2; };'
        a=compile_program_v2(left); b=compile_program_v2(right)
        self.assertNotEqual(a.semantic_hash,b.semantic_hash)
        self.assertNotEqual(a.entry.entry_hash,b.entry.entry_hash)
        ia=export_program_ir_v4_pure(a); ib=export_program_ir_v4_pure(b)
        self.assertNotEqual(ia["program_ir_hash"],ib["program_ir_hash"])
        self.assertEqual(run_program_ir_v4_pure(ia).result_encoded,{"$int":"3"})
        self.assertEqual(run_program_ir_v4_pure(ib).result_encoded,{"$int":"9"})

    def test_all_candidates_exhausted_fails_closed(self):
        source='script SelectExhausted version "2.0.0"; entry main:Int=select first_within { within_steps 2 do 1+2; within_steps 2 do 4+5; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(ir)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_SELECT_EXHAUSTED")

    def test_nested_budget_failure_does_not_trigger_fallback(self):
        source='script SelectNestedBudget version "2.0.0"; entry main:Int=select first_within { within_steps 100 do within_steps 1 do 1+2; within_steps 3 do 4+5; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(ir)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_BUDGET")

    def test_candidates_must_explicitly_declare_step_budget(self):
        source='script SelectBadCandidate version "2.0.0"; entry main:Int=select first_within { 1+2; within_steps 3 do 4+5; };'
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_SELECT_CANDIDATE")

    def test_candidate_types_must_match(self):
        source='script SelectTypes version "2.0.0"; entry main:Int=select first_within { within_steps 3 do 1+2; within_steps 1 do "x"; };'
        with self.assertRaises(TevScriptError):
            compile_program_v2(source)

    def test_program_ir_detached_preserves_priority_and_receipt(self):
        source='script SelectPortable version "2.0.0"; entry main:Int=select first_within { within_steps 2 do 1+2; within_steps 3 do 4+5; };'
        compiled,_=compile_and_run_program_v2(source)
        ir=export_program_ir_v4_pure(compiled)
        detached=json.loads(canonical_program_ir_v4_bytes(ir).decode("utf-8"))
        body=detached["entry"]["body"]
        self.assertEqual(body["op"],"PRIORITY_SELECT")
        self.assertEqual(body["selection_policy"],"canonical_priority_first_within_steps_v1")
        self.assertEqual([item["maximum_steps"] for item in body["candidates"]],[2,3])
        actual=run_program_ir_v4_pure(detached); reference=run_program_ir_v4_pure(ir)
        self.assertEqual(actual.receipt_hash,reference.receipt_hash)
        self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)

    def test_selected_task_dag_candidate_is_scheduler_independent(self):
        source='''
        script SelectDag version "2.0.0";
        entry main:Int=select first_within {
            within_steps 100 do task scope {
                spawn a:Int=1;
                spawn b:Int=2;
                return await a + await b;
            };
            within_steps 1 do 9;
        };
        '''
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        reference=run_program_ir_v4_pure(ir)
        self.assertEqual(reference.result_encoded,{"$int":"3"})
        for workers in (1,2,4):
            actual=run_program_ir_v4_pure(ir,task_strategy=BoundedThreadTaskStrategyV2(workers))
            self.assertEqual(actual.receipt_hash,reference.receipt_hash)
            self.assertEqual(actual.evaluation_receipt_hash,reference.evaluation_receipt_hash)
            self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)


if __name__=="__main__": unittest.main()
