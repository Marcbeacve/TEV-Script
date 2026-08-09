from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from .canonical import canonical_hash, canonical_json
from .contracts import MAX_EVENT_CHAIN, MAX_INSTRUCTIONS_PER_HANDLER, MAX_LOCALS_PER_HANDLER
from .contracts_v1 import (
    MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER,
    MAX_FLATTENED_BEHAVIORS_PER_ENTITY,
    MAX_PURE_FUNCTION_CALL_DEPTH,
    MAX_STATIC_LOOP_ITERATIONS,
    MAX_TYPE_NESTING,
)
from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_values import (
    RecordValueV3,
    TypeDescriptorV3,
    TypeTableV3,
    VariantValueV3,
    build_type_table_v3,
    encode_v3_value,
)
from .linked_program_v1 import LinkedProgramBundleV1
from .types import CAPABILITIES, PURE_FUNCTIONS, Signature

_BASE_TYPES = ("Bool", "Int", "Rat", "Text", "Unit", "Vec2", "Vec3")
_BINARY_TO_IR = {
    "==": "EQEQ", "!=": "NE", "<": "LT", "<=": "LE", ">": "GT", ">=": "GE",
    "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH",
}
_UNARY_TO_IR = {"not": "NOT", "-": "MINUS"}


@dataclass(frozen=True, slots=True)
class LinkedV1IrV3Bundle:
    ir: dict[str, object]
    canonical_json: str
    linked_semantic_hash: str


@dataclass(frozen=True, slots=True)
class _CapabilityContract:
    capability_id: str
    parameters: tuple[str, ...]
    return_type: str
    kind: str


@dataclass(frozen=True, slots=True)
class _Binding:
    kind: str
    type_id: str
    ir_name: str | None = None
    constant: object | None = None


@dataclass(frozen=True, slots=True)
class _Fragment:
    component_id: str
    component_kind: str
    handler: dict[str, object]


@dataclass(slots=True)
class _Scope:
    states: dict[str, _Binding]
    frames: list[dict[str, _Binding]] = field(default_factory=list)

    def push(self) -> None:
        self.frames.append({})

    def pop(self) -> None:
        self.frames.pop()

    def declare(self, name: str, binding: _Binding) -> None:
        if name in self.states or any(name in frame for frame in self.frames):
            raise TevScriptError(
                "TEVS_V1_IRV3_LOWER_SHADOW",
                f"linked program contains shadowing for {name!r}",
            )
        if not self.frames:
            self.push()
        self.frames[-1][name] = binding

    def lookup(self, name: str) -> _Binding | None:
        for frame in reversed(self.frames):
            if name in frame:
                return frame[name]
        return self.states.get(name)


@dataclass(slots=True)
class _Emitter:
    functions: dict[str, dict[str, object]]
    capabilities: dict[str, _CapabilityContract]
    type_table: TypeTableV3
    event_id: str
    instructions: list[dict[str, object]] = field(default_factory=list)
    locals: dict[str, str] = field(default_factory=dict)
    used_names: set[str] = field(default_factory=set)
    used_capabilities: dict[str, _CapabilityContract] = field(default_factory=dict)
    emitted_events: dict[str, tuple[str, ...]] = field(default_factory=dict)
    fragment_trace: list[dict[str, object]] = field(default_factory=list)
    local_counter: int = 0
    statement_counter: int = 0

    def emit(self, instruction: dict[str, object], *, component_id: str) -> int:
        index = len(self.instructions)
        self.instructions.append(instruction)
        self.fragment_trace.append({"instruction": index, "component_id": component_id})
        if len(self.instructions) > MAX_INSTRUCTIONS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_IRV3_LOWER_INSTRUCTION_BUDGET",
                f"lowered handler exceeds {MAX_INSTRUCTIONS_PER_HANDLER} instructions",
            )
        return index

    def allocate_local(self, type_id: str) -> str:
        _require_storable(self.type_table, type_id, "local")
        while True:
            candidate = f"_tev_l{self.local_counter}"
            self.local_counter += 1
            if candidate not in self.used_names:
                break
        self.used_names.add(candidate)
        self.locals[candidate] = type_id
        if len(self.locals) > MAX_LOCALS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_IRV3_LOWER_LOCAL_BUDGET",
                f"lowered handler exceeds {MAX_LOCALS_PER_HANDLER} locals",
            )
        return candidate

    def count_statement(self) -> None:
        self.statement_counter += 1
        if self.statement_counter > MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_IRV3_LOWER_STATEMENT_BUDGET",
                f"expanded handler exceeds {MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER} statement nodes",
            )


def lower_linked_program_v1_to_ir_v3(
    linked: LinkedProgramBundleV1 | dict[str, object],
) -> LinkedV1IrV3Bundle:
    if isinstance(linked, LinkedProgramBundleV1):
        program = linked.program
        linked_hash = linked.semantic_hash
    else:
        program = linked
        linked_hash = str(program.get("semantic_hash", ""))
    _verify_linked_identity(program, linked_hash)

    broad_types = _build_broad_type_table(program)
    functions = {str(item["function_id"]): item for item in _array(program, "functions")}
    behaviors = {str(item["behavior_id"]): item for item in _array(program, "behaviors")}
    capabilities = _build_capability_catalog(program, broad_types)

    entities: list[dict[str, object]] = []
    debug_entities: list[dict[str, object]] = []
    for entity in sorted(_array(program, "entities"), key=lambda item: str(item["entity_id"])):
        semantic_entity, debug_entity = _lower_entity(
            entity,
            behaviors,
            functions,
            capabilities,
            broad_types,
        )
        entities.append(semantic_entity)
        debug_entities.append(debug_entity)

    type_descriptors = _runtime_type_descriptors(entities, broad_types)
    semantic: dict[str, object] = {
        "schema": "TEV_SCRIPT_PROGRAM_IR_V3",
        "language_version": "1.0.0",
        "lowering_profile": "TEV_SCRIPT_V1_IR_V3_PROFILE_V1",
        "source_schema": "TEV_SCRIPT_LINKED_PROGRAM_V1",
        "source_semantic_hash": linked_hash,
        "program_id": str(program["program_id"]),
        "types": type_descriptors,
        "entities": entities,
        "boundary": {
            "dynamic_code": False,
            "reflection": False,
            "unbounded_loops": False,
            "implicit_physical_effects": False,
            "runtime_source_compilation": False,
            "automatic_authority_escalation": False,
            "host_object_references": False,
            "maximum_event_chain": MAX_EVENT_CHAIN,
            "maximum_value_nesting": MAX_TYPE_NESTING,
        },
    }
    ir = dict(semantic)
    ir["semantic_hash"] = canonical_hash(semantic)
    debug = {
        "source_path": "<TEV_SCRIPT_LINKED_PROGRAM_V1>",
        "source_semantic_hash": linked_hash,
        "entities": debug_entities,
    }
    ir["debug"] = debug
    ir["debug_hash"] = canonical_hash(debug)
    validate_program_ir_v3(ir, expected_source_semantic_hash=linked_hash)
    return LinkedV1IrV3Bundle(ir, canonical_json(ir), linked_hash)


def _verify_linked_identity(program: dict[str, object], expected_hash: str) -> None:
    if program.get("schema") != "TEV_SCRIPT_LINKED_PROGRAM_V1" or program.get("language_version") != "1.0.0":
        raise TevScriptError("TEVS_V1_IRV3_LOWER_SOURCE", "expected canonical TEV_SCRIPT_LINKED_PROGRAM_V1 / 1.0.0")
    stored_hash = str(program.get("semantic_hash", ""))
    semantic = {key: value for key, value in program.items() if key != "semantic_hash"}
    actual = canonical_hash(semantic)
    if stored_hash != actual or expected_hash != actual:
        raise TevScriptError(
            "TEVS_V1_IRV3_LOWER_SOURCE_HASH",
            "linked program semantic hash does not match content",
        )


def _lower_entity(
    entity: dict[str, object],
    behaviors: dict[str, dict[str, object]],
    functions: dict[str, dict[str, object]],
    capabilities: dict[str, _CapabilityContract],
    type_table: TypeTableV3,
) -> tuple[dict[str, object], dict[str, object]]:
    entity_id = str(entity["entity_id"])
    flattened = _flatten_behaviors(
        tuple(str(item) for item in _array(entity, "uses")),
        behaviors,
        owner_label=f"entity {entity_id!r}",
    )

    states: list[dict[str, object]] = []
    state_types: dict[str, str] = {}
    for behavior_id in flattened:
        for state in _array(behaviors[behavior_id], "states"):
            _add_runtime_state(states, state_types, state, behavior_id, type_table)
    for state in _array(entity, "states"):
        _add_runtime_state(states, state_types, state, entity_id, type_table)
    states.sort(key=lambda item: str(item["name"]))

    fragments: list[_Fragment] = []
    for behavior_id in flattened:
        for handler in _array(behaviors[behavior_id], "handlers"):
            fragments.append(_Fragment(behavior_id, "behavior", handler))
    for handler in _array(entity, "handlers"):
        fragments.append(_Fragment(entity_id, "entity", handler))

    by_event: dict[str, list[_Fragment]] = {}
    for fragment in fragments:
        by_event.setdefault(str(fragment.handler["event_id"]), []).append(fragment)

    event_signatures: dict[str, tuple[str, ...]] = {}
    for event_id, event_fragments in by_event.items():
        signatures = {
            tuple(str(item["type"]) for item in _array(fragment.handler, "parameters"))
            for fragment in event_fragments
        }
        if len(signatures) != 1:
            raise TevScriptError(
                "TEVS_V1_IRV3_LOWER_HANDLER_SIGNATURE",
                f"composed event {event_id!r} has conflicting signatures",
            )
        signature = next(iter(signatures))
        for type_id in signature:
            _require_storable(type_table, type_id, f"event {event_id} parameter")
        event_signatures[event_id] = signature

    handlers: list[dict[str, object]] = []
    debug_handlers: list[dict[str, object]] = []
    entity_capabilities: dict[str, _CapabilityContract] = {}
    entity_emitted: dict[str, tuple[str, ...]] = {}

    for event_id in sorted(by_event):
        event_fragments = by_event[event_id]
        signature = event_signatures[event_id]
        parameter_names = _canonical_parameter_names(len(signature), set(state_types))
        emitter = _Emitter(functions, capabilities, type_table, event_id)
        emitter.used_names.update(state_types)
        emitter.used_names.update(parameter_names)
        state_bindings = {
            name: _Binding("state", type_id, ir_name=name)
            for name, type_id in state_types.items()
        }

        for fragment in event_fragments:
            scope = _Scope(states=state_bindings)
            scope.push()
            for parameter, canonical_name, type_id in zip(
                _array(fragment.handler, "parameters"), parameter_names, signature, strict=True
            ):
                scope.declare(str(parameter["name"]), _Binding("param", type_id, ir_name=canonical_name))
            _lower_statements(
                _array(fragment.handler, "body"), emitter, scope,
                component_id=fragment.component_id,
                component_kind=fragment.component_kind,
                event_signatures=event_signatures,
                call_depth=0,
            )

        if not emitter.instructions or emitter.instructions[-1]["op"] != "RETURN":
            emitter.emit({"op": "RETURN"}, component_id=event_fragments[-1].component_id)

        handlers.append(
            {
                "event_id": event_id,
                "parameters": [
                    {"name": name, "type": type_id}
                    for name, type_id in zip(parameter_names, signature, strict=True)
                ],
                "locals": [
                    {"name": name, "type": type_id}
                    for name, type_id in sorted(emitter.locals.items())
                ],
                "instructions": emitter.instructions,
                "instruction_budget": MAX_INSTRUCTIONS_PER_HANDLER,
            }
        )
        debug_handlers.append(
            {
                "event_id": event_id,
                "fragment_order": [fragment.component_id for fragment in event_fragments],
                "instruction_origins": emitter.fragment_trace,
            }
        )
        for capability_id, contract in emitter.used_capabilities.items():
            previous = entity_capabilities.get(capability_id)
            if previous is not None and previous != contract:
                raise TevScriptError("TEVS_V1_IRV3_LOWER_CAPABILITY_CONFLICT", f"conflicting capability {capability_id!r}")
            entity_capabilities[capability_id] = contract
        for emitted_event, emitted_signature in emitter.emitted_events.items():
            previous = entity_emitted.get(emitted_event)
            if previous is not None and previous != emitted_signature:
                raise TevScriptError("TEVS_V1_IRV3_LOWER_EVENT_SIGNATURE", f"conflicting event {emitted_event!r}")
            entity_emitted[emitted_event] = emitted_signature

    return (
        {
            "entity_id": entity_id,
            "states": states,
            "handlers": handlers,
            "capabilities": [
                {
                    "capability_id": capability_id,
                    "parameters": list(contract.parameters),
                    "return_type": contract.return_type,
                    "kind": contract.kind,
                }
                for capability_id, contract in sorted(entity_capabilities.items())
            ],
            "emitted_events": [
                {"event_id": event_id, "parameters": list(signature)}
                for event_id, signature in sorted(entity_emitted.items())
            ],
        },
        {
            "entity_id": entity_id,
            "flattened_behaviors": list(flattened),
            "handlers": debug_handlers,
        },
    )


def _add_runtime_state(
    entries: list[dict[str, object]],
    state_types: dict[str, str],
    state: dict[str, object],
    component_id: str,
    table: TypeTableV3,
) -> None:
    name = str(state["name"])
    type_id = str(state["type"])
    _require_storable(table, type_id, f"state {name}")
    if name in state_types:
        raise TevScriptError(
            "TEVS_V1_IRV3_LOWER_STATE_CONFLICT",
            f"duplicate composed state {name!r} while expanding {component_id}",
        )
    state_types[name] = type_id
    value = _constant_semantic_value(state["initial"], type_id, table)
    entries.append({"name": name, "type": type_id, "initial": encode_v3_value(type_id, value, table)})


def _lower_statements(
    statements: list[dict[str, object]],
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    component_kind: str,
    event_signatures: dict[str, tuple[str, ...]],
    call_depth: int,
) -> None:
    for statement in statements:
        emitter.count_statement()
        kind = statement.get("kind")
        if kind == "let":
            type_id = str(statement["type"])
            _require_storable(emitter.type_table, type_id, "local")
            _emit_expr(statement["value"], emitter, scope, component_id=component_id, expected_type=type_id, call_depth=call_depth)
            local_name = emitter.allocate_local(type_id)
            emitter.emit({"op":"STORE_LOCAL","name":local_name,"type":type_id}, component_id=component_id)
            scope.declare(str(statement["name"]), _Binding("local", type_id, ir_name=local_name))
            continue
        if kind == "assign":
            state_name = str(statement["state"])
            binding = scope.states.get(state_name)
            if binding is None:
                raise TevScriptError("TEVS_V1_IRV3_LOWER_STATE_UNKNOWN", f"unknown composed state {state_name!r}")
            _emit_expr(statement["value"], emitter, scope, component_id=component_id, expected_type=binding.type_id, call_depth=call_depth)
            emitter.emit({"op":"STORE_STATE","name":state_name,"type":binding.type_id}, component_id=component_id)
            continue
        if kind == "call":
            capability_id = str(statement["capability_id"])
            contract = _require_capability(emitter, capability_id)
            if contract.return_type != "Unit":
                raise TevScriptError("TEVS_V1_IRV3_LOWER_CALL_RESULT_UNUSED", f"call {capability_id!r} returns {contract.return_type}")
            _emit_arguments(_array(statement, "arguments"), contract.parameters, emitter, scope, component_id=component_id, call_depth=call_depth)
            _register_capability(emitter, contract)
            emitter.emit({"op":"CALL_CAPABILITY","capability_id":capability_id,"argc":len(contract.parameters),"return_type":"Unit","kind":contract.kind}, component_id=component_id)
            continue
        if kind == "emit":
            event_id = str(statement["event_id"])
            arguments = _array(statement, "arguments")
            expected = event_signatures.get(event_id)
            if expected is None:
                signature = tuple(_expr_type(item) for item in arguments)
                for type_id in signature:
                    _require_storable(emitter.type_table, type_id, f"event {event_id}")
                for argument in arguments:
                    _emit_expr(argument, emitter, scope, component_id=component_id, expected_type=None, call_depth=call_depth)
            else:
                signature = expected
                _emit_arguments(arguments, expected, emitter, scope, component_id=component_id, call_depth=call_depth)
            previous = emitter.emitted_events.get(event_id)
            if previous is not None and previous != signature:
                raise TevScriptError("TEVS_V1_IRV3_LOWER_EVENT_SIGNATURE", f"event {event_id!r} signature conflict")
            emitter.emitted_events[event_id] = signature
            emitter.emit({"op":"EMIT_EVENT","event_id":event_id,"argument_types":list(signature),"argc":len(signature)}, component_id=component_id)
            continue
        if kind == "if":
            _emit_expr(statement["condition"], emitter, scope, component_id=component_id, expected_type="Bool", call_depth=call_depth)
            jump_false = emitter.emit({"op":"JUMP_IF_FALSE","target":-1}, component_id=component_id)
            scope.push()
            try:
                _lower_statements(_array(statement, "then"), emitter, scope, component_id=component_id, component_kind=component_kind, event_signatures=event_signatures, call_depth=call_depth)
            finally:
                scope.pop()
            else_body = _array(statement, "else")
            if else_body:
                jump_end = emitter.emit({"op":"JUMP","target":-1}, component_id=component_id)
                emitter.instructions[jump_false]["target"] = len(emitter.instructions)
                scope.push()
                try:
                    _lower_statements(else_body, emitter, scope, component_id=component_id, component_kind=component_kind, event_signatures=event_signatures, call_depth=call_depth)
                finally:
                    scope.pop()
                emitter.instructions[jump_end]["target"] = len(emitter.instructions)
            else:
                emitter.instructions[jump_false]["target"] = len(emitter.instructions)
            continue
        if kind == "for":
            lower = int(str(statement["lower"]))
            upper = int(str(statement["upper"]))
            iterations = upper - lower
            if iterations < 0 or iterations > MAX_STATIC_LOOP_ITERATIONS:
                raise TevScriptError("TEVS_V1_IRV3_LOWER_FOR_BUDGET", f"invalid for range {lower}..{upper}")
            variable = str(statement["variable"])
            for value in range(lower, upper):
                scope.push()
                try:
                    scope.declare(variable, _Binding("constant", "Int", constant=value))
                    _lower_statements(_array(statement, "body"), emitter, scope, component_id=component_id, component_kind=component_kind, event_signatures=event_signatures, call_depth=call_depth)
                finally:
                    scope.pop()
            continue
        if kind == "match":
            _lower_match(statement, emitter, scope, component_id=component_id, component_kind=component_kind, event_signatures=event_signatures, call_depth=call_depth)
            continue
        if kind == "return":
            if component_kind == "behavior":
                raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_RETURN", "behavior fragment cannot return")
            emitter.emit({"op":"RETURN"}, component_id=component_id)
            continue
        raise TevScriptError("TEVS_V1_IRV3_LOWER_STATEMENT_KIND", f"unsupported linked statement kind {kind!r}")


def _lower_match(
    statement: dict[str, object],
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    component_kind: str,
    event_signatures: dict[str, tuple[str, ...]],
    call_depth: int,
) -> None:
    value_expr = statement["value"]
    type_id = _expr_type(value_expr)
    _require_variant_type(emitter.type_table, type_id)
    _emit_expr(value_expr, emitter, scope, component_id=component_id, expected_type=type_id, call_depth=call_depth)
    scrutinee = emitter.allocate_local(type_id)
    emitter.emit({"op":"STORE_LOCAL","name":scrutinee,"type":type_id}, component_id=component_id)
    arms = _array(statement, "arms")
    if not arms:
        raise TevScriptError("TEVS_V1_IRV3_LOWER_MATCH", "match requires at least one arm")
    end_jumps: list[int] = []

    for index, arm in enumerate(arms):
        pattern = _object(arm.get("pattern"), "match.pattern")
        variant = _pattern_variant(pattern)
        payload_type = emitter.type_table.variant_payload_type(type_id, variant)
        is_last = index == len(arms) - 1
        if not is_last:
            emitter.emit({"op":"LOAD_LOCAL","name":scrutinee,"type":type_id}, component_id=component_id)
            emitter.emit({"op":"TEST_VARIANT","type":type_id,"variant":variant}, component_id=component_id)
            jump_next = emitter.emit({"op":"JUMP_IF_FALSE","target":-1}, component_id=component_id)
        else:
            jump_next = -1

        scope.push()
        try:
            binding_name = pattern.get("binding")
            if binding_name is not None:
                if payload_type is None:
                    raise TevScriptError("TEVS_V1_IRV3_LOWER_MATCH", f"payload-free variant {variant!r} cannot bind")
                emitter.emit({"op":"LOAD_LOCAL","name":scrutinee,"type":type_id}, component_id=component_id)
                emitter.emit({"op":"LOAD_VARIANT_PAYLOAD","type":type_id,"variant":variant,"payload_type":payload_type}, component_id=component_id)
                local_name = emitter.allocate_local(payload_type)
                emitter.emit({"op":"STORE_LOCAL","name":local_name,"type":payload_type}, component_id=component_id)
                scope.declare(str(binding_name), _Binding("local", payload_type, ir_name=local_name))
            _lower_statements(
                _array(arm, "body"), emitter, scope,
                component_id=component_id, component_kind=component_kind,
                event_signatures=event_signatures, call_depth=call_depth,
            )
        finally:
            scope.pop()

        arm_terminates = bool(emitter.instructions and emitter.instructions[-1]["op"] == "RETURN")
        if not is_last and not arm_terminates:
            end_jumps.append(emitter.emit({"op":"JUMP","target":-1}, component_id=component_id))
        if jump_next >= 0:
            emitter.instructions[jump_next]["target"] = len(emitter.instructions)

    end_target = len(emitter.instructions)
    for jump in end_jumps:
        emitter.instructions[jump]["target"] = end_target


def _emit_expr(
    expression: object,
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    expected_type: str | None,
    call_depth: int,
) -> str:
    expr = _object(expression, "expression")
    kind = expr.get("kind")
    actual_type = _expr_type(expr)
    _require_storable(emitter.type_table, actual_type, "runtime expression")

    if kind == "bool":
        emitter.emit({"op":"CONST","type":"Bool","value":bool(expr["value"])}, component_id=component_id)
    elif kind == "int":
        emitter.emit({"op":"CONST","type":"Int","value":{"$int":str(expr["value"])}}, component_id=component_id)
    elif kind == "rat":
        value = Fraction(int(str(expr["numerator"])), int(str(expr["denominator"])))
        emitter.emit({"op":"CONST","type":"Rat","value":{"$rat":[str(value.numerator),str(value.denominator)]}}, component_id=component_id)
    elif kind == "text":
        emitter.emit({"op":"CONST","type":"Text","value":str(expr["value"])}, component_id=component_id)
    elif kind == "name":
        symbol_id = str(expr["symbol_id"])
        binding = scope.lookup(symbol_id)
        if binding is None or binding.type_id != actual_type:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_VALUE", f"unknown/mismatched binding {symbol_id!r}")
        if binding.kind == "constant":
            emitter.emit({"op":"CONST","type":"Int","value":{"$int":str(binding.constant)}}, component_id=component_id)
        else:
            op = {"state":"LOAD_STATE","param":"LOAD_PARAM","local":"LOAD_LOCAL"}.get(binding.kind)
            if op is None or binding.ir_name is None:
                raise AssertionError(binding)
            emitter.emit({"op":op,"name":binding.ir_name,"type":binding.type_id}, component_id=component_id)
    elif kind == "field":
        target = _object(expr["target"], "field.target")
        record_type = _expr_type(target)
        descriptor = emitter.type_table.require(record_type)
        if descriptor.kind != "record":
            raise TevScriptError("TEVS_V1_IRV3_LOWER_FIELD", f"{record_type!r} is not record")
        field_name = str(expr["field"])
        result_type = descriptor.field_type(field_name)
        if result_type != actual_type:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_FIELD", f"field {field_name!r} type mismatch")
        _emit_expr(target, emitter, scope, component_id=component_id, expected_type=record_type, call_depth=call_depth)
        emitter.emit({"op":"LOAD_FIELD","record_type":record_type,"field":field_name,"result_type":actual_type}, component_id=component_id)
    elif kind == "record":
        descriptor = emitter.type_table.require(actual_type)
        if descriptor.kind != "record":
            raise TevScriptError("TEVS_V1_IRV3_LOWER_RECORD", f"{actual_type!r} is not record")
        fields = _array(expr, "fields")
        names: list[str] = []
        expected_fields = {name:type_id for name,type_id in descriptor.fields}
        for field in fields:
            name = str(field["name"])
            if name not in expected_fields or name in names:
                raise TevScriptError("TEVS_V1_IRV3_LOWER_RECORD", f"invalid record field {name!r}")
            names.append(name)
            _emit_expr(field["value"], emitter, scope, component_id=component_id, expected_type=expected_fields[name], call_depth=call_depth)
        if set(names) != set(expected_fields):
            raise TevScriptError("TEVS_V1_IRV3_LOWER_RECORD", "record constructor field set mismatch")
        emitter.emit({"op":"MAKE_RECORD","type":actual_type,"fields":names}, component_id=component_id)
    elif kind == "enum":
        variant = str(expr["variant"])
        emitter.type_table.variant_payload_type(actual_type, variant)
        emitter.emit({"op":"MAKE_VARIANT","type":actual_type,"variant":variant,"argc":0}, component_id=component_id)
    elif kind in {"some", "none", "ok", "err"}:
        variant = {"some":"Some","none":"None","ok":"Ok","err":"Err"}[str(kind)]
        payload_type = emitter.type_table.variant_payload_type(actual_type, variant)
        if payload_type is None:
            emitter.emit({"op":"MAKE_VARIANT","type":actual_type,"variant":variant,"argc":0}, component_id=component_id)
        else:
            _emit_expr(expr["value"], emitter, scope, component_id=component_id, expected_type=payload_type, call_depth=call_depth)
            emitter.emit({"op":"MAKE_VARIANT","type":actual_type,"variant":variant,"argc":1}, component_id=component_id)
    elif kind == "unary":
        _emit_expr(expr["operand"], emitter, scope, component_id=component_id, expected_type=None, call_depth=call_depth)
        operator = str(expr["operator"])
        if operator not in _UNARY_TO_IR:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_UNARY", f"unsupported unary {operator!r}")
        emitter.emit({"op":"UNARY","operator":_UNARY_TO_IR[operator],"type":actual_type}, component_id=component_id)
    elif kind == "binary":
        operator = str(expr["operator"])
        if operator in {"and", "or"}:
            _emit_short_circuit(expr, emitter, scope, component_id=component_id, call_depth=call_depth)
        else:
            _emit_binary(expr, emitter, scope, component_id=component_id, call_depth=call_depth)
    elif kind == "call":
        _emit_call_expr(expr, emitter, scope, component_id=component_id, call_depth=call_depth)
    else:
        raise TevScriptError("TEVS_V1_IRV3_LOWER_EXPRESSION_KIND", f"unsupported expression kind {kind!r}")

    if expected_type is None or actual_type == expected_type:
        return actual_type
    if actual_type == "Int" and expected_type == "Rat":
        emitter.emit({"op":"CONVERT_INT_TO_RAT"}, component_id=component_id)
        return "Rat"
    raise TevScriptError("TEVS_V1_IRV3_LOWER_TYPE", f"expected {expected_type}, got {actual_type}")


def _emit_binary(expr: dict[str, object], emitter: _Emitter, scope: _Scope, *, component_id: str, call_depth: int) -> None:
    operator = str(expr["operator"])
    if operator not in _BINARY_TO_IR:
        raise TevScriptError("TEVS_V1_IRV3_LOWER_BINARY", f"unsupported binary {operator!r}")
    left, right = expr["left"], expr["right"]
    left_type, right_type, result_type = _expr_type(left), _expr_type(right), str(expr["type"])
    left_expected, right_expected = _binary_operand_types(operator, left_type, right_type, result_type)
    _emit_expr(left, emitter, scope, component_id=component_id, expected_type=left_expected, call_depth=call_depth)
    _emit_expr(right, emitter, scope, component_id=component_id, expected_type=right_expected, call_depth=call_depth)
    emitter.emit({"op":"BINARY","operator":_BINARY_TO_IR[operator],"left_type":left_expected,"right_type":right_expected,"result_type":result_type}, component_id=component_id)


def _emit_short_circuit(expr: dict[str, object], emitter: _Emitter, scope: _Scope, *, component_id: str, call_depth: int) -> None:
    temporary = emitter.allocate_local("Bool")
    _emit_expr(expr["left"], emitter, scope, component_id=component_id, expected_type="Bool", call_depth=call_depth)
    emitter.emit({"op":"STORE_LOCAL","name":temporary,"type":"Bool"}, component_id=component_id)
    emitter.emit({"op":"LOAD_LOCAL","name":temporary,"type":"Bool"}, component_id=component_id)
    jump_false = emitter.emit({"op":"JUMP_IF_FALSE","target":-1}, component_id=component_id)
    operator = str(expr["operator"])
    if operator == "and":
        _emit_expr(expr["right"], emitter, scope, component_id=component_id, expected_type="Bool", call_depth=call_depth)
        emitter.emit({"op":"STORE_LOCAL","name":temporary,"type":"Bool"}, component_id=component_id)
        emitter.instructions[jump_false]["target"] = len(emitter.instructions)
    elif operator == "or":
        jump_end = emitter.emit({"op":"JUMP","target":-1}, component_id=component_id)
        emitter.instructions[jump_false]["target"] = len(emitter.instructions)
        _emit_expr(expr["right"], emitter, scope, component_id=component_id, expected_type="Bool", call_depth=call_depth)
        emitter.emit({"op":"STORE_LOCAL","name":temporary,"type":"Bool"}, component_id=component_id)
        emitter.instructions[jump_end]["target"] = len(emitter.instructions)
    else:
        raise AssertionError(operator)
    emitter.emit({"op":"LOAD_LOCAL","name":temporary,"type":"Bool"}, component_id=component_id)


def _emit_call_expr(expr: dict[str, object], emitter: _Emitter, scope: _Scope, *, component_id: str, call_depth: int) -> None:
    callable_kind = str(expr["callable_kind"])
    callable_id = str(expr["callable_id"])
    arguments = _array(expr, "arguments")
    result_type = str(expr["type"])
    if callable_kind == "pure_function" and callable_id in emitter.functions:
        if call_depth >= MAX_PURE_FUNCTION_CALL_DEPTH:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_FUNCTION_DEPTH", "pure function inlining depth exceeded")
        function = emitter.functions[callable_id]
        parameters = _array(function, "parameters")
        if len(arguments) != len(parameters):
            raise TevScriptError("TEVS_V1_IRV3_LOWER_CALL_SIGNATURE", f"function {callable_id!r} arity mismatch")
        temporaries: list[tuple[str,str]] = []
        for argument, parameter in zip(arguments, parameters, strict=True):
            parameter_type = str(parameter["type"])
            _emit_expr(argument, emitter, scope, component_id=component_id, expected_type=parameter_type, call_depth=call_depth)
            temporary = emitter.allocate_local(parameter_type)
            emitter.emit({"op":"STORE_LOCAL","name":temporary,"type":parameter_type}, component_id=component_id)
            temporaries.append((temporary, parameter_type))
        function_scope = _Scope(states={})
        function_scope.push()
        for parameter, (temporary, type_id) in zip(parameters, temporaries, strict=True):
            function_scope.declare(str(parameter["name"]), _Binding("local", type_id, ir_name=temporary))
        return_type = str(function["return_type"])
        _emit_expr(function["body"], emitter, function_scope, component_id=callable_id, expected_type=return_type, call_depth=call_depth+1)
        if result_type != return_type:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_CALL_RESULT", f"function {callable_id!r} result mismatch")
        return
    if callable_kind == "pure_function":
        signature = _select_builtin_pure_signature(callable_id, tuple(_expr_type(item) for item in arguments), result_type)
        _emit_arguments(arguments, signature.parameters, emitter, scope, component_id=component_id, call_depth=call_depth)
        emitter.emit({"op":"CALL_PURE","function_id":callable_id,"argc":len(arguments),"return_type":result_type}, component_id=component_id)
        return
    if callable_kind == "observation_capability":
        contract = _require_capability(emitter, callable_id)
        if contract.kind != "observation" or contract.return_type != result_type:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_CAPABILITY_EXPR", f"invalid observation {callable_id!r}")
        _emit_arguments(arguments, contract.parameters, emitter, scope, component_id=component_id, call_depth=call_depth)
        _register_capability(emitter, contract)
        emitter.emit({"op":"CALL_CAPABILITY","capability_id":callable_id,"argc":len(arguments),"return_type":result_type,"kind":"observation"}, component_id=component_id)
        return
    raise TevScriptError("TEVS_V1_IRV3_LOWER_CALL_KIND", f"unsupported callable kind {callable_kind!r}")


def _emit_arguments(arguments: list[dict[str, object]], parameters: tuple[str, ...], emitter: _Emitter, scope: _Scope, *, component_id: str, call_depth: int) -> None:
    if len(arguments) != len(parameters):
        raise TevScriptError("TEVS_V1_IRV3_LOWER_CALL_SIGNATURE", f"expected {len(parameters)} arguments, got {len(arguments)}")
    for argument, type_id in zip(arguments, parameters, strict=True):
        _emit_expr(argument, emitter, scope, component_id=component_id, expected_type=type_id, call_depth=call_depth)


def _constant_semantic_value(expression: object, expected_type: str, table: TypeTableV3) -> object:
    expr = _object(expression, "state.initial")
    if str(expr.get("type")) != expected_type:
        raise TevScriptError("TEVS_V1_IRV3_LOWER_CONSTANT", f"constant expected {expected_type}, got {expr.get('type')!r}")
    kind = expr.get("kind")
    if kind == "bool": return bool(expr["value"])
    if kind == "int": return int(str(expr["value"]))
    if kind == "rat": return Fraction(int(str(expr["numerator"])), int(str(expr["denominator"])))
    if kind == "text": return str(expr["value"])
    if kind == "call" and expected_type in {"Vec2","Vec3"}:
        function_id = "vec2" if expected_type == "Vec2" else "vec3"
        if expr.get("callable_kind") != "pure_function" or expr.get("callable_id") != function_id:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_CONSTANT", f"invalid {expected_type} constant")
        return tuple(_constant_semantic_value(item, "Rat", table) for item in _array(expr, "arguments"))
    descriptor = table.require(expected_type)
    if kind == "record" and descriptor.kind == "record":
        by_name = {
            str(field["name"]): _constant_semantic_value(field["value"], descriptor.field_type(str(field["name"])) or "", table)
            for field in _array(expr, "fields")
        }
        if set(by_name) != {name for name,_ in descriptor.fields}:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_CONSTANT", "record constant field set mismatch")
        return RecordValueV3(expected_type, tuple((name, by_name[name]) for name,_ in descriptor.fields))
    if kind == "enum" and descriptor.kind == "enum":
        variant = str(expr["variant"])
        table.variant_payload_type(expected_type, variant)
        return VariantValueV3(expected_type, variant)
    variant = {"some":"Some","none":"None","ok":"Ok","err":"Err"}.get(str(kind))
    if variant is not None:
        payload_type = table.variant_payload_type(expected_type, variant)
        if payload_type is None:
            return VariantValueV3(expected_type, variant)
        return VariantValueV3(expected_type, variant, _constant_semantic_value(expr["value"], payload_type, table))
    raise TevScriptError("TEVS_V1_IRV3_LOWER_CONSTANT", f"unsupported constant {kind!r}/{expected_type}")


def _build_broad_type_table(program: dict[str, object]) -> TypeTableV3:
    descriptors: dict[str, dict[str, object]] = {
        type_id: {"type_id":type_id,"kind":"unit" if type_id=="Unit" else "primitive"}
        for type_id in _BASE_TYPES
    }
    for record in _array(program, "records"):
        type_id = str(record["type_id"])
        descriptors[type_id] = {
            "type_id":type_id,"kind":"record",
            "fields":[{"name":str(field["name"]),"type":str(field["type"])} for field in _array(record,"fields")],
        }
    for enum in _array(program, "enums"):
        type_id = str(enum["type_id"])
        descriptors[type_id] = {"type_id":type_id,"kind":"enum","variants":[str(value) for value in _array(enum,"variants")]}

    referenced = _collect_type_ids(program)
    queue = list(referenced)
    while queue:
        type_id = queue.pop()
        if type_id in descriptors:
            continue
        parsed = _parse_constructed_type(type_id)
        if parsed is None:
            raise TevScriptError("TEVS_V1_IRV3_LOWER_TYPE_UNKNOWN", f"unknown linked type {type_id!r}")
        kind, arguments = parsed
        if kind == "option":
            descriptors[type_id] = {"type_id":type_id,"kind":"option","argument":arguments[0]}
        else:
            descriptors[type_id] = {"type_id":type_id,"kind":"result","ok_type":arguments[0],"err_type":arguments[1]}
        for child in arguments:
            if child not in descriptors:
                queue.append(child)

    synthetic = {
        "boundary":{"maximum_value_nesting":MAX_TYPE_NESTING},
        "types":[descriptors[type_id] for type_id in sorted(descriptors)],
    }
    return build_type_table_v3(synthetic)


def _runtime_type_descriptors(entities: list[dict[str, object]], broad: TypeTableV3) -> list[dict[str, object]]:
    needed = set(_BASE_TYPES)
    _collect_runtime_type_ids(entities, needed)
    queue = list(needed)
    while queue:
        type_id = queue.pop()
        descriptor = broad.require(type_id, context="IR V3 runtime closure")
        children: list[str] = []
        if descriptor.kind == "record": children.extend(child for _name,child in descriptor.fields)
        elif descriptor.kind == "option" and descriptor.argument is not None: children.append(descriptor.argument)
        elif descriptor.kind == "result":
            assert descriptor.ok_type is not None and descriptor.err_type is not None
            children.extend((descriptor.ok_type,descriptor.err_type))
        for child in children:
            if child not in needed:
                needed.add(child); queue.append(child)
    return [_descriptor_dict(broad.require(type_id)) for type_id in sorted(needed)]


def _descriptor_dict(descriptor: TypeDescriptorV3) -> dict[str, object]:
    if descriptor.kind in {"primitive","unit"}: return {"type_id":descriptor.type_id,"kind":descriptor.kind}
    if descriptor.kind == "record": return {"type_id":descriptor.type_id,"kind":"record","fields":[{"name":name,"type":type_id} for name,type_id in descriptor.fields]}
    if descriptor.kind == "enum": return {"type_id":descriptor.type_id,"kind":"enum","variants":list(descriptor.variants)}
    if descriptor.kind == "option": return {"type_id":descriptor.type_id,"kind":"option","argument":descriptor.argument}
    if descriptor.kind == "result": return {"type_id":descriptor.type_id,"kind":"result","ok_type":descriptor.ok_type,"err_type":descriptor.err_type}
    raise AssertionError(descriptor.kind)


def _collect_type_ids(value: object) -> set[str]:
    result: set[str] = set()
    stack = [value]
    type_keys = {"type","return_type","record_type","result_type","payload_type"}
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key,item in current.items():
                if key in type_keys and isinstance(item,str): result.add(item)
                elif key in {"parameters","argument_types"} and isinstance(item,list) and all(isinstance(x,str) for x in item): result.update(item)
                stack.append(item)
        elif isinstance(current,list): stack.extend(current)
    return result


def _collect_runtime_type_ids(value: object, result: set[str]) -> None:
    stack = [value]
    type_keys = {"type","return_type","record_type","result_type","payload_type"}
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key,item in current.items():
                if key in type_keys and isinstance(item,str): result.add(item)
                elif key in {"parameters","argument_types"} and isinstance(item,list) and all(isinstance(x,str) for x in item): result.update(item)
                stack.append(item)
        elif isinstance(current,list): stack.extend(current)


def _parse_constructed_type(type_id: str) -> tuple[str, tuple[str,...]] | None:
    if type_id.startswith("Option<") and type_id.endswith(">"):
        inner = type_id[7:-1]
        return ("option", (inner,)) if inner else None
    if type_id.startswith("Result<") and type_id.endswith(">"):
        inner = type_id[7:-1]
        depth = 0
        split = -1
        for index,char in enumerate(inner):
            if char == "<": depth += 1
            elif char == ">": depth -= 1
            elif char == "," and depth == 0:
                if split != -1: return None
                split = index
            if depth < 0: return None
        if depth != 0 or split <= 0 or split >= len(inner)-1: return None
        return "result", (inner[:split],inner[split+1:])
    return None


def _build_capability_catalog(program: dict[str, object], table: TypeTableV3) -> dict[str, _CapabilityContract]:
    result: dict[str,_CapabilityContract] = {}
    for capability_id, signatures in CAPABILITIES.items():
        for signature in signatures:
            _add_capability(result, _from_builtin_capability(capability_id, signature))
    for item in _array(program,"capabilities"):
        contract = _CapabilityContract(str(item["capability_id"]), tuple(str(v) for v in _array(item,"parameters")), str(item["return_type"]), str(item["kind"]))
        for type_id in contract.parameters: _require_storable(table,type_id,f"capability {contract.capability_id}")
        table.require(contract.return_type, context=f"capability {contract.capability_id} return")
        _add_capability(result, contract)
    return result


def _add_capability(result: dict[str,_CapabilityContract], contract: _CapabilityContract) -> None:
    previous = result.get(contract.capability_id)
    if previous is not None and previous != contract:
        raise TevScriptError("TEVS_V1_IRV3_LOWER_CAPABILITY_CONFLICT", f"conflicting capability {contract.capability_id!r}")
    result[contract.capability_id] = contract


def _require_capability(emitter: _Emitter, capability_id: str) -> _CapabilityContract:
    contract = emitter.capabilities.get(capability_id)
    if contract is None: raise TevScriptError("TEVS_V1_IRV3_LOWER_CAPABILITY_UNKNOWN", f"unknown capability {capability_id!r}")
    return contract


def _register_capability(emitter: _Emitter, contract: _CapabilityContract) -> None:
    previous = emitter.used_capabilities.get(contract.capability_id)
    if previous is not None and previous != contract: raise TevScriptError("TEVS_V1_IRV3_LOWER_CAPABILITY_CONFLICT", f"conflicting selected capability {contract.capability_id!r}")
    emitter.used_capabilities[contract.capability_id] = contract


def _from_builtin_capability(capability_id: str, signature: Signature) -> _CapabilityContract:
    return _CapabilityContract(capability_id, signature.parameters, signature.return_type, signature.kind)


def _select_builtin_pure_signature(callable_id: str, actual: tuple[str,...], result_type: str) -> _CapabilityContract:
    signatures = PURE_FUNCTIONS.get(callable_id)
    if signatures is None: raise TevScriptError("TEVS_V1_IRV3_LOWER_FUNCTION_UNKNOWN", f"unknown pure builtin {callable_id!r}")
    candidates = []
    for signature in signatures:
        if signature.return_type != result_type or len(signature.parameters) != len(actual): continue
        if all(a==e or (a=="Int" and e=="Rat") for a,e in zip(actual,signature.parameters,strict=True)):
            candidates.append(_CapabilityContract(callable_id,signature.parameters,signature.return_type,"pure"))
    exact = [item for item in candidates if item.parameters == actual]
    if len(exact)==1: return exact[0]
    if len(candidates)==1: return candidates[0]
    raise TevScriptError("TEVS_V1_IRV3_LOWER_CALL_SIGNATURE", f"no unambiguous pure signature for {callable_id!r}{actual}")


def _binary_operand_types(operator: str,left_type: str,right_type: str,result_type: str) -> tuple[str,str]:
    numeric={"Int","Rat"}; vectors={"Vec2","Vec3"}
    if left_type in numeric and right_type in numeric:
        if result_type=="Int" and operator!="/": return "Int","Int"
        return "Rat","Rat"
    if left_type in vectors and right_type in numeric: return left_type,"Rat"
    if right_type in vectors and left_type in numeric: return "Rat",right_type
    return left_type,right_type


def _flatten_behaviors(roots: tuple[str,...], behaviors: dict[str,dict[str,object]], *, owner_label: str) -> tuple[str,...]:
    result=[]; seen=set(); active=[]; active_set=set()
    for root_id in roots:
        if root_id not in behaviors: raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_UNKNOWN", f"unknown behavior {root_id!r}")
        if root_id in seen: raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_DUPLICATE", f"duplicate behavior {root_id!r} in {owner_label}")
        frames=[[root_id,0]]; active.append(root_id); active_set.add(root_id)
        while frames:
            behavior_id=str(frames[-1][0]); index=int(frames[-1][1]); deps=tuple(str(v) for v in _array(behaviors[behavior_id],"uses"))
            if index < len(deps):
                dep=deps[index]; frames[-1][1]=index+1
                if dep not in behaviors: raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_UNKNOWN", f"unknown behavior {dep!r}")
                if dep in active_set: raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_CYCLE", "behavior cycle: "+" -> ".join([*active,dep]))
                if dep in seen: raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_DUPLICATE", f"duplicate behavior {dep!r} in {owner_label}")
                frames.append([dep,0]); active.append(dep); active_set.add(dep); continue
            frames.pop(); popped=active.pop(); active_set.remove(popped); seen.add(behavior_id); result.append(behavior_id)
            if len(result)>MAX_FLATTENED_BEHAVIORS_PER_ENTITY: raise TevScriptError("TEVS_V1_IRV3_LOWER_BEHAVIOR_BUDGET", "flattened behavior budget exceeded")
    return tuple(result)


def _canonical_parameter_names(count: int, reserved: set[str]) -> tuple[str,...]:
    result=[]; index=0
    while len(result)<count:
        candidate=f"_tev_p{index}"; index+=1
        if candidate not in reserved: result.append(candidate)
    return tuple(result)


def _pattern_variant(pattern: dict[str, object]) -> str:
    kind=str(pattern.get("kind"))
    if kind=="enum": return str(pattern["variant"])
    return {"some":"Some","none":"None","ok":"Ok","err":"Err"}.get(kind) or _raise_pattern(kind)


def _raise_pattern(kind: str) -> str:
    raise TevScriptError("TEVS_V1_IRV3_LOWER_MATCH_PATTERN", f"unsupported pattern {kind!r}")


def _require_variant_type(table: TypeTableV3, type_id: str) -> None:
    if table.require(type_id).kind not in {"enum","option","result"}: raise TevScriptError("TEVS_V1_IRV3_LOWER_MATCH_TYPE", f"{type_id!r} is not matchable")


def _require_storable(table: TypeTableV3, type_id: str, context: str) -> None:
    if not table.is_storable(type_id): raise TevScriptError("TEVS_V1_IRV3_LOWER_TYPE", f"{context}: {type_id!r} is not storable")


def _expr_type(expression: object) -> str:
    return str(_object(expression,"expression").get("type"))


def _array(container: dict[str, object], key: str) -> list[dict[str, object]]:
    value=container.get(key)
    if not isinstance(value,list): raise TevScriptError("TEVS_V1_IRV3_LOWER_SHAPE", f"{key!r} must be array")
    return value  # type: ignore[return-value]


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value,dict): raise TevScriptError("TEVS_V1_IRV3_LOWER_SHAPE", f"{context} must be object")
    return value
