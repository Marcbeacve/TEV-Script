from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .canonical import canonical_hash
from .contracts import (
    BOUNDARY_FLAGS,
    CAPABILITY_KINDS,
    IR_SCHEMA,
    LANGUAGE_VERSION,
    MAX_ARGUMENTS,
    MAX_ENTITIES,
    MAX_EVENT_CHAIN,
    MAX_HANDLERS_PER_ENTITY,
    MAX_INSTRUCTIONS_PER_HANDLER,
    MAX_LOCALS_PER_HANDLER,
    MAX_STATES_PER_ENTITY,
    TYPE_NAMES,
    VALUE_TYPE_NAMES,
)
from .diagnostics import TevScriptError
from .values import decode_typed_value

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STABLE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _fail(path: str, message: str, code: str = "TEVS_RUNTIME_IR_CONTRACT") -> None:
    raise TevScriptError(code, f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    if not all(isinstance(key, str) for key in value):
        _fail(path, "object keys must be strings")
    return value


def _array(value: Any, path: str, *, minimum: int = 0, maximum: int | None = None) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "expected an array")
    if len(value) < minimum:
        _fail(path, f"expected at least {minimum} items")
    if maximum is not None and len(value) > maximum:
        _fail(path, f"expected at most {maximum} items")
    return value


def _exact_keys(value: dict[str, Any], path: str, expected: set[str]) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        _fail(path, f"field set mismatch; missing={missing}, extra={extra}")


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        _fail(path, "expected an identifier")
    return value


def _stable_id(value: Any, path: str) -> str:
    if not isinstance(value, str) or _STABLE_ID.fullmatch(value) is None:
        _fail(path, "expected a stable identifier")
    return value


def _type_name(value: Any, path: str, *, allow_unit: bool = True) -> str:
    allowed = TYPE_NAMES if allow_unit else VALUE_TYPE_NAMES
    if value not in allowed:
        _fail(path, f"unsupported type {value!r}")
    return str(value)


def _integer(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "expected an integer")
    if value < minimum or value > maximum:
        _fail(path, f"integer must be in [{minimum}, {maximum}]")
    return value


def _hash(value: Any, path: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        _fail(path, "expected lowercase SHA-256 hexadecimal")
    return value


def _validate_typed_value(type_name: str, value: Any, path: str) -> None:
    try:
        decode_typed_value(type_name, value)
    except (TevScriptError, TypeError, ValueError, ZeroDivisionError) as error:
        _fail(path, f"invalid {type_name} value: {error}")


def _validate_parameter(raw: Any, path: str, *, allow_unit: bool) -> tuple[str, str]:
    item = _object(raw, path)
    _exact_keys(item, path, {"name", "type"})
    return (
        _identifier(item["name"], path + ".name"),
        _type_name(item["type"], path + ".type", allow_unit=allow_unit),
    )


def _validate_instruction(
    raw: Any,
    path: str,
    *,
    index: int,
    instruction_count: int,
    states: Mapping[str, str],
    parameters: Mapping[str, str],
    locals_: Mapping[str, str],
    capabilities: Mapping[str, tuple[tuple[str, ...], str, str]],
    events: Mapping[str, tuple[str, ...]],
) -> None:
    item = _object(raw, path)
    op = item.get("op")
    if not isinstance(op, str):
        _fail(path + ".op", "expected opcode string")

    if op == "CONST":
        _exact_keys(item, path, {"op", "type", "value"})
        type_name = _type_name(item["type"], path + ".type", allow_unit=False)
        _validate_typed_value(type_name, item["value"], path + ".value")
        return

    if op in {"LOAD_STATE", "STORE_STATE", "LOAD_LOCAL", "STORE_LOCAL", "LOAD_PARAM"}:
        _exact_keys(item, path, {"op", "name", "type"})
        name = _identifier(item["name"], path + ".name")
        type_name = _type_name(item["type"], path + ".type", allow_unit=False)
        namespace = (
            states if op in {"LOAD_STATE", "STORE_STATE"}
            else locals_ if op in {"LOAD_LOCAL", "STORE_LOCAL"}
            else parameters
        )
        if namespace.get(name) != type_name:
            _fail(path, f"{op} references unknown or mismatched name {name!r}")
        return

    if op == "CONVERT_INT_TO_RAT":
        _exact_keys(item, path, {"op"})
        return

    if op == "UNARY":
        _exact_keys(item, path, {"op", "operator", "type"})
        if item["operator"] not in {"NOT", "MINUS"}:
            _fail(path + ".operator", "unsupported unary operator")
        type_name = _type_name(item["type"], path + ".type", allow_unit=False)
        if item["operator"] == "NOT" and type_name != "Bool":
            _fail(path, "NOT must produce Bool")
        if item["operator"] == "MINUS" and type_name not in {"Int", "Rat"}:
            _fail(path, "MINUS must produce Int or Rat")
        return

    if op == "BINARY":
        _exact_keys(item, path, {"op", "operator", "left_type", "right_type", "result_type"})
        if item["operator"] not in {
            "AND", "OR", "EQEQ", "NE", "LT", "LE", "GT", "GE", "PLUS", "MINUS", "STAR", "SLASH"
        }:
            _fail(path + ".operator", "unsupported binary operator")
        for field in ("left_type", "right_type", "result_type"):
            _type_name(item[field], path + "." + field, allow_unit=False)
        return

    if op == "CALL_PURE":
        _exact_keys(item, path, {"op", "function_id", "argc", "return_type"})
        function_id = _stable_id(item["function_id"], path + ".function_id")
        argc = _integer(item["argc"], path + ".argc", minimum=0, maximum=MAX_ARGUMENTS)
        return_type = _type_name(item["return_type"], path + ".return_type")
        signatures = {
            "vec2": (2, "Vec2"),
            "vec3": (3, "Vec3"),
            "max": (2, return_type),
            "min": (2, return_type),
        }
        expected = signatures.get(function_id)
        if expected is None or expected != (argc, return_type):
            _fail(path, "pure function signature does not match the V0.2 contract")
        if function_id in {"max", "min"} and return_type not in {"Int", "Rat"}:
            _fail(path, "max/min return type must be Int or Rat")
        return

    if op == "CALL_CAPABILITY":
        _exact_keys(item, path, {"op", "capability_id", "argc", "return_type", "kind"})
        capability_id = _stable_id(item["capability_id"], path + ".capability_id")
        argc = _integer(item["argc"], path + ".argc", minimum=0, maximum=MAX_ARGUMENTS)
        return_type = _type_name(item["return_type"], path + ".return_type")
        kind = item["kind"]
        if kind not in CAPABILITY_KINDS:
            _fail(path + ".kind", "capability kind must be observation or effect")
        signature = capabilities.get(capability_id)
        if signature is None:
            _fail(path, f"capability instruction references undeclared capability {capability_id!r}")
        parameter_types, declared_return_type, declared_kind = signature
        if (
            len(parameter_types) != argc
            or declared_return_type != return_type
            or declared_kind != kind
        ):
            _fail(path, f"capability instruction does not match declaration {capability_id!r}")
        return

    if op == "EMIT_EVENT":
        _exact_keys(item, path, {"op", "event_id", "argc", "argument_types"})
        event_id = _identifier(item["event_id"], path + ".event_id")
        argc = _integer(item["argc"], path + ".argc", minimum=0, maximum=MAX_ARGUMENTS)
        argument_types = tuple(
            _type_name(value, f"{path}.argument_types[{position}]", allow_unit=False)
            for position, value in enumerate(
                _array(item["argument_types"], path + ".argument_types", maximum=MAX_ARGUMENTS)
            )
        )
        if len(argument_types) != argc or events.get(event_id) != argument_types:
            _fail(path, f"event instruction does not match declaration {event_id!r}")
        return

    if op in {"JUMP", "JUMP_IF_FALSE"}:
        _exact_keys(item, path, {"op", "target"})
        target = _integer(item["target"], path + ".target", minimum=0, maximum=instruction_count)
        if target <= index:
            _fail(path + ".target", "backward or self jumps are forbidden in V0.2")
        return

    if op == "RETURN":
        _exact_keys(item, path, {"op"})
        return

    _fail(path + ".op", f"unknown opcode {op!r}", "TEVS_RUNTIME_OPCODE")


def _validate_entity(raw: Any, path: str) -> str:
    item = _object(raw, path)
    _exact_keys(item, path, {"entity_id", "states", "handlers", "capabilities", "emitted_events"})
    entity_id = _identifier(item["entity_id"], path + ".entity_id")

    states: dict[str, str] = {}
    for index, raw_state in enumerate(
        _array(item["states"], path + ".states", maximum=MAX_STATES_PER_ENTITY)
    ):
        state_path = f"{path}.states[{index}]"
        state = _object(raw_state, state_path)
        _exact_keys(state, state_path, {"name", "type", "initial"})
        name = _identifier(state["name"], state_path + ".name")
        if name in states:
            _fail(state_path + ".name", f"duplicate state {name!r}")
        type_name = _type_name(state["type"], state_path + ".type", allow_unit=False)
        _validate_typed_value(type_name, state["initial"], state_path + ".initial")
        states[name] = type_name

    capabilities: dict[str, tuple[tuple[str, ...], str, str]] = {}
    for index, raw_capability in enumerate(_array(item["capabilities"], path + ".capabilities")):
        capability_path = f"{path}.capabilities[{index}]"
        capability = _object(raw_capability, capability_path)
        _exact_keys(capability, capability_path, {"capability_id", "parameters", "return_type", "kind"})
        capability_id = _stable_id(capability["capability_id"], capability_path + ".capability_id")
        if capability_id in capabilities:
            _fail(capability_path + ".capability_id", f"duplicate capability {capability_id!r}")
        parameters = tuple(
            _type_name(value, f"{capability_path}.parameters[{position}]", allow_unit=False)
            for position, value in enumerate(
                _array(capability["parameters"], capability_path + ".parameters", maximum=MAX_ARGUMENTS)
            )
        )
        return_type = _type_name(capability["return_type"], capability_path + ".return_type")
        kind = capability["kind"]
        if kind not in CAPABILITY_KINDS:
            _fail(capability_path + ".kind", "capability kind must be observation or effect")
        capabilities[capability_id] = (parameters, return_type, str(kind))

    events: dict[str, tuple[str, ...]] = {}
    for index, raw_event in enumerate(_array(item["emitted_events"], path + ".emitted_events")):
        event_path = f"{path}.emitted_events[{index}]"
        event = _object(raw_event, event_path)
        _exact_keys(event, event_path, {"event_id", "parameters"})
        event_id = _identifier(event["event_id"], event_path + ".event_id")
        if event_id in events:
            _fail(event_path + ".event_id", f"duplicate emitted event {event_id!r}")
        parameters = tuple(
            _type_name(value, f"{event_path}.parameters[{position}]", allow_unit=False)
            for position, value in enumerate(
                _array(event["parameters"], event_path + ".parameters", maximum=MAX_ARGUMENTS)
            )
        )
        events[event_id] = parameters

    handler_ids: set[str] = set()
    for handler_index, raw_handler in enumerate(
        _array(item["handlers"], path + ".handlers", maximum=MAX_HANDLERS_PER_ENTITY)
    ):
        handler_path = f"{path}.handlers[{handler_index}]"
        handler = _object(raw_handler, handler_path)
        _exact_keys(handler, handler_path, {"event_id", "parameters", "locals", "instructions", "instruction_budget"})
        event_id = _identifier(handler["event_id"], handler_path + ".event_id")
        if event_id in handler_ids:
            _fail(handler_path + ".event_id", f"duplicate handler {event_id!r}")
        handler_ids.add(event_id)

        parameters: dict[str, str] = {}
        for index, raw_parameter in enumerate(
            _array(handler["parameters"], handler_path + ".parameters", maximum=MAX_ARGUMENTS)
        ):
            name, type_name = _validate_parameter(raw_parameter, f"{handler_path}.parameters[{index}]", allow_unit=False)
            if name in parameters or name in states:
                _fail(f"{handler_path}.parameters[{index}].name", f"duplicate or state-shadowing parameter {name!r}")
            parameters[name] = type_name

        locals_: dict[str, str] = {}
        for index, raw_local in enumerate(
            _array(handler["locals"], handler_path + ".locals", maximum=MAX_LOCALS_PER_HANDLER)
        ):
            name, type_name = _validate_parameter(raw_local, f"{handler_path}.locals[{index}]", allow_unit=False)
            if name in locals_ or name in parameters or name in states:
                _fail(f"{handler_path}.locals[{index}].name", f"duplicate or shadowing local {name!r}")
            locals_[name] = type_name

        instructions = _array(
            handler["instructions"],
            handler_path + ".instructions",
            minimum=1,
            maximum=MAX_INSTRUCTIONS_PER_HANDLER,
        )
        budget = _integer(
            handler["instruction_budget"],
            handler_path + ".instruction_budget",
            minimum=1,
            maximum=MAX_INSTRUCTIONS_PER_HANDLER,
        )
        if len(instructions) > budget:
            _fail(handler_path + ".instruction_budget", "budget is smaller than instruction count")
        final_instruction = instructions[-1]
        if not isinstance(final_instruction, dict) or final_instruction.get("op") != "RETURN":
            _fail(handler_path + ".instructions", "handler must end in RETURN")
        for index, instruction in enumerate(instructions):
            _validate_instruction(
                instruction,
                f"{handler_path}.instructions[{index}]",
                index=index,
                instruction_count=len(instructions),
                states=states,
                parameters=parameters,
                locals_=locals_,
                capabilities=capabilities,
                events=events,
            )

    return entity_id


def validate_program_ir(ir: Any) -> None:
    root = _object(ir, "$")
    _exact_keys(
        root,
        "$",
        {"schema", "language_version", "program_id", "entities", "boundary", "semantic_hash", "debug", "debug_hash"},
    )
    if root["schema"] != IR_SCHEMA:
        _fail("$.schema", f"expected {IR_SCHEMA}", "TEVS_RUNTIME_SCHEMA")
    if root["language_version"] != LANGUAGE_VERSION:
        _fail("$.language_version", f"expected {LANGUAGE_VERSION}", "TEVS_RUNTIME_LANGUAGE_VERSION")
    _identifier(root["program_id"], "$.program_id")
    _hash(root["semantic_hash"], "$.semantic_hash")
    _hash(root["debug_hash"], "$.debug_hash")

    boundary = _object(root["boundary"], "$.boundary")
    _exact_keys(boundary, "$.boundary", set(BOUNDARY_FLAGS) | {"maximum_event_chain"})
    for flag in BOUNDARY_FLAGS:
        if boundary[flag] is not False:
            _fail(f"$.boundary.{flag}", "must be false", "TEVS_RUNTIME_BOUNDARY")
    _integer(
        boundary["maximum_event_chain"],
        "$.boundary.maximum_event_chain",
        minimum=1,
        maximum=MAX_EVENT_CHAIN,
    )

    debug = _object(root["debug"], "$.debug")
    try:
        observed_debug_hash = canonical_hash(debug)
    except (TypeError, ValueError) as error:
        _fail("$.debug", f"cannot canonicalize debug object: {error}")
    if observed_debug_hash != root["debug_hash"]:
        _fail("$.debug_hash", "debug hash does not match", "TEVS_RUNTIME_DEBUG_HASH")

    entity_ids: set[str] = set()
    for index, entity in enumerate(
        _array(root["entities"], "$.entities", minimum=1, maximum=MAX_ENTITIES)
    ):
        entity_id = _validate_entity(entity, f"$.entities[{index}]")
        if entity_id in entity_ids:
            _fail(f"$.entities[{index}].entity_id", f"duplicate entity {entity_id!r}")
        entity_ids.add(entity_id)

    semantic = {
        key: value
        for key, value in root.items()
        if key not in {"semantic_hash", "debug", "debug_hash"}
    }
    try:
        observed_semantic_hash = canonical_hash(semantic)
    except (TypeError, ValueError) as error:
        _fail("$", f"cannot canonicalize semantic program: {error}")
    if observed_semantic_hash != root["semantic_hash"]:
        _fail("$.semantic_hash", "program semantic hash does not match", "TEVS_RUNTIME_SEMANTIC_HASH")
