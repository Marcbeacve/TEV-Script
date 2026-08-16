from __future__ import annotations

from dataclasses import replace
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import field_fact, field_transformation, semantic_field
from tev_script.program_ir_v5_semantic import (
    initial_process_checkpoint,
    instruction_apply,
    instruction_branch_fact,
    instruction_halt,
    instruction_jump,
    semantic_process_program,
    validate_process_checkpoint,
    validate_semantic_process_program,
)


class ProgramIrV5SemanticTests(unittest.TestCase):
    EFFECTS = "1" * 64
    RESOURCES = "2" * 64
    AUTHORITY = "3" * 64
    SOURCE = "4" * 64

    def _field_and_tx(self):
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

    def test_program_is_canonical_and_checkpoint_is_exact(self) -> None:
        closed, _opened, initial, tx = self._field_and_tx()
        instructions = (
            instruction_branch_fact(closed.fact_hash, present_pc=1, absent_pc=2),
            instruction_apply(tx.transformation_hash, next_pc=2),
            instruction_halt(),
        )
        program = semantic_process_program(
            program_id="DoorProcess",
            source_semantic_hash=self.SOURCE,
            initial_field=initial,
            transformations=(tx,),
            instructions=instructions,
            entry_pc=0,
            quantum_step_limit=8,
            authority_hash=self.AUTHORITY,
        )
        self.assertEqual(validate_semantic_process_program(program), program)
        checkpoint = initial_process_checkpoint(program)
        self.assertEqual(checkpoint.field, initial)
        self.assertEqual(checkpoint.pc, 0)
        self.assertEqual(checkpoint.next_epoch_index, 0)
        self.assertIsNone(checkpoint.previous_continuation)
        self.assertFalse(checkpoint.halted)
        self.assertEqual(validate_process_checkpoint(program, checkpoint), checkpoint)

    def test_transformation_table_order_is_nonsemantic(self) -> None:
        _closed, _opened, initial, tx = self._field_and_tx()
        tx2 = field_transformation(
            transformation_id="door.noop",
            effect_set_hash=self.EFFECTS,
            resource_vector_hash=self.RESOURCES,
        )
        instructions = (instruction_halt(),)
        left = semantic_process_program(
            program_id="P", source_semantic_hash=self.SOURCE, initial_field=initial,
            transformations=(tx, tx2), instructions=instructions, entry_pc=0,
            quantum_step_limit=1, authority_hash=self.AUTHORITY,
        )
        right = semantic_process_program(
            program_id="P", source_semantic_hash=self.SOURCE, initial_field=initial,
            transformations=(tx2, tx), instructions=instructions, entry_pc=0,
            quantum_step_limit=1, authority_hash=self.AUTHORITY,
        )
        self.assertEqual(left, right)

    def test_invalid_pc_target_rejects(self) -> None:
        _closed, _opened, initial, tx = self._field_and_tx()
        with self.assertRaises(TevScriptError):
            semantic_process_program(
                program_id="Bad", source_semantic_hash=self.SOURCE, initial_field=initial,
                transformations=(tx,), instructions=(instruction_apply(tx.transformation_hash, next_pc=9),),
                entry_pc=0, quantum_step_limit=1, authority_hash=self.AUTHORITY,
            )

    def test_unknown_transformation_and_proof_open_transformation_reject(self) -> None:
        _closed, _opened, initial, tx = self._field_and_tx()
        with self.assertRaises(TevScriptError):
            semantic_process_program(
                program_id="Unknown", source_semantic_hash=self.SOURCE, initial_field=initial,
                transformations=(tx,), instructions=(instruction_apply("f" * 64, next_pc=0),),
                entry_pc=0, quantum_step_limit=1, authority_hash=self.AUTHORITY,
            )
        proof_open = field_transformation(
            transformation_id="proof.open",
            effect_set_hash=self.EFFECTS,
            resource_vector_hash=self.RESOURCES,
            proof_requirement_hashes=("a" * 64,),
        )
        with self.assertRaises(TevScriptError):
            semantic_process_program(
                program_id="ProofOpen", source_semantic_hash=self.SOURCE, initial_field=initial,
                transformations=(proof_open,), instructions=(instruction_halt(),),
                entry_pc=0, quantum_step_limit=1, authority_hash=self.AUTHORITY,
            )

    def test_program_and_checkpoint_tamper_reject(self) -> None:
        _closed, _opened, initial, _tx = self._field_and_tx()
        program = semantic_process_program(
            program_id="P", source_semantic_hash=self.SOURCE, initial_field=initial,
            transformations=(), instructions=(instruction_jump(0),), entry_pc=0,
            quantum_step_limit=2, authority_hash=self.AUTHORITY,
        )
        with self.assertRaises(TevScriptError):
            validate_semantic_process_program(replace(program, program_hash="0" * 64))
        checkpoint = initial_process_checkpoint(program)
        with self.assertRaises(TevScriptError):
            validate_process_checkpoint(program, replace(checkpoint, checkpoint_hash="0" * 64))


if __name__ == "__main__":
    unittest.main()
