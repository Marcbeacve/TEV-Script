from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .omega_kernel_v1 import ContinuationReceiptV1, omega_wire, validate_continuation_receipt
from .omega_semantic_basis_v1 import (
    FieldTransformationV1,
    SemanticFieldV1,
    validate_field_transformation,
    validate_semantic_field,
)

PROGRAM_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1"
INSTRUCTION_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_INSTRUCTION_V1"
CHECKPOINT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V5_PROCESS_CHECKPOINT_V1"
LANGUAGE_VERSION = "3.0.0"
PROFILE = "semantic_process"
MAX_QUANTUM_STEPS = 1_000_000
MAX_INSTRUCTIONS = 65_536
_HEX = frozenset("0123456789abcdef")
_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_KINDS = frozenset({"apply", "branch_fact", "jump", "halt"})


@dataclass(frozen=True, slots=True)
class SemanticInstructionV1:
    schema: str
    kind: str
    transformation_hash: str | None
    next_pc: int | None
    fact_hash: str | None
    present_pc: int | None
    absent_pc: int | None
    target_pc: int | None
    instruction_hash: str


@dataclass(frozen=True, slots=True)
class SemanticProcessProgramV1:
    schema: str
    language_version: str
    profile: str
    program_id: str
    source_semantic_hash: str
    initial_field: SemanticFieldV1
    transformations: tuple[FieldTransformationV1, ...]
    instructions: tuple[SemanticInstructionV1, ...]
    entry_pc: int
    quantum_step_limit: int
    authority_hash: str
    program_hash: str


@dataclass(frozen=True, slots=True)
class ProcessCheckpointV1:
    schema: str
    program_hash: str
    field: SemanticFieldV1
    pc: int
    next_epoch_index: int
    previous_continuation: ContinuationReceiptV1 | None
    halted: bool
    checkpoint_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        _fail("TEVS_MAX_V3_IR5_HASH", f"{name} must be lowercase 64-hex")
    return value


def _pc(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_MAX_V3_IR5_PC", f"{name} must be integer >= 0")
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


def _tx_wire(value: FieldTransformationV1) -> dict[str, Any]:
    value = validate_field_transformation(value)
    return {
        "schema": value.schema,
        "transformation_id": value.transformation_id,
        "required_before_hash": value.required_before_hash,
        "result_profile": value.result_profile,
        "remove_fact_hashes": list(value.remove_fact_hashes),
        "add_facts": [
            {"relation": f.relation, "arguments": list(f.arguments), "fact_hash": f.fact_hash}
            for f in value.add_facts
        ],
        "effect_set_hash": value.effect_set_hash,
        "resource_vector_hash": value.resource_vector_hash,
        "proof_requirement_hashes": list(value.proof_requirement_hashes),
        "transformation_hash": value.transformation_hash,
    }


def _instruction_body(
    kind: str,
    transformation_hash: str | None,
    next_pc: int | None,
    fact_hash: str | None,
    present_pc: int | None,
    absent_pc: int | None,
    target_pc: int | None,
) -> dict[str, Any]:
    return {
        "schema": INSTRUCTION_SCHEMA,
        "kind": kind,
        "transformation_hash": transformation_hash,
        "next_pc": next_pc,
        "fact_hash": fact_hash,
        "present_pc": present_pc,
        "absent_pc": absent_pc,
        "target_pc": target_pc,
    }


def _instruction(
    kind: str,
    *,
    transformation_hash: str | None = None,
    next_pc: int | None = None,
    fact_hash: str | None = None,
    present_pc: int | None = None,
    absent_pc: int | None = None,
    target_pc: int | None = None,
) -> SemanticInstructionV1:
    if kind not in _KINDS:
        _fail("TEVS_MAX_V3_IR5_INSTRUCTION_KIND", "unknown semantic-process instruction")
    if kind == "apply":
        transformation_hash, next_pc = _sha(transformation_hash, "transformation_hash"), _pc(next_pc, "next_pc")
        fact_hash = present_pc = absent_pc = target_pc = None
    elif kind == "branch_fact":
        fact_hash = _sha(fact_hash, "fact_hash")
        present_pc, absent_pc = _pc(present_pc, "present_pc"), _pc(absent_pc, "absent_pc")
        transformation_hash = next_pc = target_pc = None
    elif kind == "jump":
        target_pc = _pc(target_pc, "target_pc")
        transformation_hash = next_pc = fact_hash = present_pc = absent_pc = None
    else:
        transformation_hash = next_pc = fact_hash = present_pc = absent_pc = target_pc = None
    body = _instruction_body(kind, transformation_hash, next_pc, fact_hash, present_pc, absent_pc, target_pc)
    return SemanticInstructionV1(
        INSTRUCTION_SCHEMA, kind, transformation_hash, next_pc, fact_hash,
        present_pc, absent_pc, target_pc, canonical_hash(body)
    )


def instruction_apply(transformation_hash: str, *, next_pc: int) -> SemanticInstructionV1:
    return _instruction("apply", transformation_hash=transformation_hash, next_pc=next_pc)


def instruction_branch_fact(fact_hash: str, *, present_pc: int, absent_pc: int) -> SemanticInstructionV1:
    return _instruction("branch_fact", fact_hash=fact_hash, present_pc=present_pc, absent_pc=absent_pc)


def instruction_jump(target_pc: int) -> SemanticInstructionV1:
    return _instruction("jump", target_pc=target_pc)


def instruction_halt() -> SemanticInstructionV1:
    return _instruction("halt")


def instruction_to_object(value: SemanticInstructionV1) -> dict[str, Any]:
    value = validate_semantic_instruction(value)
    return {
        **_instruction_body(
            value.kind, value.transformation_hash, value.next_pc, value.fact_hash,
            value.present_pc, value.absent_pc, value.target_pc
        ),
        "instruction_hash": value.instruction_hash,
    }


def validate_semantic_instruction(value: object) -> SemanticInstructionV1:
    if isinstance(value, SemanticInstructionV1):
        expected = _instruction(
            value.kind,
            transformation_hash=value.transformation_hash,
            next_pc=value.next_pc,
            fact_hash=value.fact_hash,
            present_pc=value.present_pc,
            absent_pc=value.absent_pc,
            target_pc=value.target_pc,
        )
        if value.schema != INSTRUCTION_SCHEMA or value != expected:
            _fail("TEVS_MAX_V3_IR5_INSTRUCTION_HASH", "instruction identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_IR5_INSTRUCTION", "instruction must be object")
    fields = {
        "schema", "kind", "transformation_hash", "next_pc", "fact_hash",
        "present_pc", "absent_pc", "target_pc", "instruction_hash",
    }
    if set(value) != fields or value.get("schema") != INSTRUCTION_SCHEMA:
        _fail("TEVS_MAX_V3_IR5_INSTRUCTION_FIELDS", "instruction fields mismatch")
    expected = _instruction(
        value.get("kind"), transformation_hash=value.get("transformation_hash"),
        next_pc=value.get("next_pc"), fact_hash=value.get("fact_hash"),
        present_pc=value.get("present_pc"), absent_pc=value.get("absent_pc"),
        target_pc=value.get("target_pc"),
    )
    if _sha(value.get("instruction_hash"), "instruction_hash") != expected.instruction_hash:
        _fail("TEVS_MAX_V3_IR5_INSTRUCTION_HASH", "instruction hash mismatch")
    return expected


def _program_body(
    program_id: str,
    source_semantic_hash: str,
    initial_field: SemanticFieldV1,
    transformations: Sequence[FieldTransformationV1],
    instructions: Sequence[SemanticInstructionV1],
    entry_pc: int,
    quantum_step_limit: int,
    authority_hash: str,
) -> dict[str, Any]:
    return {
        "schema": PROGRAM_SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "profile": PROFILE,
        "program_id": program_id,
        "source_semantic_hash": source_semantic_hash,
        "initial_field": _field_wire(initial_field),
        "transformations": [_tx_wire(t) for t in transformations],
        "instructions": [instruction_to_object(i) for i in instructions],
        "entry_pc": entry_pc,
        "quantum_step_limit": quantum_step_limit,
        "authority_hash": authority_hash,
    }


def semantic_process_program(
    *,
    program_id: str,
    source_semantic_hash: str,
    initial_field: SemanticFieldV1,
    transformations: Sequence[FieldTransformationV1],
    instructions: Sequence[SemanticInstructionV1],
    entry_pc: int,
    quantum_step_limit: int,
    authority_hash: str,
) -> SemanticProcessProgramV1:
    if not isinstance(program_id, str) or _ID.fullmatch(program_id) is None:
        _fail("TEVS_MAX_V3_IR5_PROGRAM_ID", "invalid program id")
    source, authority = _sha(source_semantic_hash, "source_semantic_hash"), _sha(authority_hash, "authority_hash")
    field = validate_semantic_field(initial_field)
    if isinstance(transformations, (str, bytes)):
        _fail("TEVS_MAX_V3_IR5_TRANSFORMATIONS", "transformations must be a sequence")
    txs = [validate_field_transformation(t) for t in transformations]
    hashes = [t.transformation_hash for t in txs]
    if len(set(hashes)) != len(hashes):
        _fail("TEVS_MAX_V3_IR5_TRANSFORMATION_DUPLICATE", "duplicate transformation hash")
    if any(t.proof_requirement_hashes for t in txs):
        _fail("TEVS_MAX_V3_IR5_PROOF_OPEN", "proof-open transformation is not executable in semantic-process V1")
    ordered_txs = tuple(sorted(txs, key=lambda t: t.transformation_hash))
    if isinstance(instructions, (str, bytes)):
        _fail("TEVS_MAX_V3_IR5_INSTRUCTIONS", "instructions must be a sequence")
    code = tuple(validate_semantic_instruction(i) for i in instructions)
    if not code or len(code) > MAX_INSTRUCTIONS:
        _fail("TEVS_MAX_V3_IR5_INSTRUCTION_COUNT", "instruction count outside admitted bound")
    entry = _pc(entry_pc, "entry_pc")
    if entry >= len(code):
        _fail("TEVS_MAX_V3_IR5_ENTRY_PC", "entry_pc outside instruction table")
    if isinstance(quantum_step_limit, bool) or not isinstance(quantum_step_limit, int) or not 1 <= quantum_step_limit <= MAX_QUANTUM_STEPS:
        _fail("TEVS_MAX_V3_IR5_QUANTUM_LIMIT", "quantum_step_limit outside 1..1000000")
    known = set(hashes)
    for ins in code:
        targets = [p for p in (ins.next_pc, ins.present_pc, ins.absent_pc, ins.target_pc) if p is not None]
        if any(p >= len(code) for p in targets):
            _fail("TEVS_MAX_V3_IR5_TARGET", "instruction PC target outside instruction table")
        if ins.kind == "apply" and ins.transformation_hash not in known:
            _fail("TEVS_MAX_V3_IR5_TRANSFORMATION_UNKNOWN", "apply references unknown transformation")
    body = _program_body(program_id, source, field, ordered_txs, code, entry, quantum_step_limit, authority)
    return SemanticProcessProgramV1(
        PROGRAM_SCHEMA, LANGUAGE_VERSION, PROFILE, program_id, source, field,
        ordered_txs, code, entry, quantum_step_limit, authority, canonical_hash(body)
    )


def program_to_object(value: SemanticProcessProgramV1) -> dict[str, Any]:
    value = validate_semantic_process_program(value)
    return {
        **_program_body(
            value.program_id, value.source_semantic_hash, value.initial_field,
            value.transformations, value.instructions, value.entry_pc,
            value.quantum_step_limit, value.authority_hash
        ),
        "program_hash": value.program_hash,
    }


def validate_semantic_process_program(value: object) -> SemanticProcessProgramV1:
    if isinstance(value, SemanticProcessProgramV1):
        expected = semantic_process_program(
            program_id=value.program_id, source_semantic_hash=value.source_semantic_hash,
            initial_field=value.initial_field, transformations=value.transformations,
            instructions=value.instructions, entry_pc=value.entry_pc,
            quantum_step_limit=value.quantum_step_limit, authority_hash=value.authority_hash,
        )
        if value != expected:
            _fail("TEVS_MAX_V3_IR5_PROGRAM_HASH", "program identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_IR5_PROGRAM", "program must be object")
    fields = {
        "schema", "language_version", "profile", "program_id", "source_semantic_hash",
        "initial_field", "transformations", "instructions", "entry_pc",
        "quantum_step_limit", "authority_hash", "program_hash",
    }
    if set(value) != fields or value.get("schema") != PROGRAM_SCHEMA or value.get("language_version") != LANGUAGE_VERSION or value.get("profile") != PROFILE:
        _fail("TEVS_MAX_V3_IR5_PROGRAM_FIELDS", "unsupported or malformed Program IR V5 profile")
    tx_raw, code_raw = value.get("transformations"), value.get("instructions")
    if not isinstance(tx_raw, list) or not isinstance(code_raw, list):
        _fail("TEVS_MAX_V3_IR5_PROGRAM_ARRAY", "program tables must be arrays")
    expected = semantic_process_program(
        program_id=value.get("program_id"), source_semantic_hash=value.get("source_semantic_hash"),
        initial_field=validate_semantic_field(value.get("initial_field")),
        transformations=tuple(validate_field_transformation(t) for t in tx_raw),
        instructions=tuple(validate_semantic_instruction(i) for i in code_raw),
        entry_pc=value.get("entry_pc"), quantum_step_limit=value.get("quantum_step_limit"),
        authority_hash=value.get("authority_hash"),
    )
    if _sha(value.get("program_hash"), "program_hash") != expected.program_hash:
        _fail("TEVS_MAX_V3_IR5_PROGRAM_HASH", "program hash mismatch")
    if [t.transformation_hash for t in expected.transformations] != [t.get("transformation_hash") for t in tx_raw]:
        _fail("TEVS_MAX_V3_IR5_TRANSFORMATION_ORDER", "transformation table must be canonical")
    return expected


def process_state_hash(program_hash: str, field_hash: str, pc: int) -> str:
    return canonical_hash({
        "program_hash": _sha(program_hash, "program_hash"),
        "field_hash": _sha(field_hash, "field_hash"),
        "pc": _pc(pc, "pc"),
    })


def _checkpoint_body(
    program_hash: str,
    field: SemanticFieldV1,
    pc: int,
    next_epoch_index: int,
    previous_continuation: ContinuationReceiptV1 | None,
    halted: bool,
) -> dict[str, Any]:
    return {
        "schema": CHECKPOINT_SCHEMA,
        "program_hash": program_hash,
        "field": _field_wire(field),
        "pc": pc,
        "next_epoch_index": next_epoch_index,
        "previous_continuation": None if previous_continuation is None else omega_wire(previous_continuation),
        "halted": halted,
    }


def process_checkpoint(
    program: SemanticProcessProgramV1,
    *,
    field: SemanticFieldV1,
    pc: int,
    next_epoch_index: int,
    previous_continuation: ContinuationReceiptV1 | None,
    halted: bool,
) -> ProcessCheckpointV1:
    program, field, pc = validate_semantic_process_program(program), validate_semantic_field(field), _pc(pc, "pc")
    if pc >= len(program.instructions):
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT_PC", "checkpoint pc outside program")
    if isinstance(next_epoch_index, bool) or not isinstance(next_epoch_index, int) or next_epoch_index < 0:
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT_EPOCH", "next_epoch_index must be integer >= 0")
    if not isinstance(halted, bool):
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT_HALTED", "halted must be boolean")
    previous: ContinuationReceiptV1 | None = None
    if next_epoch_index == 0:
        if previous_continuation is not None:
            _fail("TEVS_MAX_V3_IR5_CHECKPOINT_PREVIOUS", "epoch zero checkpoint cannot have continuation")
    else:
        if previous_continuation is None:
            _fail("TEVS_MAX_V3_IR5_CHECKPOINT_PREVIOUS", "resumed checkpoint requires continuation")
        previous = validate_continuation_receipt(previous_continuation)
        if previous.epoch_index != next_epoch_index - 1:
            _fail("TEVS_MAX_V3_IR5_CHECKPOINT_EPOCH", "continuation epoch does not precede checkpoint")
        if previous.state_hash != process_state_hash(program.program_hash, field.field_hash, pc):
            _fail("TEVS_MAX_V3_IR5_CHECKPOINT_STATE", "continuation state hash does not match checkpoint")
    if halted and program.instructions[pc].kind != "halt":
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT_HALTED", "halted checkpoint must point at halt instruction")
    body = _checkpoint_body(program.program_hash, field, pc, next_epoch_index, previous, halted)
    return ProcessCheckpointV1(
        CHECKPOINT_SCHEMA, program.program_hash, field, pc, next_epoch_index,
        previous, halted, canonical_hash(body)
    )


def initial_process_checkpoint(program: SemanticProcessProgramV1) -> ProcessCheckpointV1:
    program = validate_semantic_process_program(program)
    return process_checkpoint(
        program, field=program.initial_field, pc=program.entry_pc, next_epoch_index=0,
        previous_continuation=None, halted=False
    )


def checkpoint_to_object(value: ProcessCheckpointV1, program: SemanticProcessProgramV1) -> dict[str, Any]:
    value = validate_process_checkpoint(program, value)
    return {
        **_checkpoint_body(
            value.program_hash, value.field, value.pc, value.next_epoch_index,
            value.previous_continuation, value.halted
        ),
        "checkpoint_hash": value.checkpoint_hash,
    }


def validate_process_checkpoint(program: SemanticProcessProgramV1, value: object) -> ProcessCheckpointV1:
    program = validate_semantic_process_program(program)
    if isinstance(value, ProcessCheckpointV1):
        if value.program_hash != program.program_hash:
            _fail("TEVS_MAX_V3_IR5_CHECKPOINT_PROGRAM", "checkpoint program mismatch")
        expected = process_checkpoint(
            program, field=value.field, pc=value.pc, next_epoch_index=value.next_epoch_index,
            previous_continuation=value.previous_continuation, halted=value.halted
        )
        if value != expected:
            _fail("TEVS_MAX_V3_IR5_CHECKPOINT_HASH", "checkpoint identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT", "checkpoint must be object")
    fields = {
        "schema", "program_hash", "field", "pc", "next_epoch_index",
        "previous_continuation", "halted", "checkpoint_hash",
    }
    if set(value) != fields or value.get("schema") != CHECKPOINT_SCHEMA or value.get("program_hash") != program.program_hash:
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT_FIELDS", "checkpoint fields or program identity mismatch")
    previous_raw = value.get("previous_continuation")
    previous = None if previous_raw is None else validate_continuation_receipt(previous_raw)
    expected = process_checkpoint(
        program, field=validate_semantic_field(value.get("field")), pc=value.get("pc"),
        next_epoch_index=value.get("next_epoch_index"), previous_continuation=previous,
        halted=value.get("halted"),
    )
    if _sha(value.get("checkpoint_hash"), "checkpoint_hash") != expected.checkpoint_hash:
        _fail("TEVS_MAX_V3_IR5_CHECKPOINT_HASH", "checkpoint hash mismatch")
    return expected


__all__ = [
    "CHECKPOINT_SCHEMA", "INSTRUCTION_SCHEMA", "LANGUAGE_VERSION", "PROGRAM_SCHEMA",
    "ProcessCheckpointV1", "SemanticInstructionV1", "SemanticProcessProgramV1",
    "checkpoint_to_object", "initial_process_checkpoint", "instruction_apply",
    "instruction_branch_fact", "instruction_halt", "instruction_jump",
    "instruction_to_object", "process_checkpoint", "process_state_hash",
    "program_to_object", "semantic_process_program", "validate_process_checkpoint",
    "validate_semantic_instruction", "validate_semantic_process_program",
]
