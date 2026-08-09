from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any, Callable, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_values import (
    RecordValueV3,
    TypeTableV3,
    VariantValueV3,
    decode_v3_value,
    encode_v3_value,
)
from .runtime_v3 import (
    EmittedEventV3,
    _binary_v3,
    _call_pure,
    _coerce_runtime_v3,
    _unary,
)

CapabilityV3 = Callable[..., Any]
_STABLE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_LOCAL_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_UNINITIALIZED = object()

# Private execution-plan opcodes. IR V3 remains the portable semantic authority.
_CONST = 1
_LOAD_STATE = 2
_STORE_STATE = 3
_LOAD_LOCAL = 4
_STORE_LOCAL = 5
_LOAD_PARAM = 6
_CONVERT_INT_TO_RAT = 7
_UNARY = 8
_BINARY = 9
_CALL_PURE = 10
_CALL_CAPABILITY = 11
_EMIT_EVENT = 12
_MAKE_RECORD = 13
_LOAD_FIELD = 14
_MAKE_VARIANT = 15
_TEST_VARIANT = 16
_LOAD_VARIANT_PAYLOAD = 17
_JUMP_IF_FALSE = 18
_JUMP = 19
_RETURN = 20
_ADD_STATE_INT_CONST = 21
_ADD_INT = 22
_SUB_INT = 23
_MUL_INT = 24

# Closed fast-handler profiles. They are selected only after full IR validation.
_FAST_NONE = 0
_FAST_RETURN = 1
_FAST_ADD_STATE_INT_CONST = 2
_FAST_BOOL_GUARD_ADD_STATE_INT_CONST = 3


@dataclass(frozen=True, slots=True)
class CompiledInstructionV3:
    opcode: int
    operands: tuple[Any, ...] = ()
    logical_cost: int = 1


@dataclass(frozen=True, slots=True)
class CompiledHandlerV3:
    event_id: str
    parameter_types: tuple[str, ...]
    local_count: int
    instructions: tuple[CompiledInstructionV3, ...]
    instruction_budget: int
    can_emit: bool
    meter_budget: bool
    fast_kind: int = _FAST_NONE
    fast_operands: tuple[Any, ...] = ()


@dataclass(slots=True)
class OptimizedEntityRuntimeV3:
    entity_id: str
    state: dict[str, Any]
    state_types: dict[str, str]
    handlers: dict[str, CompiledHandlerV3]
    emitted_event_types: dict[str, tuple[str, ...]]


class OptimizedScriptRuntimeV3:
    """Validated IR V3 runtime with a private precompiled execution plan.

    The public semantic authority remains ``TEV_SCRIPT_PROGRAM_IR_V3``.
    Construction performs the same full validation as ``ScriptRuntimeV3`` and
    only then derives an execution plan. The plan is never serialized, hashed,
    signed, or treated as portable authority.

    The optimization rule is deliberately one-way::

        untrusted/canonical IR -> validate once -> trusted execution plan

    Runtime values entering through capabilities are still checked at the
    capability boundary. Optimization removes repeated interpretation of
    already-validated *internal* IR structure; it does not relax input
    authority or change the IR semantic hash.
    """

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
        self.maximum_event_chain = int(self.ir["boundary"]["maximum_event_chain"])
        self.entities: dict[str, OptimizedEntityRuntimeV3] = {}
        self.emitted: list[EmittedEventV3] = []

        for raw_entity in self.ir["entities"]:
            state: dict[str, Any] = {}
            state_types: dict[str, str] = {}
            entity_id = str(raw_entity["entity_id"])
            for raw_state in raw_entity["states"]:
                name = str(raw_state["name"])
                type_id = str(raw_state["type"])
                state[name] = decode_v3_value(
                    type_id,
                    raw_state["initial"],
                    self.type_table,
                    context=f"state {entity_id}.{name}",
                )
                state_types[name] = type_id

            handlers = {
                str(handler["event_id"]): _compile_handler_v3(handler, self.type_table)
                for handler in raw_entity["handlers"]
            }
            event_types = {
                str(event["event_id"]): tuple(str(value) for value in event["parameters"])
                for event in raw_entity["emitted_events"]
            }
            entity = OptimizedEntityRuntimeV3(
                entity_id,
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
        # Known IDs came from validated IR and need no regex work on every hot
        # invocation. Unknown IDs retain the reference diagnostic precedence.
        entity = self.entities.get(entity_id)
        if entity is None:
            _require_local_id(entity_id, "entity")
            raise TevScriptError("TEVS_IR_V3_ENTITY_UNKNOWN", f"unknown entity {entity_id!r}")

        handler = entity.handlers.get(event_id)
        if handler is not None:
            if len(handler.parameter_types) != len(arguments):
                raise TevScriptError(
                    "TEVS_IR_V3_EVENT_ARITY",
                    f"event {event_id!r} expects {len(handler.parameter_types)} arguments",
                )

            # Closed fast profiles still preserve the external type boundary.
            # Parameter-free handlers need no coercion; the guarded Bool profile
            # validates its one external argument before bypassing VM dispatch.
            if handler.fast_kind == _FAST_RETURN and not arguments:
                self._execute_fast_handler(entity, handler, ())
                return ()
            if handler.fast_kind == _FAST_ADD_STATE_INT_CONST and not arguments:
                self._execute_fast_handler(entity, handler, ())
                return ()
            if (
                handler.fast_kind == _FAST_BOOL_GUARD_ADD_STATE_INT_CONST
                and len(arguments) == 1
            ):
                flag = _coerce_runtime_v3(
                    "Bool",
                    arguments[0],
                    self.type_table,
                    context=f"invoke {entity_id}.{event_id}[0]",
                )
                self._execute_fast_handler(entity, handler, (flag,))
                return ()

            parameter_values = _coerce_parameters(
                entity_id,
                event_id,
                handler.parameter_types,
                arguments,
                self.type_table,
            )

            # A handler that cannot emit cannot create an internal event chain;
            # avoid queue/pending/emitted bookkeeping completely.
            if not handler.can_emit:
                self._execute_handler(entity, handler, parameter_values)
                return ()

            return self._invoke_queued(
                entity,
                entity_id,
                event_id,
                tuple(arguments),
            )

        # A declared emitted event is already a validated local identifier.
        # Only unknown external spellings require the lexical check.
        if event_id not in entity.emitted_event_types:
            _require_local_id(event_id, "event")
        return self._invoke_queued(entity, entity_id, event_id, tuple(arguments))

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

    def _execute_fast_handler(
        self,
        entity: OptimizedEntityRuntimeV3,
        handler: CompiledHandlerV3,
        parameters: tuple[Any, ...],
    ) -> None:
        if handler.fast_kind == _FAST_RETURN:
            return
        if handler.fast_kind == _FAST_ADD_STATE_INT_CONST:
            state_name, constant = handler.fast_operands
            entity.state[state_name] = entity.state[state_name] + constant
            return
        if handler.fast_kind == _FAST_BOOL_GUARD_ADD_STATE_INT_CONST:
            state_name, constant = handler.fast_operands
            if parameters[0] is True:
                entity.state[state_name] = entity.state[state_name] + constant
            return
        raise AssertionError(f"unknown fast handler kind {handler.fast_kind}")

    def _invoke_queued(
        self,
        entity: OptimizedEntityRuntimeV3,
        entity_id: str,
        event_id: str,
        arguments: tuple[Any, ...],
    ) -> tuple[EmittedEventV3, ...]:
        start = len(self.emitted)
        pending: list[tuple[str, tuple[Any, ...]]] = [(event_id, arguments)]
        cursor = 0
        processed = 0

        while cursor < len(pending):
            current_event, raw_arguments = pending[cursor]
            cursor += 1
            processed += 1
            if processed > self.maximum_event_chain:
                raise TevScriptError(
                    "TEVS_IR_V3_EVENT_BUDGET",
                    f"event chain exceeds {self.maximum_event_chain}",
                )

            handler = entity.handlers.get(current_event)
            if handler is None:
                signature = entity.emitted_event_types.get(current_event)
                if signature is None:
                    if raw_arguments:
                        raise TevScriptError(
                            "TEVS_IR_V3_EVENT_SIGNATURE_UNKNOWN",
                            f"unhandled event {current_event!r} has arguments but no portable signature",
                        )
                    signature = ()
                if len(signature) != len(raw_arguments):
                    raise TevScriptError(
                        "TEVS_IR_V3_EVENT_ARITY",
                        f"event {current_event!r} expects {len(signature)} arguments",
                    )
                coerced = tuple(
                    _coerce_runtime_v3(
                        type_id,
                        raw_arguments[index],
                        self.type_table,
                        context=f"invoke {entity_id}.{current_event}[{index}]",
                    )
                    for index, type_id in enumerate(signature)
                )
                self.emitted.append(
                    EmittedEventV3(entity_id, current_event, signature, coerced)
                )
                continue

            if len(handler.parameter_types) != len(raw_arguments):
                raise TevScriptError(
                    "TEVS_IR_V3_EVENT_ARITY",
                    f"event {current_event!r} expects {len(handler.parameter_types)} arguments",
                )
            parameters = _coerce_parameters(
                entity_id,
                current_event,
                handler.parameter_types,
                raw_arguments,
                self.type_table,
            )
            if not parameters and handler.fast_kind in {
                _FAST_RETURN,
                _FAST_ADD_STATE_INT_CONST,
            }:
                self._execute_fast_handler(entity, handler, ())
                generated: Sequence[tuple[str, tuple[str, ...], tuple[Any, ...]]] = ()
            elif (
                handler.fast_kind == _FAST_BOOL_GUARD_ADD_STATE_INT_CONST
                and len(parameters) == 1
            ):
                self._execute_fast_handler(entity, handler, parameters)
                generated = ()
            else:
                generated = self._execute_handler(entity, handler, parameters)

            for generated_event, generated_types, generated_arguments in generated:
                emitted = EmittedEventV3(
                    entity_id,
                    generated_event,
                    generated_types,
                    generated_arguments,
                )
                self.emitted.append(emitted)
                if generated_event in entity.handlers:
                    pending.append((generated_event, generated_arguments))
        return tuple(self.emitted[start:])

    def _execute_handler(
        self,
        entity: OptimizedEntityRuntimeV3,
        handler: CompiledHandlerV3,
        parameters: tuple[Any, ...],
    ) -> Sequence[tuple[str, tuple[str, ...], tuple[Any, ...]]]:
        instructions = handler.instructions
        stack: list[Any] = []
        locals_: list[Any] = (
            [_UNINITIALIZED] * handler.local_count
            if handler.local_count
            else []
        )
        emitted: list[tuple[str, tuple[str, ...], tuple[Any, ...]]] | None = (
            [] if handler.can_emit else None
        )
        pc = 0
        executed = 0

        while pc < len(instructions):
            instruction = instructions[pc]
            if handler.meter_budget:
                executed += instruction.logical_cost
                if executed > handler.instruction_budget:
                    raise TevScriptError(
                        "TEVS_IR_V3_INSTRUCTION_BUDGET",
                        f"handler {handler.event_id!r} exceeded instruction budget {handler.instruction_budget}",
                    )
            op = instruction.opcode
            operands = instruction.operands

            if op == _CONST:
                stack.append(operands[0])
            elif op == _LOAD_STATE:
                stack.append(entity.state[operands[0]])
            elif op == _STORE_STATE:
                entity.state[operands[0]] = stack.pop()
            elif op == _LOAD_LOCAL:
                stack.append(locals_[operands[0]])
            elif op == _STORE_LOCAL:
                locals_[operands[0]] = stack.pop()
            elif op == _LOAD_PARAM:
                stack.append(parameters[operands[0]])
            elif op == _CONVERT_INT_TO_RAT:
                stack.append(Fraction(stack.pop(), 1))
            elif op == _UNARY:
                stack.append(_unary(operands[0], stack.pop()))
            elif op == _ADD_INT:
                right = stack.pop()
                stack.append(stack.pop() + right)
            elif op == _SUB_INT:
                right = stack.pop()
                stack.append(stack.pop() - right)
            elif op == _MUL_INT:
                right = stack.pop()
                stack.append(stack.pop() * right)
            elif op == _BINARY:
                right = stack.pop()
                left = stack.pop()
                stack.append(
                    _binary_v3(
                        operands[0],
                        operands[1],
                        operands[2],
                        left,
                        right,
                        self.type_table,
                    )
                )
            elif op == _CALL_PURE:
                argc = operands[1]
                args = _pop_arguments_fast(stack, argc)
                result = _call_pure(operands[0], args)
                if operands[2]:
                    stack.append(result)
            elif op == _CALL_CAPABILITY:
                capability_id = operands[0]
                capability = self.capabilities.get(capability_id)
                if capability is None:
                    raise TevScriptError(
                        "TEVS_IR_V3_CAPABILITY_MISSING",
                        f"capability {capability_id!r} is not bound",
                    )
                args = _pop_arguments_fast(stack, operands[1])
                result = capability(*args)
                return_type = operands[2]
                if return_type != "Unit":
                    stack.append(
                        _coerce_runtime_v3(
                            return_type,
                            result,
                            self.type_table,
                            context=f"capability {capability_id} return",
                        )
                    )
            elif op == _EMIT_EVENT:
                event_id, argument_types, argc = operands
                args = tuple(_pop_arguments_fast(stack, argc))
                # IR flow validation proves the internal stack types. We retain
                # the reference coercion here for now because event boundaries
                # are externally observable and deserve a separate proof/gate.
                args = tuple(
                    _coerce_runtime_v3(
                        type_id,
                        value,
                        self.type_table,
                        context=f"emit {event_id}[{index}]",
                    )
                    for index, (type_id, value) in enumerate(zip(argument_types, args, strict=True))
                )
                assert emitted is not None
                emitted.append((event_id, argument_types, args))
            elif op == _MAKE_RECORD:
                type_id, canonical_fields, positions, value_count = operands
                values = _pop_arguments_fast(stack, value_count)
                stack.append(
                    RecordValueV3(
                        type_id,
                        tuple(
                            (name, values[position])
                            for name, position in zip(canonical_fields, positions, strict=True)
                        ),
                    )
                )
            elif op == _LOAD_FIELD:
                record = stack.pop()
                if not isinstance(record, RecordValueV3):
                    raise TevScriptError(
                        "TEVS_IR_V3_RUNTIME_RECORD",
                        "LOAD_FIELD received non-record value",
                    )
                stack.append(record.fields[operands[0]][1])
            elif op == _MAKE_VARIANT:
                type_id, variant, argc = operands
                if argc == 0:
                    stack.append(VariantValueV3(type_id, variant))
                else:
                    stack.append(VariantValueV3(type_id, variant, stack.pop()))
            elif op == _TEST_VARIANT:
                value = stack.pop()
                if not isinstance(value, VariantValueV3):
                    raise TevScriptError(
                        "TEVS_IR_V3_RUNTIME_VARIANT",
                        "TEST_VARIANT received non-variant value",
                    )
                stack.append(value.variant == operands[0])
            elif op == _LOAD_VARIANT_PAYLOAD:
                value = stack.pop()
                variant = operands[0]
                if (
                    not isinstance(value, VariantValueV3)
                    or value.variant != variant
                    or not value.has_payload
                ):
                    raise TevScriptError(
                        "TEVS_IR_V3_VARIANT_UNWRAP",
                        f"cannot load payload for variant {variant!r}",
                    )
                stack.append(value.payload)
            elif op == _JUMP_IF_FALSE:
                condition = stack.pop()
                if condition is not True:
                    pc = operands[0]
                    continue
            elif op == _JUMP:
                pc = operands[0]
                continue
            elif op == _ADD_STATE_INT_CONST:
                state_name, constant = operands
                entity.state[state_name] = entity.state[state_name] + constant
            elif op == _RETURN:
                break
            else:  # pragma: no cover - execution plan is internal and closed
                raise AssertionError(f"unknown compiled opcode {op}")
            pc += 1

        if stack:
            raise TevScriptError(
                "TEVS_IR_V3_RUNTIME_STACK_LEAK",
                f"handler {handler.event_id!r} left {len(stack)} values on stack",
            )
        return emitted if emitted is not None else ()


def _coerce_parameters(
    entity_id: str,
    event_id: str,
    parameter_types: tuple[str, ...],
    raw_arguments: Sequence[Any],
    table: TypeTableV3,
) -> tuple[Any, ...]:
    if not parameter_types:
        return ()
    return tuple(
        _coerce_runtime_v3(
            type_id,
            raw_arguments[index],
            table,
            context=f"invoke {entity_id}.{event_id}[{index}]",
        )
        for index, type_id in enumerate(parameter_types)
    )


def _compile_handler_v3(
    handler: Mapping[str, Any],
    table: TypeTableV3,
) -> CompiledHandlerV3:
    parameter_names = tuple(str(value["name"]) for value in handler["parameters"])
    parameter_types = tuple(str(value["type"]) for value in handler["parameters"])
    local_names = tuple(str(value["name"]) for value in handler["locals"])
    parameter_slots = {name: index for index, name in enumerate(parameter_names)}
    local_slots = {name: index for index, name in enumerate(local_names)}
    raw = list(handler["instructions"])
    has_control_flow = any(
        str(instruction["op"]) in {"JUMP", "JUMP_IF_FALSE"}
        for instruction in raw
    )
    compiled: list[CompiledInstructionV3] = []
    pc_map: dict[int, int] = {}
    pending_jumps: list[tuple[int, int]] = []
    index = 0

    while index < len(raw):
        pc_map[index] = len(compiled)

        # Conservative peephole: only straight-line handlers are fused. This
        # prevents any legal jump target from landing inside a fused sequence.
        if not has_control_flow and index + 3 < len(raw):
            a, b, c, d = raw[index:index + 4]
            if (
                a.get("op") == "LOAD_STATE"
                and b.get("op") == "CONST"
                and c.get("op") == "BINARY"
                and d.get("op") == "STORE_STATE"
                and a.get("name") == d.get("name")
                and a.get("type") == d.get("type") == "Int"
                and b.get("type") == "Int"
                and c.get("operator") == "PLUS"
                and c.get("left_type") == c.get("right_type") == c.get("result_type") == "Int"
            ):
                constant = decode_v3_value(
                    "Int",
                    b["value"],
                    table,
                    context=f"instruction {handler['event_id']}:{index + 1}",
                )
                compiled.append(
                    CompiledInstructionV3(
                        _ADD_STATE_INT_CONST,
                        (str(a["name"]), constant),
                        logical_cost=4,
                    )
                )
                for source_pc in range(index + 1, index + 4):
                    pc_map[source_pc] = len(compiled) - 1
                index += 4
                continue

        instruction = raw[index]
        op = str(instruction["op"])
        if op == "CONST":
            compiled.append(
                CompiledInstructionV3(
                    _CONST,
                    (
                        decode_v3_value(
                            str(instruction["type"]),
                            instruction["value"],
                            table,
                            context=f"instruction {handler['event_id']}:{index}",
                        ),
                    ),
                )
            )
        elif op == "LOAD_STATE":
            compiled.append(CompiledInstructionV3(_LOAD_STATE, (str(instruction["name"]),)))
        elif op == "STORE_STATE":
            compiled.append(CompiledInstructionV3(_STORE_STATE, (str(instruction["name"]),)))
        elif op == "LOAD_LOCAL":
            compiled.append(
                CompiledInstructionV3(_LOAD_LOCAL, (local_slots[str(instruction["name"])],))
            )
        elif op == "STORE_LOCAL":
            compiled.append(
                CompiledInstructionV3(_STORE_LOCAL, (local_slots[str(instruction["name"])],))
            )
        elif op == "LOAD_PARAM":
            compiled.append(
                CompiledInstructionV3(_LOAD_PARAM, (parameter_slots[str(instruction["name"])],))
            )
        elif op == "CONVERT_INT_TO_RAT":
            compiled.append(CompiledInstructionV3(_CONVERT_INT_TO_RAT))
        elif op == "UNARY":
            compiled.append(CompiledInstructionV3(_UNARY, (str(instruction["operator"]),)))
        elif op == "BINARY":
            operator = str(instruction["operator"])
            left_type = str(instruction["left_type"])
            right_type = str(instruction["right_type"])
            result_type = str(instruction["result_type"])
            if left_type == right_type == result_type == "Int" and operator == "PLUS":
                compiled.append(CompiledInstructionV3(_ADD_INT))
            elif left_type == right_type == result_type == "Int" and operator == "MINUS":
                compiled.append(CompiledInstructionV3(_SUB_INT))
            elif left_type == right_type == result_type == "Int" and operator == "STAR":
                compiled.append(CompiledInstructionV3(_MUL_INT))
            else:
                compiled.append(
                    CompiledInstructionV3(
                        _BINARY,
                        (operator, left_type, right_type),
                    )
                )
        elif op == "CALL_PURE":
            compiled.append(
                CompiledInstructionV3(
                    _CALL_PURE,
                    (
                        str(instruction["function_id"]),
                        int(instruction["argc"]),
                        str(instruction["return_type"]) != "Unit",
                    ),
                )
            )
        elif op == "CALL_CAPABILITY":
            compiled.append(
                CompiledInstructionV3(
                    _CALL_CAPABILITY,
                    (
                        str(instruction["capability_id"]),
                        int(instruction["argc"]),
                        str(instruction["return_type"]),
                    ),
                )
            )
        elif op == "EMIT_EVENT":
            compiled.append(
                CompiledInstructionV3(
                    _EMIT_EVENT,
                    (
                        str(instruction["event_id"]),
                        tuple(str(value) for value in instruction["argument_types"]),
                        int(instruction["argc"]),
                    ),
                )
            )
        elif op == "MAKE_RECORD":
            type_id = str(instruction["type"])
            descriptor = table.require(type_id)
            fields = tuple(str(value) for value in instruction["fields"])
            canonical_fields = tuple(name for name, _field_type in descriptor.fields)
            positions = tuple(fields.index(name) for name in canonical_fields)
            compiled.append(
                CompiledInstructionV3(
                    _MAKE_RECORD,
                    (type_id, canonical_fields, positions, len(fields)),
                )
            )
        elif op == "LOAD_FIELD":
            record_type = str(instruction["record_type"])
            field = str(instruction["field"])
            descriptor = table.require(record_type)
            field_index = next(
                position
                for position, (name, _type_id) in enumerate(descriptor.fields)
                if name == field
            )
            compiled.append(CompiledInstructionV3(_LOAD_FIELD, (field_index,)))
        elif op == "MAKE_VARIANT":
            compiled.append(
                CompiledInstructionV3(
                    _MAKE_VARIANT,
                    (
                        str(instruction["type"]),
                        str(instruction["variant"]),
                        int(instruction["argc"]),
                    ),
                )
            )
        elif op == "TEST_VARIANT":
            compiled.append(
                CompiledInstructionV3(_TEST_VARIANT, (str(instruction["variant"]),))
            )
        elif op == "LOAD_VARIANT_PAYLOAD":
            compiled.append(
                CompiledInstructionV3(
                    _LOAD_VARIANT_PAYLOAD,
                    (str(instruction["variant"]),),
                )
            )
        elif op == "JUMP_IF_FALSE":
            pending_jumps.append((len(compiled), int(instruction["target"])))
            compiled.append(
                CompiledInstructionV3(_JUMP_IF_FALSE, (int(instruction["target"]),))
            )
        elif op == "JUMP":
            pending_jumps.append((len(compiled), int(instruction["target"])))
            compiled.append(CompiledInstructionV3(_JUMP, (int(instruction["target"]),)))
        elif op == "RETURN":
            compiled.append(CompiledInstructionV3(_RETURN))
        else:  # pragma: no cover - full IR validation rejected this already
            raise AssertionError(op)
        index += 1

    pc_map[len(raw)] = len(compiled)
    for compiled_index, source_target in pending_jumps:
        target = pc_map[source_target]
        previous = compiled[compiled_index]
        compiled[compiled_index] = CompiledInstructionV3(
            previous.opcode,
            (target,),
            previous.logical_cost,
        )

    instructions = tuple(compiled)
    can_emit = any(item.opcode == _EMIT_EVENT for item in instructions)
    fast_kind = _FAST_NONE
    fast_operands: tuple[Any, ...] = ()
    if not parameter_types and not can_emit and not has_control_flow:
        if len(instructions) == 1 and instructions[0].opcode == _RETURN:
            fast_kind = _FAST_RETURN
        elif (
            len(instructions) == 2
            and instructions[0].opcode == _ADD_STATE_INT_CONST
            and instructions[1].opcode == _RETURN
        ):
            # Full validation already proved the original 5-op handler and its
            # instruction budget. The fused instruction retains logical_cost=4
            # and RETURN contributes the fifth logical instruction.
            fast_kind = _FAST_ADD_STATE_INT_CONST
            fast_operands = instructions[0].operands

    if (
        fast_kind == _FAST_NONE
        and parameter_types == ("Bool",)
        and len(local_names) == 0
        and not can_emit
        and len(instructions) == 7
        and tuple(item.opcode for item in instructions)
        == (
            _LOAD_PARAM,
            _JUMP_IF_FALSE,
            _LOAD_STATE,
            _CONST,
            _ADD_INT,
            _STORE_STATE,
            _RETURN,
        )
        and instructions[0].operands == (0,)
        and instructions[1].operands == (6,)
        and instructions[2].operands == instructions[5].operands
        and isinstance(instructions[3].operands[0], int)
    ):
        # Exact lowering of: if flag { state = state + <Int const>; }.
        # External Bool coercion remains in invoke(); this profile only removes
        # the already-validated internal stack/jump machinery.
        fast_kind = _FAST_BOOL_GUARD_ADD_STATE_INT_CONST
        fast_operands = (instructions[2].operands[0], instructions[3].operands[0])

    return CompiledHandlerV3(
        event_id=str(handler["event_id"]),
        parameter_types=parameter_types,
        local_count=len(local_names),
        instructions=instructions,
        instruction_budget=int(handler["instruction_budget"]),
        can_emit=can_emit,
        # Straight-line plans have fixed logical cost equal to the validated
        # source instruction count, so a per-event budget meter is redundant.
        meter_budget=has_control_flow,
        fast_kind=fast_kind,
        fast_operands=fast_operands,
    )


def _pop_arguments_fast(stack: list[Any], count: int) -> list[Any]:
    if count == 0:
        return []
    if len(stack) < count:
        raise TevScriptError(
            "TEVS_IR_V3_STACK_UNDERFLOW",
            "not enough values for operation",
        )
    values = stack[-count:]
    del stack[-count:]
    return values


def _require_local_id(value: str, kind: str) -> None:
    if _LOCAL_ID.fullmatch(value) is None:
        raise TevScriptError(
            "TEVS_IR_V3_INVOCATION_ID",
            f"non-canonical {kind} id {value!r}",
        )
