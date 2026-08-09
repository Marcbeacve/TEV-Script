from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from .canonical import canonical_hash, canonical_json
from .contracts import (
    IR_SCHEMA,
    LANGUAGE_VERSION,
    MAX_EVENT_CHAIN,
    MAX_INSTRUCTIONS_PER_HANDLER,
    MAX_LOCALS_PER_HANDLER,
)
from .contracts_v1 import (
    MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER,
    MAX_FLATTENED_BEHAVIORS_PER_ENTITY,
    MAX_PURE_FUNCTION_CALL_DEPTH,
    MAX_STATIC_LOOP_ITERATIONS,
)
from .diagnostics import TevScriptError
from .ir_validation import validate_program_ir
from .linked_program_v1 import LinkedProgramBundleV1
from .lowering_boundary_v1 import IR_V2_SIGNATURE_TYPES, IR_V2_VALUE_TYPES
from .types import CAPABILITIES, PURE_FUNCTIONS, Signature
from .values import encode_typed_value

_BINARY_TO_IR = {
    "==": "EQEQ",
    "!=": "NE",
    "<": "LT",
    "<=": "LE",
    ">": "GT",
    ">=": "GE",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
}
_UNARY_TO_IR = {"not": "NOT", "-": "MINUS"}


@dataclass(frozen=True, slots=True)
class LinkedV1IrV2Bundle:
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
                "TEVS_V1_LINKED_LOWER_SHADOW",
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


@dataclass(frozen=True, slots=True)
class _Fragment:
    component_id: str
    component_kind: str
    handler: dict[str, object]


@dataclass(slots=True)
class _Emitter:
    program: dict[str, object]
    functions: dict[str, dict[str, object]]
    capabilities: dict[str, _CapabilityContract]
    event_id: str
    instructions: list[dict[str, object]] = field(default_factory=list)
    locals: dict[str, str] = field(default_factory=dict)
    used_names: set[str] = field(default_factory=set)
    used_capabilities: dict[str, _CapabilityContract] = field(default_factory=dict)
    emitted_events: dict[str, tuple[str, ...]] = field(default_factory=dict)
    fragment_trace: list[dict[str, object]] = field(default_factory=list)
    local_counter: int = 0
    statement_counter: int = 0

    def emit(
        self,
        instruction: dict[str, object],
        *,
        component_id: str,
    ) -> int:
        index = len(self.instructions)
        self.instructions.append(instruction)
        self.fragment_trace.append(
            {
                "instruction": index,
                "component_id": component_id,
            }
        )
        if len(self.instructions) > MAX_INSTRUCTIONS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_INSTRUCTION_BUDGET",
                f"lowered handler exceeds {MAX_INSTRUCTIONS_PER_HANDLER} instructions",
            )
        return index

    def allocate_local(self, type_id: str) -> str:
        _require_v2_value_type(type_id, "local")
        while True:
            candidate = f"_tev_l{self.local_counter}"
            self.local_counter += 1
            if candidate not in self.used_names:
                break
        self.used_names.add(candidate)
        self.locals[candidate] = type_id
        if len(self.locals) > MAX_LOCALS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_LOCAL_BUDGET",
                f"lowered handler exceeds {MAX_LOCALS_PER_HANDLER} locals",
            )
        return candidate

    def count_statement(self) -> None:
        self.statement_counter += 1
        if self.statement_counter > MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_STATEMENT_BUDGET",
                f"expanded handler exceeds {MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER} statement nodes",
            )


def lower_linked_program_v1_to_ir_v2(
    linked: LinkedProgramBundleV1 | dict[str, object],
) -> LinkedV1IrV2Bundle:
    if isinstance(linked, LinkedProgramBundleV1):
        program = linked.program
        linked_hash = linked.semantic_hash
    else:
        program = linked
        linked_hash = str(program.get("semantic_hash", ""))

    _verify_linked_program_identity(program, linked_hash)
    functions = {
        str(item["function_id"]): item
        for item in _array(program, "functions")
    }
    behaviors = {
        str(item["behavior_id"]): item
        for item in _array(program, "behaviors")
    }
    capabilities = _build_capability_catalog(program)

    entities: list[dict[str, object]] = []
    debug_entities: list[dict[str, object]] = []
    for entity in sorted(
        _array(program, "entities"),
        key=lambda item: str(item["entity_id"]),
    ):
        semantic_entity, debug_entity = _lower_entity(
            program,
            entity,
            behaviors,
            functions,
            capabilities,
        )
        entities.append(semantic_entity)
        debug_entities.append(debug_entity)

    semantic: dict[str, object] = {
        "schema": IR_SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "program_id": str(program["program_id"]),
        "entities": entities,
        "boundary": {
            "dynamic_code": False,
            "reflection": False,
            "unbounded_loops": False,
            "implicit_physical_effects": False,
            "runtime_source_compilation": False,
            "automatic_authority_escalation": False,
            "maximum_event_chain": MAX_EVENT_CHAIN,
        },
    }
    ir = dict(semantic)
    ir["semantic_hash"] = canonical_hash(semantic)
    debug = {
        "source_path": "<TEV_SCRIPT_LINKED_PROGRAM_V1>",
        "v1_linked_semantic_hash": linked_hash,
        "entities": debug_entities,
    }
    ir["debug"] = debug
    ir["debug_hash"] = canonical_hash(debug)
    validate_program_ir(ir)
    return LinkedV1IrV2Bundle(
        ir=ir,
        canonical_json=canonical_json(ir),
        linked_semantic_hash=linked_hash,
    )


def _verify_linked_program_identity(
    program: dict[str, object],
    expected_hash: str,
) -> None:
    if program.get("schema") != "TEV_SCRIPT_LINKED_PROGRAM_V1":
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_SCHEMA",
            "expected TEV_SCRIPT_LINKED_PROGRAM_V1",
        )
    if program.get("language_version") != "1.0.0":
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_VERSION",
            f"expected linked language version 1.0.0, got {program.get('language_version')!r}",
        )
    stored_hash = str(program.get("semantic_hash", ""))
    semantic = {
        key: value
        for key, value in program.items()
        if key != "semantic_hash"
    }
    actual_hash = canonical_hash(semantic)
    if stored_hash != actual_hash or expected_hash != actual_hash:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_SEMANTIC_HASH",
            "linked semantic hash does not match canonical linked program content",
        )


def _lower_entity(
    program: dict[str, object],
    entity: dict[str, object],
    behaviors: dict[str, dict[str, object]],
    functions: dict[str, dict[str, object]],
    capabilities: dict[str, _CapabilityContract],
) -> tuple[dict[str, object], dict[str, object]]:
    entity_id = str(entity["entity_id"])
    flattened = _flatten_behaviors(
        tuple(str(item) for item in _array(entity, "uses")),
        behaviors,
        owner_label=f"entity {entity_id!r}",
    )

    state_entries: list[dict[str, object]] = []
    state_types: dict[str, str] = {}
    for behavior_id in flattened:
        for state in _array(behaviors[behavior_id], "states"):
            _add_runtime_state(state_entries, state_types, state, behavior_id)
    for state in _array(entity, "states"):
        _add_runtime_state(state_entries, state_types, state, entity_id)
    state_entries.sort(key=lambda item: str(item["name"]))

    fragments: list[_Fragment] = []
    for behavior_id in flattened:
        for handler in _array(behaviors[behavior_id], "handlers"):
            fragments.append(_Fragment(behavior_id, "behavior", handler))
    for handler in _array(entity, "handlers"):
        fragments.append(_Fragment(entity_id, "entity", handler))

    by_event: dict[str, list[_Fragment]] = {}
    for fragment in fragments:
        event_id = str(fragment.handler["event_id"])
        by_event.setdefault(event_id, []).append(fragment)

    event_signatures: dict[str, tuple[str, ...]] = {}
    for event_id, event_fragments in by_event.items():
        signatures = {
            tuple(str(item["type"]) for item in _array(fragment.handler, "parameters"))
            for fragment in event_fragments
        }
        if len(signatures) != 1:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_HANDLER_SIGNATURE",
                f"composed event {event_id!r} has conflicting signatures {sorted(signatures)}",
            )
        signature = next(iter(signatures))
        for type_id in signature:
            _require_v2_value_type(type_id, f"event {event_id} parameter")
        event_signatures[event_id] = signature

    handlers: list[dict[str, object]] = []
    debug_handlers: list[dict[str, object]] = []
    entity_capabilities: dict[str, _CapabilityContract] = {}
    entity_emitted: dict[str, tuple[str, ...]] = {}

    for event_id in sorted(by_event):
        event_fragments = by_event[event_id]
        signature = event_signatures[event_id]
        parameter_names = _canonical_parameter_names(
            len(signature),
            set(state_types),
        )
        emitter = _Emitter(
            program=program,
            functions=functions,
            capabilities=capabilities,
            event_id=event_id,
        )
        emitter.used_names.update(state_types)
        emitter.used_names.update(parameter_names)
        state_bindings = {
            name: _Binding("state", type_id, ir_name=name)
            for name, type_id in state_types.items()
        }

        for fragment in event_fragments:
            scope = _Scope(states=state_bindings)
            scope.push()
            source_parameters = _array(fragment.handler, "parameters")
            for parameter, canonical_name, type_id in zip(
                source_parameters,
                parameter_names,
                signature,
                strict=True,
            ):
                scope.declare(
                    str(parameter["name"]),
                    _Binding("param", type_id, ir_name=canonical_name),
                )
            _lower_statements(
                _array(fragment.handler, "body"),
                emitter,
                scope,
                component_id=fragment.component_id,
                component_kind=fragment.component_kind,
                event_signatures=event_signatures,
                call_depth=0,
            )

        if not emitter.instructions or emitter.instructions[-1]["op"] != "RETURN":
            emitter.emit(
                {"op": "RETURN"},
                component_id=event_fragments[-1].component_id,
            )

        handlers.append(
            {
                "event_id": event_id,
                "parameters": [
                    {"name": name, "type": type_id}
                    for name, type_id in zip(
                        parameter_names,
                        signature,
                        strict=True,
                    )
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
                "fragment_order": [
                    fragment.component_id for fragment in event_fragments
                ],
                "instruction_origins": emitter.fragment_trace,
            }
        )
        for capability_id, contract in emitter.used_capabilities.items():
            previous = entity_capabilities.get(capability_id)
            if previous is not None and previous != contract:
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_CAPABILITY_CONFLICT",
                    f"capability {capability_id!r} selected with conflicting contracts",
                )
            entity_capabilities[capability_id] = contract
        for emitted_event, emitted_signature in emitter.emitted_events.items():
            previous = entity_emitted.get(emitted_event)
            if previous is not None and previous != emitted_signature:
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_EVENT_SIGNATURE",
                    f"event {emitted_event!r} lowered with conflicting signatures",
                )
            entity_emitted[emitted_event] = emitted_signature

    return (
        {
            "entity_id": entity_id,
            "states": state_entries,
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


def _flatten_behaviors(
    roots: tuple[str, ...],
    behaviors: dict[str, dict[str, object]],
    *,
    owner_label: str,
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    active: list[str] = []
    active_set: set[str] = set()

    for root_id in roots:
        if root_id not in behaviors:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_BEHAVIOR_UNKNOWN",
                f"unknown linked behavior {root_id!r}",
            )
        if root_id in seen:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_BEHAVIOR_DUPLICATE",
                f"behavior {root_id!r} appears more than once in {owner_label}",
            )
        frames: list[list[object]] = [[root_id, 0]]
        active.append(root_id)
        active_set.add(root_id)

        while frames:
            behavior_id = str(frames[-1][0])
            next_index = int(frames[-1][1])
            dependencies = tuple(
                str(item) for item in _array(behaviors[behavior_id], "uses")
            )
            if next_index < len(dependencies):
                dependency = dependencies[next_index]
                frames[-1][1] = next_index + 1
                if dependency not in behaviors:
                    raise TevScriptError(
                        "TEVS_V1_LINKED_LOWER_BEHAVIOR_UNKNOWN",
                        f"unknown linked behavior {dependency!r}",
                    )
                if dependency in active_set:
                    start = active.index(dependency)
                    cycle = [*active[start:], dependency]
                    raise TevScriptError(
                        "TEVS_V1_LINKED_LOWER_BEHAVIOR_CYCLE",
                        "linked behavior cycle: " + " -> ".join(cycle),
                    )
                if dependency in seen:
                    raise TevScriptError(
                        "TEVS_V1_LINKED_LOWER_BEHAVIOR_DUPLICATE",
                        f"behavior {dependency!r} appears more than once in {owner_label}",
                    )
                frames.append([dependency, 0])
                active.append(dependency)
                active_set.add(dependency)
                continue

            frames.pop()
            popped = active.pop()
            active_set.remove(popped)
            assert popped == behavior_id
            if behavior_id in seen:
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_BEHAVIOR_DUPLICATE",
                    f"behavior {behavior_id!r} appears more than once in {owner_label}",
                )
            seen.add(behavior_id)
            result.append(behavior_id)
            if len(result) > MAX_FLATTENED_BEHAVIORS_PER_ENTITY:
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_BEHAVIOR_BUDGET",
                    f"flattened behaviors exceed {MAX_FLATTENED_BEHAVIORS_PER_ENTITY}",
                )

    return tuple(result)


def _add_runtime_state(
    entries: list[dict[str, object]],
    types: dict[str, str],
    state: dict[str, object],
    component_id: str,
) -> None:
    name = str(state["name"])
    type_id = str(state["type"])
    _require_v2_value_type(type_id, f"state {name}")
    if name in types:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_STATE_CONFLICT",
            f"duplicate composed state {name!r} while expanding {component_id}",
        )
    types[name] = type_id
    entries.append(
        {
            "name": name,
            "type": type_id,
            "initial": encode_typed_value(
                type_id,
                _decode_v2_constant(state["initial"], type_id),
            ),
        }
    )


def _decode_v2_constant(
    expression: object,
    expected_type: str,
) -> object:
    if not isinstance(expression, dict):
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_CONSTANT",
            "state initial value must be a canonical expression object",
        )
    kind = expression.get("kind")
    type_id = str(expression.get("type"))
    if type_id != expected_type:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_CONSTANT",
            f"state constant has type {type_id}, expected {expected_type}",
        )
    if kind == "bool" and type_id == "Bool":
        return bool(expression["value"])
    if kind == "int" and type_id == "Int":
        return int(str(expression["value"]))
    if kind == "rat" and type_id == "Rat":
        return Fraction(
            int(str(expression["numerator"])),
            int(str(expression["denominator"])),
        )
    if kind == "text" and type_id == "Text":
        return str(expression["value"])
    if kind == "call" and type_id in {"Vec2", "Vec3"}:
        expected_callable = "vec2" if type_id == "Vec2" else "vec3"
        if expression.get("callable_kind") != "pure_function" or expression.get("callable_id") != expected_callable:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_CONSTANT",
                f"{type_id} constant must use canonical {expected_callable} constructor",
            )
        arguments = _array(expression, "arguments")
        expected_count = 2 if type_id == "Vec2" else 3
        if len(arguments) != expected_count:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_CONSTANT",
                f"{type_id} constant requires {expected_count} components",
            )
        return tuple(
            _decode_v2_constant(argument, "Rat")
            for argument in arguments
        )
    raise TevScriptError(
        "TEVS_V1_LOWER_IR3_REQUIRED",
        f"state constant kind {kind!r}/{type_id} requires IR V3",
    )


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
            _require_v2_value_type(type_id, "local")
            _emit_expr(
                statement["value"],
                emitter,
                scope,
                component_id=component_id,
                expected_type=type_id,
                call_depth=call_depth,
            )
            local_name = emitter.allocate_local(type_id)
            emitter.emit(
                {"op": "STORE_LOCAL", "name": local_name, "type": type_id},
                component_id=component_id,
            )
            scope.declare(
                str(statement["name"]),
                _Binding("local", type_id, ir_name=local_name),
            )
            continue

        if kind == "assign":
            state_name = str(statement["state"])
            binding = scope.states.get(state_name)
            if binding is None:
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_STATE_UNKNOWN",
                    f"unknown composed state {state_name!r}",
                )
            _emit_expr(
                statement["value"],
                emitter,
                scope,
                component_id=component_id,
                expected_type=binding.type_id,
                call_depth=call_depth,
            )
            emitter.emit(
                {"op": "STORE_STATE", "name": state_name, "type": binding.type_id},
                component_id=component_id,
            )
            continue

        if kind == "call":
            capability_id = str(statement["capability_id"])
            contract = _require_capability(emitter, capability_id)
            if contract.return_type != "Unit":
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_CALL_RESULT_UNUSED",
                    f"call statement {capability_id!r} returns {contract.return_type}",
                )
            _emit_arguments(
                _array(statement, "arguments"),
                contract.parameters,
                emitter,
                scope,
                component_id=component_id,
                call_depth=call_depth,
            )
            _register_capability(emitter, contract)
            emitter.emit(
                {
                    "op": "CALL_CAPABILITY",
                    "capability_id": capability_id,
                    "argc": len(contract.parameters),
                    "return_type": "Unit",
                    "kind": contract.kind,
                },
                component_id=component_id,
            )
            continue

        if kind == "emit":
            event_id = str(statement["event_id"])
            arguments = _array(statement, "arguments")
            expected = event_signatures.get(event_id)
            if expected is None:
                signature = tuple(_expr_type(item) for item in arguments)
                for type_id in signature:
                    _require_v2_value_type(type_id, f"emitted event {event_id}")
                for argument in arguments:
                    _emit_expr(
                        argument,
                        emitter,
                        scope,
                        component_id=component_id,
                        expected_type=None,
                        call_depth=call_depth,
                    )
            else:
                signature = expected
                _emit_arguments(
                    arguments,
                    expected,
                    emitter,
                    scope,
                    component_id=component_id,
                    call_depth=call_depth,
                )
            previous = emitter.emitted_events.get(event_id)
            if previous is not None and previous != signature:
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_EVENT_SIGNATURE",
                    f"event {event_id!r} has conflicting lowered signatures",
                )
            emitter.emitted_events[event_id] = signature
            emitter.emit(
                {
                    "op": "EMIT_EVENT",
                    "event_id": event_id,
                    "argument_types": list(signature),
                    "argc": len(signature),
                },
                component_id=component_id,
            )
            continue

        if kind == "if":
            _emit_expr(
                statement["condition"],
                emitter,
                scope,
                component_id=component_id,
                expected_type="Bool",
                call_depth=call_depth,
            )
            jump_false = emitter.emit(
                {"op": "JUMP_IF_FALSE", "target": -1},
                component_id=component_id,
            )
            scope.push()
            try:
                _lower_statements(
                    _array(statement, "then"),
                    emitter,
                    scope,
                    component_id=component_id,
                    component_kind=component_kind,
                    event_signatures=event_signatures,
                    call_depth=call_depth,
                )
            finally:
                scope.pop()
            else_body = _array(statement, "else")
            if else_body:
                jump_end = emitter.emit(
                    {"op": "JUMP", "target": -1},
                    component_id=component_id,
                )
                emitter.instructions[jump_false]["target"] = len(emitter.instructions)
                scope.push()
                try:
                    _lower_statements(
                        else_body,
                        emitter,
                        scope,
                        component_id=component_id,
                        component_kind=component_kind,
                        event_signatures=event_signatures,
                        call_depth=call_depth,
                    )
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
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_FOR_BUDGET",
                    f"invalid bounded for range {lower} .. {upper}",
                )
            variable = str(statement["variable"])
            for value in range(lower, upper):
                scope.push()
                try:
                    scope.declare(
                        variable,
                        _Binding("constant", "Int", constant=value),
                    )
                    _lower_statements(
                        _array(statement, "body"),
                        emitter,
                        scope,
                        component_id=component_id,
                        component_kind=component_kind,
                        event_signatures=event_signatures,
                        call_depth=call_depth,
                    )
                finally:
                    scope.pop()
            continue

        if kind == "match":
            raise TevScriptError(
                "TEVS_V1_LOWER_IR3_REQUIRED",
                "runtime match requires IR V3",
            )

        if kind == "return":
            if component_kind == "behavior":
                raise TevScriptError(
                    "TEVS_V1_LINKED_LOWER_BEHAVIOR_RETURN",
                    "behavior fragment cannot return",
                )
            emitter.emit({"op": "RETURN"}, component_id=component_id)
            continue

        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_STATEMENT_KIND",
            f"unsupported linked statement kind {kind!r}",
        )


def _emit_expr(
    expression: object,
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    expected_type: str | None,
    call_depth: int,
) -> str:
    if not isinstance(expression, dict):
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_EXPRESSION",
            "linked expression must be an object",
        )
    kind = expression.get("kind")
    actual_type = _expr_type(expression)
    _require_v2_value_type(actual_type, "runtime expression")

    if kind == "bool":
        emitter.emit(
            {"op": "CONST", "type": "Bool", "value": bool(expression["value"])},
            component_id=component_id,
        )
    elif kind == "int":
        emitter.emit(
            {
                "op": "CONST",
                "type": "Int",
                "value": encode_typed_value("Int", int(str(expression["value"]))),
            },
            component_id=component_id,
        )
    elif kind == "rat":
        value = Fraction(
            int(str(expression["numerator"])),
            int(str(expression["denominator"])),
        )
        emitter.emit(
            {
                "op": "CONST",
                "type": "Rat",
                "value": encode_typed_value("Rat", value),
            },
            component_id=component_id,
        )
    elif kind == "text":
        emitter.emit(
            {"op": "CONST", "type": "Text", "value": str(expression["value"])},
            component_id=component_id,
        )
    elif kind == "name":
        symbol_id = str(expression["symbol_id"])
        binding = scope.lookup(symbol_id)
        if binding is None:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_VALUE_UNKNOWN",
                f"unknown linked lexical/state value {symbol_id!r}",
            )
        if binding.type_id != actual_type:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_VALUE_TYPE",
                f"binding {symbol_id!r} has {binding.type_id}, expression claims {actual_type}",
            )
        if binding.kind == "constant":
            emitter.emit(
                {
                    "op": "CONST",
                    "type": binding.type_id,
                    "value": encode_typed_value(binding.type_id, binding.constant),
                },
                component_id=component_id,
            )
        else:
            op = {
                "state": "LOAD_STATE",
                "param": "LOAD_PARAM",
                "local": "LOAD_LOCAL",
            }.get(binding.kind)
            if op is None or binding.ir_name is None:
                raise AssertionError(binding)
            emitter.emit(
                {"op": op, "name": binding.ir_name, "type": binding.type_id},
                component_id=component_id,
            )
    elif kind in {"field", "record", "enum", "some", "none", "ok", "err"}:
        raise TevScriptError(
            "TEVS_V1_LOWER_IR3_REQUIRED",
            f"runtime expression kind {kind!r} requires IR V3",
        )
    elif kind == "unary":
        _emit_expr(
            expression["operand"],
            emitter,
            scope,
            component_id=component_id,
            expected_type=None,
            call_depth=call_depth,
        )
        operator = str(expression["operator"])
        if operator not in _UNARY_TO_IR:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_UNARY",
                f"unsupported unary operator {operator!r}",
            )
        emitter.emit(
            {
                "op": "UNARY",
                "operator": _UNARY_TO_IR[operator],
                "type": actual_type,
            },
            component_id=component_id,
        )
    elif kind == "binary":
        operator = str(expression["operator"])
        if operator in {"and", "or"}:
            _emit_short_circuit(
                expression,
                emitter,
                scope,
                component_id=component_id,
                call_depth=call_depth,
            )
        else:
            _emit_binary(
                expression,
                emitter,
                scope,
                component_id=component_id,
                call_depth=call_depth,
            )
    elif kind == "call":
        _emit_call_expr(
            expression,
            emitter,
            scope,
            component_id=component_id,
            call_depth=call_depth,
        )
    else:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_EXPRESSION_KIND",
            f"unsupported linked expression kind {kind!r}",
        )

    if expected_type is not None:
        _require_v2_value_type(expected_type, "expected expression")
        if actual_type == expected_type:
            return expected_type
        if actual_type == "Int" and expected_type == "Rat":
            emitter.emit(
                {"op": "CONVERT_INT_TO_RAT"},
                component_id=component_id,
            )
            return "Rat"
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_TYPE",
            f"expected {expected_type}, got {actual_type}",
        )
    return actual_type


def _emit_binary(
    expression: dict[str, object],
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    call_depth: int,
) -> None:
    operator = str(expression["operator"])
    if operator not in _BINARY_TO_IR:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_BINARY",
            f"unsupported binary operator {operator!r}",
        )
    left = expression["left"]
    right = expression["right"]
    left_type = _expr_type(left)
    right_type = _expr_type(right)
    result_type = str(expression["type"])
    left_expected, right_expected = _binary_operand_types(
        operator,
        left_type,
        right_type,
        result_type,
    )
    _emit_expr(
        left,
        emitter,
        scope,
        component_id=component_id,
        expected_type=left_expected,
        call_depth=call_depth,
    )
    _emit_expr(
        right,
        emitter,
        scope,
        component_id=component_id,
        expected_type=right_expected,
        call_depth=call_depth,
    )
    emitter.emit(
        {
            "op": "BINARY",
            "operator": _BINARY_TO_IR[operator],
            "left_type": left_expected,
            "right_type": right_expected,
            "result_type": result_type,
        },
        component_id=component_id,
    )


def _binary_operand_types(
    operator: str,
    left_type: str,
    right_type: str,
    result_type: str,
) -> tuple[str, str]:
    numeric = {"Int", "Rat"}
    vectors = {"Vec2", "Vec3"}
    if left_type in numeric and right_type in numeric:
        if result_type == "Int" and operator != "/":
            return "Int", "Int"
        return "Rat", "Rat"
    if left_type in vectors and right_type in numeric:
        return left_type, "Rat"
    if right_type in vectors and left_type in numeric:
        return "Rat", right_type
    return left_type, right_type


def _emit_short_circuit(
    expression: dict[str, object],
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    call_depth: int,
) -> None:
    operator = str(expression["operator"])
    temporary = emitter.allocate_local("Bool")
    _emit_expr(
        expression["left"],
        emitter,
        scope,
        component_id=component_id,
        expected_type="Bool",
        call_depth=call_depth,
    )
    emitter.emit(
        {"op": "STORE_LOCAL", "name": temporary, "type": "Bool"},
        component_id=component_id,
    )
    emitter.emit(
        {"op": "LOAD_LOCAL", "name": temporary, "type": "Bool"},
        component_id=component_id,
    )
    jump_false = emitter.emit(
        {"op": "JUMP_IF_FALSE", "target": -1},
        component_id=component_id,
    )

    if operator == "and":
        _emit_expr(
            expression["right"],
            emitter,
            scope,
            component_id=component_id,
            expected_type="Bool",
            call_depth=call_depth,
        )
        emitter.emit(
            {"op": "STORE_LOCAL", "name": temporary, "type": "Bool"},
            component_id=component_id,
        )
        emitter.instructions[jump_false]["target"] = len(emitter.instructions)
    elif operator == "or":
        jump_end = emitter.emit(
            {"op": "JUMP", "target": -1},
            component_id=component_id,
        )
        emitter.instructions[jump_false]["target"] = len(emitter.instructions)
        _emit_expr(
            expression["right"],
            emitter,
            scope,
            component_id=component_id,
            expected_type="Bool",
            call_depth=call_depth,
        )
        emitter.emit(
            {"op": "STORE_LOCAL", "name": temporary, "type": "Bool"},
            component_id=component_id,
        )
        emitter.instructions[jump_end]["target"] = len(emitter.instructions)
    else:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_BOOLEAN",
            f"unsupported short-circuit operator {operator!r}",
        )

    emitter.emit(
        {"op": "LOAD_LOCAL", "name": temporary, "type": "Bool"},
        component_id=component_id,
    )


def _emit_call_expr(
    expression: dict[str, object],
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    call_depth: int,
) -> None:
    callable_kind = str(expression["callable_kind"])
    callable_id = str(expression["callable_id"])
    arguments = _array(expression, "arguments")
    result_type = str(expression["type"])

    if callable_kind == "pure_function" and callable_id in emitter.functions:
        if call_depth >= MAX_PURE_FUNCTION_CALL_DEPTH:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_FUNCTION_DEPTH",
                f"pure-function inlining exceeds {MAX_PURE_FUNCTION_CALL_DEPTH}",
            )
        function = emitter.functions[callable_id]
        parameters = _array(function, "parameters")
        if len(arguments) != len(parameters):
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_CALL_SIGNATURE",
                f"function {callable_id!r} expects {len(parameters)} arguments",
            )
        temporaries: list[tuple[str, str]] = []
        for argument, parameter in zip(arguments, parameters, strict=True):
            parameter_type = str(parameter["type"])
            _require_v2_value_type(parameter_type, f"function {callable_id} parameter")
            _emit_expr(
                argument,
                emitter,
                scope,
                component_id=component_id,
                expected_type=parameter_type,
                call_depth=call_depth,
            )
            temporary = emitter.allocate_local(parameter_type)
            emitter.emit(
                {"op": "STORE_LOCAL", "name": temporary, "type": parameter_type},
                component_id=component_id,
            )
            temporaries.append((temporary, parameter_type))

        function_scope = _Scope(states={})
        function_scope.push()
        for parameter, (temporary, type_id) in zip(
            parameters,
            temporaries,
            strict=True,
        ):
            function_scope.declare(
                str(parameter["name"]),
                _Binding("local", type_id, ir_name=temporary),
            )
        return_type = str(function["return_type"])
        _require_v2_value_type(return_type, f"function {callable_id} return")
        _emit_expr(
            function["body"],
            emitter,
            function_scope,
            component_id=callable_id,
            expected_type=return_type,
            call_depth=call_depth + 1,
        )
        if result_type != return_type:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_CALL_RESULT",
                f"function expression claims {result_type}, declaration returns {return_type}",
            )
        return

    if callable_kind == "pure_function":
        signature = _select_builtin_pure_signature(
            callable_id,
            tuple(_expr_type(item) for item in arguments),
            result_type,
        )
        _emit_arguments(
            arguments,
            signature.parameters,
            emitter,
            scope,
            component_id=component_id,
            call_depth=call_depth,
        )
        emitter.emit(
            {
                "op": "CALL_PURE",
                "function_id": callable_id,
                "argc": len(arguments),
                "return_type": result_type,
            },
            component_id=component_id,
        )
        return

    if callable_kind == "observation_capability":
        contract = _require_capability(emitter, callable_id)
        if contract.kind != "observation" or contract.return_type != result_type:
            raise TevScriptError(
                "TEVS_V1_LINKED_LOWER_CAPABILITY_EXPRESSION",
                f"invalid observation capability expression {callable_id!r}",
            )
        _emit_arguments(
            arguments,
            contract.parameters,
            emitter,
            scope,
            component_id=component_id,
            call_depth=call_depth,
        )
        _register_capability(emitter, contract)
        emitter.emit(
            {
                "op": "CALL_CAPABILITY",
                "capability_id": callable_id,
                "argc": len(arguments),
                "return_type": result_type,
                "kind": "observation",
            },
            component_id=component_id,
        )
        return

    raise TevScriptError(
        "TEVS_V1_LINKED_LOWER_CALL_KIND",
        f"unsupported linked callable kind {callable_kind!r}",
    )


def _emit_arguments(
    arguments: list[dict[str, object]],
    parameters: tuple[str, ...],
    emitter: _Emitter,
    scope: _Scope,
    *,
    component_id: str,
    call_depth: int,
) -> None:
    if len(arguments) != len(parameters):
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_CALL_SIGNATURE",
            f"expected {len(parameters)} arguments, got {len(arguments)}",
        )
    for argument, type_id in zip(arguments, parameters, strict=True):
        _emit_expr(
            argument,
            emitter,
            scope,
            component_id=component_id,
            expected_type=type_id,
            call_depth=call_depth,
        )


def _build_capability_catalog(
    program: dict[str, object],
) -> dict[str, _CapabilityContract]:
    result: dict[str, _CapabilityContract] = {}
    for capability_id, signatures in CAPABILITIES.items():
        for signature in signatures:
            _add_capability_contract(
                result,
                _from_builtin_capability(capability_id, signature),
            )
    for item in _array(program, "capabilities"):
        contract = _CapabilityContract(
            str(item["capability_id"]),
            tuple(str(value) for value in _array(item, "parameters")),
            str(item["return_type"]),
            str(item["kind"]),
        )
        for type_id in (*contract.parameters, contract.return_type):
            if type_id not in IR_V2_SIGNATURE_TYPES:
                # Declaration itself is legal V1; it becomes a blocker only if
                # selected by an IR-V2-lowered runtime expression/statement.
                break
        _add_capability_contract(result, contract)
    return result


def _add_capability_contract(
    result: dict[str, _CapabilityContract],
    contract: _CapabilityContract,
) -> None:
    previous = result.get(contract.capability_id)
    if previous is not None and previous != contract:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_CAPABILITY_CONFLICT",
            f"conflicting capability contract {contract.capability_id!r}",
        )
    result[contract.capability_id] = contract


def _require_capability(
    emitter: _Emitter,
    capability_id: str,
) -> _CapabilityContract:
    contract = emitter.capabilities.get(capability_id)
    if contract is None:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_CAPABILITY_UNKNOWN",
            f"unknown linked capability {capability_id!r}",
        )
    for type_id in (*contract.parameters, contract.return_type):
        if type_id not in IR_V2_SIGNATURE_TYPES:
            raise TevScriptError(
                "TEVS_V1_LOWER_IR3_REQUIRED",
                f"capability {capability_id!r} uses V1-only type {type_id}",
            )
    return contract


def _register_capability(
    emitter: _Emitter,
    contract: _CapabilityContract,
) -> None:
    previous = emitter.used_capabilities.get(contract.capability_id)
    if previous is not None and previous != contract:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_CAPABILITY_CONFLICT",
            f"conflicting selected capability {contract.capability_id!r}",
        )
    emitter.used_capabilities[contract.capability_id] = contract


def _select_builtin_pure_signature(
    callable_id: str,
    actual_types: tuple[str, ...],
    result_type: str,
) -> _CapabilityContract:
    signatures = PURE_FUNCTIONS.get(callable_id)
    if signatures is None:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_FUNCTION_UNKNOWN",
            f"unknown pure builtin {callable_id!r}",
        )
    candidates: list[_CapabilityContract] = []
    for signature in signatures:
        if signature.return_type != result_type:
            continue
        if len(signature.parameters) != len(actual_types):
            continue
        if all(
            actual == expected or (actual == "Int" and expected == "Rat")
            for actual, expected in zip(
                actual_types,
                signature.parameters,
                strict=True,
            )
        ):
            candidates.append(
                _CapabilityContract(
                    callable_id,
                    signature.parameters,
                    signature.return_type,
                    "pure",
                )
            )
    exact = [
        item
        for item in candidates
        if item.parameters == actual_types
    ]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    raise TevScriptError(
        "TEVS_V1_LINKED_LOWER_FUNCTION_SIGNATURE",
        f"cannot select pure builtin {callable_id!r} for {actual_types} -> {result_type}",
    )


def _from_builtin_capability(
    capability_id: str,
    signature: Signature,
) -> _CapabilityContract:
    return _CapabilityContract(
        capability_id,
        signature.parameters,
        signature.return_type,
        signature.kind,
    )


def _canonical_parameter_names(
    count: int,
    forbidden: set[str],
) -> tuple[str, ...]:
    result: list[str] = []
    used = set(forbidden)
    for index in range(count):
        suffix = index
        while True:
            candidate = f"_tev_p{suffix}"
            suffix += count + 1
            if candidate not in used:
                used.add(candidate)
                result.append(candidate)
                break
    return tuple(result)


def _expr_type(expression: object) -> str:
    if not isinstance(expression, dict) or "type" not in expression:
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_EXPRESSION_TYPE",
            "linked expression lacks canonical type",
        )
    return str(expression["type"])


def _require_v2_value_type(type_id: str, context: str) -> None:
    if type_id not in IR_V2_VALUE_TYPES:
        raise TevScriptError(
            "TEVS_V1_LOWER_IR3_REQUIRED",
            f"{context} uses V1-only runtime type {type_id}",
        )


def _array(value: dict[str, object], key: str) -> list[dict[str, object]]:
    selected = value.get(key)
    if not isinstance(selected, list):
        raise TevScriptError(
            "TEVS_V1_LINKED_LOWER_SHAPE",
            f"linked field {key!r} must be an array",
        )
    return selected
