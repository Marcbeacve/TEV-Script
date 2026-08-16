from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .program_ir_v4 import (
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
)
from .program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    TotalCoreUnitV1,
    VerifiedProofAdmissionV1,
)
from .source_effect_program_v2 import (
    build_effect_program_ir_v4,
    compile_effect_program_v2,
)
from .source_program_v2 import compile_program_v2
from .source_semantic_process_v3 import (
    compile_semantic_process_v3,
    parse_semantic_process_v3,
)

LANGUAGE_VERSION_V31 = "3.1.0"
SOURCE_MODEL_SCHEMA_V31 = "TEV_SCRIPT_V31_TOTAL_CORE_SOURCE_MODEL_V1"

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEADER = re.compile(
    r'^process\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s+version\s+"([^"]+)"$'
)
_UNIT = re.compile(
    r"^unit\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s+profile\s+(pure|recursive|effects)$"
)
_LABEL = re.compile(r"^label\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s*=\s*(.+)$")
_INVOKE = re.compile(
    r"^invoke_v4\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s+result\s+"
    r"([A-Za-z_][A-Za-z0-9_.:/-]*)\s+([A-Za-z_][A-Za-z0-9_.:/-]*)$"
)


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _split_statements(source: str) -> tuple[str, ...]:
    if not isinstance(source, str):
        _fail("TEVS_V31_SOURCE_TYPE", "source must be text")
    cleaned_lines: list[str] = []
    for raw in source.splitlines():
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        cleaned_lines.append(raw)
    text = "\n".join(cleaned_lines)
    statements: list[str] = []
    buf: list[str] = []
    in_string = False
    escape = False
    square = 0
    for ch in text:
        if in_string:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            buf.append(ch)
        elif ch == "[":
            square += 1
            buf.append(ch)
        elif ch == "]":
            square -= 1
            if square < 0:
                _fail("TEVS_V31_SOURCE_BRACKETS", "unbalanced ]")
            buf.append(ch)
        elif ch == ";" and square == 0:
            statement = " ".join("".join(buf).split())
            if statement:
                statements.append(statement)
            buf.clear()
        else:
            buf.append(ch)
    if in_string or square != 0:
        _fail("TEVS_V31_SOURCE_UNCLOSED", "unclosed string or array")
    if "".join(buf).strip():
        _fail("TEVS_V31_SOURCE_SEMICOLON", "every declaration must end with semicolon")
    return tuple(statements)


def _normalize_process_source(
    source: str,
) -> tuple[
    str,
    tuple[tuple[str, str], ...],
    dict[str, tuple[str, str, str]],
]:
    statements = _split_statements(source)
    translated: list[str] = []
    units: dict[str, str] = {}
    invokes: dict[str, tuple[str, str, str]] = {}
    header_seen = False

    for statement in statements:
        header = _HEADER.fullmatch(statement)
        if header is not None:
            if header_seen:
                _fail("TEVS_V31_SOURCE_DUPLICATE", "duplicate process header")
            header_seen = True
            program_id, version = header.groups()
            if version != LANGUAGE_VERSION_V31:
                _fail(
                    "TEVS_V31_SOURCE_VERSION",
                    f"Total-Core source requires version {LANGUAGE_VERSION_V31}",
                )
            translated.append(f'process {program_id} version "3.0.0"')
            continue

        unit = _UNIT.fullmatch(statement)
        if unit is not None:
            unit_id, profile = unit.groups()
            if unit_id in units:
                _fail("TEVS_V31_SOURCE_UNIT_DUPLICATE", f"duplicate unit {unit_id}")
            units[unit_id] = profile
            continue

        label = _LABEL.fullmatch(statement)
        if label is not None:
            label_name, body = label.groups()
            invoke = _INVOKE.fullmatch(body)
            if invoke is not None:
                if label_name in invokes:
                    _fail(
                        "TEVS_V31_SOURCE_LABEL_DUPLICATE",
                        f"duplicate invoke label {label_name}",
                    )
                invokes[label_name] = invoke.groups()
                translated.append(f"label {label_name} = halt")
                continue

        translated.append(statement)

    if not header_seen:
        _fail("TEVS_V31_SOURCE_REQUIRED", "process header is required")

    translated_source = ";\n".join(translated) + ";\n"
    return (
        translated_source,
        tuple(sorted(units.items())),
        invokes,
    )


def _validate_source_mapping(
    declared_units: Sequence[tuple[str, str]],
    unit_sources: Mapping[str, str],
) -> dict[str, str]:
    if not isinstance(unit_sources, Mapping):
        _fail("TEVS_V31_SOURCE_UNITS", "unit_sources must be a mapping")
    declared = {unit_id for unit_id, _ in declared_units}
    supplied = set(unit_sources)
    if supplied != declared:
        missing = sorted(declared - supplied)
        extra = sorted(supplied - declared)
        _fail(
            "TEVS_V31_SOURCE_UNIT_SET",
            f"unit_sources mismatch missing={missing} extra={extra}",
        )
    result: dict[str, str] = {}
    for unit_id in sorted(declared):
        source = unit_sources[unit_id]
        if not isinstance(source, str):
            _fail("TEVS_V31_SOURCE_UNIT_TEXT", f"unit {unit_id} source must be text")
        result[unit_id] = source
    return result


def _validate_effect_inputs(
    declared_units: Sequence[tuple[str, str]],
    raw: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    inputs: Mapping[str, Mapping[str, Any]]
    if raw is None:
        inputs = {}
    elif isinstance(raw, Mapping):
        inputs = raw
    else:
        _fail("TEVS_V31_SOURCE_EFFECT_INPUTS", "effect_inputs must be a mapping")

    profiles = dict(declared_units)
    expected = {unit_id for unit_id, profile in declared_units if profile == "effects"}
    supplied = set(inputs)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        _fail(
            "TEVS_V31_SOURCE_EFFECT_INPUT_SET",
            f"effect_inputs mismatch missing={missing} extra={extra}",
        )

    normalized: dict[str, dict[str, Any]] = {}
    for unit_id in sorted(supplied):
        if profiles.get(unit_id) != "effects":
            _fail(
                "TEVS_V31_SOURCE_EFFECT_INPUT_PROFILE",
                f"unit {unit_id} is not an effects unit",
            )
        value = inputs[unit_id]
        if not isinstance(value, Mapping):
            _fail(
                "TEVS_V31_SOURCE_EFFECT_INPUT",
                f"effect input for {unit_id} must be an object",
            )
        fields = set(value)
        if fields not in ({"scenario"}, {"scenario", "current_state"}):
            _fail(
                "TEVS_V31_SOURCE_EFFECT_INPUT_FIELDS",
                f"effect input for {unit_id} has invalid field set",
            )
        scenario = value.get("scenario")
        current_state = value.get("current_state")
        if not isinstance(scenario, Mapping):
            _fail(
                "TEVS_V31_SOURCE_EFFECT_SCENARIO",
                f"effect scenario for {unit_id} must be an object",
            )
        if current_state is not None and not isinstance(current_state, Mapping):
            _fail(
                "TEVS_V31_SOURCE_EFFECT_STATE",
                f"current_state for {unit_id} must be an object or null",
            )
        normalized[unit_id] = {
            "scenario": dict(scenario),
            "current_state": None if current_state is None else dict(current_state),
        }
    return normalized


def _compile_unit(
    unit_id: str,
    profile: str,
    source: str,
    effect_input: Mapping[str, Any] | None,
) -> tuple[TotalCoreUnitV1, str]:
    if profile == "pure":
        compiled = compile_program_v2(source)
        if compiled.entry.function_kind != "pure":
            _fail(
                "TEVS_V31_SOURCE_UNIT_PROFILE",
                f"unit {unit_id} declared pure but child entry is {compiled.entry.function_kind}",
            )
        ir = export_program_ir_v4_pure(compiled)
        return TotalCoreUnitV1.build(unit_id, profile, ir), compiled.semantic_hash

    if profile == "recursive":
        compiled = compile_program_v2(source)
        if compiled.entry.function_kind != "recursive":
            _fail(
                "TEVS_V31_SOURCE_UNIT_PROFILE",
                f"unit {unit_id} declared recursive but child entry is {compiled.entry.function_kind}",
            )
        ir = export_program_ir_v4_recursive(compiled)
        return TotalCoreUnitV1.build(unit_id, profile, ir), compiled.semantic_hash

    if profile == "effects":
        if effect_input is None:
            _fail(
                "TEVS_V31_SOURCE_EFFECT_INPUT_REQUIRED",
                f"effects unit {unit_id} requires external effect input",
            )
        compiled = compile_effect_program_v2(source)
        ir = build_effect_program_ir_v4(
            compiled,
            effect_input["scenario"],
            current_state=effect_input.get("current_state"),
        )
        return TotalCoreUnitV1.build(unit_id, profile, ir), compiled.semantic_hash

    _fail("TEVS_V31_SOURCE_UNIT_PROFILE", f"unsupported unit profile {profile!r}")


def _convert_instruction(
    instruction: Any,
) -> TotalCoreInstructionV1:
    if instruction.kind == "halt":
        return TotalCoreInstructionV1.halt()
    if instruction.kind == "jump":
        return TotalCoreInstructionV1.jump(instruction.target_pc)
    if instruction.kind == "apply":
        return TotalCoreInstructionV1.apply(
            instruction.transformation_hash,
            next_pc=instruction.next_pc,
        )
    if instruction.kind == "branch_fact":
        return TotalCoreInstructionV1.branch_fact(
            instruction.fact_hash,
            present_pc=instruction.present_pc,
            absent_pc=instruction.absent_pc,
        )
    _fail(
        "TEVS_V31_SOURCE_V3_INSTRUCTION",
        f"unexpected V3 instruction kind {instruction.kind!r}",
    )


def compile_total_core_v31(
    process_source: str,
    *,
    unit_sources: Mapping[str, str],
    effect_inputs: Mapping[str, Mapping[str, Any]] | None = None,
    proof_admissions: Sequence[VerifiedProofAdmissionV1] = (),
) -> TotalCoreProgramV1:
    translated_source, declared_units, invokes = _normalize_process_source(process_source)
    sources = _validate_source_mapping(declared_units, unit_sources)
    effects = _validate_effect_inputs(declared_units, effect_inputs)

    v3_model = parse_semantic_process_v3(translated_source)
    v3_program = compile_semantic_process_v3(translated_source)
    labels = tuple(sorted(v3_model.labels, key=lambda item: item.name))
    pc = {label.name: index for index, label in enumerate(labels)}

    units: list[TotalCoreUnitV1] = []
    child_semantics: list[dict[str, str]] = []
    units_by_id: dict[str, TotalCoreUnitV1] = {}
    for unit_id, profile in declared_units:
        unit, child_semantic_hash = _compile_unit(
            unit_id,
            profile,
            sources[unit_id],
            effects.get(unit_id),
        )
        units.append(unit)
        units_by_id[unit_id] = unit
        child_semantics.append(
            {
                "unit_id": unit_id,
                "profile": profile,
                "child_source_semantic_hash": child_semantic_hash,
            }
        )

    for label_name, (unit_id, result_relation, next_label) in invokes.items():
        if label_name not in pc:
            _fail(
                "TEVS_V31_SOURCE_UNKNOWN_LABEL",
                f"invoke label {label_name} was not admitted by V3 process parser",
            )
        if unit_id not in units_by_id:
            _fail(
                "TEVS_V31_SOURCE_UNKNOWN_UNIT",
                f"invoke label {label_name} references unknown unit {unit_id}",
            )
        if _NAME.fullmatch(result_relation) is None:
            _fail(
                "TEVS_V31_SOURCE_RELATION",
                f"invoke label {label_name} has invalid result relation",
            )
        if next_label not in pc:
            _fail(
                "TEVS_V31_SOURCE_UNKNOWN_LABEL",
                f"invoke label {label_name} references unknown target {next_label}",
            )

    instructions: list[TotalCoreInstructionV1] = []
    for index, label in enumerate(labels):
        invoke = invokes.get(label.name)
        if invoke is not None:
            unit_id, result_relation, next_label = invoke
            instructions.append(
                TotalCoreInstructionV1.invoke_v4(
                    unit_hash=units_by_id[unit_id].unit_hash,
                    result_relation=result_relation,
                    next_pc=pc[next_label],
                )
            )
        else:
            instructions.append(_convert_instruction(v3_program.instructions[index]))

    source_semantic_hash = canonical_hash(
        {
            "schema": SOURCE_MODEL_SCHEMA_V31,
            "language_version": LANGUAGE_VERSION_V31,
            "v3_process_semantic_hash": v3_program.source_semantic_hash,
            "units": sorted(
                child_semantics,
                key=lambda item: (item["unit_id"], item["profile"]),
            ),
            "invoke_v4": [
                {
                    "label": label_name,
                    "unit_id": unit_id,
                    "result_relation": result_relation,
                    "next_label": next_label,
                }
                for label_name, (unit_id, result_relation, next_label)
                in sorted(invokes.items())
            ],
        }
    )

    return TotalCoreProgramV1.build(
        program_id=v3_program.program_id,
        source_semantic_hash=source_semantic_hash,
        initial_field=v3_program.initial_field,
        transformations=v3_program.transformations,
        v4_units=tuple(units),
        proof_admissions=tuple(proof_admissions),
        instructions=tuple(instructions),
        entry_pc=v3_program.entry_pc,
        quantum_step_limit=v3_program.quantum_step_limit,
        authority_hash=v3_program.authority_hash,
    )


__all__ = [
    "LANGUAGE_VERSION_V31",
    "SOURCE_MODEL_SCHEMA_V31",
    "compile_total_core_v31",
]
