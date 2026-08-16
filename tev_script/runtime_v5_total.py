from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .ir_v4_pure import TaskScopeExecutionStrategyV4
from .omega_kernel_v1 import (
    ContinuationReceiptV1,
    EpochIdentityV1,
    continuation_receipt,
    epoch_identity,
    omega_wire,
    validate_continuation_receipt,
)
from .omega_semantic_basis_v1 import (
    SemanticFieldV1,
    apply_field_transformation,
    field_fact,
    field_transformation,
    validate_semantic_field,
)
from .program_ir_v4 import (
    run_program_ir_v4_effects,
    run_program_ir_v4_pure,
    run_program_ir_v4_recursive,
)
from .program_ir_v5_total import (
    TotalCoreProgramV1,
    TotalCoreUnitV1,
    validate_total_core_program,
)

CHECKPOINT_SCHEMA_V31 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CHECKPOINT_V1"
QUANTUM_RESULT_SCHEMA_V31 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_QUANTUM_RESULT_V1"
_STATUSES = frozenset({"HALTED", "SUSPENDED"})
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class TotalCoreCheckpointV1:
    schema: str
    program_hash: str
    field: SemanticFieldV1
    pc: int
    next_epoch_index: int
    previous_continuation: ContinuationReceiptV1 | None
    halted: bool
    checkpoint_hash: str


@dataclass(frozen=True, slots=True)
class TotalCoreQuantumResultV1:
    schema: str
    program_hash: str
    epoch: EpochIdentityV1
    status: str
    steps_used: int
    v4_evaluation_steps: int
    field: SemanticFieldV1
    pc: int
    apply_receipt_hashes: tuple[str, ...]
    child_receipt_hashes: tuple[str, ...]
    result_hash: str
    continuation: ContinuationReceiptV1
    next_checkpoint: TotalCoreCheckpointV1
    quantum_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        _fail("TEVS_V31_RUNTIME_HASH", f"{name} must be lowercase 64-hex")
    return value


def _pc(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_V31_RUNTIME_PC", f"{name} must be an integer >= 0")
    return value


def _field_wire(value: SemanticFieldV1) -> dict[str, Any]:
    field = validate_semantic_field(value)
    return {
        "schema": field.schema,
        "profile": field.profile,
        "facts": [
            {
                "relation": fact.relation,
                "arguments": list(fact.arguments),
                "fact_hash": fact.fact_hash,
            }
            for fact in field.facts
        ],
        "field_hash": field.field_hash,
    }


def total_core_state_hash(program_hash: str, field_hash: str, pc: int) -> str:
    return canonical_hash(
        {
            "program_hash": _sha(program_hash, "program_hash"),
            "field_hash": _sha(field_hash, "field_hash"),
            "pc": _pc(pc, "pc"),
        }
    )


def _checkpoint_body(
    program_hash: str,
    field: SemanticFieldV1,
    pc: int,
    next_epoch_index: int,
    previous_continuation: ContinuationReceiptV1 | None,
    halted: bool,
) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA_V31,
        "program_hash": program_hash,
        "field": _field_wire(field),
        "pc": pc,
        "next_epoch_index": next_epoch_index,
        "previous_continuation": (
            None if previous_continuation is None else omega_wire(previous_continuation)
        ),
        "halted": halted,
    }


def total_core_checkpoint(
    program: TotalCoreProgramV1,
    *,
    field: SemanticFieldV1,
    pc: int,
    next_epoch_index: int,
    previous_continuation: ContinuationReceiptV1 | None,
    halted: bool,
) -> TotalCoreCheckpointV1:
    program = validate_total_core_program(program)
    field = validate_semantic_field(field)
    pc = _pc(pc, "pc")
    if pc >= len(program.instructions):
        _fail("TEVS_V31_RUNTIME_CHECKPOINT_PC", "checkpoint pc outside program")
    if (
        isinstance(next_epoch_index, bool)
        or not isinstance(next_epoch_index, int)
        or next_epoch_index < 0
    ):
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_EPOCH",
            "next_epoch_index must be an integer >= 0",
        )
    if not isinstance(halted, bool):
        _fail("TEVS_V31_RUNTIME_CHECKPOINT_HALTED", "halted must be boolean")

    previous: ContinuationReceiptV1 | None = None
    if next_epoch_index == 0:
        if previous_continuation is not None:
            _fail(
                "TEVS_V31_RUNTIME_CHECKPOINT_PREVIOUS",
                "epoch zero checkpoint cannot have continuation",
            )
    else:
        if previous_continuation is None:
            _fail(
                "TEVS_V31_RUNTIME_CHECKPOINT_PREVIOUS",
                "resumed checkpoint requires continuation",
            )
        previous = validate_continuation_receipt(previous_continuation)
        if previous.epoch_index != next_epoch_index - 1:
            _fail(
                "TEVS_V31_RUNTIME_CHECKPOINT_EPOCH",
                "continuation epoch does not precede checkpoint",
            )
        if previous.state_hash != total_core_state_hash(
            program.program_hash, field.field_hash, pc
        ):
            _fail(
                "TEVS_V31_RUNTIME_CHECKPOINT_STATE",
                "continuation state hash does not match checkpoint",
            )

    if halted and program.instructions[pc].kind != "halt":
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_HALTED",
            "halted checkpoint must point at a halt instruction",
        )

    body = _checkpoint_body(
        program.program_hash,
        field,
        pc,
        next_epoch_index,
        previous,
        halted,
    )
    return TotalCoreCheckpointV1(
        CHECKPOINT_SCHEMA_V31,
        program.program_hash,
        field,
        pc,
        next_epoch_index,
        previous,
        halted,
        canonical_hash(body),
    )


def initial_total_core_checkpoint(program: TotalCoreProgramV1) -> TotalCoreCheckpointV1:
    program = validate_total_core_program(program)
    return total_core_checkpoint(
        program,
        field=program.initial_field,
        pc=program.entry_pc,
        next_epoch_index=0,
        previous_continuation=None,
        halted=False,
    )


def validate_total_core_checkpoint(
    program: TotalCoreProgramV1,
    value: object,
) -> TotalCoreCheckpointV1:
    program = validate_total_core_program(program)
    if not isinstance(value, TotalCoreCheckpointV1):
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT",
            "checkpoint must be TotalCoreCheckpointV1",
        )
    if value.program_hash != program.program_hash:
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM",
            "checkpoint program mismatch",
        )
    expected = total_core_checkpoint(
        program,
        field=value.field,
        pc=value.pc,
        next_epoch_index=value.next_epoch_index,
        previous_continuation=value.previous_continuation,
        halted=value.halted,
    )
    if value != expected:
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_HASH",
            "checkpoint identity mismatch",
        )
    return value


def _bridge_payload(unit: TotalCoreUnitV1, receipt: Any) -> tuple[dict[str, Any], int, str | None, str | None]:
    common: dict[str, Any] = {
        "unit_id": unit.unit_id,
        "unit_hash": unit.unit_hash,
        "program_ir_hash": unit.program_ir_hash,
        "run_receipt_hash": receipt.receipt_hash,
    }
    if unit.profile in {"pure", "recursive"}:
        common.update(
            {
                "result_type": receipt.result_type,
                "result_encoded": receipt.result_encoded,
                "result_hash": receipt.result_hash,
                "evaluation_steps": receipt.evaluation_steps,
            }
        )
        return common, receipt.evaluation_steps, None, None

    common.update(
        {
            "final_state": list(receipt.final_state),
            "final_state_hash": receipt.final_state_hash,
            "capability_transcript_hash": receipt.capability_transcript_hash,
            "evaluation_steps": receipt.evaluation_steps,
            "observation_calls": receipt.observation_calls,
            "transition_receipt_hash": receipt.transition_receipt_hash,
        }
    )
    return (
        common,
        receipt.evaluation_steps,
        receipt.capability_transcript_hash,
        receipt.transition_receipt_hash,
    )


def _run_v4_unit(
    unit: TotalCoreUnitV1,
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None,
) -> tuple[Any, dict[str, Any], int, str | None, str | None]:
    if unit.profile == "pure":
        receipt = run_program_ir_v4_pure(
            unit.program_ir_v4,
            expected_program_ir_hash=unit.program_ir_hash,
            task_strategy=task_strategy,
        )
    elif unit.profile == "recursive":
        receipt = run_program_ir_v4_recursive(
            unit.program_ir_v4,
            expected_program_ir_hash=unit.program_ir_hash,
        )
    elif unit.profile == "effects":
        receipt = run_program_ir_v4_effects(
            unit.program_ir_v4,
            expected_program_ir_hash=unit.program_ir_hash,
        )
    else:
        _fail("TEVS_V31_RUNTIME_UNIT_PROFILE", "unsupported V4 unit profile")
    payload, evaluation_steps, observation_hash, effect_hash = _bridge_payload(unit, receipt)
    return receipt, payload, evaluation_steps, observation_hash, effect_hash


def _append_bridge_fact(
    field: SemanticFieldV1,
    *,
    unit: TotalCoreUnitV1,
    relation: str,
    payload: dict[str, Any],
    run_receipt_hash: str,
    evaluation_steps: int,
) -> tuple[SemanticFieldV1, str]:
    fact = field_fact(relation, (payload,))
    bridge = field_transformation(
        transformation_id=f"tev.total.bridge.{unit.unit_id}.{run_receipt_hash[:16]}",
        required_before_hash=field.field_hash,
        add_facts=(fact,),
        effect_set_hash=canonical_hash([]),
        resource_vector_hash=canonical_hash(
            {"v4_evaluation_steps": evaluation_steps}
        ),
        proof_requirement_hashes=(),
    )
    after, apply_receipt = apply_field_transformation(field, bridge)
    if apply_receipt.status != "PASS":
        _fail(
            "TEVS_V31_RUNTIME_BRIDGE_APPLY",
            "derived V4 bridge transformation did not close as PASS",
        )
    return after, apply_receipt.receipt_hash


def _apply_total_core_transformation(
    program: TotalCoreProgramV1,
    field: SemanticFieldV1,
    transformation: Any,
) -> tuple[SemanticFieldV1, Any, str | None]:
    # The canonical transformation is never mutated. Proof-open execution
    # uses an execution-local derivative bound to exact VERIFIED admissions.
    if not transformation.proof_requirement_hashes:
        after, receipt = apply_field_transformation(field, transformation)
        return after, receipt, None

    admissions_by_requirement = {
        admission.requirement_hash: admission
        for admission in program.proof_admissions
    }
    selected = []
    for requirement_hash in transformation.proof_requirement_hashes:
        admission = admissions_by_requirement.get(requirement_hash)
        if admission is None:
            _fail(
                "TEVS_V31_RUNTIME_PROOF_REQUIRED",
                "proof-open Apply has no exact runtime admission",
            )
        if admission.status != "VERIFIED":
            _fail(
                "TEVS_V31_RUNTIME_PROOF_STATUS",
                "proof admission is not VERIFIED",
            )
        if admission.authority_hash != program.authority_hash:
            _fail(
                "TEVS_V31_RUNTIME_PROOF_AUTHORITY",
                "proof admission authority differs from program authority",
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
    after, receipt = apply_field_transformation(field, execution_local)
    if receipt.status != "PASS":
        _fail(
            "TEVS_V31_RUNTIME_PROOF_APPLY",
            "proof-admitted execution-local Apply did not close as PASS",
        )
    return after, receipt, proof_use_hash


def _result_semantic_hash(status: str, field_hash: str, pc: int) -> str:
    return canonical_hash({"status": status, "field_hash": field_hash, "pc": pc})


def _checkpoint_wire(value: TotalCoreCheckpointV1) -> dict[str, Any]:
    return {
        **_checkpoint_body(
            value.program_hash,
            value.field,
            value.pc,
            value.next_epoch_index,
            value.previous_continuation,
            value.halted,
        ),
        "checkpoint_hash": value.checkpoint_hash,
    }


def _quantum_body(
    *,
    program_hash: str,
    epoch: EpochIdentityV1,
    status: str,
    steps_used: int,
    v4_evaluation_steps: int,
    field: SemanticFieldV1,
    pc: int,
    apply_receipt_hashes: tuple[str, ...],
    child_receipt_hashes: tuple[str, ...],
    result_hash: str,
    continuation: ContinuationReceiptV1,
    next_checkpoint: TotalCoreCheckpointV1,
) -> dict[str, Any]:
    return {
        "schema": QUANTUM_RESULT_SCHEMA_V31,
        "program_hash": program_hash,
        "epoch": omega_wire(epoch),
        "status": status,
        "steps_used": steps_used,
        "v4_evaluation_steps": v4_evaluation_steps,
        "field": _field_wire(field),
        "pc": pc,
        "apply_receipt_hashes": list(apply_receipt_hashes),
        "child_receipt_hashes": list(child_receipt_hashes),
        "result_hash": result_hash,
        "continuation": omega_wire(continuation),
        "next_checkpoint": _checkpoint_wire(next_checkpoint),
    }


def _build_quantum_result(
    program: TotalCoreProgramV1,
    *,
    epoch: EpochIdentityV1,
    status: str,
    steps_used: int,
    v4_evaluation_steps: int,
    field: SemanticFieldV1,
    pc: int,
    apply_receipt_hashes: tuple[str, ...],
    child_receipt_hashes: tuple[str, ...],
    continuation: ContinuationReceiptV1,
    next_checkpoint: TotalCoreCheckpointV1,
) -> TotalCoreQuantumResultV1:
    program = validate_total_core_program(program)
    field = validate_semantic_field(field)
    continuation = validate_continuation_receipt(continuation)
    next_checkpoint = validate_total_core_checkpoint(program, next_checkpoint)

    if status not in _STATUSES:
        _fail("TEVS_V31_RUNTIME_STATUS", "invalid quantum status")
    if (
        isinstance(steps_used, bool)
        or not isinstance(steps_used, int)
        or not 1 <= steps_used <= program.quantum_step_limit
    ):
        _fail("TEVS_V31_RUNTIME_STEPS", "steps_used outside quantum budget")
    if (
        isinstance(v4_evaluation_steps, bool)
        or not isinstance(v4_evaluation_steps, int)
        or v4_evaluation_steps < 0
    ):
        _fail(
            "TEVS_V31_RUNTIME_V4_STEPS",
            "v4_evaluation_steps must be an integer >= 0",
        )
    if isinstance(pc, bool) or not isinstance(pc, int) or not 0 <= pc < len(program.instructions):
        _fail("TEVS_V31_RUNTIME_PC", "quantum result pc outside program")

    apply_hashes = tuple(_sha(item, "apply_receipt_hash") for item in apply_receipt_hashes)
    child_hashes = tuple(_sha(item, "child_receipt_hash") for item in child_receipt_hashes)
    result_hash = _result_semantic_hash(status, field.field_hash, pc)
    if continuation.result_hash != result_hash:
        _fail(
            "TEVS_V31_RUNTIME_CONTINUATION_RESULT",
            "continuation result hash mismatch",
        )
    state_hash = total_core_state_hash(program.program_hash, field.field_hash, pc)
    if continuation.state_hash != state_hash:
        _fail(
            "TEVS_V31_RUNTIME_CONTINUATION_STATE",
            "continuation state hash mismatch",
        )
    if next_checkpoint.previous_continuation != continuation:
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_CONTINUATION",
            "next checkpoint does not bind continuation",
        )
    if next_checkpoint.field != field or next_checkpoint.pc != pc:
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_STATE",
            "next checkpoint does not bind result state",
        )
    if next_checkpoint.halted != (status == "HALTED"):
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_STATUS",
            "next checkpoint halt state mismatch",
        )
    if next_checkpoint.next_epoch_index != continuation.epoch_index + 1:
        _fail(
            "TEVS_V31_RUNTIME_CHECKPOINT_EPOCH",
            "next checkpoint epoch mismatch",
        )

    body = _quantum_body(
        program_hash=program.program_hash,
        epoch=epoch,
        status=status,
        steps_used=steps_used,
        v4_evaluation_steps=v4_evaluation_steps,
        field=field,
        pc=pc,
        apply_receipt_hashes=apply_hashes,
        child_receipt_hashes=child_hashes,
        result_hash=result_hash,
        continuation=continuation,
        next_checkpoint=next_checkpoint,
    )
    return TotalCoreQuantumResultV1(
        QUANTUM_RESULT_SCHEMA_V31,
        program.program_hash,
        epoch,
        status,
        steps_used,
        v4_evaluation_steps,
        field,
        pc,
        apply_hashes,
        child_hashes,
        result_hash,
        continuation,
        next_checkpoint,
        canonical_hash(body),
    )


def run_total_core_quantum(
    program: TotalCoreProgramV1,
    checkpoint: TotalCoreCheckpointV1,
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> TotalCoreQuantumResultV1:
    program = validate_total_core_program(program)
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
    v4_evaluation_steps = 0
    apply_receipt_hashes: list[str] = []
    child_receipt_hashes: list[str] = []
    observation_hashes: list[str] = []
    effect_hashes: list[str] = []
    status = "SUSPENDED"

    transformations = {
        item.transformation_hash: item for item in program.transformations
    }
    units = {item.unit_hash: item for item in program.v4_units}

    while steps_used < program.quantum_step_limit:
        instruction = program.instructions[pc]
        steps_used += 1

        if instruction.kind == "apply":
            assert (
                instruction.transformation_hash is not None
                and instruction.next_pc is not None
            )
            transformation = transformations[instruction.transformation_hash]
            field, receipt, proof_use_hash = _apply_total_core_transformation(
                program,
                field,
                transformation,
            )
            if receipt.status != "PASS":
                _fail(
                    "TEVS_V31_RUNTIME_APPLY_OPEN",
                    "runtime Apply did not close as PASS",
                )
            apply_receipt_hashes.append(receipt.receipt_hash)
            if proof_use_hash is not None:
                effect_hashes.append(proof_use_hash)
            effect_hashes.append(receipt.effect_set_hash)
            pc = instruction.next_pc

        elif instruction.kind == "branch_fact":
            assert (
                instruction.fact_hash is not None
                and instruction.present_pc is not None
                and instruction.absent_pc is not None
            )
            present = any(
                fact.fact_hash == instruction.fact_hash for fact in field.facts
            )
            pc = (
                instruction.present_pc
                if present
                else instruction.absent_pc
            )

        elif instruction.kind == "jump":
            assert instruction.target_pc is not None
            pc = instruction.target_pc

        elif instruction.kind == "invoke_v4":
            assert (
                instruction.unit_hash is not None
                and instruction.result_relation is not None
                and instruction.next_pc is not None
            )
            unit = units[instruction.unit_hash]
            (
                child_receipt,
                payload,
                child_steps,
                observation_hash,
                child_effect_hash,
            ) = _run_v4_unit(unit, task_strategy=task_strategy)
            field, bridge_apply_hash = _append_bridge_fact(
                field,
                unit=unit,
                relation=instruction.result_relation,
                payload=payload,
                run_receipt_hash=child_receipt.receipt_hash,
                evaluation_steps=child_steps,
            )
            apply_receipt_hashes.append(bridge_apply_hash)
            child_receipt_hashes.append(child_receipt.receipt_hash)
            v4_evaluation_steps += child_steps
            if observation_hash is not None:
                observation_hashes.append(observation_hash)
            if child_effect_hash is not None:
                effect_hashes.append(child_effect_hash)
            pc = instruction.next_pc

        else:
            status = "HALTED"
            break

    result_hash = _result_semantic_hash(status, field.field_hash, pc)
    state_hash = total_core_state_hash(program.program_hash, field.field_hash, pc)
    continuation = continuation_receipt(
        epoch=epoch,
        result_hash=result_hash,
        state_hash=state_hash,
        observations_hash=canonical_hash(observation_hashes),
        effects_hash=canonical_hash(effect_hashes),
        resources_hash=canonical_hash(
            {
                "v5_steps": steps_used,
                "v4_evaluation_steps": v4_evaluation_steps,
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
        v4_evaluation_steps=v4_evaluation_steps,
        field=field,
        pc=pc,
        apply_receipt_hashes=tuple(apply_receipt_hashes),
        child_receipt_hashes=tuple(child_receipt_hashes),
        continuation=continuation,
        next_checkpoint=next_checkpoint,
    )


def validate_total_core_quantum_result(
    program: TotalCoreProgramV1,
    value: object,
) -> TotalCoreQuantumResultV1:
    program = validate_total_core_program(program)
    if not isinstance(value, TotalCoreQuantumResultV1):
        _fail(
            "TEVS_V31_RUNTIME_RESULT",
            "quantum result must be TotalCoreQuantumResultV1",
        )
    if value.program_hash != program.program_hash:
        _fail(
            "TEVS_V31_RUNTIME_RESULT_PROGRAM",
            "quantum result program mismatch",
        )
    expected = _build_quantum_result(
        program,
        epoch=value.epoch,
        status=value.status,
        steps_used=value.steps_used,
        v4_evaluation_steps=value.v4_evaluation_steps,
        field=value.field,
        pc=value.pc,
        apply_receipt_hashes=value.apply_receipt_hashes,
        child_receipt_hashes=value.child_receipt_hashes,
        continuation=value.continuation,
        next_checkpoint=value.next_checkpoint,
    )
    if value != expected:
        _fail(
            "TEVS_V31_RUNTIME_RESULT_HASH",
            "quantum result identity mismatch",
        )
    return value


__all__ = [
    "CHECKPOINT_SCHEMA_V31",
    "QUANTUM_RESULT_SCHEMA_V31",
    "TotalCoreCheckpointV1",
    "TotalCoreQuantumResultV1",
    "initial_total_core_checkpoint",
    "run_total_core_quantum",
    "total_core_checkpoint",
    "total_core_state_hash",
    "validate_total_core_checkpoint",
    "validate_total_core_quantum_result",
]
