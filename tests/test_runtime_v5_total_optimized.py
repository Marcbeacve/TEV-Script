from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

import tev_script.runtime_v5_total_optimized as optimized_runtime
from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import (
    field_fact,
    field_transformation,
    semantic_field,
)
from tev_script.program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    VerifiedProofAdmissionV1,
)
from tev_script.runtime_v5_total import (
    initial_total_core_checkpoint,
    run_total_core_quantum,
)
from tev_script.runtime_v5_total_optimized import (
    _OP_HALT,
    _OP_JUMP,
    _fact_hash_index,
    prepare_total_core_execution_plan,
    run_prepared_total_core_quantum,
)
from tests.test_runtime_v5_total import RuntimeV5TotalCoreTests, _base_program


AUTHORITY = "a" * 64
SOURCE = "b" * 64
REQUIREMENT = "c" * 64
VERIFICATION_RECEIPT = "d" * 64
VERIFIER = "e" * 64


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


def _branch_program(*, fact_count: int, present: bool) -> TotalCoreProgramV1:
    facts = tuple(
        field_fact("tev.optimized.fact", ({"index": index},))
        for index in range(fact_count)
    )
    needle = facts[-1] if present and facts else field_fact("tev.optimized.missing", ({"index": -1},))
    return TotalCoreProgramV1.build(
        program_id=f"OptimizedBranch{fact_count}{'Present' if present else 'Absent'}",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field(facts, profile="actual"),
        transformations=(),
        v4_units=(),
        proof_admissions=(),
        instructions=(
            TotalCoreInstructionV1.branch_fact(
                needle.fact_hash,
                present_pc=1,
                absent_pc=2,
            ),
            TotalCoreInstructionV1.halt(),
            TotalCoreInstructionV1.halt(),
        ),
        entry_pc=0,
        quantum_step_limit=3,
        authority_hash=AUTHORITY,
    )


def _plain_apply_program() -> TotalCoreProgramV1:
    before = field_fact("tev.optimized.before", ({"value": 1},))
    after = field_fact("tev.optimized.after", ({"value": 2},))
    transformation = field_transformation(
        transformation_id="optimized.plain.apply",
        remove_fact_hashes=(before.fact_hash,),
        add_facts=(after,),
        effect_set_hash="1" * 64,
        resource_vector_hash="2" * 64,
        proof_requirement_hashes=(),
    )
    return TotalCoreProgramV1.build(
        program_id="OptimizedPlainApply",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((before,), profile="actual"),
        transformations=(transformation,),
        v4_units=(),
        proof_admissions=(),
        instructions=(
            TotalCoreInstructionV1.apply(transformation.transformation_hash, next_pc=1),
            TotalCoreInstructionV1.halt(),
        ),
        entry_pc=0,
        quantum_step_limit=3,
        authority_hash=AUTHORITY,
    )


def _proof_apply_program() -> TotalCoreProgramV1:
    fact = field_fact("tev.optimized.proof", ({"value": "verified"},))
    transformation = field_transformation(
        transformation_id="optimized.proof.apply",
        add_facts=(fact,),
        effect_set_hash="3" * 64,
        resource_vector_hash="4" * 64,
        proof_requirement_hashes=(REQUIREMENT,),
    )
    admission = VerifiedProofAdmissionV1.build(
        requirement_hash=REQUIREMENT,
        verification_receipt_hash=VERIFICATION_RECEIPT,
        verifier_identity_hash=VERIFIER,
        authority_hash=AUTHORITY,
    )
    return TotalCoreProgramV1.build(
        program_id="OptimizedProofApply",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((), profile="actual"),
        transformations=(transformation,),
        v4_units=(),
        proof_admissions=(admission,),
        instructions=(
            TotalCoreInstructionV1.apply(transformation.transformation_hash, next_pc=1),
            TotalCoreInstructionV1.halt(),
        ),
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

    def test_prepare_calls_canonical_program_validator_once(self) -> None:
        program = _proof_apply_program()
        validator = optimized_runtime.validate_total_core_program
        with patch.object(
            optimized_runtime,
            "validate_total_core_program",
            wraps=validator,
        ) as observed:
            plan = optimized_runtime.prepare_total_core_execution_plan(program)
        self.assertIs(plan.program, program)
        self.assertEqual(observed.call_count, 1)

    def test_execution_plan_tables_are_read_only(self) -> None:
        plan = prepare_total_core_execution_plan(_plain_apply_program())
        with self.assertRaises(TypeError):
            plan.transformations_by_hash["f" * 64] = plan.program.transformations[0]  # type: ignore[index]
        with self.assertRaises(TypeError):
            plan.units_by_hash["f" * 64] = None  # type: ignore[index,assignment]
        with self.assertRaises(TypeError):
            plan.proof_admissions_by_requirement["f" * 64] = None  # type: ignore[index,assignment]
        with self.assertRaises(TypeError):
            plan.prepared_proof_applies["f" * 64] = None  # type: ignore[index,assignment]

    def test_execution_plan_cannot_be_rewritten_with_dataclasses_replace(self) -> None:
        plan = prepare_total_core_execution_plan(_halt_program())
        forged_instruction = replace(
            plan.instructions[0],
            opcode=_OP_JUMP,
            target_pc=0,
        )
        with self.assertRaises(TypeError):
            replace(plan, instructions=(forged_instruction,))

    def test_proof_preparation_is_not_repeated_per_quantum(self) -> None:
        program = _proof_apply_program()
        plan = prepare_total_core_execution_plan(program)
        checkpoint = initial_total_core_checkpoint(program)
        with patch.object(
            optimized_runtime,
            "_prepare_proof_apply",
            side_effect=AssertionError("proof preparation repeated in quantum"),
        ):
            prepared = run_prepared_total_core_quantum(plan, checkpoint)
        self.assertEqual(prepared, run_total_core_quantum(program, checkpoint))

    def assert_reference_equivalent(self, program: TotalCoreProgramV1):
        checkpoint = initial_total_core_checkpoint(program)
        reference = run_total_core_quantum(program, checkpoint)
        prepared = run_prepared_total_core_quantum(
            prepare_total_core_execution_plan(program),
            checkpoint,
        )
        self.assertEqual(prepared, reference)
        return prepared

    def test_halt_quantum_is_exactly_reference_equivalent(self) -> None:
        self.assert_reference_equivalent(_halt_program())

    def test_jump_suspension_is_exactly_reference_equivalent(self) -> None:
        prepared = self.assert_reference_equivalent(_jump_program())
        self.assertEqual(prepared.status, "SUSPENDED")
        self.assertEqual(prepared.steps_used, 3)
        self.assertEqual(prepared.pc, 0)

    def test_jump_resume_chain_is_exactly_reference_equivalent(self) -> None:
        program = _jump_program()
        plan = prepare_total_core_execution_plan(program)
        checkpoint = initial_total_core_checkpoint(program)

        reference_first = run_total_core_quantum(program, checkpoint)
        prepared_first = run_prepared_total_core_quantum(plan, checkpoint)
        self.assertEqual(prepared_first, reference_first)

        reference_second = run_total_core_quantum(program, reference_first.next_checkpoint)
        prepared_second = run_prepared_total_core_quantum(plan, prepared_first.next_checkpoint)
        self.assertEqual(prepared_second, reference_second)
        self.assertEqual(
            prepared_second.continuation.previous_continuation_hash,
            prepared_first.continuation.continuation_hash,
        )

    def test_branch_cardinalities_are_exactly_reference_equivalent(self) -> None:
        for fact_count in (0, 1, 10, 100, 1_000, 10_000):
            for present in ((False,) if fact_count == 0 else (False, True)):
                with self.subTest(fact_count=fact_count, present=present):
                    prepared = self.assert_reference_equivalent(
                        _branch_program(fact_count=fact_count, present=present)
                    )
                    self.assertEqual(
                        _fact_hash_index(prepared.field),
                        {fact.fact_hash for fact in prepared.field.facts},
                    )

    def test_plain_apply_is_exactly_reference_equivalent(self) -> None:
        prepared = self.assert_reference_equivalent(_plain_apply_program())
        self.assertTrue(any(fact.relation == "tev.optimized.after" for fact in prepared.field.facts))
        self.assertFalse(any(fact.relation == "tev.optimized.before" for fact in prepared.field.facts))
        self.assertEqual(_fact_hash_index(prepared.field), {fact.fact_hash for fact in prepared.field.facts})

    def test_proof_apply_is_prepared_once_and_reference_equivalent(self) -> None:
        program = _proof_apply_program()
        plan = prepare_total_core_execution_plan(program)
        transformation = program.transformations[0]
        self.assertIn(transformation.transformation_hash, plan.prepared_proof_applies)

        checkpoint = initial_total_core_checkpoint(program)
        reference = run_total_core_quantum(program, checkpoint)
        prepared = run_prepared_total_core_quantum(plan, checkpoint)

        self.assertEqual(prepared, reference)
        self.assertTrue(any(fact.relation == "tev.optimized.proof" for fact in prepared.field.facts))
        self.assertEqual(_fact_hash_index(prepared.field), {fact.fact_hash for fact in prepared.field.facts})

    def test_invoke_v4_pure_is_exactly_reference_equivalent(self) -> None:
        unit = RuntimeV5TotalCoreTests().pure_unit()
        self.assert_reference_equivalent(_base_program(unit))

    def test_invoke_v4_recursive_is_exactly_reference_equivalent(self) -> None:
        unit = RuntimeV5TotalCoreTests().recursive_unit()
        self.assert_reference_equivalent(_base_program(unit))

    def test_invoke_v4_effects_is_exactly_reference_equivalent(self) -> None:
        unit = RuntimeV5TotalCoreTests().effects_unit()
        self.assert_reference_equivalent(_base_program(unit))

    def test_checkpoint_from_other_program_is_rejected_with_exact_code(self) -> None:
        left = _halt_program()
        right = TotalCoreProgramV1.build(
            program_id="OtherOptimized",
            source_semantic_hash="9" * 64,
            initial_field=semantic_field((), profile="actual"),
            transformations=(),
            v4_units=(),
            proof_admissions=(),
            instructions=(TotalCoreInstructionV1.halt(),),
            entry_pc=0,
            quantum_step_limit=1,
            authority_hash=AUTHORITY,
        )
        with self.assertRaises(TevScriptError) as captured:
            run_prepared_total_core_quantum(
                prepare_total_core_execution_plan(right),
                initial_total_core_checkpoint(left),
            )
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM",
        )

    def test_halted_checkpoint_cannot_be_resumed(self) -> None:
        program = _halt_program()
        plan = prepare_total_core_execution_plan(program)
        first = run_prepared_total_core_quantum(
            plan,
            initial_total_core_checkpoint(program),
        )
        with self.assertRaises(TevScriptError) as captured:
            run_prepared_total_core_quantum(plan, first.next_checkpoint)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V31_RUNTIME_HALTED",
        )


if __name__ == "__main__":
    unittest.main()
