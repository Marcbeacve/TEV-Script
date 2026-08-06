from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Mapping

from .diagnostics import TevScriptError
from .ir_validation import validate_program_ir
from .values import decode_typed_value, encode_typed_value

Capability = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class EmittedEvent:
    entity_id: str
    event_id: str
    arguments: tuple[Any, ...]


@dataclass(slots=True)
class EntityRuntime:
    entity_id: str
    state: dict[str, Any]
    state_types: dict[str, str]
    handlers: dict[str, dict[str, Any]]


class ScriptRuntime:
    def __init__(
        self,
        ir: Mapping[str, Any],
        capabilities: Mapping[str, Capability] | None = None,
    ) -> None:
        self.ir = deepcopy(dict(ir))
        self.capabilities = dict(capabilities or {})
        self.entities: dict[str, EntityRuntime] = {}
        self.emitted: list[EmittedEvent] = []
        self._validate_program()
        for raw_entity in self.ir["entities"]:
            state: dict[str, Any] = {}
            state_types: dict[str, str] = {}
            for raw_state in raw_entity["states"]:
                state[raw_state["name"]] = _decode_value(
                    raw_state["type"], raw_state["initial"]
                )
                state_types[raw_state["name"]] = raw_state["type"]
            handlers = {
                handler["event_id"]: handler for handler in raw_entity["handlers"]
            }
            runtime = EntityRuntime(
                entity_id=raw_entity["entity_id"],
                state=state,
                state_types=state_types,
                handlers=handlers,
            )
            self.entities[runtime.entity_id] = runtime

    def invoke(
        self,
        entity_id: str,
        event_id: str,
        *arguments: Any,
    ) -> tuple[EmittedEvent, ...]:
        entity = self.entities.get(entity_id)
        if entity is None:
            raise TevScriptError(
                "TEVS_RUNTIME_ENTITY_UNKNOWN",
                f"unknown entity {entity_id}",
            )
        start = len(self.emitted)
        queue: deque[tuple[str, tuple[Any, ...]]] = deque()
        queue.append((event_id, tuple(arguments)))
        maximum = int(self.ir["boundary"]["maximum_event_chain"])
        processed = 0
        while queue:
            processed += 1
            if processed > maximum:
                raise TevScriptError(
                    "TEVS_RUNTIME_EVENT_BUDGET",
                    f"event chain exceeds {maximum}",
                )
            current_event, current_arguments = queue.popleft()
            handler = entity.handlers.get(current_event)
            if handler is None:
                self.emitted.append(
                    EmittedEvent(entity_id, current_event, current_arguments)
                )
                continue
            parameters = handler["parameters"]
            if len(parameters) != len(current_arguments):
                raise TevScriptError(
                    "TEVS_RUNTIME_EVENT_ARITY",
                    f"event {current_event} expects {len(parameters)} arguments",
                )
            parameter_values = {
                parameter["name"]: _coerce_runtime(
                    current_arguments[index], parameter["type"]
                )
                for index, parameter in enumerate(parameters)
            }
            generated = self._execute_handler(
                entity,
                handler,
                parameter_values,
            )
            for generated_event, generated_arguments in generated:
                self.emitted.append(
                    EmittedEvent(
                        entity_id,
                        generated_event,
                        generated_arguments,
                    )
                )
                if generated_event in entity.handlers:
                    queue.append((generated_event, generated_arguments))
        return tuple(self.emitted[start:])

    def state(self, entity_id: str) -> dict[str, Any]:
        entity = self.entities.get(entity_id)
        if entity is None:
            raise KeyError(entity_id)
        return dict(entity.state)

    def _execute_handler(
        self,
        entity: EntityRuntime,
        handler: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> list[tuple[str, tuple[Any, ...]]]:
        instructions = list(handler["instructions"])
        budget = int(handler["instruction_budget"])
        stack: list[Any] = []
        locals_: dict[str, Any] = {}
        emitted: list[tuple[str, tuple[Any, ...]]] = []
        pc = 0
        executed = 0
        while pc < len(instructions):
            executed += 1
            if executed > budget:
                raise TevScriptError(
                    "TEVS_RUNTIME_INSTRUCTION_BUDGET",
                    f"handler {handler['event_id']} exceeded its instruction budget",
                )
            instruction = instructions[pc]
            op = instruction["op"]
            if op == "CONST":
                stack.append(_decode_value(instruction["type"], instruction["value"]))
            elif op == "LOAD_STATE":
                stack.append(entity.state[instruction["name"]])
            elif op == "STORE_STATE":
                entity.state[instruction["name"]] = stack.pop()
            elif op == "LOAD_LOCAL":
                stack.append(locals_[instruction["name"]])
            elif op == "STORE_LOCAL":
                locals_[instruction["name"]] = stack.pop()
            elif op == "LOAD_PARAM":
                stack.append(parameters[instruction["name"]])
            elif op == "CONVERT_INT_TO_RAT":
                stack.append(Fraction(stack.pop(), 1))
            elif op == "UNARY":
                value = stack.pop()
                stack.append(_unary(instruction["operator"], value))
            elif op == "BINARY":
                right = stack.pop()
                left = stack.pop()
                stack.append(_binary(instruction["operator"], left, right))
            elif op == "CALL_PURE":
                arguments = _pop_arguments(stack, int(instruction["argc"]))
                result = _call_pure(instruction["function_id"], arguments)
                if instruction["return_type"] != "Unit":
                    stack.append(result)
            elif op == "CALL_CAPABILITY":
                capability_id = instruction["capability_id"]
                capability = self.capabilities.get(capability_id)
                if capability is None:
                    raise TevScriptError(
                        "TEVS_RUNTIME_CAPABILITY_MISSING",
                        f"capability {capability_id} is not bound",
                    )
                arguments = _pop_arguments(stack, int(instruction["argc"]))
                result = capability(*arguments)
                if instruction["return_type"] != "Unit":
                    stack.append(
                        _coerce_runtime(result, instruction["return_type"])
                    )
            elif op == "EMIT_EVENT":
                arguments = tuple(
                    _pop_arguments(stack, int(instruction["argc"]))
                )
                emitted.append((instruction["event_id"], arguments))
            elif op == "JUMP_IF_FALSE":
                condition = stack.pop()
                if condition is not True:
                    pc = int(instruction["target"])
                    continue
            elif op == "JUMP":
                pc = int(instruction["target"])
                continue
            elif op == "RETURN":
                break
            else:
                raise TevScriptError(
                    "TEVS_RUNTIME_OPCODE",
                    f"unknown opcode {op}",
                )
            pc += 1
        if stack:
            raise TevScriptError(
                "TEVS_RUNTIME_STACK_LEAK",
                f"handler {handler['event_id']} left {len(stack)} values on the stack",
            )
        return emitted

    def _validate_program(self) -> None:
        validate_program_ir(self.ir)


def _pop_arguments(stack: list[Any], count: int) -> list[Any]:
    if count == 0:
        return []
    if len(stack) < count:
        raise TevScriptError(
            "TEVS_RUNTIME_STACK_UNDERFLOW",
            "not enough values for call",
        )
    values = stack[-count:]
    del stack[-count:]
    return values


def _decode_value(type_name: str, raw: Any) -> Any:
    return decode_typed_value(type_name, raw)


def encode_runtime_value(type_name: str, value: Any) -> Any:
    return encode_typed_value(type_name, value)

def _coerce_runtime(value: Any, type_name: str) -> Any:
    if type_name == "Rat":
        if isinstance(value, Fraction):
            return value
        if isinstance(value, bool):
            raise TypeError("bool is not Rat")
        if isinstance(value, int):
            return Fraction(value, 1)
        if isinstance(value, str):
            return decode_typed_value("Rat", {"$rat": [value, "1"]})
        raise TypeError("expected Rat")
    if type_name == "Int":
        if isinstance(value, bool):
            raise TypeError("bool is not Int")
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            return decode_typed_value("Int", {"$int": value})
        raise TypeError("expected Int")
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise TypeError("expected Bool")
        return value
    if type_name == "Text":
        if not isinstance(value, str):
            raise TypeError("expected Text")
        return value
    if type_name in {"Vec2", "Vec3"}:
        expected = 2 if type_name == "Vec2" else 3
        if not isinstance(value, (tuple, list)) or len(value) != expected:
            raise TypeError(f"expected {type_name}")
        return tuple(_coerce_runtime(item, "Rat") for item in value)
    if type_name == "Unit":
        return None
    raise TypeError(type_name)


def _unary(operator: str, value: Any) -> Any:
    if operator == "NOT":
        return not value
    if operator == "MINUS":
        if isinstance(value, tuple):
            return tuple(-item for item in value)
        return -value
    raise TevScriptError("TEVS_RUNTIME_UNARY", operator)


def _binary(operator: str, left: Any, right: Any) -> Any:
    if operator == "AND":
        return bool(left and right)
    if operator == "OR":
        return bool(left or right)
    if operator == "EQEQ":
        return left == right
    if operator == "NE":
        return left != right
    if operator == "LT":
        return left < right
    if operator == "LE":
        return left <= right
    if operator == "GT":
        return left > right
    if operator == "GE":
        return left >= right
    if operator == "PLUS":
        return _vector_or_scalar(left, right, lambda a, b: a + b)
    if operator == "MINUS":
        return _vector_or_scalar(left, right, lambda a, b: a - b)
    if operator == "STAR":
        if isinstance(left, tuple) and not isinstance(right, tuple):
            return tuple(item * right for item in left)
        if isinstance(right, tuple) and not isinstance(left, tuple):
            return tuple(left * item for item in right)
        return left * right
    if operator == "SLASH":
        if right == 0:
            raise TevScriptError("TEVS_RUNTIME_DIVIDE_ZERO", "division by zero")
        if isinstance(left, tuple):
            return tuple(item / right for item in left)
        return Fraction(left) / Fraction(right)
    raise TevScriptError("TEVS_RUNTIME_BINARY", operator)


def _vector_or_scalar(left: Any, right: Any, operation: Callable[[Any, Any], Any]) -> Any:
    if isinstance(left, tuple) or isinstance(right, tuple):
        if not isinstance(left, tuple) or not isinstance(right, tuple):
            raise TevScriptError(
                "TEVS_RUNTIME_VECTOR_OPERAND",
                "vector addition/subtraction requires two vectors",
            )
        return tuple(operation(a, b) for a, b in zip(left, right, strict=True))
    return operation(left, right)


def _call_pure(function_id: str, arguments: list[Any]) -> Any:
    if function_id == "vec2":
        return tuple(Fraction(item) for item in arguments)
    if function_id == "vec3":
        return tuple(Fraction(item) for item in arguments)
    if function_id == "max":
        return max(arguments)
    if function_id == "min":
        return min(arguments)
    raise TevScriptError(
        "TEVS_RUNTIME_PURE_FUNCTION",
        f"unknown pure function {function_id}",
    )
