from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .ir_v4_pure import TaskScopeExecutionStrategyV4
from .omega_kernel_v1 import continuation_receipt, epoch_identity
from .omega_semantic_basis_v1 import FieldTransformationV1, field_transformation
from .program_ir_v5_total import (
    TotalCoreProgramV1,
    TotalCoreUnitV1,
    VerifiedProofAdmissionV1,
    validate_total_core_program,
)
from .runtime_v5_total import (
    TotalCoreCheckpointV1,
    TotalCoreQuantumResultV1,
    _build_quantum_result,
    _result_semantic_hash,
    total_core_checkpoint,
    total_core_state_hash,
    validate_total_core_checkpoint,
)

# Private execution-plan opcodes. Program IR V5 Total-Core remains the
# canonical semantic authority; these values are never serialized or hashed.
_OP_APPLY = 1
_OP_BRANCH_FACT = 2
_OP_JUMP = 3
_OP_HALT = 4
_OP_INVOKE_V4 = 5


@dataclass(frozen=True, slots=True)
class PreparedTotalCoreInstructionV1:
    opcode: int
    transformation: FieldTransformationV1 | None = None
    unit: TotalCoreUnitV1 | None = None
    fact_hash: str | None = None
    next_pc: int | None = None
    present_pc: int | None = None
    absent_pc: int | None = None
    target_pc: int | None = None
    result_relation: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedProofApplyV1:
    proof_use_hash: str
    execution_local_transformation: FieldTransformationV1


@dataclass(frozen=True, slots=True)
class TotalCoreExecutionPlanV1:
    """Derived, disposable execution data for one canonical Total-Core program.

    ``program`` is the sole semantic authority. Every other member is derived
    from that already-validated object and exists only to remove repeated
    lookup/decoding work from execution. The plan has intentionally no schema,
    canonical hash, signature, or wire representation.
    """

    program: TotalCoreProgramV1
    program_hash: str
    authority_hash: str
    entry_pc: int
    quantum_step_limit: int
    instructions: tuple[PreparedTotalCoreInstructionV1, ...]
    transformations_by_hash: Mapping[str, FieldTransformationV1]
    units_by_hash: Mapping[str, TotalCoreUnitV1]
    proof_admissions_by_requirement: Mapping[str, VerifiedProofAdmissionV1]
    prepared_proof_applies: Mapping[str, PreparedProofApplyV1]


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _prepare_proof_apply(
    program: TotalCoreProgramV1,
    transformation: FieldTransformationV1,
    admissions_by_requirement: Mapping[str, VerifiedProofAdmissionV1],
) -> PreparedProofApplyV1:
    selected: list[VerifiedProofAdmissionV1] = []
    for requirement_hash in transformation.proof_requirement_hashes:
        admission = admissions_by_requirement.get(requirement_hash)
        if admission is None:
            _fail(
                "TEVS_V31_OPT_PLAN_PROOF_REQUIRED",
                "validated program lost an exact proof admission during plan preparation",
            )
        if admission.status != "VERIFIED":
            _fail(
                "TEVS_V31_OPT_PLAN_PROOF_STATUS",
                "validated proof admission is not VERIFIED during plan preparation",
            )
        if admission.authority_hash != program.authority_hash:
            _fail(
                "TEVS_V31_OPT_PLAN_PROOF_AUTHORITY",
                "validated proof admission authority differs from plan program authority",
            )
        selected.append(admission)

    admission_hashes = tuple(admission.admission_hash for admission in selected)
    proof_use_hash = canonical_hash(
        {
            "schema": "TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_USE_V1",
            "program_hash": program.program_hash,
            "authority_hash": program.authority_hash,
            "transformation_hash": transformation.transformation_hash,
            "requirement_hashes": list(transformation.proof_requirement_hashes),
            "admission_hashes": list(admission_hashes),
        }
    )
    execution_local = field_transformation(
        transformation_id=f"tev.total.proof_admitted.{proof_use_hash[:32]}",
        remove_fact_hashes=transformation.remove_fact_hashes,
        add_facts=transformation.add_facts,
        required_before_hash=transformation.required_before_hash,
        result_profile=transformation.result_profile,
        effect_set_hash=transformation.effect_set_hash,
        resource_vector_hash=transformation.resource_vector_hash,
        proof_requirement_hashes=(),
    )
    return PreparedProofApplyV1(proof_use_hash, execution_local)


def _prepare_instruction(
    raw: Any,
    transformations_by_hash: Mapping[str, FieldTransformationV1],
    units_by_hash: Mapping[str, TotalCoreUnitV1],
) -> PreparedTotalCoreInstructionV1:
    if raw.kind == "apply":
        transformation = transformations_by_hash.get(raw.transformation_hash)
        if transformation is None or raw.next_pc is None:
            _fail(
                "TEVS_V31_OPT_PLAN_APPLY",
                "validated Apply could not be resolved during plan preparation",
            )
        return PreparedTotalCoreInstructionV1(
            _OP_APPLY,
            transformation=transformation,
            next_pc=raw.next_pc,
        )

    if raw.kind == "branch_fact":
        if raw.fact_hash is None or raw.present_pc is None or raw.absent_pc is None:
            _fail(
                "TEVS_V31_OPT_PLAN_BRANCH",
                "validated branch_fact lost an operand during plan preparation",
            )
        return PreparedTotalCoreInstructionV1(
            _OP_BRANCH_FACT,
            fact_hash=raw.fact_hash,
            present_pc=raw.present_pc,
            absent_pc=raw.absent_pc,
        )

    if raw.kind == "jump":
        if raw.target_pc is None:
            _fail(
                "TEVS_V31_OPT_PLAN_JUMP",
                "validated jump lost its target during plan preparation",
            )
        return PreparedTotalCoreInstructionV1(_OP_JUMP, target_pc=raw.target_pc)

    if raw.kind == "halt":
        return PreparedTotalCoreInstructionV1(_OP_HALT)

    if raw.kind == "invoke_v4":
        unit = units_by_hash.get(raw.unit_hash)
        if unit is None or raw.result_relation is None or raw.next_pc is None:
            _fail(
                "TEVS_V31_OPT_PLAN_UNIT",
                "validated invoke_v4 could not be resolved during plan preparation",
            )
        return PreparedTotalCoreInstructionV1(
            _OP_INVOKE_V4,
            unit=unit,
            result_relation=raw.result_relation,
            next_pc=raw.next_pc,
        )

    _fail(
        "TEVS_V31_OPT_PLAN_OPCODE",
        f"validated program contains unsupported instruction kind {raw.kind!r}",
    )


def prepare_total_core_execution_plan(
    program: TotalCoreProgramV1,
) -> TotalCoreExecutionPlanV1:
    """Validate one canonical program and derive an immutable execution plan."""

    program = validate_total_core_program(program)

    transformations = {
        item.transformation_hash: item for item in program.transformations
    }
    units = {item.unit_hash: item for item in program.v4_units}
    admissions = {
        item.requirement_hash: item for item in program.proof_admissions
    }

    prepared_proof_applies = {
        transformation.transformation_hash: _prepare_proof_apply(
            program,
            transformation,
            admissions,
        )
        for transformation in program.transformations
        if transformation.proof_requirement_hashes
    }

    instructions = tuple(
        _prepare_instruction(raw, transformations, units)
        for raw in program.instructions
    )

    return TotalCoreExecutionPlanV1(
        program=program,
        program_hash=program.program_hash,
        authority_hash=program.authority_hash,
        entry_pc=program.entry_pc,
        quantum_step_limit=program.quantum_step_limit,
        instructions=instructions,
        transformations_by_hash=MappingProxyType(transformations),
        units_by_hash=MappingProxyType(units),
        proof_admissions_by_requirement=MappingProxyType(admissions),
        prepared_proof_applies=MappingProxyType(prepared_proof_applies),
    )


def _validate_plan_identity(plan: object) -> TotalCoreExecutionPlanV1:
    if not isinstance(plan, TotalCoreExecutionPlanV1):
        _fail(
            "TEVS_V31_OPT_PLAN",
            "prepared execution requires TotalCoreExecutionPlanV1",
        )
    program = plan.program
    if (
        plan.program_hash != program.program_hash
        or plan.authority_hash != program.authority_hash
        or plan.entry_pc != program.entry_pc
        or plan.quantum_step_limit != program.quantum_step_limit
        or len(plan.instructions) != len(program.instructions)
    ):
        _fail(
            "TEVS_V31_OPT_PLAN_IDENTITY",
            "execution plan identity does not match its canonical program",
        )
    return plan


def run_prepared_total_core_quantum(
    plan: TotalCoreExecutionPlanV1,
    checkpoint: TotalCoreCheckpointV1,
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> TotalCoreQuantumResultV1:
    """Execute one quantum from a prepared plan.

    Phase A currently handles prepared control flow. Canonical checkpoint and
    result/evidence validation remain delegated to the reference runtime
    boundary constructors.
    """

    del task_strategy  # Used when prepared invoke_v4 support is enabled.
    plan = _validate_plan_identity(plan)
    program = plan.program
    checkpoint = validate_total_core_checkpoint(program, checkpoint)
    if checkpoint.halted:
        _fail(
            "TEVS_V31_RUNTIME_HALTED",
            "halted checkpoint cannot be resumed",
        )

    input_state_hash = total_core_state_hash(
        program.program_hash,
        checkpoint.field.field_hash,
        checkpoint.pc,
    )
    previous_hash = (
        None
        if checkpoint.previous_continuation is None
        else checkpoint.previous_continuation.continuation_hash
    )
    epoch = epoch_identity(
        epoch_index=checkpoint.next_epoch_index,
        computation_hash=program.program_hash,
        input_state_hash=input_state_hash,
        authority_hash=program.authority_hash,
        previous_continuation_hash=previous_hash,
    )

    field = checkpoint.field
    pc = checkpoint.pc
    steps_used = 0
    status = "SUSPENDED"

    while steps_used < plan.quantum_step_limit:
        instruction = plan.instructions[pc]
        steps_used += 1

        if instruction.opcode == _OP_JUMP:
            if instruction.target_pc is None:
                _fail(
                    "TEVS_V31_OPT_PLAN_JUMP",
                    "prepared jump has no target",
                )
            pc = instruction.target_pc
            continue

        if instruction.opcode == _OP_HALT:
            status = "HALTED"
            break

        _fail(
            "TEVS_V31_OPT_RUNTIME_OPCODE",
            f"prepared opcode {instruction.opcode} is not enabled in this phase",
        )

    result_hash = _result_semantic_hash(status, field.field_hash, pc)
    state_hash = total_core_state_hash(program.program_hash, field.field_hash, pc)
    continuation = continuation_receipt(
        epoch=epoch,
        result_hash=result_hash,
        state_hash=state_hash,
        observations_hash=canonical_hash([]),
        effects_hash=canonical_hash([]),
        resources_hash=canonical_hash(
            {
                "v5_steps": steps_used,
                "v4_evaluation_steps": 0,
            }
        ),
    )
    next_checkpoint = total_core_checkpoint(
        program,
        field=field,
        pc=pc,
        next_epoch_index=checkpoint.next_epoch_index + 1,
        previous_continuation=continuation,
        halted=status == "HALTED",
    )
    return _build_quantum_result(
        program,
        epoch=epoch,
        status=status,
        steps_used=steps_used,
        v4_evaluation_steps=0,
        field=field,
        pc=pc,
        apply_receipt_hashes=(),
        child_receipt_hashes=(),
        continuation=continuation,
        next_checkpoint=next_checkpoint,
    )


__all__ = [
    "PreparedProofApplyV1",
    "PreparedTotalCoreInstructionV1",
    "TotalCoreExecutionPlanV1",
    "prepare_total_core_execution_plan",
    "run_prepared_total_core_quantum",
]
