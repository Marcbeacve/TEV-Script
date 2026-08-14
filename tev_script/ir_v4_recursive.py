from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v4_pure import (
    MAX_PURE_EVAL_STEPS_V4,
    PureBindingV4,
    TypedValueV4,
    canonical_expression_v4,
    evaluate_pure_v4,
    hash_type_table_v4,
    validate_pure_v4,
)
from .ir_v4_values import TypeTableV4, decode_v4_value, encode_v4_value

MAX_RECURSION_DEPTH_V4 = 256
_SELF_RESULT = "__tev_self_result"
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class RecursiveContractV4:
    parameter_names: tuple[str, ...]
    parameter_type_ids: tuple[str, ...]
    return_type_id: str
    body: dict[str, Any]
    measure_parameter: str
    measure_index: int
    max_depth: int
    local_static_step_upper_bound: int
    recursive_static_step_upper_bound: int
    maximum_steps: int
    body_expression_hash: str
    contract_hash: str


@dataclass(frozen=True, slots=True)
class RecursiveEvaluationReceiptV4:
    schema: str
    contract_hash: str
    type_table_hash: str
    arguments_hash: str
    result_type: str
    result_encoded: Any
    result_hash: str
    evaluation_steps: int
    recursion_calls: int
    maximum_observed_depth: int
    max_depth: int
    local_static_step_upper_bound: int
    recursive_static_step_upper_bound: int
    receipt_hash: str


@dataclass(slots=True)
class _RuntimeStats:
    steps: int = 0
    recursion_calls: int = 0
    maximum_depth: int = 0


def validate_recursive_v4(
    body: Mapping[str, Any],
    table: TypeTableV4,
    parameter_names: Sequence[str],
    parameter_type_ids: Sequence[str],
    return_type_id: str,
    *,
    measure_parameter: str,
    max_depth: int,
    maximum_steps: int = 1_000_000,
) -> RecursiveContractV4:
    names = tuple(parameter_names)
    types = tuple(parameter_type_ids)
    if not 1 <= len(names) <= 64 or len(names) != len(types):
        _fail("TEVS_IR_V4_RECURSIVE_PARAMETERS", "recursive V4 requires 1..64 parameter names with matching types")
    if len(set(names)) != len(names) or any(_NAME.fullmatch(name) is None or name.startswith("__tev_") for name in names):
        _fail("TEVS_IR_V4_RECURSIVE_PARAMETERS", "recursive V4 parameter names must be unique, valid, and non-reserved")
    for name, type_id in zip(names, types, strict=True):
        table.require(type_id, context=f"recursive V4 parameter {name}")
    table.require(return_type_id, context="recursive V4 return type")
    if measure_parameter not in names:
        _fail("TEVS_IR_V4_RECURSIVE_MEASURE", f"measure parameter {measure_parameter!r} is not a parameter")
    measure_index = names.index(measure_parameter)
    if types[measure_index] != "Int":
        _fail("TEVS_IR_V4_RECURSIVE_MEASURE", f"decreases_int measure must be Int, got {types[measure_index]}")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 1 <= max_depth <= MAX_RECURSION_DEPTH_V4:
        _fail("TEVS_IR_V4_RECURSIVE_DEPTH", f"max_depth must be 1..{MAX_RECURSION_DEPTH_V4}")
    if isinstance(maximum_steps, bool) or not isinstance(maximum_steps, int) or not 1 <= maximum_steps <= MAX_PURE_EVAL_STEPS_V4:
        _fail("TEVS_IR_V4_RECURSIVE_BUDGET", f"maximum_steps must be 1..{MAX_PURE_EVAL_STEPS_V4}")

    canonical = canonical_expression_v4(body)
    analysis = _analyze_self_calls(canonical)
    if analysis["count"] != 1:
        _fail("TEVS_IR_V4_RECURSIVE_CALL_SITE", f"R1 requires exactly one static SELF_CALL site, got {analysis['count']}")
    if analysis["inside_loop"]:
        _fail("TEVS_IR_V4_RECURSIVE_LOOP", "SELF_CALL inside FOR_FOLD/WHILE_FOLD is forbidden")
    if analysis["inside_condition"]:
        _fail("TEVS_IR_V4_RECURSIVE_CONDITION", "SELF_CALL inside condition is forbidden")
    if analysis["nested_argument"]:
        _fail("TEVS_IR_V4_RECURSIVE_ARGUMENT", "SELF_CALL arguments cannot contain SELF_CALL")

    self_call = _single_self_call(canonical)
    raw_arguments = self_call.get("arguments")
    if not isinstance(raw_arguments, list) or len(raw_arguments) != len(types):
        _fail("TEVS_IR_V4_RECURSIVE_ARITY", f"SELF_CALL expects {len(types)} arguments")
    environment = dict(zip(names, types, strict=True))
    argument_validations = []
    for index, (argument_expr, expected_type) in enumerate(zip(raw_arguments, types, strict=True)):
        validation = validate_pure_v4(argument_expr, table, environment)
        if validation.result_type != expected_type:
            _fail("TEVS_IR_V4_RECURSIVE_TYPE", f"SELF_CALL argument {index} expected {expected_type}, got {validation.result_type}")
        argument_validations.append(validation)

    placeholder = _replace_self_call_with_placeholder(canonical, return_type_id)
    placeholder_environment = dict(environment)
    placeholder_environment[_SELF_RESULT] = return_type_id
    local_validation = validate_pure_v4(placeholder, table, placeholder_environment)
    if local_validation.result_type != return_type_id:
        _fail("TEVS_IR_V4_RECURSIVE_RETURN", f"recursive body returns {local_validation.result_type}, declared {return_type_id}")

    argument_bound = sum(item.static_step_upper_bound for item in argument_validations)
    frame_bound = 4 * (local_validation.static_step_upper_bound + argument_bound + 4)
    recursive_bound = frame_bound * (max_depth + 1)
    if recursive_bound > MAX_PURE_EVAL_STEPS_V4:
        _fail("TEVS_IR_V4_RECURSIVE_STATIC_BUDGET", f"recursive upper bound {recursive_bound} exceeds global {MAX_PURE_EVAL_STEPS_V4}")
    if recursive_bound > maximum_steps:
        _fail("TEVS_IR_V4_RECURSIVE_STATIC_BUDGET", f"recursive upper bound {recursive_bound} exceeds maximum_steps {maximum_steps}")

    body_hash = _hash(canonical)
    contract_payload = {
        "schema": "TEV_SCRIPT_IR_V4_RECURSIVE_CONTRACT_V1",
        "parameter_names": list(names),
        "parameter_type_ids": list(types),
        "return_type_id": return_type_id,
        "body_expression_hash": body_hash,
        "measure_parameter": measure_parameter,
        "measure_parameter_index": measure_index,
        "measure_type": "Int",
        "max_depth": max_depth,
        "single_static_self_call": True,
        "self_call_in_loops": False,
        "self_call_in_conditions": False,
        "local_static_step_upper_bound": local_validation.static_step_upper_bound,
        "recursive_static_step_upper_bound": recursive_bound,
        "maximum_steps": maximum_steps,
    }
    return RecursiveContractV4(
        names,
        types,
        return_type_id,
        canonical,
        measure_parameter,
        measure_index,
        max_depth,
        local_validation.static_step_upper_bound,
        recursive_bound,
        maximum_steps,
        body_hash,
        _hash(contract_payload),
    )


def evaluate_recursive_v4(
    contract: RecursiveContractV4,
    table: TypeTableV4,
    arguments: Sequence[Any],
) -> RecursiveEvaluationReceiptV4:
    if not isinstance(contract, RecursiveContractV4):
        _fail("TEVS_IR_V4_RECURSIVE_CALL", "evaluate requires RecursiveContractV4")
    if len(arguments) != len(contract.parameter_names):
        _fail("TEVS_IR_V4_RECURSIVE_CALL", f"expected {len(contract.parameter_names)} arguments, got {len(arguments)}")
    normalized: list[Any] = []
    argument_wire: list[dict[str, Any]] = []
    for name, type_id, raw in zip(contract.parameter_names, contract.parameter_type_ids, arguments, strict=True):
        encoded = encode_v4_value(type_id, raw, table, context=f"recursive V4 argument {name}")
        value = decode_v4_value(type_id, encoded, table, context=f"recursive V4 argument {name}")
        normalized.append(value)
        argument_wire.append({"name": name, "type": type_id, "value": encoded})
    initial_measure = normalized[contract.measure_index]
    _require_measure(initial_measure, context="initial recursion measure")
    arguments_hash = _hash({"schema": "TEV_SCRIPT_IR_V4_RECURSIVE_ARGUMENTS_V1", "arguments": argument_wire})
    stats = _RuntimeStats()
    result = _invoke(contract, table, tuple(normalized), depth=0, parent_measure=None, stats=stats)
    if stats.steps > contract.maximum_steps:
        _fail("TEVS_IR_V4_RECURSIVE_BUDGET", "runtime recursive step budget exceeded")
    encoded = encode_v4_value(contract.return_type_id, result.value, table, context="recursive V4 result")
    result_hash = _hash({"type": contract.return_type_id, "value": encoded})
    payload = {
        "schema": "TEV_SCRIPT_IR_V4_RECURSIVE_EVALUATION_RECEIPT_V1",
        "contract_hash": contract.contract_hash,
        "type_table_hash": hash_type_table_v4(table),
        "arguments_hash": arguments_hash,
        "result_type": contract.return_type_id,
        "result_encoded": encoded,
        "result_hash": result_hash,
        "evaluation_steps": stats.steps,
        "recursion_calls": stats.recursion_calls,
        "maximum_observed_depth": stats.maximum_depth,
        "max_depth": contract.max_depth,
        "local_static_step_upper_bound": contract.local_static_step_upper_bound,
        "recursive_static_step_upper_bound": contract.recursive_static_step_upper_bound,
    }
    return RecursiveEvaluationReceiptV4(
        payload["schema"], contract.contract_hash, payload["type_table_hash"], arguments_hash,
        contract.return_type_id, encoded, result_hash, stats.steps, stats.recursion_calls,
        stats.maximum_depth, contract.max_depth, contract.local_static_step_upper_bound,
        contract.recursive_static_step_upper_bound, _hash(payload),
    )


def _invoke(contract: RecursiveContractV4, table: TypeTableV4, arguments: tuple[Any, ...], *, depth: int, parent_measure: int | None, stats: _RuntimeStats) -> TypedValueV4:
    stats.maximum_depth = max(stats.maximum_depth, depth)
    measure = arguments[contract.measure_index]
    _require_measure(measure, context="recursive frame measure")
    if parent_measure is not None and not measure < parent_measure:
        _fail("TEVS_IR_V4_RECURSIVE_MEASURE_NOT_DECREASING", f"SELF_CALL measure must satisfy 0 <= next < current; got next={measure}, current={parent_measure}")
    environment = {
        name: TypedValueV4(type_id, value)
        for name, type_id, value in zip(contract.parameter_names, contract.parameter_type_ids, arguments, strict=True)
    }
    result = _evaluate_recursive_node(contract.body, contract, table, environment, current_measure=measure, depth=depth, stats=stats)
    if result.type_id != contract.return_type_id:
        _fail("TEVS_IR_V4_RECURSIVE_RETURN", "runtime recursive result type diverged from contract")
    return result


def _evaluate_recursive_node(node: Mapping[str, Any], contract: RecursiveContractV4, table: TypeTableV4, environment: Mapping[str, TypedValueV4], *, current_measure: int, depth: int, stats: _RuntimeStats) -> TypedValueV4:
    if not _contains_self_call(node):
        return _pure_eval(node, table, environment, contract, stats)
    op = str(node.get("op"))
    if op == "SELF_CALL":
        if depth >= contract.max_depth:
            _fail("TEVS_IR_V4_RECURSIVE_DEPTH_EXHAUSTED", f"SELF_CALL would exceed max_depth={contract.max_depth}")
        raw_arguments = node["arguments"]
        next_values = []
        for index, (argument_expr, expected_type) in enumerate(zip(raw_arguments, contract.parameter_type_ids, strict=True)):
            if _contains_self_call(argument_expr):
                _fail("TEVS_IR_V4_RECURSIVE_ARGUMENT", "nested SELF_CALL in recursive arguments is forbidden")
            value = _pure_eval(argument_expr, table, environment, contract, stats)
            if value.type_id != expected_type:
                _fail("TEVS_IR_V4_RECURSIVE_TYPE", f"SELF_CALL argument {index} expected {expected_type}, got {value.type_id}")
            next_values.append(value.value)
        next_measure = next_values[contract.measure_index]
        _require_measure(next_measure, context="SELF_CALL measure")
        if not next_measure < current_measure:
            _fail("TEVS_IR_V4_RECURSIVE_MEASURE_NOT_DECREASING", f"SELF_CALL measure must satisfy 0 <= next < current; got next={next_measure}, current={current_measure}")
        stats.steps += 1
        stats.recursion_calls += 1
        _check_runtime_budget(contract, stats)
        return _invoke(contract, table, tuple(next_values), depth=depth + 1, parent_measure=current_measure, stats=stats)
    if op == "IF":
        if _contains_self_call(node["condition"]):
            _fail("TEVS_IR_V4_RECURSIVE_CONDITION", "SELF_CALL in IF condition is forbidden")
        condition = _pure_eval(node["condition"], table, environment, contract, stats)
        if condition.type_id != "Bool":
            _fail("TEVS_IR_V4_RECURSIVE_TYPE", "recursive IF condition must be Bool")
        branch = node["then"] if condition.value else node["else"]
        return _evaluate_recursive_node(branch, contract, table, environment, current_measure=current_measure, depth=depth, stats=stats)
    if op == "LET":
        value = _evaluate_recursive_node(node["value"], contract, table, environment, current_measure=current_measure, depth=depth, stats=stats)
        declared = str(node["type"])
        if value.type_id != declared:
            _fail("TEVS_IR_V4_RECURSIVE_TYPE", f"recursive LET expected {declared}, got {value.type_id}")
        nested = dict(environment)
        nested[str(node["name"])] = value
        result = _evaluate_recursive_node(node["body"], contract, table, nested, current_measure=current_measure, depth=depth, stats=stats)
        if result.type_id != str(node["result_type"]):
            _fail("TEVS_IR_V4_RECURSIVE_TYPE", "recursive LET body result type mismatch")
        return result
    if op in {"FOR_FOLD", "WHILE_FOLD"}:
        _fail("TEVS_IR_V4_RECURSIVE_LOOP", "SELF_CALL inside loop is forbidden")
    materialized = _materialize_self_calls(node, contract, table, environment, current_measure=current_measure, depth=depth, stats=stats)
    return _pure_eval(materialized, table, environment, contract, stats)


def _materialize_self_calls(value: Any, contract: RecursiveContractV4, table: TypeTableV4, environment: Mapping[str, TypedValueV4], *, current_measure: int, depth: int, stats: _RuntimeStats) -> Any:
    if isinstance(value, Mapping) and value.get("op") == "SELF_CALL":
        result = _evaluate_recursive_node(value, contract, table, environment, current_measure=current_measure, depth=depth, stats=stats)
        return _const_node(result, table)
    if isinstance(value, Mapping) and value.get("op") in {"IF", "LET"} and _contains_self_call(value):
        result = _evaluate_recursive_node(value, contract, table, environment, current_measure=current_measure, depth=depth, stats=stats)
        return _const_node(result, table)
    if isinstance(value, Mapping):
        return {key: _materialize_self_calls(child, contract, table, environment, current_measure=current_measure, depth=depth, stats=stats) for key, child in value.items()}
    if isinstance(value, list):
        return [_materialize_self_calls(child, contract, table, environment, current_measure=current_measure, depth=depth, stats=stats) for child in value]
    return value


def _pure_eval(node: Mapping[str, Any], table: TypeTableV4, environment: Mapping[str, TypedValueV4], contract: RecursiveContractV4, stats: _RuntimeStats) -> TypedValueV4:
    if _contains_self_call(node):
        _fail("TEVS_IR_V4_RECURSIVE_INTERNAL", "unresolved SELF_CALL reached pure evaluator")
    bindings = [PureBindingV4(name, value.type_id, value.value) for name, value in sorted(environment.items())]
    validation = validate_pure_v4(node, table, {name: value.type_id for name, value in environment.items()})
    receipt = evaluate_pure_v4(node, table, bindings, maximum_steps=max(validation.static_step_upper_bound, 1))
    stats.steps += receipt.evaluation_steps
    _check_runtime_budget(contract, stats)
    return TypedValueV4(receipt.result_type, decode_v4_value(receipt.result_type, receipt.result_encoded, table, context="recursive V4 pure fragment"))


def _check_runtime_budget(contract: RecursiveContractV4, stats: _RuntimeStats) -> None:
    if stats.steps > contract.maximum_steps:
        _fail("TEVS_IR_V4_RECURSIVE_BUDGET", f"runtime recursive steps {stats.steps} exceed maximum_steps {contract.maximum_steps}")


def _analyze_self_calls(body: Mapping[str, Any]) -> dict[str, Any]:
    result = {"count": 0, "inside_loop": False, "inside_condition": False, "nested_argument": False}
    def visit(value: Any, *, in_loop: bool = False, in_condition: bool = False, in_self_argument: bool = False) -> None:
        if isinstance(value, Mapping):
            op = value.get("op")
            if op == "SELF_CALL":
                result["count"] += 1
                result["inside_loop"] = result["inside_loop"] or in_loop
                result["inside_condition"] = result["inside_condition"] or in_condition
                result["nested_argument"] = result["nested_argument"] or in_self_argument
                for argument in value.get("arguments", []): visit(argument, in_loop=in_loop, in_self_argument=True)
                return
            if op in {"FOR_FOLD", "WHILE_FOLD"}:
                for child in value.values(): visit(child, in_loop=True, in_self_argument=in_self_argument)
                return
            if op == "IF":
                visit(value.get("condition"), in_loop=in_loop, in_condition=True, in_self_argument=in_self_argument)
                visit(value.get("then"), in_loop=in_loop, in_self_argument=in_self_argument)
                visit(value.get("else"), in_loop=in_loop, in_self_argument=in_self_argument)
                return
            for child in value.values(): visit(child, in_loop=in_loop, in_condition=in_condition, in_self_argument=in_self_argument)
        elif isinstance(value, list):
            for child in value: visit(child, in_loop=in_loop, in_condition=in_condition, in_self_argument=in_self_argument)
    visit(body)
    return result


def _single_self_call(body: Mapping[str, Any]) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    def visit(value: Any) -> None:
        if isinstance(value, Mapping):
            if value.get("op") == "SELF_CALL": found.append(dict(value)); return
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(body)
    if len(found) != 1:
        _fail("TEVS_IR_V4_RECURSIVE_CALL_SITE", f"expected exactly one SELF_CALL, found {len(found)}")
    return found[0]


def _replace_self_call_with_placeholder(body: Mapping[str, Any], return_type: str) -> dict[str, Any]:
    def visit(value: Any) -> Any:
        if isinstance(value, Mapping):
            if value.get("op") == "SELF_CALL": return {"op": "PARAM", "name": _SELF_RESULT, "type": return_type}
            return {key: visit(child) for key, child in value.items()}
        if isinstance(value, list): return [visit(child) for child in value]
        return value
    result = visit(body)
    assert isinstance(result, dict)
    return canonical_expression_v4(result)


def _contains_self_call(value: Any) -> bool:
    if isinstance(value, Mapping): return value.get("op") == "SELF_CALL" or any(_contains_self_call(child) for child in value.values())
    if isinstance(value, list): return any(_contains_self_call(child) for child in value)
    return False


def _const_node(value: TypedValueV4, table: TypeTableV4) -> dict[str, Any]:
    return {"op": "CONST", "type": value.type_id, "value": encode_v4_value(value.type_id, value.value, table, context="recursive V4 materialization")}


def _require_measure(value: Any, *, context: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_IR_V4_RECURSIVE_MEASURE", f"{context} must be a non-negative Int, got {value!r}")


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
