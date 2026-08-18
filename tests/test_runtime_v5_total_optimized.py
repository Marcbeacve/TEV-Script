from __future__ import annotations

import unittest

from tev_script.omega_semantic_basis_v1 import semantic_field
from tev_script.program_ir_v5_total import TotalCoreInstructionV1, TotalCoreProgramV1
from tev_script.runtime_v5_total import (
    initial_total_core_checkpoint,
    run_total_core_quantum,
)
from tev_script.runtime_v5_total_optimized import (
    _OP_HALT,
    prepare_total_core_execution_plan,
    run_prepared_total_core_quantum,
)


AUTHORITY = "a" * 64
SOURCE = "b" * 64


def _halt_program() -> TotalCoreProgramV1:
    return TotalCoreProgramV1.build(
        program_id="OptimizedHalt",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((), profile="actual"),
        transformations=(),
        v4_units=(),
        proof_admissions=(),
        instructions=(TotalCoreInstructionV1.halt(),),
        entry_pc=0,
        quantum_step_limit=1,
        authority_hash=AUTHORITY,
    )


def _jump_program() -> TotalCoreProgramV1:
    return TotalCoreProgramV1.build(
        program_id="OptimizedJump",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((), profile="actual"),
        transformations=(),
        v4_units=(),
        proof_admissions=(),
        instructions=(TotalCoreInstructionV1.jump(0),),
        entry_pc=0,
        quantum_step_limit=3,
        authority_hash=AUTHORITY,
    )


class RuntimeV5TotalOptimizedPlanTests(unittest.TestCase):
    def test_prepare_plan_binds_exact_validated_program(self) -> None:
        program = _halt_program()

        plan = prepare_total_core_execution_plan(program)

        self.assertIs(plan.program, program)
        self.assertEqual(plan.program_hash, program.program_hash)
        self.assertEqual(plan.authority_hash, program.authority_hash)
        self.assertEqual(plan.entry_pc, 0)
        self.assertEqual(plan.quantum_step_limit, 1)
        self.assertEqual(len(plan.instructions), 1)
        self.assertEqual(plan.instructions[0].opcode, _OP_HALT)

    def test_halt_quantum_is_exactly_reference_equivalent(self) -> None:
        program = _halt_program()
        checkpoint = initial_total_core_checkpoint(program)
        reference = run_total_core_quantum(program, checkpoint)

        prepared = run_prepared_total_core_quantum(
            prepare_total_core_execution_plan(program),
            checkpoint,
        )

        self.assertEqual(prepared, reference)

    def test_jump_suspension_is_exactly_reference_equivalent(self) -> None:
        program = _jump_program()
        checkpoint = initial_total_core_checkpoint(program)
        reference = run_total_core_quantum(program, checkpoint)

        prepared = run_prepared_total_core_quantum(
            prepare_total_core_execution_plan(program),
            checkpoint,
        )

        self.assertEqual(prepared, reference)
        self.assertEqual(prepared.status, "SUSPENDED")
        self.assertEqual(prepared.steps_used, 3)
        self.assertEqual(prepared.pc, 0)


if __name__ == "__main__":
    unittest.main()
