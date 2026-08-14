from __future__ import annotations

import threading
import time
from pathlib import Path
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.file_observation_acquisition_v2 import (
    FileReadAcquiredCallV2,
    acquire_file_read_observations_v2,
    build_file_read_acquisition_request_v2,
    scenario_from_file_read_evidence_v2,
)
from tev_script.file_observation_scheduler_v2 import BoundedThreadFileReadAcquisitionStrategyV2
from tev_script.source_effect_program_v2 import compile_effect_program_v2


SOURCE = 'script ParallelRead version "2.0.0"; state content:Text=""; capability observation file.read(Text)->Text; action load() { observe body=file.read("a.txt"); set content=body; } entry main=load();'


class FileObservationSchedulerV2Tests(unittest.TestCase):
    def compiled(self):
        return compile_effect_program_v2(SOURCE)

    def test_workers_1_2_4_produce_identical_evidence_and_scenario(self):
        compiled=self.compiled()
        request=build_file_read_acquisition_request_v2(compiled.capabilities,["a.txt","b.txt","c.txt"])
        with tempfile.TemporaryDirectory(prefix="tev-file-par-") as td:
            root=Path(td)
            for name,text in (("a.txt","alpha"),("b.txt","beta"),("c.txt","gamma")):
                (root/name).write_text(text,encoding="utf-8")
            reference=acquire_file_read_observations_v2(request,compiled.capabilities,root)
            reference_scenario=scenario_from_file_read_evidence_v2(reference,compiled.capabilities)
            for workers in (1,2,4):
                actual=acquire_file_read_observations_v2(
                    request,compiled.capabilities,root,
                    execution_strategy=BoundedThreadFileReadAcquisitionStrategyV2(workers),
                )
                self.assertEqual(actual,reference)
                self.assertEqual(actual["evidence_hash"],reference["evidence_hash"])
                self.assertEqual(scenario_from_file_read_evidence_v2(actual,compiled.capabilities),reference_scenario)

    def test_scheduler_is_physically_concurrent(self):
        strategy=BoundedThreadFileReadAcquisitionStrategyV2(2)
        barrier=threading.Barrier(2)
        lock=threading.Lock(); thread_ids=set()
        def acquire(index,call):
            with lock: thread_ids.add(threading.get_ident())
            barrier.wait(timeout=2)
            return FileReadAcquiredCallV2(index,{"call_index":index})
        result=strategy.run(((0,{"arguments":["a"]}),(1,{"arguments":["b"]})),acquire)
        self.assertEqual([item.call_index for item in result],[0,1])
        self.assertEqual(len(thread_ids),2)

    def test_failure_selection_follows_request_order_not_completion_order(self):
        strategy=BoundedThreadFileReadAcquisitionStrategyV2(2)
        def acquire(index,call):
            if index==0:
                time.sleep(0.03)
                raise TevScriptError("TEVS_TEST_CANONICAL_FIRST","first")
            raise TevScriptError("TEVS_TEST_FAST_SECOND","second")
        with self.assertRaises(TevScriptError) as captured:
            strategy.run(((0,{}),(1,{})),acquire)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_TEST_CANONICAL_FIRST")

    def test_core_reassembles_strategy_completion_order_by_call_index(self):
        compiled=self.compiled()
        request=build_file_read_acquisition_request_v2(compiled.capabilities,["a.txt","b.txt"])
        class ReverseStrategy:
            def run(self,calls,acquire_call):
                return tuple(reversed([acquire_call(index,call) for index,call in calls]))
        with tempfile.TemporaryDirectory(prefix="tev-file-reverse-") as td:
            root=Path(td); (root/"a.txt").write_text("A",encoding="utf-8"); (root/"b.txt").write_text("B",encoding="utf-8")
            reference=acquire_file_read_observations_v2(request,compiled.capabilities,root)
            actual=acquire_file_read_observations_v2(request,compiled.capabilities,root,execution_strategy=ReverseStrategy())
            self.assertEqual(actual,reference)
            self.assertEqual([row["call_index"] for row in actual["calls"]],[0,1])

    def test_missing_duplicate_or_forged_indexes_fail_closed(self):
        compiled=self.compiled()
        request=build_file_read_acquisition_request_v2(compiled.capabilities,["a.txt","b.txt"])
        class DuplicateStrategy:
            def run(self,calls,acquire_call):
                first=acquire_call(*calls[0]); return (first,first)
        with tempfile.TemporaryDirectory(prefix="tev-file-broken-") as td:
            root=Path(td); (root/"a.txt").write_text("A",encoding="utf-8"); (root/"b.txt").write_text("B",encoding="utf-8")
            with self.assertRaises(TevScriptError) as captured:
                acquire_file_read_observations_v2(request,compiled.capabilities,root,execution_strategy=DuplicateStrategy())
            self.assertEqual(captured.exception.diagnostic.code,"TEVS_FILE_READ_ACQUISITION_STRATEGY")

    def test_worker_bounds_and_descriptor_are_operational(self):
        for value in (0,65):
            with self.assertRaises(TevScriptError): BoundedThreadFileReadAcquisitionStrategyV2(value)
        descriptor=BoundedThreadFileReadAcquisitionStrategyV2(3).descriptor()
        self.assertEqual(descriptor["worker_count"],3)
        self.assertFalse(descriptor["worker_count_is_semantic"])
        self.assertEqual(descriptor["assembly_policy"],"canonical_request_order_v1")


if __name__=="__main__": unittest.main()
