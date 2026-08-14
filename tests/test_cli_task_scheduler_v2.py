from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v2 import main
from tev_script.program_ir_v4 import (
    canonical_program_ir_v4_bytes,
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
    run_program_ir_v4_pure,
)
from tev_script.source_program_v2 import compile_program_v2


class CliTaskSchedulerV2Tests(unittest.TestCase):
    def test_run_task_workers_preserves_exact_pure_receipt(self) -> None:
        source='script CliAsync version "2.0.0"; entry main:Int=await all(a:Int=1+2,b:Int=3+4)=>a+b;'
        compiled=compile_program_v2(source)
        ir=export_program_ir_v4_pure(compiled)
        reference=run_program_ir_v4_pure(ir)
        with tempfile.TemporaryDirectory(prefix="tev-cli-task-") as td:
            root=Path(td); program=root/"program.json"; output=root/"receipt.json"
            program.write_bytes(canonical_program_ir_v4_bytes(ir)+b"\n")
            stdout=StringIO(); stderr=StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code=main(["run",str(program),"--task-workers","2","--output",str(output)])
            self.assertEqual(code,0,stderr.getvalue())
            actual=json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(actual["receipt_hash"],reference.receipt_hash)
            self.assertEqual(actual["evaluation_receipt_hash"],reference.evaluation_receipt_hash)
            self.assertEqual(actual["evaluation_steps"],reference.evaluation_steps)
            summary=json.loads(stdout.getvalue().strip())
            self.assertEqual(summary["task_scheduler"]["worker_count"],2)
            self.assertFalse(summary["task_scheduler"]["worker_count_is_semantic"])

    def test_invalid_workers_fail_before_output_clobber(self) -> None:
        source='script CliAsyncBound version "2.0.0"; entry main:Int=await all(a:Int=1,b:Int=2)=>a+b;'
        ir=export_program_ir_v4_pure(compile_program_v2(source))
        with tempfile.TemporaryDirectory(prefix="tev-cli-task-bound-") as td:
            root=Path(td); program=root/"program.json"; output=root/"receipt.json"
            program.write_bytes(canonical_program_ir_v4_bytes(ir)+b"\n")
            output.write_bytes(b"sentinel")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code=main(["run",str(program),"--task-workers","0","--output",str(output)])
            self.assertEqual(code,2)
            self.assertEqual(output.read_bytes(),b"sentinel")

    def test_recursive_profile_rejects_physical_scheduler_r1(self) -> None:
        source='script CliRecursive version "2.0.0"; recursive fn f(n:Int)->Int decreases n max_depth 4=if n==0 then 0 else self(n-1); entry main:Int=f(2);'
        ir=export_program_ir_v4_recursive(compile_program_v2(source))
        with tempfile.TemporaryDirectory(prefix="tev-cli-task-rec-") as td:
            root=Path(td); program=root/"program.json"; output=root/"receipt.json"
            program.write_bytes(canonical_program_ir_v4_bytes(ir)+b"\n")
            stderr=StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                code=main(["run",str(program),"--task-workers","2","--output",str(output)])
            self.assertEqual(code,2)
            self.assertFalse(output.exists())
            self.assertIn("TEVS_PROGRAM_IR_V4_TASK_SCHEDULER_PROFILE",stderr.getvalue())


if __name__=="__main__": unittest.main()
