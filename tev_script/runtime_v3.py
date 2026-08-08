from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any, Callable, Mapping

from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_values import (
    RecordValueV3,
    TypeTableV3,
    VariantValueV3,
    decode_v3_value,
    encode_v3_value,
    v3_values_equal,
)

CapabilityV3 = Callable[..., Any]
_STABLE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_LOCAL_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class EmittedEventV3:
    entity_id: str
    event_id: str
    argument_types: tuple[str, ...]
    arguments: tuple[Any, ...]

    def canonical_arguments(self, table: TypeTableV3) -> tuple[Any, ...]:
        return tuple(
            encode_v3_value(type_id, value, table, context=f"event {self.event_id}")
            for type_id, value in zip(self.argument_types, self.arguments, strict=True)
        )


@dataclass(slots=True)
class EntityRuntimeV3:
    entity_id: str
    state: dict[str, Any]
    state_types: dict[str, str]
    handlers: dict[str, dict[str, Any]]
    emitted_event_types: dict[str, tuple[str, ...]]


class ScriptRuntimeV3:
    def __init__(
        self,
        ir: Mapping[str, Any],
        capabilities: Mapping[str, CapabilityV3] | None = None,
        *,
        expected_source_semantic_hash: str | None = None,
    ) -> None:
        self.ir = deepcopy(dict(ir))
        self.type_table = validate_program_ir_v3(
            self.ir,
            expected_source_semantic_hash=expected_source_semantic_hash,
        )
        self.capabilities = dict(capabilities or {})
        for capability_id in self.capabilities:
            if _STABLE_ID.fullmatch(capability_id) is None:
                raise TevScriptError(
                    "TEVS_IR_V3_CAPABILITY_BINDING_ID",
                    f"non-canonical capability binding id {capability_id!r}",
                )
        self.entities: dict[str, EntityRuntimeV3] = {}
        self.emitted: list[EmittedEventV3] = []
        for raw_entity in self.ir["entities"]:
            state: dict[str, Any] = {}
            state_types: dict[str, str] = {}
            for raw_state in raw_entity["states"]:
                name = str(raw_state["name"])
                type_id = str(raw_state["type"])
                state[name] = decode_v3_value(
                    type_id,
                    raw_state["initial"],
                    self.type_table,
                    context=f"state {raw_entity['entity_id']}.{name}",
                )
                state_types[name] = type_id
            handlers = {
                str(handler["event_id"]): handler
                for handler in raw_entity["handlers"]
            }
            event_types = {
                str(event["event_id"]): tuple(str(value) for value in event["parameters"])
                for event in raw_entity["emitted_events"]
            }
            entity = EntityRuntimeV3(
                str(raw_entity["entity_id"]),
                state,
                state_types,
                handlers,
                event_types,
            )
            self.entities[entity.entity_id] = entity

    @property
    def source_semantic_hash(self) -> str:
        return str(self.ir["source_semantic_hash"])

    @property
    def semantic_hash(self) -> str:
        return str(self.ir["semantic_hash"])

    def invoke(
        self,
        entity_id: str,
        event_id: str,
        *arguments: Any,
    ) -> tuple[EmittedEventV3, ...]:
        _require_local_id(entity_id, "entity")
        _require_local_id(event_id, "event")
        entity = self.entities.get(entity_id)
        if entity is None:
            raise TevScriptError("TEVS_IR_V3_ENTITY_UNKNOWN", f"unknown entity {entity_id!r}")

        start = len(self.emitted)
        queue: deque[tuple[str, tuple[Any, ...]]] = deque()
        queue.append((event_id, tuple(arguments)))
        maximum = int(self.ir["boundary"]["maximum_event_chain"])
        processed = 0

        while queue:
            processed += 1
            if processed > maximum:
                raise TevScriptError(
                    "TEVS_IR_V3_EVENT_BUDGET",
                    f"event chain exceeds {maximum}",
                )
            current_event, raw_arguments = queue.popleft()
            handler = entity.handlers.get(current_event)
            if handler is None:
                # External/unhandled invocation has no declaration from which a
                # portable argument signature can be inferred. This matches the
                # historical local-handler event model: only emitted events are
                # recorded canonically.
                continue
            parameters = handler["parameters"]
            if len(parameters) != len(raw_arguments):
                raise TevScriptError(
                    "TEVS_IR_V3_EVENT_ARITY",
                    f"event {current_event!r} expects {len(parameters)} arguments",
                )
            parameter_values = {
                str(parameter["name"]): _coerce_runtime_v3(
                    str(parameter["type"]),
                    raw_arguments[index],
                    self.type_table,
                    context=f"invoke {entity_id}.{current_event}[{index}]",
                )
                for index, parameter in enumerate(parameters)
            }
            generated = self._execute_handler(entity, handler, parameter_values)
            for generated_event, generated_types, generated_arguments in generated:
                emitted = EmittedEventV3(
                    entity_id,
                    generated_event,
                    generated_types,
                    generated_arguments,
                )
                self.emitted.append(emitted)
                if generated_event in entity.handlers:
                    queue.append((generated_event, generated_arguments))
        return tuple(self.emitted[start:])

    def state(self, entity_id: str) -> dict[str, Any]:
        entity = self.entities.get(entity_id)
        if entity is None:
            raise KeyError(entity_id)
        return dict(entity.state)

    def canonical_state(self, entity_id: str) -> dict[str, Any]:
        entity = self.entities.get(entity_id)
        if entity is None:
            raise KeyError(entity_id)
        return {
            name: encode_v3_value(
                entity.state_types[name],
                entity.state[name],
                self.type_table,
                context=f"state {entity_id}.{name}",
            )
            for name in sorted(entity.state)
        }

    def _execute_handler(
        self,
        entity: EntityRuntimeV3,
        handler: Mapping[str, Any],
        parameters: Mapping[str, Any],
    ) -> list[tuple[str, tuple[str, ...], tuple[Any, ...]]]:
        instructions = list(handler["instructions"])
        budget = int(handler["instruction_budget"])
        stack: list[Any] = []
        locals_: dict[str, Any] = {}
        emitted: list[tuple[str, tuple[str, ...], tuple[Any, ...]]] = []
        pc = 0
        executed = 0

        while pc < len(instructions):
            executed += 1
            if executed > budget:
                raise TevScriptError(
                    "TEVS_IR_V3_INSTRUCTION_BUDGET",
                    f"handler {handler['event_id']!r} exceeded instruction budget {budget}",
                )
            instruction = instructions[pc]
            op = str(instruction["op"])

            if op == "CONST":
                stack.append(
                    decode_v3_value(
                        str(instruction["type"]),
                        instruction["value"],
                        self.type_table,
                        context=f"instruction {handler['event_id']}:{pc}",
                    )
                )
            elif op == "LOAD_STATE":
                stack.append(entity.state[str(instruction["name"])])
            elif op == "STORE_STATE":
                entity.state[str(instruction["name"])] = stack.pop()
            elif op == "LOAD_LOCAL":
                stack.append(locals_[str(instruction["name"])])
            elif op == "STORE_LOCAL":
                locals_[str(instruction["name"])] = stack.pop()
            elif op == "LOAD_PARAM":
                stack.append(parameters[str(instruction["name"])])
            elif op == "CONVERT_INT_TO_RAT":
                stack.append(Fraction(stack.pop(), 1))
            elif op == "UNARY":
                stack.append(_unary(str(instruction["operator"]), stack.pop()))
            elif op == "BINARY":
                right = stack.pop()
                left = stack.pop()
                stack.append(
                    _binary_v3(
                        str(instruction["operator"]),
                        str(instruction["left_type"]),
                        str(instruction["right_type"]),
                        left,
                        right,
                        self.type_table,
                    )
                )
            elif op == "CALL_PURE":
                args = _pop_arguments(stack, int(instruction["argc"]))
                result = _call_pure(str(instruction["function_id"]), args)
                if str(instruction["return_type"]) != "Unit":
                    stack.append(result)
            elif op == "CALL_CAPABILITY":
                capability_id = str(instruction["capability_id"])
                capability = self.capabilities.get(capability_id)
                if capability is None:
                    raise TevScriptError(
                        "TEVS_IR_V3_CAPABILITY_MISSING",
                        f"capability {capability_id!r} is not bound",
                    )
                args = _pop_arguments(stack, int(instruction["argc"]))
                result = capability(*args)
                return_type = str(instruction["return_type"])
                if return_type != "Unit":
                    stack.append(
                        _coerce_runtime_v3(
                            return_type,
                            result,
                            self.type_table,
                            context=f"capability {capability_id} return",
                        )
                    )
            elif op == "EMIT_EVENT":
                argument_types = tuple(str(value) for value in instruction["argument_types"])
                args = tuple(_pop_arguments(stack, int(instruction["argc"])))
                # Values are already typed by the verified stack. Canonicalize and
                # decode once to guarantee host representation cannot leak.
                args = tuple(
                    _coerce_runtime_v3(
                        type_id,
                        value,
                        self.type_table,
                        context=f"emit {instruction['event_id']}[{index}]",
                    )
                    for index, (type_id, value) in enumerate(zip(argument_types, args, strict=True))
                )
                emitted.append((str(instruction["event_id"]), argument_types, args))
            elif op == "MAKE_RECORD":
                type_id = str(instruction["type"])
                descriptor = self.type_table.require(type_id)
                fields = tuple(str(name) for name in instruction["fields"])
                values = _pop_arguments(stack, len(fields))
                by_name = dict(zip(fields, values, strict=True))
                record = RecordValueV3(
                    type_id,
                    tuple((name, by_name[name]) for name, _field_type in descriptor.fields),
                )
                # Encoding validates nested semantic representations and returns a
                # canonical representation; decode normalizes any host containers.
                stack.append(
                    decode_v3_value(
                        type_id,
                        encode_v3_value(type_id, record, self.type_table),
                        self.type_table,
                    )
                )
            elif op == "LOAD_FIELD":
                record = stack.pop()
                if not isinstance(record, RecordValueV3):
                    raise TevScriptError("TEVS_IR_V3_RUNTIME_RECORD", "LOAD_FIELD received non-record value")
                stack.append(record.field(str(instruction["field"])))
            elif op == "MAKE_VARIANT":
                type_id = str(instruction["type"])
                variant = str(instruction["variant"])
                argc = int(instruction["argc"])
                if argc == 0:
                    value = VariantValueV3(type_id, variant)
                else:
                    value = VariantValueV3(type_id, variant, stack.pop())
                stack.append(
                    decode_v3_value(
                        type_id,
                        encode_v3_value(type_id, value, self.type_table),
                        self.type_table,
                    )
                )
            elif op == "TEST_VARIANT":
                value = stack.pop()
                if not isinstance(value, VariantValueV3):
                    raise TevScriptError("TEVS_IR_V3_RUNTIME_VARIANT", "TEST_VARIANT received non-variant value")
                stack.append(value.variant == str(instruction["variant"]))
            elif op == "LOAD_VARIANT_PAYLOAD":
                value = stack.pop()
                variant = str(instruction["variant"])
                if not isinstance(value, VariantValueV3) or value.variant != variant or not value.has_payload:
                    raise TevScriptError(
                        "TEVS_IR_V3_VARIANT_UNWRAP",
                        f"cannot load payload for variant {variant!r}",
                    )
                stack.append(value.payload)
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
                raise TevScriptError("TEVS_IR_V3_OPCODE", f"unknown V3 opcode {op!r}")
            pc += 1

        if stack:
            raise TevScriptError(
                "TEVS_IR_V3_RUNTIME_STACK_LEAK",
                f"handler {handler['event_id']!r} left {len(stack)} values on stack",
            )
        return emitted


def _coerce_runtime_v3(type_id: str, value: Any, table: TypeTableV3, *, context: str) -> Any:
    descriptor = table.require(type_id, context=context)
    if descriptor.kind == "primitive":
        if type_id == "Rat":
            if isinstance(value, Fraction):
                return value
            if isinstance(value, bool):
                raise TevScriptError("TEVS_IR_V3_CAPABILITY_COERCION", f"{context}: bool is not Rat")
            if isinstance(value, int):
                return Fraction(value, 1)
        elif type_id == "Int":
            if isinstance(value, bool) or not isinstance(value, int):
                raise TevScriptError("TEVS_IR_V3_CAPABILITY_COERCION", f"{context}: expected Int")
            return value
        elif type_id == "Bool":
            if not isinstance(value, bool):
                raise TevScriptError("TEVS_IR_V3_CAPABILITY_COERCION", f"{context}: expected Bool")
            return value
        elif type_id == "Text":
            if not isinstance(value, str):
                raise TevScriptError("TEVS_IR_V3_CAPABILITY_COERCION", f"{context}: expected Text")
            return value
        elif type_id in {"Vec2", "Vec3"}:
            expected = 2 if type_id == "Vec2" else 3
            if not isinstance(value, (tuple, list)) or len(value) != expected:
                raise TevScriptError("TEVS_IR_V3_CAPABILITY_COERCION", f"{context}: expected {type_id}")
            return tuple(_coerce_runtime_v3("Rat", item, table, context=context) for item in value)
        raise AssertionError(type_id)

    if isinstance(value, (RecordValueV3, VariantValueV3)):
        raw = encode_v3_value(type_id, value, table, context=context)
        return decode_v3_value(type_id, raw, table, context=context)
    if isinstance(value, dict):
        return decode_v3_value(type_id, value, table, context=context)
    raise TevScriptError(
        "TEVS_IR_V3_CAPABILITY_COERCION",
        f"{context}: composite value must be a canonical encoded value or V3 semantic value",
    )


def _binary_v3(
    operator: str,
    left_type: str,
    right_type: str,
    left: Any,
    right: Any,
    table: TypeTableV3,
) -> Any:
    if operator == "AND":
        return bool(left and right)
    if operator == "OR":
        return bool(left or right)
    if operator in {"EQEQ", "NE"}:
        if {left_type, right_type} == {"Int", "Rat"}:
            equal = Fraction(left) == Fraction(right)
        elif left_type == right_type:
            equal = v3_values_equal(left_type, left, right, table)
        else:
            raise TevScriptError("TEVS_IR_V3_RUNTIME_BINARY", "invalid equality types")
        return equal if operator == "EQEQ" else not equal
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
            raise TevScriptError("TEVS_IR_V3_DIVIDE_ZERO", "division by zero")
        if isinstance(left, tuple):
            return tuple(Fraction(item) / Fraction(right) for item in left)
        return Fraction(left) / Fraction(right)
    raise TevScriptError("TEVS_IR_V3_RUNTIME_BINARY", f"unknown binary operator {operator!r}")


def _unary(operator: str, value: Any) -> Any:
    if operator == "NOT":
        return not value
    if operator == "MINUS":
        return -value
    raise TevScriptError("TEVS_IR_V3_RUNTIME_UNARY", f"unknown unary operator {operator!r}")


def _vector_or_scalar(left: Any, right: Any, operation: Callable[[Any, Any], Any]) -> Any:
    if isinstance(left, tuple) or isinstance(right, tuple):
        if not isinstance(left, tuple) or not isinstance(right, tuple):
            raise TevScriptError("TEVS_IR_V3_VECTOR_OPERAND", "vector plus/minus requires two vectors")
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
    raise TevScriptError("TEVS_IR_V3_PURE_FUNCTION", f"unknown pure intrinsic {function_id!r}")


def _pop_arguments(stack: list[Any], count: int) -> list[Any]:
    if count == 0:
        return []
    if len(stack) < count:
        raise TevScriptError("TEVS_IR_V3_STACK_UNDERFLOW", "not enough values for operation")
    values = stack[-count:]
    del stack[-count:]
    return values


def _require_local_id(value: str, kind: str) -> None:
    if _LOCAL_ID.fullmatch(value) is None:
        raise TevScriptError("TEVS_IR_V3_INVOCATION_ID", f"non-canonical {kind} id {value!r}")
