from __future__ import annotations

import threading
import time
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_pure import PrioritySelectCandidateOutcomeV4, TypedValueV4
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_program_v2
from tev_script.task_scheduler_v2 import BoundedThreadTaskStrategyV2


class PrioritySelectSpeculationV2Tests(unittest.TestCase):
    def test_run_select_is_physically_concurrent(self):
        strategy=BoundedThreadTaskStrategyV2(2)
        barrier=threading.Barrier(2)
        lock=threading.Lock(); thread_ids=set()
        def evaluate(item):
            index,_candidate=item
            with lock: thread_ids.add(threading.get_ident())
            barrier.wait(timeout=2)
            return PrioritySelectCandidateOutcomeV4(index,TypedValueV4("Int",index),1,0,None)
        outcomes=strategy.run_select(((0,{}),(1,{})),evaluate)
        self.assertEqual([item.index for item in outcomes],[0,1])
        self.assertEqual(len(thread_ids),2)

    def test_fallback_receipt_is_identical_with_speculation(self):
        source='script SelectSpecFallback version "2.0.0"; entry main:Int=select first_within { within_steps 2 do 1+2; within_steps 3 do 4+5; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        reference=run_program_ir_v4_pure(ir)
        for workers in (1,2,4):
            actual=run_program_ir_v4_pure(ir,task_strategy=BoundedThreadTaskStrategyV2(workers))
            self.assertEqual(actual.receipt_hash,reference.receipt_hash)
            self.assertEqual(actual.evaluation_receipt_hash,reference.evaluation_receipt_hash)
            self.assertEqual(actual.evaluation_steps,reference.evaluation_steps)
            self.assertEqual(actual.result_encoded,{"$int":"9"})

    def test_lower_priority_fatal_error_is_unobservable_when_higher_priority_wins(self):
        source='script SelectSpecLazy version "2.0.0"; entry main:Rat=select first_within { within_steps 3 do 1/1; within_steps 3 do 1/0; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        reference=run_program_ir_v4_pure(ir)
        actual=run_program_ir_v4_pure(ir,task_strategy=BoundedThreadTaskStrategyV2(2))
        self.assertEqual(actual.receipt_hash,reference.receipt_hash)
        self.assertEqual(actual.result_encoded,{"$rat":["1","1"]})

    def test_lower_priority_fatal_error_becomes_visible_after_budget_fallback(self):
        source='script SelectSpecFatal version "2.0.0"; entry main:Rat=select first_within { within_steps 2 do 1/1; within_steps 3 do 1/0; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        for strategy in (None,BoundedThreadTaskStrategyV2(2)):
            with self.assertRaises(TevScriptError) as captured:
                run_program_ir_v4_pure(ir,task_strategy=strategy)
            self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_DIVIDE_ZERO")

    def test_speculation_suppresses_nested_thread_pools(self):
        source='''
        script SelectSpecNested version "2.0.0";
        entry main:Int=select first_within {
            within_steps 100 do task scope { spawn a:Int=1; spawn b:Int=2; return await a+await b; };
            within_steps 1 do 9;
        };
        '''
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        class ProbeStrategy:
            def __init__(self): self.run_calls=0; self.select_calls=0
            def run(self,tasks,evaluate_child):
                self.run_calls+=1
                raise AssertionError("nested task scheduler must not be invoked during select speculation")
            def run_select(self,candidates,evaluate_candidate):
                self.select_calls+=1
                return tuple(evaluate_candidate(item) for item in candidates)
        strategy=ProbeStrategy()
        actual=run_program_ir_v4_pure(ir,task_strategy=strategy)
        self.assertEqual(actual.result_encoded,{"$int":"3"})
        self.assertEqual(strategy.select_calls,1)
        self.assertEqual(strategy.run_calls,0)

    def test_malformed_speculation_outcome_set_fails_closed(self):
        source='script SelectSpecBroken version "2.0.0"; entry main:Int=select first_within { within_steps 3 do 1+2; within_steps 3 do 4+5; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        class BrokenStrategy:
            def run_select(self,candidates,evaluate_candidate):
                return (evaluate_candidate(candidates[0]),)
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(ir,task_strategy=BrokenStrategy())
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_SELECT_STRATEGY")

    def test_scheduler_descriptor_declares_nonsemantic_speculation_policy(self):
        descriptor=BoundedThreadTaskStrategyV2(3).descriptor()
        self.assertTrue(descriptor["priority_select_speculation"])
        self.assertEqual(descriptor["select_observation_policy"],"priority_order_v1")
        self.assertEqual(descriptor["select_semantic_accounting"],"reference_prefix_v1")
        self.assertEqual(descriptor["nested_select_candidate_task_scheduling"],"sequential_v1")
        self.assertEqual(descriptor["select_cancellation_policy"],"cooperative_lower_priority_only_v1")
        self.assertEqual(descriptor["select_terminal_authority"],"kernel_priority_prefix_v1")
        self.assertFalse(descriptor["worker_count_is_semantic"])


    def test_cooperative_scheduler_cancels_running_lower_priority_candidate(self):
        strategy=BoundedThreadTaskStrategyV2(2)
        barrier=threading.Barrier(2); cancelled=threading.Event()
        def evaluate(item,cancel_check):
            index,_candidate=item
            barrier.wait(timeout=2)
            if index==0:
                return PrioritySelectCandidateOutcomeV4(0,TypedValueV4("Int",7),1,0,None)
            for _ in range(10000):
                if cancel_check():
                    cancelled.set()
                    return PrioritySelectCandidateOutcomeV4(1,None,0,0,RuntimeError("operational-cancel"))
                time.sleep(0.0001)
            self.fail("lower-priority candidate never observed cooperative cancellation")
        def terminal(item,outcome):
            return outcome.index==0
        outcomes=strategy.run_select_cooperative(((0,{}),(1,{})),evaluate,terminal)
        self.assertEqual([item.index for item in outcomes],[0])
        self.assertTrue(cancelled.is_set())

    def test_kernel_rejects_premature_cooperative_prefix(self):
        source='script SelectPremature version "2.0.0"; entry main:Int=select first_within { within_steps 2 do 1+2; within_steps 3 do 4+5; };'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        class PrematureStrategy:
            def run_select_cooperative(self,candidates,evaluate_candidate,is_terminal):
                first=evaluate_candidate(candidates[0],lambda:False)
                self.assert_not_terminal=is_terminal(candidates[0],first)
                return (first,)
        strategy=PrematureStrategy()
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(ir,task_strategy=strategy)
        self.assertFalse(strategy.assert_not_terminal)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_PURE_SELECT_STRATEGY")

if __name__=="__main__": unittest.main()
