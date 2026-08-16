from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Sequence

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .omega_semantic_basis_v1 import FieldFactV1, field_fact, field_transformation, semantic_field
from .program_ir_v5_semantic import (
    SemanticProcessProgramV1,
    instruction_apply,
    instruction_branch_fact,
    instruction_halt,
    instruction_jump,
    semantic_process_program,
)

SOURCE_MODEL_SCHEMA = "TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE_MODEL_V1"
LANGUAGE_VERSION = "3.0.0"
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEADER = re.compile(r'^process\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s+version\s+"([^"]+)"$')
_AUTHORITY = re.compile(r"^authority\s+([0-9a-f]{64})$")
_QUANTUM = re.compile(r"^quantum_steps\s+([0-9]+)$")
_FACT = re.compile(r"^fact\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s*=\s*([A-Za-z_][A-Za-z0-9_.:/-]*)\s+(.+)$")
_FIELD = re.compile(r"^field\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s*=\s*(\[.*\])$")
_TRANSFORM = re.compile(
    r"^transform\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s+effects\s+([0-9a-f]{64})\s+"
    r"resources\s+([0-9a-f]{64})\s+remove\s+(\[.*?\])\s+add\s+(\[.*\])$"
)
_LABEL = re.compile(r"^label\s+([A-Za-z_][A-Za-z0-9_.:/-]*)\s*=\s*(.+)$")
_ENTRY = re.compile(r"^entry\s+([A-Za-z_][A-Za-z0-9_.:/-]*)$")


@dataclass(frozen=True, slots=True)
class SourceFactV3:
    name: str
    relation: str
    arguments: tuple[Any, ...]
    fact: FieldFactV1


@dataclass(frozen=True, slots=True)
class SourceTransformV3:
    name: str
    effect_set_hash: str
    resource_vector_hash: str
    remove_names: tuple[str, ...]
    add_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SourceLabelV3:
    name: str
    kind: str
    operands: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticProcessSourceV3:
    schema: str
    language_version: str
    program_id: str
    authority_hash: str
    quantum_step_limit: int
    facts: tuple[SourceFactV3, ...]
    field_profile: str
    field_fact_names: tuple[str, ...]
    transformations: tuple[SourceTransformV3, ...]
    labels: tuple[SourceLabelV3, ...]
    entry_label: str
    source_semantic_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _split_statements(source: str) -> tuple[str, ...]:
    if not isinstance(source, str):
        _fail("TEVS_V3_SOURCE_TYPE", "source must be text")
    cleaned_lines = [raw for raw in source.splitlines() if not raw.lstrip().startswith("#")]
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
                _fail("TEVS_V3_SOURCE_BRACKETS", "unbalanced ]")
            buf.append(ch)
        elif ch == ";" and square == 0:
            statement = " ".join("".join(buf).split())
            if statement:
                statements.append(statement)
            buf.clear()
        else:
            buf.append(ch)
    if in_string or square != 0:
        _fail("TEVS_V3_SOURCE_UNCLOSED", "unclosed string or array")
    if "".join(buf).strip():
        _fail("TEVS_V3_SOURCE_SEMICOLON", "every declaration must end with semicolon")
    return tuple(statements)


def _json_array(text: str, what: str) -> list[Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        _fail("TEVS_V3_SOURCE_JSON", f"invalid {what}: {error.msg}")
    if not isinstance(value, list):
        _fail("TEVS_V3_SOURCE_JSON", f"{what} must be JSON array")
    return value


def _bare_name_list(text: str, what: str) -> tuple[str, ...]:
    value = text.strip()
    if not (value.startswith("[") and value.endswith("]")):
        _fail("TEVS_V3_SOURCE_NAME_LIST", f"{what} must be [name,...]")
    inner = value[1:-1].strip()
    if not inner:
        return ()
    names = tuple(part.strip() for part in inner.split(","))
    if any(_NAME.fullmatch(name) is None for name in names):
        _fail("TEVS_V3_SOURCE_NAME_LIST", f"invalid symbolic name in {what}")
    if len(set(names)) != len(names):
        _fail("TEVS_V3_SOURCE_DUPLICATE_REF", f"{what} contains duplicate name")
    return tuple(sorted(names))


def _label_body(name: str, body: str) -> SourceLabelV3:
    parts = body.split()
    if not parts:
        _fail("TEVS_V3_SOURCE_LABEL", f"empty label {name}")
    kind = parts[0]
    expected_arity = {"halt": 0, "jump": 1, "apply": 2, "branch_fact": 3}.get(kind)
    if expected_arity is None or len(parts) - 1 != expected_arity:
        _fail("TEVS_V3_SOURCE_LABEL", f"invalid {kind!r} label body")
    operands = tuple(parts[1:])
    if any(_NAME.fullmatch(item) is None for item in operands):
        _fail("TEVS_V3_SOURCE_LABEL", "label operands must be stable names")
    return SourceLabelV3(name, kind, operands)


def _source_model_object(
    *, program_id: str, authority_hash: str, quantum_step_limit: int,
    facts: Sequence[SourceFactV3], field_profile: str, field_fact_names: Sequence[str],
    transformations: Sequence[SourceTransformV3], labels: Sequence[SourceLabelV3],
    entry_label: str,
) -> dict[str, Any]:
    return {
        "schema": SOURCE_MODEL_SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "program_id": program_id,
        "authority_hash": authority_hash,
        "quantum_step_limit": quantum_step_limit,
        "facts": [
            {"name": row.name, "relation": row.relation, "arguments": list(row.arguments)}
            for row in sorted(facts, key=lambda row: row.name)
        ],
        "field": {"profile": field_profile, "fact_names": list(sorted(field_fact_names))},
        "transformations": [
            {
                "name": row.name,
                "effect_set_hash": row.effect_set_hash,
                "resource_vector_hash": row.resource_vector_hash,
                "remove_names": list(row.remove_names),
                "add_names": list(row.add_names),
            }
            for row in sorted(transformations, key=lambda row: row.name)
        ],
        "labels": [
            {"name": row.name, "kind": row.kind, "operands": list(row.operands)}
            for row in sorted(labels, key=lambda row: row.name)
        ],
        "entry_label": entry_label,
    }


def parse_semantic_process_v3(source: str) -> SemanticProcessSourceV3:
    statements = _split_statements(source)
    program_id: str | None = None
    authority_hash: str | None = None
    quantum_step_limit: int | None = None
    fact_rows: dict[str, SourceFactV3] = {}
    field_profile: str | None = None
    field_names: tuple[str, ...] | None = None
    transforms: dict[str, SourceTransformV3] = {}
    labels: dict[str, SourceLabelV3] = {}
    entry_label: str | None = None

    for statement in statements:
        if match := _HEADER.fullmatch(statement):
            if program_id is not None:
                _fail("TEVS_V3_SOURCE_DUPLICATE", "duplicate process header")
            program_id, version = match.groups()
            if version != LANGUAGE_VERSION:
                _fail("TEVS_V3_SOURCE_VERSION", f"semantic_process requires version {LANGUAGE_VERSION}")
            continue
        if match := _AUTHORITY.fullmatch(statement):
            if authority_hash is not None:
                _fail("TEVS_V3_SOURCE_DUPLICATE", "duplicate authority")
            authority_hash = match.group(1)
            continue
        if match := _QUANTUM.fullmatch(statement):
            if quantum_step_limit is not None:
                _fail("TEVS_V3_SOURCE_DUPLICATE", "duplicate quantum_steps")
            quantum_step_limit = int(match.group(1))
            if not 1 <= quantum_step_limit <= 1_000_000:
                _fail("TEVS_V3_SOURCE_QUANTUM", "quantum_steps outside 1..1000000")
            continue
        if match := _FACT.fullmatch(statement):
            name, relation, args_text = match.groups()
            if name in fact_rows:
                _fail("TEVS_V3_SOURCE_DUPLICATE", f"duplicate fact {name}")
            args = _json_array(args_text, "fact arguments")
            fact = field_fact(relation, args)
            fact_rows[name] = SourceFactV3(name, relation, fact.arguments, fact)
            continue
        if match := _FIELD.fullmatch(statement):
            if field_profile is not None:
                _fail("TEVS_V3_SOURCE_DUPLICATE", "duplicate field")
            field_profile, names_text = match.groups()
            field_names = _bare_name_list(names_text, "field fact list")
            continue
        if match := _TRANSFORM.fullmatch(statement):
            name, effects, resources, removes_text, adds_text = match.groups()
            if name in transforms:
                _fail("TEVS_V3_SOURCE_DUPLICATE", f"duplicate transform {name}")
            transforms[name] = SourceTransformV3(
                name, effects, resources,
                _bare_name_list(removes_text, "transform remove list"),
                _bare_name_list(adds_text, "transform add list"),
            )
            continue
        if match := _LABEL.fullmatch(statement):
            name, body = match.groups()
            if name in labels:
                _fail("TEVS_V3_SOURCE_DUPLICATE", f"duplicate label {name}")
            labels[name] = _label_body(name, body)
            continue
        if match := _ENTRY.fullmatch(statement):
            if entry_label is not None:
                _fail("TEVS_V3_SOURCE_DUPLICATE", "duplicate entry")
            entry_label = match.group(1)
            continue
        _fail("TEVS_V3_SOURCE_SYNTAX", f"unrecognized declaration: {statement!r}")

    if program_id is None or authority_hash is None or quantum_step_limit is None:
        _fail("TEVS_V3_SOURCE_REQUIRED", "process, authority and quantum_steps are required")
    if field_profile is None or field_names is None:
        _fail("TEVS_V3_SOURCE_REQUIRED", "exactly one field declaration is required")
    if entry_label is None or not labels:
        _fail("TEVS_V3_SOURCE_REQUIRED", "labels and entry are required")

    for name in field_names:
        if name not in fact_rows:
            _fail("TEVS_V3_SOURCE_UNKNOWN_FACT", f"field references unknown fact {name}")
    for tx in transforms.values():
        for name in (*tx.remove_names, *tx.add_names):
            if name not in fact_rows:
                _fail("TEVS_V3_SOURCE_UNKNOWN_FACT", f"transform {tx.name} references unknown fact {name}")
        if set(tx.remove_names).intersection(tx.add_names):
            _fail("TEVS_V3_SOURCE_TRANSFORM_COLLISION", f"transform {tx.name} removes and adds same fact")
    if entry_label not in labels:
        _fail("TEVS_V3_SOURCE_UNKNOWN_LABEL", f"entry references unknown label {entry_label}")
    for label in labels.values():
        if label.kind == "apply":
            tx_name, next_label = label.operands
            if tx_name not in transforms:
                _fail("TEVS_V3_SOURCE_UNKNOWN_TRANSFORM", f"label {label.name} references unknown transform {tx_name}")
            if next_label not in labels:
                _fail("TEVS_V3_SOURCE_UNKNOWN_LABEL", f"label {label.name} references unknown label {next_label}")
        elif label.kind == "branch_fact":
            fact_name, present, absent = label.operands
            if fact_name not in fact_rows:
                _fail("TEVS_V3_SOURCE_UNKNOWN_FACT", f"label {label.name} references unknown fact {fact_name}")
            for target in (present, absent):
                if target not in labels:
                    _fail("TEVS_V3_SOURCE_UNKNOWN_LABEL", f"label {label.name} references unknown label {target}")
        elif label.kind == "jump" and label.operands[0] not in labels:
            _fail("TEVS_V3_SOURCE_UNKNOWN_LABEL", f"label {label.name} references unknown label {label.operands[0]}")

    facts = tuple(sorted(fact_rows.values(), key=lambda row: row.name))
    txs = tuple(sorted(transforms.values(), key=lambda row: row.name))
    label_rows = tuple(sorted(labels.values(), key=lambda row: row.name))
    source_object = _source_model_object(
        program_id=program_id, authority_hash=authority_hash,
        quantum_step_limit=quantum_step_limit, facts=facts,
        field_profile=field_profile, field_fact_names=field_names,
        transformations=txs, labels=label_rows, entry_label=entry_label,
    )
    return SemanticProcessSourceV3(
        SOURCE_MODEL_SCHEMA, LANGUAGE_VERSION, program_id, authority_hash,
        quantum_step_limit, facts, field_profile, field_names, txs, label_rows,
        entry_label, canonical_hash(source_object),
    )


def compile_semantic_process_v3(source: str) -> SemanticProcessProgramV1:
    model = parse_semantic_process_v3(source)
    facts = {row.name: row.fact for row in model.facts}
    initial = semantic_field(tuple(facts[name] for name in model.field_fact_names), profile=model.field_profile)
    tx_by_name = {
        row.name: field_transformation(
            transformation_id=row.name,
            remove_fact_hashes=tuple(facts[name].fact_hash for name in row.remove_names),
            add_facts=tuple(facts[name] for name in row.add_names),
            effect_set_hash=row.effect_set_hash,
            resource_vector_hash=row.resource_vector_hash,
        )
        for row in model.transformations
    }
    labels = tuple(sorted(model.labels, key=lambda row: row.name))
    pc = {label.name: index for index, label in enumerate(labels)}
    instructions = []
    for label in labels:
        if label.kind == "halt":
            instructions.append(instruction_halt())
        elif label.kind == "jump":
            instructions.append(instruction_jump(pc[label.operands[0]]))
        elif label.kind == "apply":
            tx_name, next_label = label.operands
            instructions.append(instruction_apply(tx_by_name[tx_name].transformation_hash, next_pc=pc[next_label]))
        else:
            fact_name, present, absent = label.operands
            instructions.append(
                instruction_branch_fact(
                    facts[fact_name].fact_hash,
                    present_pc=pc[present],
                    absent_pc=pc[absent],
                )
            )
    return semantic_process_program(
        program_id=model.program_id,
        source_semantic_hash=model.source_semantic_hash,
        initial_field=initial,
        transformations=tuple(tx_by_name.values()),
        instructions=tuple(instructions),
        entry_pc=pc[model.entry_label],
        quantum_step_limit=model.quantum_step_limit,
        authority_hash=model.authority_hash,
    )


__all__ = [
    "LANGUAGE_VERSION",
    "SOURCE_MODEL_SCHEMA",
    "SemanticProcessSourceV3",
    "SourceFactV3",
    "SourceLabelV3",
    "SourceTransformV3",
    "compile_semantic_process_v3",
    "parse_semantic_process_v3",
]
