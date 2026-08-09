from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .diagnostics import TevScriptError


@dataclass(frozen=True, slots=True)
class _FlowState:
    stack: tuple[str, ...]
    initialized_locals: frozenset[str]


def _fail(path: str, message: str) -> None:
    raise TevScriptError("TEVS_IR_FLOW_INVALID", f"{path}: {message}")


def _binary_signature(operator: str, left: str, right: str, result: str) -> bool:
    if operator in {"AND", "OR"}:
        return left == right == result == "Bool"
    if operator in {"EQEQ", "NE"}:
        return result == "Bool" and (
            left == right or (left == right == "Rat")
        )
    if operator in {"LT", "LE", "GT", "GE"}:
        return left == right and left in {"Int", "Rat"} and result == "Bool"
    if operator in {"PLUS", "MINUS"}:
        return (
            (left == right == result == "Int")
            or (left == right == result == "Rat")
            or (left == right == result and result in {"Vec2", "Vec3"})
        )
    if operator == "STAR":
        return (
            (left == right == result == "Int")
            or (left == right == result == "Rat")
            or (left in {"Vec2", "Vec3"} and right == "Rat" and result == left)
            or (right in {"Vec2", "Vec3"} and left == "Rat" and result == right)
        )
    if operator == "SLASH":
        return (
            (left == right == result == "Rat")
            or (left in {"Vec2", "Vec3"} and right == "Rat" and result == left)
        )
    return False


def _maps(entity: dict[str, Any], handler: dict[str, Any]) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, str],
    dict[str, tuple[tuple[str, ...], str, str]],
    dict[str, tuple[str, ...]],
]:
    states = {str(item["name"]): str(item["type"]) for item in entity["states"]}
    parameters = {
        str(item["name"]): str(item["type"]) for item in handler["parameters"]
    }
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
    return states, parameters, locals_, capabilities, events


def validate_entity_handler_flow(
    entity: dict[str, Any],
    handler: dict[str, Any],
    path: str,
) -> None:
    states, parameters, locals_, capabilities, events = _maps(entity, handler)
    instructions = list(handler["instructions"])
    count = len(instructions)
    incoming: list[_FlowState | None] = [None] * count
    incoming[0] = _FlowState((), frozenset())
    reached_return = False

    def merge(target: int, stack: list[str], initialized: set[str], source: str) -> None:
        if target < 0 or target >= count:
            _fail(source, "control flow must target an instruction, not handler exit")
        state = _FlowState(tuple(stack), frozenset(initialized))
        current = incoming[target]
        if current is None:
            incoming[target] = state
            return
        if current.stack != state.stack:
            _fail(source, f"CFG merge stack mismatch at instruction {target}")
        incoming[target] = _FlowState(
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
            stack.append(str(instruction["type"]))
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
            stack.append(parameters[str(instruction["name"])])
        elif op == "CONVERT_INT_TO_RAT":
            pop("Int")
            stack.append("Rat")
        elif op == "UNARY":
            result = str(instruction["type"])
            operator = str(instruction["operator"])
            expected = "Bool" if operator == "NOT" else result
            pop(expected)
            stack.append(result)
        elif op == "BINARY":
            left = str(instruction["left_type"])
            right = str(instruction["right_type"])
            result = str(instruction["result_type"])
            operator = str(instruction["operator"])
            if not _binary_signature(operator, left, right, result):
                _fail(current_path, "binary operator/type contract is not a V0.2 lowering")
            pop(right)
            pop(left)
            stack.append(result)
        elif op == "CALL_PURE":
            function_id = str(instruction["function_id"])
            return_type = str(instruction["return_type"])
            if function_id == "vec2":
                expected = ("Rat", "Rat")
            elif function_id == "vec3":
                expected = ("Rat", "Rat", "Rat")
            elif function_id in {"max", "min"}:
                expected = (return_type, return_type)
            else:
                _fail(current_path, f"unknown pure function {function_id!r}")
                raise AssertionError
            for type_name in reversed(expected):
                pop(type_name)
            if return_type != "Unit":
                stack.append(return_type)
        elif op == "CALL_CAPABILITY":
            capability_id = str(instruction["capability_id"])
            signature = capabilities[capability_id]
            for type_name in reversed(signature[0]):
                pop(type_name)
            if signature[1] != "Unit":
                stack.append(signature[1])
        elif op == "EMIT_EVENT":
            event_id = str(instruction["event_id"])
            for type_name in reversed(events[event_id]):
                pop(type_name)
        elif op == "JUMP_IF_FALSE":
            pop("Bool")
            merge(int(instruction["target"]), stack, initialized, current_path)
            if pc + 1 >= count:
                _fail(current_path, "conditional fallthrough exits the handler")
            merge(pc + 1, stack, initialized, current_path)
            continue
        elif op == "JUMP":
            merge(int(instruction["target"]), stack, initialized, current_path)
            continue
        elif op == "RETURN":
            if stack:
                _fail(current_path, f"RETURN requires empty stack, found {stack}")
            reached_return = True
            continue
        else:
            _fail(current_path, f"unknown opcode {op!r}")

        if pc + 1 >= count:
            _fail(current_path, "reachable control flow falls off the handler")
        merge(pc + 1, stack, initialized, current_path)

    if not reached_return:
        _fail(path, "no reachable RETURN")
