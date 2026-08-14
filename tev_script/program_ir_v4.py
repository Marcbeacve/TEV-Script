from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v4_pure import (
    PureBindingV4,
    TaskScopeExecutionStrategyV4,
    canonical_expression_v4,
    evaluate_pure_v4,
    hash_type_table_v4,
    validate_pure_v4,
)
from .ir_v4_recursive import RecursiveContractV4, evaluate_recursive_v4, validate_recursive_v4
from .ir_v4_effects import (
    CapabilityTableV4,
    EffectActionV4,
    EffectScenarioV4,
    StateSchemaV4,
    build_capability_table_v4,
    build_effect_action_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
    execute_effect_action_v4,
)
from .ir_v4_values import (
    TypeDescriptorV4,
    TypeTableV4,
    build_type_table_v4,
    decode_v4_value,
    encode_v4_value,
)

PROGRAM_IR_V4_PURE_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1"
PROGRAM_IR_V4_RUN_RECEIPT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_PURE_RUN_RECEIPT_V1"
PROGRAM_IR_V4_RECURSIVE_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1"
PROGRAM_IR_V4_RECURSIVE_RUN_RECEIPT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_RUN_RECEIPT_V1"
PROGRAM_IR_V4_EFFECTS_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1"
PROGRAM_IR_V4_EFFECTS_RUN_RECEIPT_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_RUN_RECEIPT_V1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ProgramIRV4PureValidation:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    body_expression_hash: str
    return_type: str
    static_step_upper_bound: int
    maximum_steps: int
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    argument_values: tuple[Any, ...]
    table: TypeTableV4
    body: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ProgramIRV4PureRunReceipt:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    body_expression_hash: str
    environment_hash: str
    evaluation_receipt_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    evaluation_steps: int
    static_step_upper_bound: int
    bounded_loop_iterations: int
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class ProgramIRV4RecursiveValidation:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    return_type: str
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    argument_values: tuple[Any, ...]
    contract: RecursiveContractV4
    table: TypeTableV4


@dataclass(frozen=True, slots=True)
class ProgramIRV4RecursiveRunReceipt:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    recursion_contract_hash: str
    evaluation_receipt_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    evaluation_steps: int
    recursion_calls: int
    maximum_observed_depth: int
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class ProgramIRV4EffectsValidation:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    state_schema_hash: str
    capability_table_hash: str
    action_hash: str
    scenario_hash: str
    current_state: dict[str, Any]
    arguments: tuple[Any, ...]
    table: TypeTableV4
    states: StateSchemaV4
    capabilities: CapabilityTableV4
    action: EffectActionV4
    scenario: EffectScenarioV4


@dataclass(frozen=True, slots=True)
class ProgramIRV4EffectsRunReceipt:
    schema: str
    program_ir_hash: str
    source_semantic_hash: str
    type_table_hash: str
    state_schema_hash: str
    capability_table_hash: str
    action_hash: str
    scenario_hash: str
    transition_receipt_hash: str
    initial_state_hash: str
    final_state: tuple[dict[str, Any], ...]
    final_state_hash: str
    capability_transcript_hash: str
    evaluation_steps: int
    observation_calls: int
    receipt_hash: str


def export_program_ir_v4_pure(compiled: Any) -> dict[str, Any]:
    """Export one compiled V2 pure entry as a self-contained portable IR V4 artifact."""

    if getattr(compiled, "schema", None) != "TEV_SCRIPT_COMPILED_PROGRAM_V2_V1":
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "export requires a compiled TEV Script V2 program")
    entry = getattr(compiled, "entry", None)
    if entry is None or getattr(entry, "function_kind", None) != "pure":
        _fail("TEVS_PROGRAM_IR_V4_PROFILE", "Program IR V4 Pure V1 exports pure entries only")
    from .generic_functions_v2 import GenericPureFunctionInstantiationV2
    instantiation = getattr(entry, "instantiation", None)
    if not isinstance(instantiation, GenericPureFunctionInstantiationV2):
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "pure entry does not carry a pure function instantiation")

    table = compiled.types.table
    type_table = {
        "boundary": {"maximum_value_nesting": table.maximum_value_nesting},
        "types": [_descriptor_wire(item) for item in sorted(table.descriptors, key=lambda item: item.type_id)],
    }
    type_table_hash = hash_type_table_v4(table)
    canonical_body = canonical_expression_v4(instantiation.body)
    validation = validate_pure_v4(
        canonical_body,
        table,
        dict(zip(instantiation.parameter_names, instantiation.parameter_type_ids, strict=True)),
    )
    if validation.expression_hash != instantiation.body_expression_hash:
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "compiled body hash diverges from canonical IR V4 body")
    if validation.result_type != instantiation.return_type_id:
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "compiled return type diverges from canonical IR V4 body")
    if validation.static_step_upper_bound != instantiation.static_step_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "compiled static step bound diverges from canonical IR V4 body")

    arguments = [
        {"name": name, "type": type_id, "value": encoded}
        for name, type_id, encoded in zip(
            instantiation.parameter_names,
            instantiation.parameter_type_ids,
            entry.argument_encodings,
            strict=True,
        )
    ]
    roots = tuple(sorted(instantiation.dependency_roots))
    payload: dict[str, Any] = {
        "schema": PROGRAM_IR_V4_PURE_SCHEMA,
        "source": {
            "program_id": compiled.program_id,
            "language_version": compiled.language_version,
            "semantic_hash": compiled.semantic_hash,
            "entry_hash": entry.entry_hash,
            "callable_id": instantiation.callable_id,
        },
        "profile": "pure",
        "type_table": type_table,
        "type_table_hash": type_table_hash,
        "entry": {
            "name": entry.name,
            "parameters": [
                {"name": name, "type": type_id}
                for name, type_id in zip(instantiation.parameter_names, instantiation.parameter_type_ids, strict=True)
            ],
            "return_type": instantiation.return_type_id,
            "body": canonical_body,
            "body_expression_hash": validation.expression_hash,
            "type_closure_roots": list(roots),
            "type_closure_hash": _type_closure_hash(table, roots),
            "static_step_upper_bound": validation.static_step_upper_bound,
            "maximum_steps": instantiation.maximum_steps,
            "arguments": arguments,
        },
    }
    payload["program_ir_hash"] = _hash(payload)
    validate_program_ir_v4_pure(payload)
    return payload


def validate_program_ir_v4_pure(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4PureValidation:
    root = _object(raw, "$")
    expected_root = {
        "schema", "source", "profile", "type_table", "type_table_hash", "entry", "program_ir_hash"
    }
    if set(root) != expected_root:
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"root field set mismatch: {sorted(set(root) ^ expected_root)}")
    if root["schema"] != PROGRAM_IR_V4_PURE_SCHEMA:
        _fail("TEVS_PROGRAM_IR_V4_SCHEMA", f"unsupported schema {root['schema']!r}")
    if root["profile"] != "pure":
        _fail("TEVS_PROGRAM_IR_V4_PROFILE", "Program IR V4 Pure V1 requires profile 'pure'")

    source = _object(root["source"], "$.source")
    if set(source) != {"program_id", "language_version", "semantic_hash", "entry_hash", "callable_id"}:
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "source field set mismatch")
    program_id = _string(source["program_id"], "$.source.program_id")
    language_version = _string(source["language_version"], "$.source.language_version")
    if language_version != "2.0.0":
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", f"expected source language version '2.0.0', got {language_version!r}")
    source_semantic_hash = _sha(source["semantic_hash"], "$.source.semantic_hash")
    _sha(source["entry_hash"], "$.source.entry_hash")
    _string(source["callable_id"], "$.source.callable_id")
    if not program_id:
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "program_id must be non-empty")

    type_table_raw = _object(root["type_table"], "$.type_table")
    if set(type_table_raw) != {"boundary", "types"}:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE", "type_table field set mismatch")
    boundary = _object(type_table_raw["boundary"], "$.type_table.boundary")
    if set(boundary) != {"maximum_value_nesting"}:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE", "type_table boundary field set mismatch")
    table = build_type_table_v4(type_table_raw)
    computed_type_table_hash = hash_type_table_v4(table)
    declared_type_table_hash = _sha(root["type_table_hash"], "$.type_table_hash")
    if declared_type_table_hash != computed_type_table_hash:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE_HASH", "type table hash mismatch")

    entry = _object(root["entry"], "$.entry")
    expected_entry = {
        "name", "parameters", "return_type", "body", "body_expression_hash",
        "type_closure_roots", "type_closure_hash", "static_step_upper_bound",
        "maximum_steps", "arguments",
    }
    if set(entry) != expected_entry:
        _fail("TEVS_PROGRAM_IR_V4_ENTRY", "entry field set mismatch")
    _string(entry["name"], "$.entry.name")
    return_type = _string(entry["return_type"], "$.entry.return_type")
    table.require(return_type, context="program IR entry return")

    raw_parameters = _array(entry["parameters"], "$.entry.parameters")
    parameter_names: list[str] = []
    parameter_types: list[str] = []
    for index, raw_parameter in enumerate(raw_parameters):
        item = _object(raw_parameter, f"$.entry.parameters[{index}]")
        if set(item) != {"name", "type"}:
            _fail("TEVS_PROGRAM_IR_V4_PARAMETERS", f"parameter {index} field set mismatch")
        name = _string(item["name"], f"$.entry.parameters[{index}].name")
        type_id = _string(item["type"], f"$.entry.parameters[{index}].type")
        if name in parameter_names:
            _fail("TEVS_PROGRAM_IR_V4_PARAMETERS", f"duplicate parameter {name!r}")
        table.require(type_id, context=f"program IR parameter {name}")
        parameter_names.append(name)
        parameter_types.append(type_id)

    body_raw = _object(entry["body"], "$.entry.body")
    canonical_body = canonical_expression_v4(body_raw)
    if canonical_body != body_raw:
        _fail("TEVS_PROGRAM_IR_V4_BODY_CANONICAL", "entry body is not canonical IR V4")
    pure_validation = validate_pure_v4(
        canonical_body,
        table,
        dict(zip(parameter_names, parameter_types, strict=True)),
    )
    declared_body_hash = _sha(entry["body_expression_hash"], "$.entry.body_expression_hash")
    if declared_body_hash != pure_validation.expression_hash:
        _fail("TEVS_PROGRAM_IR_V4_BODY_HASH", "body expression hash mismatch")
    if pure_validation.result_type != return_type:
        _fail("TEVS_PROGRAM_IR_V4_RETURN", f"body returns {pure_validation.result_type}, declared {return_type}")

    static_bound = _integer(entry["static_step_upper_bound"], "$.entry.static_step_upper_bound", 1, 1_000_000)
    if static_bound != pure_validation.static_step_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_STATIC_BOUND", "static step upper bound mismatch")
    maximum_steps = _integer(entry["maximum_steps"], "$.entry.maximum_steps", 1, 1_000_000)
    if maximum_steps < static_bound:
        _fail("TEVS_PROGRAM_IR_V4_BUDGET", "maximum_steps is below static step upper bound")

    roots_raw = _array(entry["type_closure_roots"], "$.entry.type_closure_roots")
    roots = tuple(_string(item, f"$.entry.type_closure_roots[{index}]") for index, item in enumerate(roots_raw))
    if roots != tuple(sorted(set(roots))) or not roots:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_CLOSURE", "type closure roots must be non-empty unique sorted ids")
    for type_id in roots:
        table.require(type_id, context="program IR type closure root")
    declared_closure_hash = _sha(entry["type_closure_hash"], "$.entry.type_closure_hash")
    computed_closure_hash = _type_closure_hash(table, roots)
    if declared_closure_hash != computed_closure_hash:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_CLOSURE_HASH", "type closure hash mismatch")

    required_roots = set(parameter_types)
    required_roots.add(return_type)
    if not required_roots.issubset(set(roots)):
        _fail("TEVS_PROGRAM_IR_V4_TYPE_CLOSURE", "type closure roots omit parameter or return types")

    raw_arguments = _array(entry["arguments"], "$.entry.arguments")
    if len(raw_arguments) != len(parameter_names):
        _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", f"expected {len(parameter_names)} arguments, got {len(raw_arguments)}")
    values: list[Any] = []
    for index, (raw_argument, name, type_id) in enumerate(zip(raw_arguments, parameter_names, parameter_types, strict=True)):
        item = _object(raw_argument, f"$.entry.arguments[{index}]")
        if set(item) != {"name", "type", "value"}:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", f"argument {index} field set mismatch")
        if item["name"] != name or item["type"] != type_id:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", f"argument {index} signature mismatch")
        value = decode_v4_value(type_id, item["value"], table, context=f"program IR argument {name}")
        recoded = encode_v4_value(type_id, value, table, context=f"program IR argument {name}")
        if recoded != item["value"]:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENT_CANONICAL", f"argument {name!r} is not canonically encoded")
        values.append(value)

    declared_program_hash = _sha(root["program_ir_hash"], "$.program_ir_hash")
    payload = dict(root)
    payload.pop("program_ir_hash")
    computed_program_hash = _hash(payload)
    if declared_program_hash != computed_program_hash:
        _fail("TEVS_PROGRAM_IR_V4_HASH", "program IR hash mismatch")
    if expected_program_ir_hash is not None:
        pinned_program_hash = _sha(expected_program_ir_hash, "expected_program_ir_hash")
        if computed_program_hash != pinned_program_hash:
            _fail("TEVS_PROGRAM_IR_V4_EXPECTED_HASH", "program IR does not match the externally pinned hash")
    if expected_source_semantic_hash is not None:
        pinned_source_hash = _sha(expected_source_semantic_hash, "expected_source_semantic_hash")
        if source_semantic_hash != pinned_source_hash:
            _fail("TEVS_PROGRAM_IR_V4_EXPECTED_SOURCE", "program IR source semantic hash does not match the external pin")

    return ProgramIRV4PureValidation(
        PROGRAM_IR_V4_PURE_SCHEMA,
        computed_program_hash,
        source_semantic_hash,
        computed_type_table_hash,
        pure_validation.expression_hash,
        return_type,
        pure_validation.static_step_upper_bound,
        maximum_steps,
        tuple(parameter_names),
        tuple(parameter_types),
        tuple(values),
        table,
        canonical_body,
    )


def run_program_ir_v4_pure(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> ProgramIRV4PureRunReceipt:
    validation = validate_program_ir_v4_pure(
        raw,
        expected_program_ir_hash=expected_program_ir_hash,
        expected_source_semantic_hash=expected_source_semantic_hash,
    )
    bindings = tuple(
        PureBindingV4(name, type_id, value)
        for name, type_id, value in zip(
            validation.parameter_names,
            validation.parameter_type_ids,
            validation.argument_values,
            strict=True,
        )
    )
    evaluation = evaluate_pure_v4(
        validation.body,
        validation.table,
        bindings,
        maximum_steps=validation.maximum_steps,
        task_strategy=task_strategy,
    )
    if evaluation.result_type != validation.return_type:
        _fail("TEVS_PROGRAM_IR_V4_RUNTIME_RETURN", "runtime result type diverged from validated return type")
    payload = {
        "schema": PROGRAM_IR_V4_RUN_RECEIPT_SCHEMA,
        "program_ir_hash": validation.program_ir_hash,
        "source_semantic_hash": validation.source_semantic_hash,
        "type_table_hash": validation.type_table_hash,
        "body_expression_hash": validation.body_expression_hash,
        "environment_hash": evaluation.environment_hash,
        "evaluation_receipt_hash": evaluation.receipt_hash,
        "result_type": evaluation.result_type,
        "result_encoded": evaluation.result_encoded,
        "result_hash": evaluation.result_hash,
        "evaluation_steps": evaluation.evaluation_steps,
        "static_step_upper_bound": evaluation.static_step_upper_bound,
        "bounded_loop_iterations": evaluation.bounded_loop_iterations,
    }
    return ProgramIRV4PureRunReceipt(
        payload["schema"],
        validation.program_ir_hash,
        validation.source_semantic_hash,
        validation.type_table_hash,
        validation.body_expression_hash,
        evaluation.environment_hash,
        evaluation.receipt_hash,
        evaluation.result_type,
        evaluation.result_encoded,
        evaluation.result_hash,
        evaluation.evaluation_steps,
        evaluation.static_step_upper_bound,
        evaluation.bounded_loop_iterations,
        _hash(payload),
    )



def export_program_ir_v4_recursive(compiled: Any) -> dict[str, Any]:
    if getattr(compiled, "schema", None) != "TEV_SCRIPT_COMPILED_PROGRAM_V2_V1":
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "export requires a compiled TEV Script V2 program")
    entry = getattr(compiled, "entry", None)
    if entry is None or getattr(entry, "function_kind", None) != "recursive":
        _fail("TEVS_PROGRAM_IR_V4_PROFILE", "Program IR V4 Recursive V1 exports recursive entries only")
    from .recursive_functions_v2 import RecursivePureFunctionInstantiationV2
    instantiation = getattr(entry, "instantiation", None)
    if not isinstance(instantiation, RecursivePureFunctionInstantiationV2):
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "recursive entry does not carry a recursive instantiation")
    table = compiled.types.table
    type_table = {
        "boundary": {"maximum_value_nesting": table.maximum_value_nesting},
        "types": [_descriptor_wire(item) for item in sorted(table.descriptors, key=lambda item: item.type_id)],
    }
    contract = validate_recursive_v4(
        instantiation.body,
        table,
        instantiation.parameter_names,
        instantiation.parameter_type_ids,
        instantiation.return_type_id,
        measure_parameter=instantiation.measure_parameter,
        max_depth=instantiation.max_depth,
        maximum_steps=instantiation.maximum_steps,
    )
    if contract.measure_index != instantiation.measure_index:
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "recursive measure index diverges from compiler instantiation")
    if contract.local_static_step_upper_bound != instantiation.local_static_step_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "recursive local bound diverges from compiler instantiation")
    if contract.recursive_static_step_upper_bound != instantiation.recursive_static_step_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_EXPORT", "recursive total bound diverges from compiler instantiation")
    roots = tuple(sorted(instantiation.dependency_roots))
    arguments = [
        {"name": name, "type": type_id, "value": encoded}
        for name, type_id, encoded in zip(
            instantiation.parameter_names,
            instantiation.parameter_type_ids,
            entry.argument_encodings,
            strict=True,
        )
    ]
    payload: dict[str, Any] = {
        "schema": PROGRAM_IR_V4_RECURSIVE_SCHEMA,
        "source": {
            "program_id": compiled.program_id,
            "language_version": compiled.language_version,
            "semantic_hash": compiled.semantic_hash,
            "entry_hash": entry.entry_hash,
            "callable_id": instantiation.callable_id,
        },
        "profile": "recursive",
        "type_table": type_table,
        "type_table_hash": hash_type_table_v4(table),
        "entry": {
            "name": entry.name,
            "parameters": [
                {"name": name, "type": type_id}
                for name, type_id in zip(instantiation.parameter_names, instantiation.parameter_type_ids, strict=True)
            ],
            "return_type": instantiation.return_type_id,
            "body": contract.body,
            "body_expression_hash": contract.body_expression_hash,
            "type_closure_roots": list(roots),
            "type_closure_hash": _type_closure_hash(table, roots),
            "recursion_contract": {
                "kind": "decreases_int",
                "measure_parameter": contract.measure_parameter,
                "measure_parameter_index": contract.measure_index,
                "measure_type": "Int",
                "max_depth": contract.max_depth,
                "single_static_self_call": True,
                "self_call_in_loops": False,
                "self_call_in_conditions": False,
                "local_static_step_upper_bound": contract.local_static_step_upper_bound,
                "recursive_static_step_upper_bound": contract.recursive_static_step_upper_bound,
                "maximum_steps": contract.maximum_steps,
                "contract_hash": contract.contract_hash,
            },
            "arguments": arguments,
        },
    }
    payload["program_ir_hash"] = _hash(payload)
    validate_program_ir_v4_recursive(payload)
    return payload


def validate_program_ir_v4_recursive(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4RecursiveValidation:
    root = _object(raw, "$")
    expected_root = {"schema", "source", "profile", "type_table", "type_table_hash", "entry", "program_ir_hash"}
    if set(root) != expected_root:
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"root field set mismatch: {sorted(set(root) ^ expected_root)}")
    if root["schema"] != PROGRAM_IR_V4_RECURSIVE_SCHEMA or root["profile"] != "recursive":
        _fail("TEVS_PROGRAM_IR_V4_PROFILE", "expected Program IR V4 Recursive V1")
    source = _object(root["source"], "$.source")
    if set(source) != {"program_id", "language_version", "semantic_hash", "entry_hash", "callable_id"}:
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "source field set mismatch")
    _string(source["program_id"], "$.source.program_id")
    if _string(source["language_version"], "$.source.language_version") != "2.0.0":
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "recursive source language version must be 2.0.0")
    source_semantic_hash = _sha(source["semantic_hash"], "$.source.semantic_hash")
    _sha(source["entry_hash"], "$.source.entry_hash")
    _string(source["callable_id"], "$.source.callable_id")

    type_table_raw = _object(root["type_table"], "$.type_table")
    if set(type_table_raw) != {"boundary", "types"}:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE", "type_table field set mismatch")
    table = build_type_table_v4(type_table_raw)
    computed_type_hash = hash_type_table_v4(table)
    if _sha(root["type_table_hash"], "$.type_table_hash") != computed_type_hash:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE_HASH", "type table hash mismatch")

    entry = _object(root["entry"], "$.entry")
    expected_entry = {
        "name", "parameters", "return_type", "body", "body_expression_hash",
        "type_closure_roots", "type_closure_hash", "recursion_contract", "arguments",
    }
    if set(entry) != expected_entry:
        _fail("TEVS_PROGRAM_IR_V4_ENTRY", "recursive entry field set mismatch")
    _string(entry["name"], "$.entry.name")
    return_type = _string(entry["return_type"], "$.entry.return_type")
    table.require(return_type, context="recursive program IR return")
    names: list[str] = []
    types: list[str] = []
    for index, raw_parameter in enumerate(_array(entry["parameters"], "$.entry.parameters")):
        item = _object(raw_parameter, f"$.entry.parameters[{index}]")
        if set(item) != {"name", "type"}:
            _fail("TEVS_PROGRAM_IR_V4_PARAMETERS", "recursive parameter field set mismatch")
        name = _string(item["name"], f"$.entry.parameters[{index}].name")
        type_id = _string(item["type"], f"$.entry.parameters[{index}].type")
        if name in names:
            _fail("TEVS_PROGRAM_IR_V4_PARAMETERS", f"duplicate parameter {name!r}")
        table.require(type_id, context=f"recursive program IR parameter {name}")
        names.append(name); types.append(type_id)

    rc = _object(entry["recursion_contract"], "$.entry.recursion_contract")
    expected_rc = {
        "kind", "measure_parameter", "measure_parameter_index", "measure_type", "max_depth",
        "single_static_self_call", "self_call_in_loops", "self_call_in_conditions",
        "local_static_step_upper_bound", "recursive_static_step_upper_bound", "maximum_steps", "contract_hash",
    }
    if set(rc) != expected_rc or rc["kind"] != "decreases_int" or rc["measure_type"] != "Int":
        _fail("TEVS_PROGRAM_IR_V4_RECURSION_CONTRACT", "invalid recursive contract shape/kind")
    if rc["single_static_self_call"] is not True or rc["self_call_in_loops"] is not False or rc["self_call_in_conditions"] is not False:
        _fail("TEVS_PROGRAM_IR_V4_RECURSION_CONTRACT", "recursive R1 invariant flags are invalid")
    measure_parameter = _string(rc["measure_parameter"], "$.entry.recursion_contract.measure_parameter")
    max_depth = _integer(rc["max_depth"], "$.entry.recursion_contract.max_depth", 1, 256)
    maximum_steps = _integer(rc["maximum_steps"], "$.entry.recursion_contract.maximum_steps", 1, 1_000_000)
    contract = validate_recursive_v4(
        _object(entry["body"], "$.entry.body"), table, names, types, return_type,
        measure_parameter=measure_parameter, max_depth=max_depth, maximum_steps=maximum_steps,
    )
    comparisons = (
        ("measure_parameter_index", contract.measure_index),
        ("local_static_step_upper_bound", contract.local_static_step_upper_bound),
        ("recursive_static_step_upper_bound", contract.recursive_static_step_upper_bound),
    )
    for field, expected in comparisons:
        if _integer(rc[field], f"$.entry.recursion_contract.{field}", 0 if field == "measure_parameter_index" else 1, 1_000_000) != expected:
            _fail("TEVS_PROGRAM_IR_V4_RECURSION_CONTRACT", f"recursive contract {field} mismatch")
    if _sha(rc["contract_hash"], "$.entry.recursion_contract.contract_hash") != contract.contract_hash:
        _fail("TEVS_PROGRAM_IR_V4_RECURSION_CONTRACT_HASH", "recursive contract hash mismatch")
    if _sha(entry["body_expression_hash"], "$.entry.body_expression_hash") != contract.body_expression_hash:
        _fail("TEVS_PROGRAM_IR_V4_BODY_HASH", "recursive body hash mismatch")

    roots = tuple(_string(item, f"$.entry.type_closure_roots[{i}]") for i, item in enumerate(_array(entry["type_closure_roots"], "$.entry.type_closure_roots")))
    if roots != tuple(sorted(set(roots))) or not roots:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_CLOSURE", "recursive type closure roots must be non-empty unique sorted ids")
    for type_id in roots: table.require(type_id, context="recursive program IR type closure root")
    if _sha(entry["type_closure_hash"], "$.entry.type_closure_hash") != _type_closure_hash(table, roots):
        _fail("TEVS_PROGRAM_IR_V4_TYPE_CLOSURE_HASH", "recursive type closure hash mismatch")
    required_roots = set(types); required_roots.add(return_type)
    if not required_roots.issubset(set(roots)):
        _fail("TEVS_PROGRAM_IR_V4_TYPE_CLOSURE", "recursive type closure omits signature types")

    raw_args = _array(entry["arguments"], "$.entry.arguments")
    if len(raw_args) != len(names):
        _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", "recursive argument count mismatch")
    values: list[Any] = []
    for index, (raw_arg, name, type_id) in enumerate(zip(raw_args, names, types, strict=True)):
        item = _object(raw_arg, f"$.entry.arguments[{index}]")
        if set(item) != {"name", "type", "value"} or item["name"] != name or item["type"] != type_id:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", f"recursive argument {index} signature mismatch")
        value = decode_v4_value(type_id, item["value"], table, context=f"recursive program IR argument {name}")
        if encode_v4_value(type_id, value, table, context=f"recursive program IR argument {name}") != item["value"]:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENT_CANONICAL", f"recursive argument {name!r} is not canonical")
        values.append(value)

    declared_hash = _sha(root["program_ir_hash"], "$.program_ir_hash")
    payload = dict(root); payload.pop("program_ir_hash")
    computed_hash = _hash(payload)
    if declared_hash != computed_hash:
        _fail("TEVS_PROGRAM_IR_V4_HASH", "recursive program IR hash mismatch")
    if expected_program_ir_hash is not None and computed_hash != _sha(expected_program_ir_hash, "expected_program_ir_hash"):
        _fail("TEVS_PROGRAM_IR_V4_EXPECTED_HASH", "recursive program IR does not match external hash pin")
    if expected_source_semantic_hash is not None and source_semantic_hash != _sha(expected_source_semantic_hash, "expected_source_semantic_hash"):
        _fail("TEVS_PROGRAM_IR_V4_EXPECTED_SOURCE", "recursive source semantic hash does not match external pin")
    return ProgramIRV4RecursiveValidation(
        PROGRAM_IR_V4_RECURSIVE_SCHEMA, computed_hash, source_semantic_hash, computed_type_hash,
        return_type, tuple(names), tuple(types), tuple(values), contract, table,
    )


def run_program_ir_v4_recursive(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4RecursiveRunReceipt:
    validation = validate_program_ir_v4_recursive(
        raw,
        expected_program_ir_hash=expected_program_ir_hash,
        expected_source_semantic_hash=expected_source_semantic_hash,
    )
    evaluation = evaluate_recursive_v4(validation.contract, validation.table, validation.argument_values)
    if evaluation.result_type != validation.return_type:
        _fail("TEVS_PROGRAM_IR_V4_RUNTIME_RETURN", "recursive runtime return type mismatch")
    payload = {
        "schema": PROGRAM_IR_V4_RECURSIVE_RUN_RECEIPT_SCHEMA,
        "program_ir_hash": validation.program_ir_hash,
        "source_semantic_hash": validation.source_semantic_hash,
        "type_table_hash": validation.type_table_hash,
        "recursion_contract_hash": validation.contract.contract_hash,
        "evaluation_receipt_hash": evaluation.receipt_hash,
        "result_type": evaluation.result_type,
        "result_encoded": evaluation.result_encoded,
        "result_hash": evaluation.result_hash,
        "evaluation_steps": evaluation.evaluation_steps,
        "recursion_calls": evaluation.recursion_calls,
        "maximum_observed_depth": evaluation.maximum_observed_depth,
    }
    return ProgramIRV4RecursiveRunReceipt(
        payload["schema"], validation.program_ir_hash, validation.source_semantic_hash,
        validation.type_table_hash, validation.contract.contract_hash, evaluation.receipt_hash,
        evaluation.result_type, evaluation.result_encoded, evaluation.result_hash,
        evaluation.evaluation_steps, evaluation.recursion_calls, evaluation.maximum_observed_depth,
        _hash(payload),
    )



def build_program_ir_v4_effects(
    *,
    program_id: str,
    source_semantic_hash: str,
    table: TypeTableV4,
    states: StateSchemaV4,
    capabilities: CapabilityTableV4,
    action: EffectActionV4,
    scenario: EffectScenarioV4,
    current_state: Mapping[str, Any],
    arguments: Sequence[Any] = (),
) -> dict[str, Any]:
    if not isinstance(program_id, str) or not program_id:
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "program_id must be non-empty")
    source_hash = _sha(source_semantic_hash, "source_semantic_hash")
    if action.state_schema_hash != states.schema_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", "action state schema hash mismatch")
    if action.capability_table_hash != capabilities.table_hash or scenario.capability_table_hash != capabilities.table_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_CAPABILITIES", "effects capability table hash mismatch")
    if len(arguments) != len(action.parameter_names):
        _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", f"effects action expects {len(action.parameter_names)} arguments, got {len(arguments)}")

    type_table = {
        "boundary": {"maximum_value_nesting": table.maximum_value_nesting},
        "types": [_descriptor_wire(item) for item in sorted(table.descriptors, key=lambda item: item.type_id)],
    }
    state_wire = [
        {"name": slot.name, "type": slot.type_id, "initial": slot.initial_encoded}
        for slot in states.slots
    ]
    capability_wire = [
        {
            "capability_id": contract.capability_id,
            "parameters": list(contract.parameter_type_ids),
            "return_type": contract.return_type_id,
            "kind": contract.kind,
            "contract_hash": contract.contract_hash,
        }
        for contract in capabilities.contracts
    ]
    action_wire = {
        "action_id": action.action_id,
        "parameters": [
            {"name": name, "type": type_id}
            for name, type_id in zip(action.parameter_names, action.parameter_type_ids, strict=True)
        ],
        "steps": [_effect_step_wire(step) for step in action.steps],
        "static_step_upper_bound": action.static_step_upper_bound,
        "observation_call_upper_bound": action.observation_call_upper_bound,
        "action_hash": action.action_hash,
    }
    scenario_wire = {
        "capability_table_hash": capabilities.table_hash,
        "capabilities": [
            {
                "capability_id": lane.capability_id,
                "contract_hash": lane.contract_hash,
                "calls": [
                    {"arguments": list(call.argument_encodings), "return": call.return_encoded}
                    for call in lane.calls
                ],
            }
            for lane in scenario.lanes
        ],
        "scenario_hash": scenario.scenario_hash,
    }
    current_wire = _effects_state_wire(states, current_state, table)
    argument_wire = []
    for name, type_id, value in zip(action.parameter_names, action.parameter_type_ids, arguments, strict=True):
        encoded = encode_v4_value(type_id, value, table, context=f"effects program IR argument {name}")
        decoded = decode_v4_value(type_id, encoded, table, context=f"effects program IR argument {name}")
        argument_wire.append({"name": name, "type": type_id, "value": encode_v4_value(type_id, decoded, table, context=f"effects program IR argument {name}")})

    payload: dict[str, Any] = {
        "schema": PROGRAM_IR_V4_EFFECTS_SCHEMA,
        "source": {
            "program_id": program_id,
            "language_version": "2.0.0",
            "semantic_hash": source_hash,
        },
        "profile": "effects",
        "type_table": type_table,
        "type_table_hash": hash_type_table_v4(table),
        "state_schema": {
            "states": state_wire,
            "schema_hash": states.schema_hash,
            "initial_state_hash": states.initial_state_hash,
        },
        "capabilities": {
            "contracts": capability_wire,
            "table_hash": capabilities.table_hash,
        },
        "action": action_wire,
        "scenario": scenario_wire,
        "execution": {
            "current_state": current_wire,
            "arguments": argument_wire,
        },
    }
    payload["program_ir_hash"] = _hash(payload)
    validate_program_ir_v4_effects(payload)
    return payload


def validate_program_ir_v4_effects(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4EffectsValidation:
    root = _object(raw, "$")
    expected_root = {
        "schema", "source", "profile", "type_table", "type_table_hash",
        "state_schema", "capabilities", "action", "scenario", "execution", "program_ir_hash",
    }
    if set(root) != expected_root:
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"effects root field set mismatch: {sorted(set(root) ^ expected_root)}")
    if root["schema"] != PROGRAM_IR_V4_EFFECTS_SCHEMA or root["profile"] != "effects":
        _fail("TEVS_PROGRAM_IR_V4_PROFILE", "expected Program IR V4 Effects V1")

    source = _object(root["source"], "$.source")
    if set(source) != {"program_id", "language_version", "semantic_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "effects source field set mismatch")
    _string(source["program_id"], "$.source.program_id")
    if _string(source["language_version"], "$.source.language_version") != "2.0.0":
        _fail("TEVS_PROGRAM_IR_V4_SOURCE", "effects source language version must be 2.0.0")
    source_hash = _sha(source["semantic_hash"], "$.source.semantic_hash")

    type_table_raw = _object(root["type_table"], "$.type_table")
    if set(type_table_raw) != {"boundary", "types"}:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE", "effects type_table field set mismatch")
    table = build_type_table_v4(type_table_raw)
    type_hash = hash_type_table_v4(table)
    if _sha(root["type_table_hash"], "$.type_table_hash") != type_hash:
        _fail("TEVS_PROGRAM_IR_V4_TYPE_TABLE_HASH", "effects type table hash mismatch")

    state_raw = _object(root["state_schema"], "$.state_schema")
    if set(state_raw) != {"states", "schema_hash", "initial_state_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", "effects state schema field set mismatch")
    raw_states = _array(state_raw["states"], "$.state_schema.states")
    states = build_state_schema_v4(raw_states, table)
    if _sha(state_raw["schema_hash"], "$.state_schema.schema_hash") != states.schema_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE_HASH", "effects state schema hash mismatch")
    if _sha(state_raw["initial_state_hash"], "$.state_schema.initial_state_hash") != states.initial_state_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_INITIAL_STATE_HASH", "effects initial state hash mismatch")

    capabilities_raw = _object(root["capabilities"], "$.capabilities")
    if set(capabilities_raw) != {"contracts", "table_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_CAPABILITIES", "effects capability table field set mismatch")
    raw_contracts = _array(capabilities_raw["contracts"], "$.capabilities.contracts")
    rebuild_contracts: list[dict[str, Any]] = []
    declared_contract_hashes: list[str] = []
    for index, raw_contract in enumerate(raw_contracts):
        item = _object(raw_contract, f"$.capabilities.contracts[{index}]")
        if set(item) != {"capability_id", "parameters", "return_type", "kind", "contract_hash"}:
            _fail("TEVS_PROGRAM_IR_V4_EFFECTS_CAPABILITIES", f"effects capability contract {index} field set mismatch")
        rebuild_contracts.append({
            "capability_id": item["capability_id"],
            "parameters": item["parameters"],
            "return_type": item["return_type"],
            "kind": item["kind"],
        })
        declared_contract_hashes.append(_sha(item["contract_hash"], f"$.capabilities.contracts[{index}].contract_hash"))
    capabilities = build_capability_table_v4(rebuild_contracts, table)
    if _sha(capabilities_raw["table_hash"], "$.capabilities.table_hash") != capabilities.table_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_CAPABILITY_TABLE_HASH", "effects capability table hash mismatch")
    if tuple(declared_contract_hashes) != tuple(contract.contract_hash for contract in capabilities.contracts):
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_CAPABILITY_CONTRACT_HASH", "effects capability contract hash mismatch")

    action_raw = _object(root["action"], "$.action")
    if set(action_raw) != {"action_id", "parameters", "steps", "static_step_upper_bound", "observation_call_upper_bound", "action_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_ACTION", "effects action field set mismatch")
    action = build_effect_action_v4(
        {"action_id": action_raw["action_id"], "parameters": action_raw["parameters"], "steps": action_raw["steps"]},
        table, states, capabilities,
    )
    if _integer(action_raw["static_step_upper_bound"], "$.action.static_step_upper_bound", 1, 1_000_000) != action.static_step_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_ACTION_BOUND", "effects action static bound mismatch")
    declared_obs_bound = action_raw["observation_call_upper_bound"]
    if isinstance(declared_obs_bound, bool) or not isinstance(declared_obs_bound, int) or declared_obs_bound < 0 or declared_obs_bound > 8192:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_ACTION_BOUND", "effects observation bound is invalid")
    if declared_obs_bound != action.observation_call_upper_bound:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_ACTION_BOUND", "effects observation bound mismatch")
    if _sha(action_raw["action_hash"], "$.action.action_hash") != action.action_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_ACTION_HASH", "effects action hash mismatch")

    scenario_raw = _object(root["scenario"], "$.scenario")
    if set(scenario_raw) != {"capability_table_hash", "capabilities", "scenario_hash"}:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_SCENARIO", "effects scenario field set mismatch")
    scenario = build_effect_scenario_v4(
        {"capability_table_hash": scenario_raw["capability_table_hash"], "capabilities": scenario_raw["capabilities"]},
        table, capabilities,
    )
    if _sha(scenario_raw["scenario_hash"], "$.scenario.scenario_hash") != scenario.scenario_hash:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_SCENARIO_HASH", "effects scenario hash mismatch")

    execution = _object(root["execution"], "$.execution")
    if set(execution) != {"current_state", "arguments"}:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_EXECUTION", "effects execution field set mismatch")
    current_state = _decode_effects_state_wire(states, _array(execution["current_state"], "$.execution.current_state"), table)
    raw_arguments = _array(execution["arguments"], "$.execution.arguments")
    if len(raw_arguments) != len(action.parameter_names):
        _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", "effects argument count mismatch")
    arguments: list[Any] = []
    for index, (raw_arg, name, type_id) in enumerate(zip(raw_arguments, action.parameter_names, action.parameter_type_ids, strict=True)):
        item = _object(raw_arg, f"$.execution.arguments[{index}]")
        if set(item) != {"name", "type", "value"} or item["name"] != name or item["type"] != type_id:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENTS", f"effects argument {index} signature mismatch")
        value = decode_v4_value(type_id, item["value"], table, context=f"effects program IR argument {name}")
        if encode_v4_value(type_id, value, table, context=f"effects program IR argument {name}") != item["value"]:
            _fail("TEVS_PROGRAM_IR_V4_ARGUMENT_CANONICAL", f"effects argument {name!r} is not canonical")
        arguments.append(value)

    declared_hash = _sha(root["program_ir_hash"], "$.program_ir_hash")
    payload = dict(root); payload.pop("program_ir_hash")
    computed_hash = _hash(payload)
    if declared_hash != computed_hash:
        _fail("TEVS_PROGRAM_IR_V4_HASH", "effects program IR hash mismatch")
    if expected_program_ir_hash is not None and computed_hash != _sha(expected_program_ir_hash, "expected_program_ir_hash"):
        _fail("TEVS_PROGRAM_IR_V4_EXPECTED_HASH", "effects program IR does not match external hash pin")
    if expected_source_semantic_hash is not None and source_hash != _sha(expected_source_semantic_hash, "expected_source_semantic_hash"):
        _fail("TEVS_PROGRAM_IR_V4_EXPECTED_SOURCE", "effects source semantic hash does not match external pin")

    return ProgramIRV4EffectsValidation(
        PROGRAM_IR_V4_EFFECTS_SCHEMA, computed_hash, source_hash, type_hash,
        states.schema_hash, capabilities.table_hash, action.action_hash, scenario.scenario_hash,
        current_state, tuple(arguments), table, states, capabilities, action, scenario,
    )


def run_program_ir_v4_effects(
    raw: Mapping[str, Any],
    *,
    expected_program_ir_hash: str | None = None,
    expected_source_semantic_hash: str | None = None,
) -> ProgramIRV4EffectsRunReceipt:
    validation = validate_program_ir_v4_effects(
        raw,
        expected_program_ir_hash=expected_program_ir_hash,
        expected_source_semantic_hash=expected_source_semantic_hash,
    )
    transition = execute_effect_action_v4(
        validation.action, validation.table, validation.states, validation.capabilities,
        validation.scenario, validation.current_state, validation.arguments,
    )
    payload = {
        "schema": PROGRAM_IR_V4_EFFECTS_RUN_RECEIPT_SCHEMA,
        "program_ir_hash": validation.program_ir_hash,
        "source_semantic_hash": validation.source_semantic_hash,
        "type_table_hash": validation.type_table_hash,
        "state_schema_hash": validation.state_schema_hash,
        "capability_table_hash": validation.capability_table_hash,
        "action_hash": validation.action_hash,
        "scenario_hash": validation.scenario_hash,
        "transition_receipt_hash": transition.receipt_hash,
        "initial_state_hash": transition.initial_state_hash,
        "final_state": list(transition.final_state),
        "final_state_hash": transition.final_state_hash,
        "capability_transcript_hash": transition.capability_transcript_hash,
        "evaluation_steps": transition.evaluation_steps,
        "observation_calls": transition.observation_calls,
    }
    return ProgramIRV4EffectsRunReceipt(
        payload["schema"], validation.program_ir_hash, validation.source_semantic_hash,
        validation.type_table_hash, validation.state_schema_hash, validation.capability_table_hash,
        validation.action_hash, validation.scenario_hash, transition.receipt_hash,
        transition.initial_state_hash, transition.final_state, transition.final_state_hash,
        transition.capability_transcript_hash, transition.evaluation_steps, transition.observation_calls,
        _hash(payload),
    )


def _effect_step_wire(step: Mapping[str, Any]) -> dict[str, Any]:
    op = step["op"]
    if op == "OBSERVE":
        return {"op": "OBSERVE", "capability_id": step["capability_id"], "arguments": step["arguments"], "bind": step["bind"]}
    if op == "OBSERVE_ALL":
        observations=[]
        for observation in step["observations"]:
            observations.append({"bind":observation["bind"],"capability_id":observation["capability_id"],"arguments":observation["arguments"]})
        return {"op":"OBSERVE_ALL","reservation_policy":step["reservation_policy"],"observations":observations}
    if op == "LET_LOCAL":
        return {"op": "LET_LOCAL", "name": step["name"], "type": step["type"], "value": step["value"]}
    if op == "SET_STATE":
        return {"op": "SET_STATE", "state": step["state"], "value": step["value"]}
    if op == "ASSERT":
        return {"op": "ASSERT", "condition": step["condition"]}
    _fail("TEVS_PROGRAM_IR_V4_EFFECTS_ACTION", f"unsupported normalized effects op {op!r}")


def _effects_state_wire(states: StateSchemaV4, state: Mapping[str, Any], table: TypeTableV4) -> list[dict[str, Any]]:
    if not isinstance(state, Mapping):
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", "effects current_state must be a mapping")
    expected = {slot.name for slot in states.slots}
    if set(state) != expected:
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", f"effects current state keys mismatch: {sorted(set(state) ^ expected)}")
    return [
        {"name": slot.name, "type": slot.type_id, "value": encode_v4_value(slot.type_id, state[slot.name], table, context=f"effects current state {slot.name}")}
        for slot in states.slots
    ]


def _decode_effects_state_wire(states: StateSchemaV4, raw: Sequence[Any], table: TypeTableV4) -> dict[str, Any]:
    if len(raw) != len(states.slots):
        _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", "effects current state length mismatch")
    result: dict[str, Any] = {}
    for index, (raw_slot, slot) in enumerate(zip(raw, states.slots, strict=True)):
        item = _object(raw_slot, f"$.execution.current_state[{index}]")
        if set(item) != {"name", "type", "value"} or item["name"] != slot.name or item["type"] != slot.type_id:
            _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", f"effects current state slot {index} signature/order mismatch")
        value = decode_v4_value(slot.type_id, item["value"], table, context=f"effects current state {slot.name}")
        if encode_v4_value(slot.type_id, value, table, context=f"effects current state {slot.name}") != item["value"]:
            _fail("TEVS_PROGRAM_IR_V4_EFFECTS_STATE", f"effects current state {slot.name!r} is noncanonical")
        result[slot.name] = value
    return result

def validate_program_ir_v4(raw: Mapping[str, Any], **pins: Any) -> ProgramIRV4PureValidation | ProgramIRV4RecursiveValidation | ProgramIRV4EffectsValidation:
    schema = raw.get("schema") if isinstance(raw, Mapping) else None
    if schema == PROGRAM_IR_V4_PURE_SCHEMA:
        return validate_program_ir_v4_pure(raw, **pins)
    if schema == PROGRAM_IR_V4_RECURSIVE_SCHEMA:
        return validate_program_ir_v4_recursive(raw, **pins)
    if schema == PROGRAM_IR_V4_EFFECTS_SCHEMA:
        return validate_program_ir_v4_effects(raw, **pins)
    _fail("TEVS_PROGRAM_IR_V4_SCHEMA", f"unsupported Program IR V4 schema {schema!r}")


def run_program_ir_v4(
    raw: Mapping[str, Any],
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
    **pins: Any,
) -> ProgramIRV4PureRunReceipt | ProgramIRV4RecursiveRunReceipt | ProgramIRV4EffectsRunReceipt:
    schema = raw.get("schema") if isinstance(raw, Mapping) else None
    if schema == PROGRAM_IR_V4_PURE_SCHEMA:
        return run_program_ir_v4_pure(raw, task_strategy=task_strategy, **pins)
    if task_strategy is not None:
        _fail("TEVS_PROGRAM_IR_V4_TASK_SCHEDULER_PROFILE", "physical task scheduling is supported only for Pure Program IR in R1")
    if schema == PROGRAM_IR_V4_RECURSIVE_SCHEMA:
        return run_program_ir_v4_recursive(raw, **pins)
    if schema == PROGRAM_IR_V4_EFFECTS_SCHEMA:
        return run_program_ir_v4_effects(raw, **pins)
    _fail("TEVS_PROGRAM_IR_V4_SCHEMA", f"unsupported Program IR V4 schema {schema!r}")

def canonical_program_ir_v4_bytes(raw: Mapping[str, Any]) -> bytes:
    validate_program_ir_v4(raw)
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _type_closure_hash(table: TypeTableV4, roots: Sequence[str]) -> str:
    closure: set[str] = set()
    stack = list(roots)
    while stack:
        type_id = stack.pop()
        if type_id in closure:
            continue
        descriptor = table.require(type_id, context="program IR type dependency")
        closure.add(type_id)
        stack.extend(_descriptor_children(descriptor))
    payload = {
        "schema": "TEV_SCRIPT_PROGRAM_IR_V4_TYPE_CLOSURE_V1",
        "types": [_descriptor_wire(table.require(type_id)) for type_id in sorted(closure)],
    }
    return _hash(payload)


def _descriptor_children(descriptor: TypeDescriptorV4) -> tuple[str, ...]:
    if descriptor.kind == "record": return tuple(type_id for _name, type_id in descriptor.fields)
    if descriptor.kind == "option": return (descriptor.argument,) if descriptor.argument is not None else ()
    if descriptor.kind == "result": return tuple(item for item in (descriptor.ok_type, descriptor.err_type) if item is not None)
    if descriptor.kind in {"list", "array", "set"}: return (descriptor.element_type,) if descriptor.element_type is not None else ()
    if descriptor.kind == "map": return tuple(item for item in (descriptor.key_type, descriptor.value_type) if item is not None)
    return ()


def _descriptor_wire(item: TypeDescriptorV4) -> dict[str, Any]:
    result: dict[str, Any] = {"type_id": item.type_id, "kind": item.kind}
    if item.kind == "record": result["fields"] = [{"name": name, "type": type_id} for name, type_id in item.fields]
    elif item.kind == "enum": result["variants"] = list(item.variants)
    elif item.kind == "option": result["argument"] = item.argument
    elif item.kind == "result": result.update({"ok_type": item.ok_type, "err_type": item.err_type})
    elif item.kind in {"list", "set"}: result.update({"element_type": item.element_type, "capacity": item.capacity, "order_policy": item.order_policy})
    elif item.kind == "array": result.update({"element_type": item.element_type, "length": item.length, "order_policy": item.order_policy})
    elif item.kind == "map": result.update({"key_type": item.key_type, "value_type": item.value_type, "capacity": item.capacity, "order_policy": item.order_policy})
    return result


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"{path} must be an object")
    return dict(value)


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"{path} must be an array")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"{path} must be a non-empty string")
    return value


def _sha(value: Any, path: str) -> str:
    text = _string(value, path)
    if _SHA256.fullmatch(text) is None:
        _fail("TEVS_PROGRAM_IR_V4_HASH_FORMAT", f"{path} must be lowercase sha256 hex")
    return text


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail("TEVS_PROGRAM_IR_V4_SHAPE", f"{path} must be integer {minimum}..{maximum}")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
