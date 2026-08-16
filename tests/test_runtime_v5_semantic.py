from __future__ import annotations

from dataclasses import replace
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_kernel_v1 import verify_continuation_link
from tev_script.omega_semantic_basis_v1 import field_fact, field_transformation, semantic_field
from tev_script.program_ir_v5_semantic import (
    initial_process_checkpoint,
    instruction_apply,
    instruction_branch_fact,
    instruction_halt,
    instruction_jump,
    semantic_process_program,
)
from tev_script.runtime_v5_semantic import run_semantic_quantum, validate_quantum_result


class RuntimeV5SemanticTests(unittest.TestCase):
    EFFECTS = "1" * 64
    RESOURCES = "2" * 64
    AUTHORITY = "3" * 64
    SOURCE = "4" * 64

    def _door(self, *, step_limit: int = 8):
        closed = field_fact("door.state", ("closed",))
        opened = field_fact("door.state", ("open",))
        initial = semantic_field((closed,), profile="actual")
        tx = field_transformation(
            transformation_id="door.open",
            remove_fact_hashes=(closed.fact_hash,),
            add_facts=(opened,),
            effect_set_hash=self.EFFECTS,
            resource_vector_hash=self.RESOURCES,
        )
        return closed, opened, initial, tx

    def test_apply_then_halt_returns_halted_continuation(self) -> None:
        _closed, opened, initial, tx = self._door()
        program = semantic_process_program(
            program_id="Door", source_semantic_hash=self.SOURCE,
            initial_field=initial, transformations=(tx,),
            instructions=(instruction_apply(tx.transformation_hash, next_pc=1), instruction_halt()),
            entry_pc=0, quantum_step_limit=8, authority_hash=self.AUTHORITY,
        )
        result = run_semantic_quantum(program, initial_process_checkpoint(program))
        self.assertEqual(result.status, "HALTED")
        self.assertEqual(result.steps_used, 2)
        self.assertEqual(result.field.facts, (opened,))
        self.assertEqual(result.pc, 1)
        self.assertTrue(result.next_checkpoint.halted)
        self.assertEqual(result.next_checkpoint.next_epoch_index, 1)
        self.assertEqual(result.next_checkpoint.previous_continuation, result.continuation)
        self.assertEqual(len(result.apply_receipt_hashes), 1)
        self.assertEqual(validate_quantum_result(program, result), result)

    def test_cycle_suspends_exactly_at_quantum_budget(self) -> None:
        _closed, _opened, initial, _tx = self._door(step_limit=3)
        program = semantic_process_program(
            program_id="Cycle", source_semantic_hash=self.SOURCE,
            initial_field=initial, transformations=(),
            instructions=(instruction_jump(0),), entry_pc=0,
            quantum_step_limit=3, authority_hash=self.AUTHORITY,
        )
        first = run_semantic_quantum(program, initial_process_checkpoint(program))
        self.assertEqual(first.status, "SUSPENDED")
        self.assertEqual(first.steps_used, 3)
        self.assertEqual(first.pc, 0)
        self.assertFalse(first.next_checkpoint.halted)
        second = run_semantic_quantum(program, first.next_checkpoint)
        self.assertEqual(second.status, "SUSPENDED")
        self.assertEqual(second.steps_used, 3)
        self.assertTrue(verify_continuation_link(first.continuation, second.continuation))
        self.assertEqual(second.continuation.epoch_index, 1)

    def test_branch_fact_is_deterministic(self) -> None:
        closed, _opened, initial, _tx = self._door()
        program = semantic_process_program(
            program_id="Branch", source_semantic_hash=self.SOURCE,
            initial_field=initial, transformations=(),
            instructions=(
                instruction_branch_fact(closed.fact_hash, present_pc=1, absent_pc=2),
                instruction_halt(),
                instruction_jump(2),
            ),
            entry_pc=0, quantum_step_limit=4, authority_hash=self.AUTHORITY,
        )
        result = run_semantic_quantum(program, initial_process_checkpoint(program))
        self.assertEqual(result.status, "HALTED")
        self.assertEqual(result.steps_used, 2)
        self.assertEqual(result.pc, 1)

    def test_inapplicable_transformation_fails_closed_without_continuation(self) -> None:
        _closed, _opened, initial, _tx = self._door()
        missing = field_fact("door.missing", (True,))
        bad = field_transformation(
            transformation_id="bad.remove",
            remove_fact_hashes=(missing.fact_hash,),
            effect_set_hash=self.EFFECTS,
            resource_vector_hash=self.RESOURCES,
        )
        program = semantic_process_program(
            program_id="Bad", source_semantic_hash=self.SOURCE,
            initial_field=initial, transformations=(bad,),
            instructions=(instruction_apply(bad.transformation_hash, next_pc=1), instruction_halt()),
            entry_pc=0, quantum_step_limit=4, authority_hash=self.AUTHORITY,
        )
        with self.assertRaises(TevScriptError):
            run_semantic_quantum(program, initial_process_checkpoint(program))

    def test_halted_checkpoint_cannot_resume(self) -> None:
        _closed, _opened, initial, _tx = self._door()
        program = semantic_process_program(
            program_id="H", source_semantic_hash=self.SOURCE,
            initial_field=initial, transformations=(), instructions=(instruction_halt(),),
            entry_pc=0, quantum_step_limit=1, authority_hash=self.AUTHORITY,
        )
        result = run_semantic_quantum(program, initial_process_checkpoint(program))
        self.assertEqual(result.status, "HALTED")
        with self.assertRaises(TevScriptError):
            run_semantic_quantum(program, result.next_checkpoint)

    def test_quantum_result_tamper_is_rejected(self) -> None:
        _closed, _opened, initial, _tx = self._door()
        program = semantic_process_program(
            program_id="T", source_semantic_hash=self.SOURCE,
            initial_field=initial, transformations=(), instructions=(instruction_jump(0),),
            entry_pc=0, quantum_step_limit=2, authority_hash=self.AUTHORITY,
        )
        result = run_semantic_quantum(program, initial_process_checkpoint(program))
        with self.assertRaises(TevScriptError):
            validate_quantum_result(program, replace(result, result_hash="0" * 64))
        with self.assertRaises(TevScriptError):
            validate_quantum_result(program, replace(result, quantum_hash="0" * 64))


if __name__ == "__main__":
    unittest.main()
