from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import unittest

from tev_script.canonical import canonical_json
from tev_script.program_ir_v5_total import total_core_program_to_mapping
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
from tev_script.runtime_v5_total_optimized import (
    prepare_total_core_execution_plan,
    run_prepared_total_core_quantum,
)
from tests.test_runtime_v5_total import RuntimeV5TotalCoreTests, _base_program
from tests.test_runtime_v5_total_optimized import _jump_program, _proof_apply_program


ROOT = Path(__file__).resolve().parents[1]
JS_RUNTIME = ROOT / "runtime_js_v31" / "runtime_v5_total.mjs"


class OptimizedJavaScriptRuntimeV5TotalCoreParityTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def _python_bytes(result) -> str:
        return canonical_json(asdict(result)) + "\n"

    def _node_raw(
        self,
        program_mapping: dict,
        checkpoint_mapping: dict,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("node", str(JS_RUNTIME)),
            input=canonical_json(
                {
                    "program": program_mapping,
                    "checkpoint": checkpoint_mapping,
                }
            ),
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=30,
            check=False,
        )

    def _assert_direct_parity(self, program) -> None:
        checkpoint = initial_total_core_checkpoint(program)
        reference = run_total_core_quantum(program, checkpoint)
        optimized = run_prepared_total_core_quantum(
            prepare_total_core_execution_plan(program),
            checkpoint,
        )
        self.assertEqual(optimized, reference)

        completed = self._node_raw(
            total_core_program_to_mapping(program),
            asdict(checkpoint),
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, self._python_bytes(optimized))

    def test_pure_v4_child_is_directly_identical_to_optimized_python(self) -> None:
        unit = RuntimeV5TotalCoreTests().pure_unit()
        self._assert_direct_parity(_base_program(unit))

    def test_recursive_v4_child_is_directly_identical_to_optimized_python(self) -> None:
        unit = RuntimeV5TotalCoreTests().recursive_unit()
        self._assert_direct_parity(_base_program(unit))

    def test_effects_v4_child_is_directly_identical_to_optimized_python(self) -> None:
        unit = RuntimeV5TotalCoreTests().effects_unit()
        self._assert_direct_parity(_base_program(unit))

    def test_proof_admitted_apply_is_directly_identical_to_optimized_python(self) -> None:
        self._assert_direct_parity(_proof_apply_program())

    def test_two_epoch_cycle_matches_optimized_continuation_chain(self) -> None:
        program = _jump_program()
        plan = prepare_total_core_execution_plan(program)
        initial = initial_total_core_checkpoint(program)

        optimized_first = run_prepared_total_core_quantum(plan, initial)
        reference_first = run_total_core_quantum(program, initial)
        self.assertEqual(optimized_first, reference_first)
        js_first = self._node_raw(
            total_core_program_to_mapping(program),
            asdict(initial),
        )
        self.assertEqual(js_first.returncode, 0, js_first.stderr)
        self.assertEqual(js_first.stdout, self._python_bytes(optimized_first))

        optimized_second = run_prepared_total_core_quantum(
            plan,
            optimized_first.next_checkpoint,
        )
        reference_second = run_total_core_quantum(
            program,
            reference_first.next_checkpoint,
        )
        self.assertEqual(optimized_second, reference_second)

        js_first_object = json.loads(js_first.stdout)
        js_second = self._node_raw(
            total_core_program_to_mapping(program),
            js_first_object["next_checkpoint"],
        )
        self.assertEqual(js_second.returncode, 0, js_second.stderr)
        self.assertEqual(js_second.stdout, self._python_bytes(optimized_second))
        self.assertEqual(
            json.loads(js_second.stdout)["continuation"]["previous_continuation_hash"],
            optimized_first.continuation.continuation_hash,
        )


if __name__ == "__main__":
    unittest.main()
