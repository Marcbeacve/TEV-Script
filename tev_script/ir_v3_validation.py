from __future__ import annotations

import re
from typing import Any, Mapping

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .ir_v3_flow import validate_entity_handler_flow_v3
from .ir_v3_values import TypeTableV3, build_type_table_v3, decode_v3_value

_HASH = re.compile(r"^[0-9a-f]{64}$")
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_ROOT_KEYS = {
    "schema", "language_version", "lowering_profile", "source_schema",
    "source_semantic_hash", "program_id", "types", "entities", "boundary",
    "semantic_hash", "debug", "debug_hash",
}
_BOUNDARY_KEYS = {
    "dynamic_code", "reflection", "unbounded_loops", "implicit_physical_effects",
    "runtime_source_compilation", "automatic_authority_escalation",
    "host_object_references", "maximum_event_chain", "maximum_value_nesting",
}


def validate_program_ir_v3(
    ir: Any,
    *,
    expected_source_semantic_hash: str | None = None,
) -> TypeTableV3:
    root = _object(ir, "$")
    _exact_keys(root, "$", _ROOT_KEYS)
    if root["schema"] != "TEV_SCRIPT_PROGRAM_IR_V3":
        _fail("$.schema", "expected TEV_SCRIPT_PROGRAM_IR_V3", "TEVS_IR_V3_SCHEMA")
    if root["language_version"] != "1.0.0":
        _fail("$.language_version", "expected 1.0.0", "TEVS_IR_V3_LANGUAGE_VERSION")

    source_schema = _string(root["source_schema"], "$.source_schema")
    profile = _string(root["lowering_profile"], "$.lowering_profile")
    expected_profile = {
        "TEV_SCRIPT_LINKED_PROGRAM_V1": "TEV_SCRIPT_V1_IR_V3_PROFILE_V1",
        "TEV_SCRIPT_PROGRAM_IR_V2": "TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1",
    }.get(source_schema)
    if expected_profile is None or profile != expected_profile:
        _fail(
            "$.lowering_profile",
            f"profile/source mismatch: {profile!r} / {source_schema!r}",
            "TEVS_IR_V3_LOWERING_PROFILE",
        )

    source_hash = _hash(root["source_semantic_hash"], "$.source_semantic_hash")
    if expected_source_semantic_hash is not None and source_hash != expected_source_semantic_hash:
        _fail(
            "$.source_semantic_hash",
            "source semantic hash does not match expected source artifact",
            "TEVS_IR_V3_SOURCE_HASH",
        )
    _local_name(root["program_id"], "$.program_id")
    _hash(root["semantic_hash"], "$.semantic_hash")
    _hash(root["debug_hash"], "$.debug_hash")

    boundary = _object(root["boundary"], "$.boundary")
    _exact_keys(boundary, "$.boundary", _BOUNDARY_KEYS)
    for flag in (
        "dynamic_code", "reflection", "unbounded_loops", "implicit_physical_effects",
        "runtime_source_compilation", "automatic_authority_escalation",
        "host_object_references",
    ):
        if boundary[flag] is not False:
            _fail(f"$.boundary.{flag}", "must be false", "TEVS_IR_V3_BOUNDARY")
    _integer(boundary["maximum_event_chain"], "$.boundary.maximum_event_chain", 1, 128)
    _integer(boundary["maximum_value_nesting"], "$.boundary.maximum_value_nesting", 1, 128)

    table = build_type_table_v3(root)
    entities = _array(root["entities"], "$.entities", 1, 128)
    entity_ids: set[str] = set()
    observed_entity_order: list[str] = []
    for entity_index, raw_entity in enumerate(entities):
        entity_id = _validate_entity(
            _object(raw_entity, f"$.entities[{entity_index}]"),
            table,
            f"$.entities[{entity_index}]",
        )
        if entity_id in entity_ids:
            _fail(f"$.entities[{entity_index}].entity_id", f"duplicate entity {entity_id!r}")
        entity_ids.add(entity_id)
        observed_entity_order.append(entity_id)
    if observed_entity_order != sorted(observed_entity_order):
        _fail("$.entities", "entities must be sorted lexically by entity_id")

    _validate_closed_type_table(root, table)

    debug = _object(root["debug"], "$.debug")
    try:
        debug_hash = canonical_hash(debug)
    except (TypeError, ValueError) as exc:
        _fail("$.debug", f"cannot canonicalize debug object: {exc}")
    if debug_hash != root["debug_hash"]:
        _fail("$.debug_hash", "debug hash mismatch", "TEVS_IR_V3_DEBUG_HASH")

    semantic = {
        key: value
        for key, value in root.items()
        if key not in {"semantic_hash", "debug", "debug_hash"}
    }
    try:
        semantic_hash = canonical_hash(semantic)
    except (TypeError, ValueError) as exc:
        _fail("$", f"cannot canonicalize semantic IR: {exc}")
    if semantic_hash != root["semantic_hash"]:
        _fail("$.semantic_hash", "semantic hash mismatch", "TEVS_IR_V3_SEMANTIC_HASH")
    return table


def _validate_entity(entity: dict[str, Any], table: TypeTableV3, path: str) -> str:
    _exact_keys(entity, path, {"entity_id", "states", "handlers", "capabilities", "emitted_events"})
    entity_id = _local_name(entity["entity_id"], path + ".entity_id")

    states: dict[str, str] = {}
    state_order: list[str] = []
    for index, raw_state in enumerate(_array(entity["states"], path + ".states", 0, 256)):
        state_path = f"{path}.states[{index}]"
        state = _object(raw_state, state_path)
        _exact_keys(state, state_path, {"name", "type", "initial"})
        name = _local_name(state["name"], state_path + ".name")
        if name in states:
            _fail(state_path + ".name", f"duplicate state {name!r}")
        type_id = _storable_type(table, state["type"], state_path + ".type")
        decode_v3_value(type_id, state["initial"], table, context=state_path + ".initial")
        states[name] = type_id
        state_order.append(name)
    if state_order != sorted(state_order):
        _fail(path + ".states", "states must be sorted lexically by name")

    capabilities: dict[str, tuple[tuple[str, ...], str, str]] = {}
    capability_order: list[str] = []
    for index, raw_capability in enumerate(_array(entity["capabilities"], path + ".capabilities", 0, 8192)):
        capability_path = f"{path}.capabilities[{index}]"
        capability = _object(raw_capability, capability_path)
        _exact_keys(capability, capability_path, {"capability_id", "parameters", "return_type", "kind"})
        capability_id = _stable_id(capability["capability_id"], capability_path + ".capability_id")
        if capability_id in capabilities:
            _fail(capability_path + ".capability_id", f"duplicate capability {capability_id!r}")
        parameters = tuple(
            _storable_type(table, value, f"{capability_path}.parameters[{position}]")
            for position, value in enumerate(_array(capability["parameters"], capability_path + ".parameters", 0, 64))
        )
        return_type = _string(capability["return_type"], capability_path + ".return_type")
        return_descriptor = table.require(return_type, context=capability_path + ".return_type")
        if return_descriptor.kind != "unit" and not table.is_storable(return_type):
            _fail(capability_path + ".return_type", f"invalid capability return {return_type!r}")
        kind = _string(capability["kind"], capability_path + ".kind")
        if kind not in {"observation", "effect"}:
            _fail(capability_path + ".kind", "kind must be observation or effect")
        capabilities[capability_id] = (parameters, return_type, kind)
        capability_order.append(capability_id)
    if capability_order != sorted(capability_order):
        _fail(path + ".capabilities", "capabilities must be sorted lexically by id")

    events: dict[str, tuple[str, ...]] = {}
    event_order: list[str] = []
    for index, raw_event in enumerate(_array(entity["emitted_events"], path + ".emitted_events", 0, 256)):
        event_path = f"{path}.emitted_events[{index}]"
        event = _object(raw_event, event_path)
        _exact_keys(event, event_path, {"event_id", "parameters"})
        event_id = _local_name(event["event_id"], event_path + ".event_id")
        if event_id in events:
            _fail(event_path + ".event_id", f"duplicate emitted event {event_id!r}")
        parameters = tuple(
            _storable_type(table, value, f"{event_path}.parameters[{position}]")
            for position, value in enumerate(_array(event["parameters"], event_path + ".parameters", 0, 64))
        )
        events[event_id] = parameters
        event_order.append(event_id)
    if event_order != sorted(event_order):
        _fail(path + ".emitted_events", "emitted events must be sorted lexically by id")

    handlers = _array(entity["handlers"], path + ".handlers", 0, 256)
    handler_ids: set[str] = set()
    handler_order: list[str] = []
    for index, raw_handler in enumerate(handlers):
        handler_path = f"{path}.handlers[{index}]"
        handler = _object(raw_handler, handler_path)
        _exact_keys(handler, handler_path, {"event_id", "parameters", "locals", "instructions", "instruction_budget"})
        event_id = _local_name(handler["event_id"], handler_path + ".event_id")
        if event_id in handler_ids:
            _fail(handler_path + ".event_id", f"duplicate handler {event_id!r}")
        handler_ids.add(event_id)
        handler_order.append(event_id)

        parameters: dict[str, str] = {}
        for position, raw_parameter in enumerate(_array(handler["parameters"], handler_path + ".parameters", 0, 64)):
            parameter_path = f"{handler_path}.parameters[{position}]"
            name, type_id = _typed_binding(raw_parameter, table, parameter_path)
            if name in parameters or name in states:
                _fail(parameter_path + ".name", f"duplicate/state-shadowing parameter {name!r}")
            parameters[name] = type_id

        locals_: dict[str, str] = {}
        local_order: list[str] = []
        for position, raw_local in enumerate(_array(handler["locals"], handler_path + ".locals", 0, 256)):
            local_path = f"{handler_path}.locals[{position}]"
            name, type_id = _typed_binding(raw_local, table, local_path)
            if name in locals_ or name in parameters or name in states:
                _fail(local_path + ".name", f"duplicate/shadowing local {name!r}")
            locals_[name] = type_id
            local_order.append(name)
        if local_order != sorted(local_order):
            _fail(handler_path + ".locals", "locals must be sorted lexically by name")

        instructions = _array(handler["instructions"], handler_path + ".instructions", 1, 8192)
        budget = _integer(handler["instruction_budget"], handler_path + ".instruction_budget", 1, 8192)
        if len(instructions) > budget:
            _fail(handler_path + ".instruction_budget", "budget smaller than instruction count")
        if not isinstance(instructions[-1], dict) or instructions[-1].get("op") != "RETURN":
            _fail(handler_path + ".instructions", "handler must end in RETURN")

        for pc, raw_instruction in enumerate(instructions):
            _validate_instruction_shape(
                _object(raw_instruction, f"{handler_path}.instructions[{pc}]"),
                table, states, parameters, locals_, capabilities, events,
                pc, len(instructions), f"{handler_path}.instructions[{pc}]",
            )
        validate_entity_handler_flow_v3(entity, handler, table, handler_path)

    if handler_order != sorted(handler_order):
        _fail(path + ".handlers", "handlers must be sorted lexically by event id")
    return entity_id


def _validate_instruction_shape(
    instruction: dict[str, Any], table: TypeTableV3,
    states: Mapping[str, str], parameters: Mapping[str, str], locals_: Mapping[str, str],
    capabilities: Mapping[str, tuple[tuple[str, ...], str, str]],
    events: Mapping[str, tuple[str, ...]], pc: int, count: int, path: str,
) -> None:
    op = _string(instruction.get("op"), path + ".op")
    if op == "CONST":
        _exact_keys(instruction, path, {"op", "type", "value"})
        type_id = _storable_type(table, instruction["type"], path + ".type")
        decode_v3_value(type_id, instruction["value"], table, context=path + ".value")
        return
    if op in {"LOAD_STATE", "STORE_STATE", "LOAD_LOCAL", "STORE_LOCAL", "LOAD_PARAM"}:
        _exact_keys(instruction, path, {"op", "name", "type"})
        name = _local_name(instruction["name"], path + ".name")
        type_id = _storable_type(table, instruction["type"], path + ".type")
        namespace = states if op in {"LOAD_STATE", "STORE_STATE"} else locals_ if op in {"LOAD_LOCAL", "STORE_LOCAL"} else parameters
        if namespace.get(name) != type_id:
            _fail(path, f"{op} references unknown/mismatched binding {name!r}")
        return
    if op == "CONVERT_INT_TO_RAT":
        _exact_keys(instruction, path, {"op"})
        return
    if op == "UNARY":
        _exact_keys(instruction, path, {"op", "operator", "type"})
        _string(instruction["operator"], path + ".operator")
        _storable_type(table, instruction["type"], path + ".type")
        return
    if op == "BINARY":
        _exact_keys(instruction, path, {"op", "operator", "left_type", "right_type", "result_type"})
        _string(instruction["operator"], path + ".operator")
        for key in ("left_type", "right_type", "result_type"):
            _storable_type(table, instruction[key], path + "." + key)
        return
    if op == "CALL_PURE":
        _exact_keys(instruction, path, {"op", "function_id", "argc", "return_type"})
        if instruction["function_id"] not in {"vec2", "vec3", "min", "max"}:
            _fail(path + ".function_id", "unsupported runtime pure intrinsic")
        _integer(instruction["argc"], path + ".argc", 0, 64)
        _storable_type(table, instruction["return_type"], path + ".return_type")
        return
    if op == "CALL_CAPABILITY":
        _exact_keys(instruction, path, {"op", "capability_id", "argc", "return_type", "kind"})
        capability_id = _stable_id(instruction["capability_id"], path + ".capability_id")
        signature = capabilities.get(capability_id)
        if signature is None:
            _fail(path, f"undeclared capability {capability_id!r}")
        if int(instruction["argc"]) != len(signature[0]) or instruction["return_type"] != signature[1] or instruction["kind"] != signature[2]:
            _fail(path, f"capability contract mismatch for {capability_id!r}")
        return
    if op == "EMIT_EVENT":
        _exact_keys(instruction, path, {"op", "event_id", "argument_types", "argc"})
        event_id = _local_name(instruction["event_id"], path + ".event_id")
        signature = events.get(event_id)
        if signature is None:
            _fail(path, f"undeclared emitted event {event_id!r}")
        argument_types = tuple(
            _storable_type(table, value, f"{path}.argument_types[{position}]")
            for position, value in enumerate(_array(instruction["argument_types"], path + ".argument_types", 0, 64))
        )
        if argument_types != signature or int(instruction["argc"]) != len(signature):
            _fail(path, f"event contract mismatch for {event_id!r}")
        return
    if op in {"JUMP", "JUMP_IF_FALSE"}:
        _exact_keys(instruction, path, {"op", "target"})
        target = _integer(instruction["target"], path + ".target", 0, count - 1)
        if target <= pc:
            _fail(path + ".target", "backward/self jumps are forbidden")
        return
    if op == "RETURN":
        _exact_keys(instruction, path, {"op"})
        return
    if op == "MAKE_RECORD":
        _exact_keys(instruction, path, {"op", "type", "fields"})
        type_id = _storable_type(table, instruction["type"], path + ".type")
        descriptor = table.require(type_id)
        if descriptor.kind != "record":
            _fail(path + ".type", "MAKE_RECORD requires record descriptor")
        fields = [_local_name(value, f"{path}.fields[{position}]") for position, value in enumerate(_array(instruction["fields"], path + ".fields", 1, 256))]
        if len(fields) != len(set(fields)):
            _fail(path + ".fields", "MAKE_RECORD fields must be unique")
        if set(fields) != {name for name, _ in descriptor.fields}:
            _fail(path + ".fields", "MAKE_RECORD fields must equal descriptor field set")
        return
    if op == "LOAD_FIELD":
        _exact_keys(instruction, path, {"op", "record_type", "field", "result_type"})
        record_type = _storable_type(table, instruction["record_type"], path + ".record_type")
        descriptor = table.require(record_type)
        if descriptor.kind != "record":
            _fail(path + ".record_type", "LOAD_FIELD requires record type")
        field = _local_name(instruction["field"], path + ".field")
        result_type = _storable_type(table, instruction["result_type"], path + ".result_type")
        if descriptor.field_type(field) != result_type:
            _fail(path, "LOAD_FIELD descriptor mismatch")
        return
    if op == "MAKE_VARIANT":
        _exact_keys(instruction, path, {"op", "type", "variant", "argc"})
        type_id = _storable_type(table, instruction["type"], path + ".type")
        variant = _local_name(instruction["variant"], path + ".variant")
        payload_type = table.variant_payload_type(type_id, variant)
        expected_argc = 0 if payload_type is None else 1
        if _integer(instruction["argc"], path + ".argc", 0, 1) != expected_argc:
            _fail(path + ".argc", f"variant requires argc {expected_argc}")
        return
    if op == "TEST_VARIANT":
        _exact_keys(instruction, path, {"op", "type", "variant"})
        type_id = _storable_type(table, instruction["type"], path + ".type")
        variant = _local_name(instruction["variant"], path + ".variant")
        table.variant_payload_type(type_id, variant)
        return
    if op == "LOAD_VARIANT_PAYLOAD":
        _exact_keys(instruction, path, {"op", "type", "variant", "payload_type"})
        type_id = _storable_type(table, instruction["type"], path + ".type")
        variant = _local_name(instruction["variant"], path + ".variant")
        payload_type = table.variant_payload_type(type_id, variant)
        if payload_type is None:
            _fail(path, "selected variant has no payload")
        if instruction["payload_type"] != payload_type:
            _fail(path + ".payload_type", "variant payload type mismatch")
        return
    _fail(path + ".op", f"unknown V3 opcode {op!r}", "TEVS_IR_V3_OPCODE")


def _validate_closed_type_table(root: Mapping[str, Any], table: TypeTableV3) -> None:
    needed = {"Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit"}
    for entity in root["entities"]:
        for state in entity["states"]:
            needed.add(str(state["type"]))
        for capability in entity["capabilities"]:
            needed.update(str(type_id) for type_id in capability["parameters"])
            needed.add(str(capability["return_type"]))
        for event in entity["emitted_events"]:
            needed.update(str(type_id) for type_id in event["parameters"])
        for handler in entity["handlers"]:
            needed.update(str(item["type"]) for item in handler["parameters"])
            needed.update(str(item["type"]) for item in handler["locals"])
            for instruction in handler["instructions"]:
                for key in ("type", "left_type", "right_type", "result_type", "return_type", "record_type", "payload_type"):
                    if key in instruction:
                        needed.add(str(instruction[key]))
                needed.update(str(type_id) for type_id in instruction.get("argument_types", []))

    queue = list(needed)
    while queue:
        type_id = queue.pop()
        descriptor = table.require(type_id, context="closed type table")
        children: list[str] = []
        if descriptor.kind == "record":
            children.extend(child for _name, child in descriptor.fields)
        elif descriptor.kind == "option" and descriptor.argument is not None:
            children.append(descriptor.argument)
        elif descriptor.kind == "result":
            assert descriptor.ok_type is not None and descriptor.err_type is not None
            children.extend((descriptor.ok_type, descriptor.err_type))
        for child in children:
            if child not in needed:
                needed.add(child)
                queue.append(child)

    observed = {item.type_id for item in table.descriptors}
    extra = sorted(observed - needed)
    missing = sorted(needed - observed)
    if missing:
        _fail("$.types", f"closed type table missing referenced descriptors {missing}")
    if extra:
        _fail("$.types", f"closed type table contains unused descriptors {extra}")


def _typed_binding(raw: Any, table: TypeTableV3, path: str) -> tuple[str, str]:
    item = _object(raw, path)
    _exact_keys(item, path, {"name", "type"})
    return _local_name(item["name"], path + ".name"), _storable_type(table, item["type"], path + ".type")


def _storable_type(table: TypeTableV3, value: Any, path: str) -> str:
    type_id = _string(value, path)
    if not table.is_storable(type_id):
        _fail(path, f"type {type_id!r} is unknown or not storable")
    return type_id


def _fail(path: str, message: str, code: str = "TEVS_IR_V3_CONTRACT") -> None:
    raise TevScriptError(code, f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail(path, "expected object with string keys")
    return value


def _array(value: Any, path: str, minimum: int, maximum: int) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "expected array")
    if not minimum <= len(value) <= maximum:
        _fail(path, f"array length must be in [{minimum}, {maximum}]")
    return value


def _exact_keys(value: Mapping[str, Any], path: str, expected: set[str]) -> None:
    observed = set(value)
    if observed != expected:
        _fail(path, f"field set mismatch; missing={sorted(expected-observed)}, extra={sorted(observed-expected)}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail(path, "expected string")
    return value


def _local_name(value: Any, path: str) -> str:
    result = _string(value, path)
    if _LOCAL.fullmatch(result) is None:
        _fail(path, f"expected local identifier, got {result!r}")
    return result


def _stable_id(value: Any, path: str) -> str:
    result = _string(value, path)
    if _STABLE.fullmatch(result) is None:
        _fail(path, f"expected stable identifier, got {result!r}")
    return result


def _hash(value: Any, path: str) -> str:
    result = _string(value, path)
    if _HASH.fullmatch(result) is None:
        _fail(path, "expected lowercase SHA-256")
    return result


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        _fail(path, f"expected integer in [{minimum}, {maximum}]")
    return value
