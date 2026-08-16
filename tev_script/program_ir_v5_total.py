from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash, canonical_json
from .diagnostics import TevScriptError
from .omega_semantic_basis_v1 import (
    FieldTransformationV1,
    SemanticFieldV1,
    validate_field_transformation,
    validate_semantic_field,
)
from .program_ir_v4 import (
    PROGRAM_IR_V4_EFFECTS_SCHEMA,
    PROGRAM_IR_V4_PURE_SCHEMA,
    PROGRAM_IR_V4_RECURSIVE_SCHEMA,
    validate_program_ir_v4_effects,
    validate_program_ir_v4_pure,
    validate_program_ir_v4_recursive,
)

PROGRAM_SCHEMA_V31 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1"
UNIT_SCHEMA_V31 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1"
INSTRUCTION_SCHEMA_V31 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_INSTRUCTION_V1"
PROOF_ADMISSION_SCHEMA_V31 = "TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1"
LANGUAGE_VERSION_V31 = "3.1.0"
PROFILE_TOTAL_CORE = "total_core"
MAX_TOTAL_CORE_INSTRUCTIONS_V1 = 65_536
MAX_TOTAL_CORE_QUANTUM_STEPS_V1 = 1_000_000

_HEX = frozenset("0123456789abcdef")
_STABLE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_PROFILES = frozenset({"pure", "recursive", "effects"})
_KINDS = frozenset({"apply", "branch_fact", "jump", "halt", "invoke_v4"})


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        _fail("TEVS_V31_TOTAL_HASH", f"{name} must be lowercase 64-hex")
    return value


def _stable(value: Any, name: str) -> str:
    if not isinstance(value, str) or _STABLE_ID.fullmatch(value) is None:
        _fail("TEVS_V31_TOTAL_ID", f"{name} must be a stable identifier")
    return value


def _pc(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_V31_TOTAL_PC", f"{name} must be an integer >= 0")
    return value


def _detached_mapping(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TEVS_V31_TOTAL_MAPPING", f"{name} must be an object")
    try:
        detached = json.loads(canonical_json(dict(value)))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        _fail("TEVS_V31_TOTAL_CANONICAL", f"{name} is not canonical JSON data: {exc}")
    if not isinstance(detached, dict):
        _fail("TEVS_V31_TOTAL_MAPPING", f"{name} must be an object")
    return detached


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


def _transformation_wire(value: FieldTransformationV1) -> dict[str, Any]:
    tx = validate_field_transformation(value)
    return {
        "schema": tx.schema,
        "transformation_id": tx.transformation_id,
        "required_before_hash": tx.required_before_hash,
        "result_profile": tx.result_profile,
        "remove_fact_hashes": list(tx.remove_fact_hashes),
        "add_facts": [
            {
                "relation": fact.relation,
                "arguments": list(fact.arguments),
                "fact_hash": fact.fact_hash,
            }
            for fact in tx.add_facts
        ],
        "effect_set_hash": tx.effect_set_hash,
        "resource_vector_hash": tx.resource_vector_hash,
        "proof_requirement_hashes": list(tx.proof_requirement_hashes),
        "transformation_hash": tx.transformation_hash,
    }


def _validate_v4_profile(profile: str, raw: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    if profile not in _PROFILES:
        _fail("TEVS_V31_TOTAL_UNIT_PROFILE", f"unsupported V4 unit profile {profile!r}")
    detached = _detached_mapping(raw, "program_ir_v4")
    declared_hash = _sha(detached.get("program_ir_hash"), "program_ir_hash")
    if profile == "pure":
        if detached.get("schema") != PROGRAM_IR_V4_PURE_SCHEMA:
            _fail("TEVS_V31_TOTAL_UNIT_SCHEMA", "pure unit must embed Program IR V4 Pure V1")
        validation = validate_program_ir_v4_pure(detached, expected_program_ir_hash=declared_hash)
    elif profile == "recursive":
        if detached.get("schema") != PROGRAM_IR_V4_RECURSIVE_SCHEMA:
            _fail("TEVS_V31_TOTAL_UNIT_SCHEMA", "recursive unit must embed Program IR V4 Recursive V1")
        validation = validate_program_ir_v4_recursive(detached, expected_program_ir_hash=declared_hash)
    else:
        if detached.get("schema") != PROGRAM_IR_V4_EFFECTS_SCHEMA:
            _fail("TEVS_V31_TOTAL_UNIT_SCHEMA", "effects unit must embed Program IR V4 Effects V1")
        validation = validate_program_ir_v4_effects(detached, expected_program_ir_hash=declared_hash)
    if validation.program_ir_hash != declared_hash:
        _fail("TEVS_V31_TOTAL_UNIT_HASH", "V4 validator diverged from declared program_ir_hash")
    return detached, declared_hash


@dataclass(frozen=True, slots=True)
class TotalCoreUnitV1:
    schema: str
    unit_id: str
    profile: str
    program_ir_v4: dict[str, Any]
    program_ir_hash: str
    unit_hash: str

    @classmethod
    def build(cls, unit_id: str, profile: str, program_ir_v4: Mapping[str, Any]) -> "TotalCoreUnitV1":
        uid = _stable(unit_id, "unit_id")
        if not isinstance(profile, str):
            _fail("TEVS_V31_TOTAL_UNIT_PROFILE", "profile must be text")
        detached, program_hash = _validate_v4_profile(profile, program_ir_v4)
        body = {
            "schema": UNIT_SCHEMA_V31,
            "unit_id": uid,
            "profile": profile,
            "program_ir_hash": program_hash,
        }
        return cls(UNIT_SCHEMA_V31, uid, profile, detached, program_hash, canonical_hash(body))


def _unit_wire(value: TotalCoreUnitV1) -> dict[str, Any]:
    unit = validate_total_core_unit(value)
    return {
        "schema": unit.schema,
        "unit_id": unit.unit_id,
        "profile": unit.profile,
        "program_ir_v4": unit.program_ir_v4,
        "program_ir_hash": unit.program_ir_hash,
        "unit_hash": unit.unit_hash,
    }


def validate_total_core_unit(value: object) -> TotalCoreUnitV1:
    if isinstance(value, TotalCoreUnitV1):
        expected = TotalCoreUnitV1.build(value.unit_id, value.profile, value.program_ir_v4)
        if value != expected:
            _fail("TEVS_V31_TOTAL_UNIT_IDENTITY", "unit identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_V31_TOTAL_UNIT", "unit must be an object")
    fields = {"schema", "unit_id", "profile", "program_ir_v4", "program_ir_hash", "unit_hash"}
    if set(value) != fields or value.get("schema") != UNIT_SCHEMA_V31:
        _fail("TEVS_V31_TOTAL_UNIT_FIELDS", "unit field set or schema mismatch")
    embedded = value.get("program_ir_v4")
    if not isinstance(embedded, Mapping):
        _fail("TEVS_V31_TOTAL_UNIT", "program_ir_v4 must be an object")
    expected = TotalCoreUnitV1.build(value.get("unit_id"), value.get("profile"), embedded)
    if _sha(value.get("program_ir_hash"), "program_ir_hash") != expected.program_ir_hash:
        _fail("TEVS_V31_TOTAL_UNIT_HASH", "unit program_ir_hash mismatch")
    if _sha(value.get("unit_hash"), "unit_hash") != expected.unit_hash:
        _fail("TEVS_V31_TOTAL_UNIT_HASH", "unit_hash mismatch")
    return expected


@dataclass(frozen=True, slots=True)
class VerifiedProofAdmissionV1:
    schema: str
    requirement_hash: str
    verification_receipt_hash: str
    verifier_identity_hash: str
    authority_hash: str
    status: str
    admission_hash: str

    @classmethod
    def build(
        cls,
        *,
        requirement_hash: str,
        verification_receipt_hash: str,
        verifier_identity_hash: str,
        authority_hash: str,
    ) -> "VerifiedProofAdmissionV1":
        requirement = _sha(requirement_hash, "requirement_hash")
        receipt = _sha(verification_receipt_hash, "verification_receipt_hash")
        verifier = _sha(verifier_identity_hash, "verifier_identity_hash")
        authority = _sha(authority_hash, "authority_hash")
        body = {
            "schema": PROOF_ADMISSION_SCHEMA_V31,
            "requirement_hash": requirement,
            "verification_receipt_hash": receipt,
            "verifier_identity_hash": verifier,
            "authority_hash": authority,
            "status": "VERIFIED",
        }
        return cls(
            PROOF_ADMISSION_SCHEMA_V31,
            requirement,
            receipt,
            verifier,
            authority,
            "VERIFIED",
            canonical_hash(body),
        )


def _proof_wire(value: VerifiedProofAdmissionV1) -> dict[str, Any]:
    proof = validate_verified_proof_admission(value)
    return {
        "schema": proof.schema,
        "requirement_hash": proof.requirement_hash,
        "verification_receipt_hash": proof.verification_receipt_hash,
        "verifier_identity_hash": proof.verifier_identity_hash,
        "authority_hash": proof.authority_hash,
        "status": proof.status,
        "admission_hash": proof.admission_hash,
    }


def validate_verified_proof_admission(value: object) -> VerifiedProofAdmissionV1:
    if isinstance(value, VerifiedProofAdmissionV1):
        expected = VerifiedProofAdmissionV1.build(
            requirement_hash=value.requirement_hash,
            verification_receipt_hash=value.verification_receipt_hash,
            verifier_identity_hash=value.verifier_identity_hash,
            authority_hash=value.authority_hash,
        )
        if value != expected:
            _fail("TEVS_V31_TOTAL_PROOF_IDENTITY", "proof admission identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_V31_TOTAL_PROOF", "proof admission must be an object")
    fields = {
        "schema", "requirement_hash", "verification_receipt_hash", "verifier_identity_hash",
        "authority_hash", "status", "admission_hash",
    }
    if set(value) != fields or value.get("schema") != PROOF_ADMISSION_SCHEMA_V31 or value.get("status") != "VERIFIED":
        _fail("TEVS_V31_TOTAL_PROOF_FIELDS", "proof admission fields mismatch")
    expected = VerifiedProofAdmissionV1.build(
        requirement_hash=value.get("requirement_hash"),
        verification_receipt_hash=value.get("verification_receipt_hash"),
        verifier_identity_hash=value.get("verifier_identity_hash"),
        authority_hash=value.get("authority_hash"),
    )
    if _sha(value.get("admission_hash"), "admission_hash") != expected.admission_hash:
        _fail("TEVS_V31_TOTAL_PROOF_HASH", "proof admission hash mismatch")
    return expected


@dataclass(frozen=True, slots=True)
class TotalCoreInstructionV1:
    schema: str
    kind: str
    transformation_hash: str | None
    next_pc: int | None
    fact_hash: str | None
    present_pc: int | None
    absent_pc: int | None
    target_pc: int | None
    unit_hash: str | None
    result_relation: str | None
    instruction_hash: str

    @classmethod
    def apply(cls, transformation_hash: str, *, next_pc: int) -> "TotalCoreInstructionV1":
        return _instruction("apply", transformation_hash=transformation_hash, next_pc=next_pc)

    @classmethod
    def branch_fact(cls, fact_hash: str, *, present_pc: int, absent_pc: int) -> "TotalCoreInstructionV1":
        return _instruction("branch_fact", fact_hash=fact_hash, present_pc=present_pc, absent_pc=absent_pc)

    @classmethod
    def jump(cls, target_pc: int) -> "TotalCoreInstructionV1":
        return _instruction("jump", target_pc=target_pc)

    @classmethod
    def halt(cls) -> "TotalCoreInstructionV1":
        return _instruction("halt")

    @classmethod
    def invoke_v4(cls, *, unit_hash: str, result_relation: str, next_pc: int) -> "TotalCoreInstructionV1":
        return _instruction("invoke_v4", unit_hash=unit_hash, result_relation=result_relation, next_pc=next_pc)


def _instruction_body(
    kind: str,
    *,
    transformation_hash: str | None,
    next_pc: int | None,
    fact_hash: str | None,
    present_pc: int | None,
    absent_pc: int | None,
    target_pc: int | None,
    unit_hash: str | None,
    result_relation: str | None,
) -> dict[str, Any]:
    return {
        "schema": INSTRUCTION_SCHEMA_V31,
        "kind": kind,
        "transformation_hash": transformation_hash,
        "next_pc": next_pc,
        "fact_hash": fact_hash,
        "present_pc": present_pc,
        "absent_pc": absent_pc,
        "target_pc": target_pc,
        "unit_hash": unit_hash,
        "result_relation": result_relation,
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
    unit_hash: str | None = None,
    result_relation: str | None = None,
) -> TotalCoreInstructionV1:
    if kind not in _KINDS:
        _fail("TEVS_V31_TOTAL_INSTRUCTION_KIND", f"unknown instruction kind {kind!r}")
    if kind == "apply":
        transformation_hash = _sha(transformation_hash, "transformation_hash")
        next_pc = _pc(next_pc, "next_pc")
        fact_hash = present_pc = absent_pc = target_pc = unit_hash = result_relation = None
    elif kind == "branch_fact":
        fact_hash = _sha(fact_hash, "fact_hash")
        present_pc = _pc(present_pc, "present_pc")
        absent_pc = _pc(absent_pc, "absent_pc")
        transformation_hash = next_pc = target_pc = unit_hash = result_relation = None
    elif kind == "jump":
        target_pc = _pc(target_pc, "target_pc")
        transformation_hash = next_pc = fact_hash = present_pc = absent_pc = unit_hash = result_relation = None
    elif kind == "invoke_v4":
        unit_hash = _sha(unit_hash, "unit_hash")
        result_relation = _stable(result_relation, "result_relation")
        next_pc = _pc(next_pc, "next_pc")
        transformation_hash = fact_hash = present_pc = absent_pc = target_pc = None
    else:
        transformation_hash = next_pc = fact_hash = present_pc = absent_pc = target_pc = unit_hash = result_relation = None
    body = _instruction_body(
        kind,
        transformation_hash=transformation_hash,
        next_pc=next_pc,
        fact_hash=fact_hash,
        present_pc=present_pc,
        absent_pc=absent_pc,
        target_pc=target_pc,
        unit_hash=unit_hash,
        result_relation=result_relation,
    )
    return TotalCoreInstructionV1(
        INSTRUCTION_SCHEMA_V31,
        kind,
        transformation_hash,
        next_pc,
        fact_hash,
        present_pc,
        absent_pc,
        target_pc,
        unit_hash,
        result_relation,
        canonical_hash(body),
    )


def _instruction_wire(value: TotalCoreInstructionV1) -> dict[str, Any]:
    instruction = validate_total_core_instruction(value)
    return {
        **_instruction_body(
            instruction.kind,
            transformation_hash=instruction.transformation_hash,
            next_pc=instruction.next_pc,
            fact_hash=instruction.fact_hash,
            present_pc=instruction.present_pc,
            absent_pc=instruction.absent_pc,
            target_pc=instruction.target_pc,
            unit_hash=instruction.unit_hash,
            result_relation=instruction.result_relation,
        ),
        "instruction_hash": instruction.instruction_hash,
    }


def validate_total_core_instruction(value: object) -> TotalCoreInstructionV1:
    if isinstance(value, TotalCoreInstructionV1):
        expected = _instruction(
            value.kind,
            transformation_hash=value.transformation_hash,
            next_pc=value.next_pc,
            fact_hash=value.fact_hash,
            present_pc=value.present_pc,
            absent_pc=value.absent_pc,
            target_pc=value.target_pc,
            unit_hash=value.unit_hash,
            result_relation=value.result_relation,
        )
        if value != expected:
            _fail("TEVS_V31_TOTAL_INSTRUCTION_IDENTITY", "instruction identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_V31_TOTAL_INSTRUCTION", "instruction must be an object")
    fields = {
        "schema", "kind", "transformation_hash", "next_pc", "fact_hash", "present_pc",
        "absent_pc", "target_pc", "unit_hash", "result_relation", "instruction_hash",
    }
    if set(value) != fields or value.get("schema") != INSTRUCTION_SCHEMA_V31:
        _fail("TEVS_V31_TOTAL_INSTRUCTION_FIELDS", "instruction field set or schema mismatch")
    expected = _instruction(
        value.get("kind"),
        transformation_hash=value.get("transformation_hash"),
        next_pc=value.get("next_pc"),
        fact_hash=value.get("fact_hash"),
        present_pc=value.get("present_pc"),
        absent_pc=value.get("absent_pc"),
        target_pc=value.get("target_pc"),
        unit_hash=value.get("unit_hash"),
        result_relation=value.get("result_relation"),
    )
    if _sha(value.get("instruction_hash"), "instruction_hash") != expected.instruction_hash:
        _fail("TEVS_V31_TOTAL_INSTRUCTION_HASH", "instruction hash mismatch")
    return expected


@dataclass(frozen=True, slots=True)
class TotalCoreProgramV1:
    schema: str
    language_version: str
    profile: str
    program_id: str
    source_semantic_hash: str
    initial_field: SemanticFieldV1
    transformations: tuple[FieldTransformationV1, ...]
    v4_units: tuple[TotalCoreUnitV1, ...]
    proof_admissions: tuple[VerifiedProofAdmissionV1, ...]
    instructions: tuple[TotalCoreInstructionV1, ...]
    entry_pc: int
    quantum_step_limit: int
    authority_hash: str
    program_hash: str

    @classmethod
    def build(
        cls,
        *,
        program_id: str,
        source_semantic_hash: str,
        initial_field: SemanticFieldV1,
        transformations: Sequence[FieldTransformationV1],
        v4_units: Sequence[TotalCoreUnitV1],
        proof_admissions: Sequence[VerifiedProofAdmissionV1],
        instructions: Sequence[TotalCoreInstructionV1],
        entry_pc: int,
        quantum_step_limit: int,
        authority_hash: str,
    ) -> "TotalCoreProgramV1":
        pid = _stable(program_id, "program_id")
        source = _sha(source_semantic_hash, "source_semantic_hash")
        authority = _sha(authority_hash, "authority_hash")
        field = validate_semantic_field(initial_field)

        if isinstance(transformations, (str, bytes)):
            _fail("TEVS_V31_TOTAL_TRANSFORMATIONS", "transformations must be a sequence")
        txs = tuple(validate_field_transformation(item) for item in transformations)
        tx_hashes = [item.transformation_hash for item in txs]
        if len(set(tx_hashes)) != len(tx_hashes):
            _fail("TEVS_V31_TOTAL_TRANSFORMATION_DUPLICATE", "duplicate transformation hash")
        ordered_txs = tuple(sorted(txs, key=lambda item: item.transformation_hash))

        if isinstance(v4_units, (str, bytes)):
            _fail("TEVS_V31_TOTAL_UNITS", "v4_units must be a sequence")
        units = tuple(validate_total_core_unit(item) for item in v4_units)
        unit_ids = [item.unit_id for item in units]
        unit_hashes = [item.unit_hash for item in units]
        if len(set(unit_ids)) != len(unit_ids):
            _fail("TEVS_V31_TOTAL_UNIT_ID_DUPLICATE", "duplicate unit_id")
        if len(set(unit_hashes)) != len(unit_hashes):
            _fail("TEVS_V31_TOTAL_UNIT_HASH_DUPLICATE", "duplicate unit_hash")
        ordered_units = tuple(sorted(units, key=lambda item: (item.unit_id, item.unit_hash)))

        if isinstance(proof_admissions, (str, bytes)):
            _fail("TEVS_V31_TOTAL_PROOFS", "proof_admissions must be a sequence")
        proofs = tuple(validate_verified_proof_admission(item) for item in proof_admissions)
        requirements = [item.requirement_hash for item in proofs]
        admissions = [item.admission_hash for item in proofs]
        if len(set(requirements)) != len(requirements):
            _fail("TEVS_V31_TOTAL_PROOF_REQUIREMENT_DUPLICATE", "duplicate proof requirement admission")
        if len(set(admissions)) != len(admissions):
            _fail("TEVS_V31_TOTAL_PROOF_DUPLICATE", "duplicate proof admission hash")
        if any(item.authority_hash != authority for item in proofs):
            _fail("TEVS_V31_TOTAL_PROOF_AUTHORITY", "proof admission authority differs from program authority")
        ordered_proofs = tuple(sorted(proofs, key=lambda item: (item.requirement_hash, item.admission_hash)))

        if isinstance(instructions, (str, bytes)):
            _fail("TEVS_V31_TOTAL_INSTRUCTIONS", "instructions must be a sequence")
        code = tuple(validate_total_core_instruction(item) for item in instructions)
        if not code or len(code) > MAX_TOTAL_CORE_INSTRUCTIONS_V1:
            _fail("TEVS_V31_TOTAL_INSTRUCTION_COUNT", "instruction count outside admitted bound")

        entry = _pc(entry_pc, "entry_pc")
        if entry >= len(code):
            _fail("TEVS_V31_TOTAL_ENTRY_PC", "entry_pc outside instruction table")
        if isinstance(quantum_step_limit, bool) or not isinstance(quantum_step_limit, int):
            _fail("TEVS_V31_TOTAL_QUANTUM_LIMIT", "quantum_step_limit must be an integer")
        if not 1 <= quantum_step_limit <= MAX_TOTAL_CORE_QUANTUM_STEPS_V1:
            _fail("TEVS_V31_TOTAL_QUANTUM_LIMIT", "quantum_step_limit outside admitted bound")

        known_txs = {item.transformation_hash: item for item in ordered_txs}
        known_units = {item.unit_hash: item for item in ordered_units}
        admitted_requirements = {item.requirement_hash for item in ordered_proofs}
        for instruction in code:
            targets = tuple(
                target
                for target in (
                    instruction.next_pc,
                    instruction.present_pc,
                    instruction.absent_pc,
                    instruction.target_pc,
                )
                if target is not None
            )
            if any(target >= len(code) for target in targets):
                _fail("TEVS_V31_TOTAL_TARGET", "instruction PC target outside instruction table")
            if instruction.kind == "apply":
                tx = known_txs.get(instruction.transformation_hash)
                if tx is None:
                    _fail("TEVS_V31_TOTAL_TRANSFORMATION_UNKNOWN", "apply references unknown transformation")
                missing = set(tx.proof_requirement_hashes) - admitted_requirements
                if missing:
                    _fail("TEVS_V31_TOTAL_PROOF_REQUIRED", "apply references proof-open transformation without exact admission")
            elif instruction.kind == "invoke_v4" and instruction.unit_hash not in known_units:
                _fail("TEVS_V31_TOTAL_UNIT_UNKNOWN", "invoke_v4 references unknown unit")

        body = _program_body(
            pid,
            source,
            field,
            ordered_txs,
            ordered_units,
            ordered_proofs,
            code,
            entry,
            quantum_step_limit,
            authority,
        )
        return cls(
            PROGRAM_SCHEMA_V31,
            LANGUAGE_VERSION_V31,
            PROFILE_TOTAL_CORE,
            pid,
            source,
            field,
            ordered_txs,
            ordered_units,
            ordered_proofs,
            code,
            entry,
            quantum_step_limit,
            authority,
            canonical_hash(body),
        )


def _program_body(
    program_id: str,
    source_semantic_hash: str,
    initial_field: SemanticFieldV1,
    transformations: Sequence[FieldTransformationV1],
    v4_units: Sequence[TotalCoreUnitV1],
    proof_admissions: Sequence[VerifiedProofAdmissionV1],
    instructions: Sequence[TotalCoreInstructionV1],
    entry_pc: int,
    quantum_step_limit: int,
    authority_hash: str,
) -> dict[str, Any]:
    return {
        "schema": PROGRAM_SCHEMA_V31,
        "language_version": LANGUAGE_VERSION_V31,
        "profile": PROFILE_TOTAL_CORE,
        "program_id": program_id,
        "source_semantic_hash": source_semantic_hash,
        "initial_field": _field_wire(initial_field),
        "transformations": [_transformation_wire(item) for item in transformations],
        "v4_units": [_unit_wire(item) for item in v4_units],
        "proof_admissions": [_proof_wire(item) for item in proof_admissions],
        "instructions": [_instruction_wire(item) for item in instructions],
        "entry_pc": entry_pc,
        "quantum_step_limit": quantum_step_limit,
        "authority_hash": authority_hash,
    }


def total_core_program_to_mapping(value: TotalCoreProgramV1) -> dict[str, Any]:
    program = validate_total_core_program(value)
    return {
        **_program_body(
            program.program_id,
            program.source_semantic_hash,
            program.initial_field,
            program.transformations,
            program.v4_units,
            program.proof_admissions,
            program.instructions,
            program.entry_pc,
            program.quantum_step_limit,
            program.authority_hash,
        ),
        "program_hash": program.program_hash,
    }


def validate_total_core_program(value: object) -> TotalCoreProgramV1:
    if isinstance(value, TotalCoreProgramV1):
        expected = TotalCoreProgramV1.build(
            program_id=value.program_id,
            source_semantic_hash=value.source_semantic_hash,
            initial_field=value.initial_field,
            transformations=value.transformations,
            v4_units=value.v4_units,
            proof_admissions=value.proof_admissions,
            instructions=value.instructions,
            entry_pc=value.entry_pc,
            quantum_step_limit=value.quantum_step_limit,
            authority_hash=value.authority_hash,
        )
        if value != expected:
            _fail("TEVS_V31_TOTAL_PROGRAM_IDENTITY", "program identity mismatch")
        return value

    if not isinstance(value, Mapping):
        _fail("TEVS_V31_TOTAL_PROGRAM", "program must be an object")
    fields = {
        "schema", "language_version", "profile", "program_id", "source_semantic_hash",
        "initial_field", "transformations", "v4_units", "proof_admissions", "instructions",
        "entry_pc", "quantum_step_limit", "authority_hash", "program_hash",
    }
    if (
        set(value) != fields
        or value.get("schema") != PROGRAM_SCHEMA_V31
        or value.get("language_version") != LANGUAGE_VERSION_V31
        or value.get("profile") != PROFILE_TOTAL_CORE
    ):
        _fail("TEVS_V31_TOTAL_PROGRAM_FIELDS", "unsupported or malformed Total-Core program")

    tx_raw = value.get("transformations")
    units_raw = value.get("v4_units")
    proofs_raw = value.get("proof_admissions")
    code_raw = value.get("instructions")
    if not all(isinstance(item, list) for item in (tx_raw, units_raw, proofs_raw, code_raw)):
        _fail("TEVS_V31_TOTAL_PROGRAM_ARRAY", "program tables must be arrays")

    expected = TotalCoreProgramV1.build(
        program_id=value.get("program_id"),
        source_semantic_hash=value.get("source_semantic_hash"),
        initial_field=validate_semantic_field(value.get("initial_field")),
        transformations=tuple(validate_field_transformation(item) for item in tx_raw),
        v4_units=tuple(validate_total_core_unit(item) for item in units_raw),
        proof_admissions=tuple(validate_verified_proof_admission(item) for item in proofs_raw),
        instructions=tuple(validate_total_core_instruction(item) for item in code_raw),
        entry_pc=value.get("entry_pc"),
        quantum_step_limit=value.get("quantum_step_limit"),
        authority_hash=value.get("authority_hash"),
    )

    if _sha(value.get("program_hash"), "program_hash") != expected.program_hash:
        _fail("TEVS_V31_TOTAL_PROGRAM_HASH", "program_hash mismatch")
    if [item.get("transformation_hash") for item in tx_raw] != [item.transformation_hash for item in expected.transformations]:
        _fail("TEVS_V31_TOTAL_TRANSFORMATION_ORDER", "transformation table must be canonical")
    if [item.get("unit_hash") for item in units_raw] != [item.unit_hash for item in expected.v4_units]:
        _fail("TEVS_V31_TOTAL_UNIT_ORDER", "V4 unit table must be canonical")
    if [item.get("admission_hash") for item in proofs_raw] != [item.admission_hash for item in expected.proof_admissions]:
        _fail("TEVS_V31_TOTAL_PROOF_ORDER", "proof admission table must be canonical")
    return expected


def canonical_total_core_program_bytes(value: TotalCoreProgramV1 | Mapping[str, Any]) -> bytes:
    program = validate_total_core_program(value)
    return canonical_json(total_core_program_to_mapping(program)).encode("utf-8")
