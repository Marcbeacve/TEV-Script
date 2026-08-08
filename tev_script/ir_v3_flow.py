from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .ir_v3_values import TypeTableV3


@dataclass(frozen=True, slots=True)
class _FlowStateV3:
    stack: tuple[str, ...]
    initialized_locals: frozenset[str]


def validate_entity_handler_flow_v3(
    entity: Mapping[str, Any],
    handler: Mapping[str, Any],
    table: TypeTableV3,
    path: str,
) -> None:
    states = {str(item["name"]): str(item["type"]) for item in entity["states"]}
    parameters = {str(item["name"]): str(item["type"]) for item in handler["parameters"]}
    locals_ = {str(item["name"]): str(item["type"]) for item in handler["locals"]}
    capabilities = {
        str(item["capability_id"]): (
            tuple(str(value) for value in item["parameters"]),
            str(item["return_type"]),
            str(item["kind"]),
        )
        for item in entity["capabilities"]
    }
    events = {
        str(item["event_id"]): tuple(str(value) for value in item["parameters"])
        for item in entity["emitted_events"]
    }
    instructions = list(handler["instructions"])
    count = len(instructions)
    incoming: list[_FlowStateV3 | None] = [None] * count
    incoming[0] = _FlowStateV3((), frozenset())
    reached_return = False

    def merge(target: int, stack: list[str], initialized: set[str], source: str) -> None:
        if target < 0 or target >= count:
            _fail(source, "control flow must target an instruction, not handler exit")
        state = _FlowStateV3(tuple(stack), frozenset(initialized))
        current = incoming[target]
        if current is None:
            incoming[target] = state
            return
        if current.stack != state.stack:
            _fail(
                source,
                f"CFG merge stack mismatch at instruction {target}: {current.stack} vs {state.stack}",
            )
        incoming[target] = _FlowStateV3(
            current.stack,
            current.initialized_locals & state.initialized_locals,
        )

    for pc, instruction in enumerate(instructions):
        state = incoming[pc]
        if state is None:
            continue
        stack = list(state.stack)
        initialized = set(state.initialized_locals)
        op = str(instruction["op"])
        current_path = f"{path}.instructions[{pc}]"

        def pop(expected: str) -> None:
            if not stack:
                _fail(current_path, f"stack underflow; expected {expected}")
            actual = stack.pop()
            if actual != expected:
                _fail(current_path, f"stack type mismatch; expected {expected}, got {actual}")

        if op == "CONST":
            type_id = str(instruction["type"])
            _require_storable(table, type_id, current_path)
            stack.append(type_id)
        elif op == "LOAD_STATE":
            stack.append(states[str(instruction["name"])])
        elif op == "STORE_STATE":
            pop(states[str(instruction["name"])])
        elif op == "LOAD_LOCAL":
            name = str(instruction["name"])
            if name not in initialized:
                _fail(current_path, f"local {name!r} is not definitely initialized")
            stack.append(locals_[name])
        elif op == "STORE_LOCAL":
            name = str(instruction["name"])
            pop(locals_[name])
            initialized.add(name)
        elif op == "LOAD_PARAM":
            stack.append(parameters[str(instruction["name"])] )
        elif op == "CONVERT_INT_TO_RAT":
            pop("Int")
            stack.append("Rat")
        elif op == "UNARY":
            result = str(instruction["type"])
            operator = str(instruction["operator"])
            expected = "Bool" if operator == "NOT" else result
            if operator == "NOT":
                if result != "Bool":
                    _fail(current_path, "NOT must produce Bool")
            elif operator == "MINUS":
                if result not in {"Int", "Rat"}:
                    _fail(current_path, "MINUS requires Int or Rat")
            else:
                _fail(current_path, f"unsupported unary operator {operator!r}")
            pop(expected)
            stack.append(result)
        elif op == "BINARY":
            left = str(instruction["left_type"])
            right = str(instruction["right_type"])
            result = str(instruction["result_type"])
            operator = str(instruction["operator"])
            if not _binary_signature_v3(operator, left, right, result, table):
                _fail(current_path, f"invalid V3 binary signature {operator}({left},{right})->{result}")
            pop(right)
            pop(left)
            stack.append(result)
        elif op == "CALL_PURE":
            function_id = str(instruction["function_id"])
            return_type = str(instruction["return_type"])
            argc = int(instruction["argc"])
            expected = _pure_signature(function_id, return_type)
            if len(expected) != argc:
                _fail(current_path, f"{function_id} argc mismatch")
            for type_id in reversed(expected):
                pop(type_id)
            if return_type != "Unit":
                _require_storable(table, return_type, current_path)
                stack.append(return_type)
        elif op == "CALL_CAPABILITY":
            capability_id = str(instruction["capability_id"])
            signature = capabilities.get(capability_id)
            if signature is None:
                _fail(current_path, f"undeclared capability {capability_id!r}")
            parameters_, return_type, kind = signature
            if (
                int(instruction["argc"]) != len(parameters_)
                or str(instruction["return_type"]) != return_type
                or str(instruction["kind"]) != kind
            ):
                _fail(current_path, f"capability instruction contract mismatch for {capability_id!r}")
            for type_id in reversed(parameters_):
                pop(type_id)
            if return_type != "Unit":
                stack.append(return_type)
        elif op == "EMIT_EVENT":
            event_id = str(instruction["event_id"])
            expected = events.get(event_id)
            if expected is None:
                _fail(current_path, f"undeclared emitted event {event_id!r}")
            declared = tuple(str(value) for value in instruction["argument_types"])
            if declared != expected or int(instruction["argc"]) != len(expected):
                _fail(current_path, f"event instruction contract mismatch for {event_id!r}")
            for type_id in reversed(expected):
                pop(type_id)
        elif op == "MAKE_RECORD":
            type_id = str(instruction["type"])
            descriptor = table.require(type_id, context=current_path)
            if descriptor.kind != "record":
                _fail(current_path, f"MAKE_RECORD requires record type, got {type_id!r}")
            fields = tuple(str(value) for value in instruction["fields"])
            descriptor_fields = {name: field_type for name, field_type in descriptor.fields}
            if len(fields) != len(descriptor.fields) or set(fields) != set(descriptor_fields):
                _fail(current_path, "MAKE_RECORD fields must equal descriptor field set exactly")
            if len(set(fields)) != len(fields):
                _fail(current_path, "MAKE_RECORD fields must be unique")
            for field_name in reversed(fields):
                pop(descriptor_fields[field_name])
            stack.append(type_id)
        elif op == "LOAD_FIELD":
            record_type = str(instruction["record_type"])
            field = str(instruction["field"])
            result_type = str(instruction["result_type"])
            descriptor = table.require(record_type, context=current_path)
            if descriptor.kind != "record":
                _fail(current_path, "LOAD_FIELD target type is not a record")
            actual_field_type = descriptor.field_type(field)
            if actual_field_type != result_type:
                _fail(current_path, f"LOAD_FIELD descriptor mismatch for {record_type}.{field}")
            pop(record_type)
            stack.append(result_type)
        elif op == "MAKE_VARIANT":
            type_id = str(instruction["type"])
            variant = str(instruction["variant"])
            payload_type = table.variant_payload_type(type_id, variant)
            expected_argc = 0 if payload_type is None else 1
            if int(instruction["argc"]) != expected_argc:
                _fail(current_path, f"MAKE_VARIANT {type_id}.{variant} expects argc={expected_argc}")
            if payload_type is not None:
                pop(payload_type)
            stack.append(type_id)
        elif op == "TEST_VARIANT":
            type_id = str(instruction["type"])
            variant = str(instruction["variant"])
            table.variant_payload_type(type_id, variant)
            pop(type_id)
            stack.append("Bool")
        elif op == "LOAD_VARIANT_PAYLOAD":
            type_id = str(instruction["type"])
            variant = str(instruction["variant"])
            payload_type = table.variant_payload_type(type_id, variant)
            if payload_type is None:
                _fail(current_path, f"{type_id}.{variant} is payload-free and cannot be loaded")
            if str(instruction["payload_type"]) != payload_type:
                _fail(current_path, "LOAD_VARIANT_PAYLOAD result type mismatch")
            pop(type_id)
            stack.append(payload_type)
        elif op == "JUMP_IF_FALSE":
            pop("Bool")
            target = int(instruction["target"])
            if target <= pc:
                _fail(current_path, "backward/self jump is forbidden")
            merge(target, stack, initialized, current_path)
            if pc + 1 >= count:
                _fail(current_path, "conditional fallthrough exits handler")
            merge(pc + 1, stack, initialized, current_path)
            continue
        elif op == "JUMP":
            target = int(instruction["target"])
            if target <= pc:
                _fail(current_path, "backward/self jump is forbidden")
            merge(target, stack, initialized, current_path)
            continue
        elif op == "RETURN":
            if stack:
                _fail(current_path, f"RETURN requires empty stack, found {stack}")
            reached_return = True
            continue
        else:
            _fail(current_path, f"unknown V3 opcode {op!r}")

        if pc + 1 >= count:
            _fail(current_path, "reachable control flow falls off handler")
        merge(pc + 1, stack, initialized, current_path)

    if not reached_return:
        _fail(path, "no reachable RETURN")


def _binary_signature_v3(operator: str, left: str, right: str, result: str, table: TypeTableV3) -> bool:
    if operator in {"AND", "OR"}:
        return left == right == result == "Bool"
    if operator in {"EQEQ", "NE"}:
        if result != "Bool":
            return False
        if left == right and table.is_storable(left):
            return True
        return {left, right} == {"Int", "Rat"}
    if operator in {"LT", "LE", "GT", "GE"}:
        return left == right and left in {"Int", "Rat"} and result == "Bool"
    if operator in {"PLUS", "MINUS"}:
        return (
            left == right == result == "Int"
            or left == right == result == "Rat"
            or left == right == result and result in {"Vec2", "Vec3"}
        )
    if operator == "STAR":
        return (
            left == right == result == "Int"
            or left == right == result == "Rat"
            or left in {"Vec2", "Vec3"} and right == "Rat" and result == left
            or right in {"Vec2", "Vec3"} and left == "Rat" and result == right
        )
    if operator == "SLASH":
        return (
            left == right == result == "Rat"
            or left in {"Vec2", "Vec3"} and right == "Rat" and result == left
        )
    return False


def _pure_signature(function_id: str, return_type: str) -> tuple[str, ...]:
    if function_id == "vec2" and return_type == "Vec2":
        return ("Rat", "Rat")
    if function_id == "vec3" and return_type == "Vec3":
        return ("Rat", "Rat", "Rat")
    if function_id in {"min", "max"} and return_type in {"Int", "Rat"}:
        return (return_type, return_type)
    raise TevScriptError("TEVS_IR_V3_FLOW_INVALID", f"invalid pure intrinsic signature {function_id!r}->{return_type}")


def _require_storable(table: TypeTableV3, type_id: str, path: str) -> None:
    if not table.is_storable(type_id):
        _fail(path, f"type {type_id!r} is not storable")


def _fail(path: str, message: str) -> None:
    raise TevScriptError("TEVS_IR_V3_FLOW_INVALID", f"{path}: {message}")
