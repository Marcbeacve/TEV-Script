from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_hash
from .diagnostics import TevScriptError
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
    validate_semantic_field,
)
from .program_ir_v5_semantic import (
    ProcessCheckpointV1,
    SemanticProcessProgramV1,
    process_checkpoint,
    process_state_hash,
    validate_process_checkpoint,
    validate_semantic_process_program,
)

QUANTUM_RESULT_SCHEMA = "TEV_SCRIPT_MAX_V3_QUANTUM_RESULT_V1"
_STATUSES = frozenset({"HALTED", "SUSPENDED"})
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class QuantumResultV1:
    schema: str
    program_hash: str
    epoch: EpochIdentityV1
    status: str
    steps_used: int
    field: SemanticFieldV1
    pc: int
    apply_receipt_hashes: tuple[str, ...]
    result_hash: str
    continuation: ContinuationReceiptV1
    next_checkpoint: ProcessCheckpointV1
    quantum_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        _fail("TEVS_MAX_V3_RUNTIME5_HASH", f"{name} must be lowercase 64-hex")
    return value


def _field_wire(value: SemanticFieldV1) -> dict[str, Any]:
    value = validate_semantic_field(value)
    return {
        "schema": value.schema,
        "profile": value.profile,
        "facts": [
            {"relation": f.relation, "arguments": list(f.arguments), "fact_hash": f.fact_hash}
            for f in value.facts
        ],
        "field_hash": value.field_hash,
    }


def _checkpoint_wire(value: ProcessCheckpointV1) -> dict[str, Any]:
    return {
        "schema": value.schema,
        "program_hash": value.program_hash,
        "field": _field_wire(value.field),
        "pc": value.pc,
        "next_epoch_index": value.next_epoch_index,
        "previous_continuation": None if value.previous_continuation is None else omega_wire(value.previous_continuation),
        "halted": value.halted,
        "checkpoint_hash": value.checkpoint_hash,
    }


def _result_semantic_hash(status: str, field_hash: str, pc: int) -> str:
    return canonical_hash({"status": status, "field_hash": field_hash, "pc": pc})


def _quantum_body(
    *,
    program_hash: str,
    epoch: EpochIdentityV1,
    status: str,
    steps_used: int,
    field: SemanticFieldV1,
    pc: int,
    apply_receipt_hashes: tuple[str, ...],
    result_hash: str,
    continuation: ContinuationReceiptV1,
    next_checkpoint: ProcessCheckpointV1,
) -> dict[str, Any]:
    return {
        "schema": QUANTUM_RESULT_SCHEMA,
        "program_hash": program_hash,
        "epoch": omega_wire(epoch),
        "status": status,
        "steps_used": steps_used,
        "field": _field_wire(field),
        "pc": pc,
        "apply_receipt_hashes": list(apply_receipt_hashes),
        "result_hash": result_hash,
        "continuation": omega_wire(continuation),
        "next_checkpoint": _checkpoint_wire(next_checkpoint),
    }


def _build_quantum_result(
    program: SemanticProcessProgramV1,
    *,
    epoch: EpochIdentityV1,
    status: str,
    steps_used: int,
    field: SemanticFieldV1,
    pc: int,
    apply_receipt_hashes: tuple[str, ...],
    continuation: ContinuationReceiptV1,
    next_checkpoint: ProcessCheckpointV1,
) -> QuantumResultV1:
    program = validate_semantic_process_program(program)
    field = validate_semantic_field(field)
    continuation = validate_continuation_receipt(continuation)
    next_checkpoint = validate_process_checkpoint(program, next_checkpoint)
    if status not in _STATUSES:
        _fail("TEVS_MAX_V3_RUNTIME5_STATUS", "invalid quantum status")
    if isinstance(steps_used, bool) or not isinstance(steps_used, int) or not 1 <= steps_used <= program.quantum_step_limit:
        _fail("TEVS_MAX_V3_RUNTIME5_STEPS", "steps_used outside quantum budget")
    if isinstance(pc, bool) or not isinstance(pc, int) or not 0 <= pc < len(program.instructions):
        _fail("TEVS_MAX_V3_RUNTIME5_PC", "quantum result pc outside program")
    hashes = tuple(_sha(value, "apply_receipt_hash") for value in apply_receipt_hashes)
    result_hash = _result_semantic_hash(status, field.field_hash, pc)
    if continuation.result_hash != result_hash:
        _fail("TEVS_MAX_V3_RUNTIME5_CONTINUATION_RESULT", "continuation result hash mismatch")
    state_hash = process_state_hash(program.program_hash, field.field_hash, pc)
    if continuation.state_hash != state_hash:
        _fail("TEVS_MAX_V3_RUNTIME5_CONTINUATION_STATE", "continuation state hash mismatch")
    if next_checkpoint.previous_continuation != continuation:
        _fail("TEVS_MAX_V3_RUNTIME5_CHECKPOINT_CONTINUATION", "next checkpoint does not bind continuation")
    if next_checkpoint.field != field or next_checkpoint.pc != pc:
        _fail("TEVS_MAX_V3_RUNTIME5_CHECKPOINT_STATE", "next checkpoint does not bind result state")
    if next_checkpoint.halted != (status == "HALTED"):
        _fail("TEVS_MAX_V3_RUNTIME5_CHECKPOINT_STATUS", "next checkpoint halt state mismatch")
    if next_checkpoint.next_epoch_index != continuation.epoch_index + 1:
        _fail("TEVS_MAX_V3_RUNTIME5_CHECKPOINT_EPOCH", "next checkpoint epoch mismatch")
    body = _quantum_body(
        program_hash=program.program_hash,
        epoch=epoch,
        status=status,
        steps_used=steps_used,
        field=field,
        pc=pc,
        apply_receipt_hashes=hashes,
        result_hash=result_hash,
        continuation=continuation,
        next_checkpoint=next_checkpoint,
    )
    return QuantumResultV1(
        QUANTUM_RESULT_SCHEMA, program.program_hash, epoch, status, steps_used,
        field, pc, hashes, result_hash, continuation, next_checkpoint,
        canonical_hash(body),
    )


def run_semantic_quantum(
    program: SemanticProcessProgramV1,
    checkpoint: ProcessCheckpointV1,
) -> QuantumResultV1:
    program = validate_semantic_process_program(program)
    checkpoint = validate_process_checkpoint(program, checkpoint)
    if checkpoint.halted:
        _fail("TEVS_MAX_V3_RUNTIME5_HALTED", "halted checkpoint cannot be resumed")

    input_state_hash = process_state_hash(program.program_hash, checkpoint.field.field_hash, checkpoint.pc)
    previous_hash = None if checkpoint.previous_continuation is None else checkpoint.previous_continuation.continuation_hash
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
    applied: list[str] = []
    effect_hashes: list[str] = []
    status = "SUSPENDED"
    transformations = {t.transformation_hash: t for t in program.transformations}

    while steps_used < program.quantum_step_limit:
        instruction = program.instructions[pc]
        steps_used += 1
        if instruction.kind == "apply":
            assert instruction.transformation_hash is not None and instruction.next_pc is not None
            transformation = transformations[instruction.transformation_hash]
            field, receipt = apply_field_transformation(field, transformation)
            if receipt.status != "PASS":
                _fail("TEVS_MAX_V3_RUNTIME5_APPLY_OPEN", "runtime cannot execute proof-open Apply")
            applied.append(receipt.receipt_hash)
            effect_hashes.append(receipt.effect_set_hash)
            pc = instruction.next_pc
        elif instruction.kind == "branch_fact":
            assert instruction.fact_hash is not None and instruction.present_pc is not None and instruction.absent_pc is not None
            present = any(f.fact_hash == instruction.fact_hash for f in field.facts)
            pc = instruction.present_pc if present else instruction.absent_pc
        elif instruction.kind == "jump":
            assert instruction.target_pc is not None
            pc = instruction.target_pc
        else:
            status = "HALTED"
            break

    result_hash = _result_semantic_hash(status, field.field_hash, pc)
    state_hash = process_state_hash(program.program_hash, field.field_hash, pc)
    continuation = continuation_receipt(
        epoch=epoch,
        result_hash=result_hash,
        state_hash=state_hash,
        observations_hash=canonical_hash([]),
        effects_hash=canonical_hash(effect_hashes),
        resources_hash=canonical_hash({"steps_used": steps_used}),
    )
    next_checkpoint = process_checkpoint(
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
        field=field,
        pc=pc,
        apply_receipt_hashes=tuple(applied),
        continuation=continuation,
        next_checkpoint=next_checkpoint,
    )


def validate_quantum_result(program: SemanticProcessProgramV1, value: object) -> QuantumResultV1:
    program = validate_semantic_process_program(program)
    if not isinstance(value, QuantumResultV1):
        _fail("TEVS_MAX_V3_RUNTIME5_RESULT", "quantum result must be QuantumResultV1")
    if value.program_hash != program.program_hash:
        _fail("TEVS_MAX_V3_RUNTIME5_PROGRAM", "quantum result program mismatch")
    expected = _build_quantum_result(
        program,
        epoch=value.epoch,
        status=value.status,
        steps_used=value.steps_used,
        field=value.field,
        pc=value.pc,
        apply_receipt_hashes=value.apply_receipt_hashes,
        continuation=value.continuation,
        next_checkpoint=value.next_checkpoint,
    )
    if value.schema != QUANTUM_RESULT_SCHEMA or value.result_hash != expected.result_hash or value.quantum_hash != expected.quantum_hash:
        _fail("TEVS_MAX_V3_RUNTIME5_RESULT_HASH", "quantum result identity mismatch")
    return value


__all__ = [
    "QUANTUM_RESULT_SCHEMA",
    "QuantumResultV1",
    "run_semantic_quantum",
    "validate_quantum_result",
]
