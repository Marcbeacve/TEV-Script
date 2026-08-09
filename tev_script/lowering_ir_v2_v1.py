from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .ast_v1 import (
    AnimateStmt,
    AssignStmt,
    CallStmt,
    EmitStmt,
    Expr,
    ForStmt,
    FunctionDecl,
    IfStmt,
    LetStmt,
    LogStmt,
    MatchStmt,
    MoveStmt,
    ReturnStmt,
)
from .behavior_model_v1 import CompositeModelV1, HandlerFragmentSourceV1
from .canonical import canonical_hash, canonical_json
from .compiler import _binary_operand_expectations, _binary_result
from .constant_eval_v1 import ConstantEvaluationV1, ConstantValueV1, evaluate_v1_state_constants
from .contracts import (
    IR_SCHEMA,
    LANGUAGE_VERSION,
    MAX_EVENT_CHAIN,
    MAX_INSTRUCTIONS_PER_HANDLER,
    MAX_LOCALS_PER_HANDLER,
)
from .contracts_v1 import (
    MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER,
    MAX_PURE_FUNCTION_CALL_DEPTH,
)
from .diagnostics import SourceSpan, TevScriptError
from .ir_validation import validate_program_ir
from .linker_v1 import (
    NAMESPACE_CAPABILITY,
    NAMESPACE_FUNCTION,
    LinkPlanV1,
    SourceInputV1,
    SymbolV1,
    link_v1_mapping,
    link_v1_sources,
    resolve_symbol,
)
from .lowering_boundary_v1 import (
    IR_V2_SIGNATURE_TYPES,
    IR_V2_VALUE_TYPES,
    LoweringBoundaryV1,
    analyze_ir_v2_lowering_boundary,
)
from .semantic_types_v1 import (
    CallableSignatureV1,
    ResolvedTypeV1,
    TypeEnvironmentV1,
    primitive_type,
    require_assignable,
    resolve_type,
    select_callable,
)
from .static_semantics_v1 import (
    CompositeSummaryV1,
    StaticSemanticsV1,
    analyze_v1_static_semantics,
)
from .values import encode_typed_value

_BINARY_TO_V02 = {
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
_UNARY_TO_V02 = {"not": "NOT", "-": "MINUS"}


@dataclass(frozen=True, slots=True)
class V1IrV2LoweringBundle:
    ir: dict[str, object]
    canonical_json: str
    v1_static_semantic_hash: str
    lowering_boundary: LoweringBoundaryV1


@dataclass(frozen=True, slots=True)
class _BindingV1:
    kind: str
    type_ref: ResolvedTypeV1
    ir_name: str | None = None
    constant: ConstantValueV1 | None = None


@dataclass(slots=True)
class _LowerScopeV1:
    states: dict[str, _BindingV1]
    frames: list[dict[str, _BindingV1]] = field(default_factory=list)

    def push(self) -> None:
        self.frames.append({})

    def pop(self) -> None:
        self.frames.pop()

    def declare(self, name: str, binding: _BindingV1, span: SourceSpan) -> None:
        if name in self.states or any(name in frame for frame in self.frames):
            raise TevScriptError(
                "TEVS_V1_LOWER_SCOPE",
                f"lowering encountered illegal shadowing for {name!r}",
                span,
            )
        if not self.frames:
            self.push()
        self.frames[-1][name] = binding

    def lookup(self, name: str) -> _BindingV1 | None:
        for frame in reversed(self.frames):
            if name in frame:
                return frame[name]
        return self.states.get(name)


@dataclass(slots=True)
class _HandlerEmitterV1:
    semantics: StaticSemanticsV1
    model: CompositeModelV1
    summary: CompositeSummaryV1
    constants: ConstantEvaluationV1
    event_id: str
    parameter_names: tuple[str, ...]
    parameter_types: tuple[ResolvedTypeV1, ...]
    instructions: list[dict[str, object]] = field(default_factory=list)
    source_map: list[dict[str, object]] = field(default_factory=list)
    locals: dict[str, ResolvedTypeV1] = field(default_factory=dict)
    capabilities: dict[str, CallableSignatureV1] = field(default_factory=dict)
    emitted_events: dict[str, tuple[str, ...]] = field(default_factory=dict)
    used_ir_names: set[str] = field(default_factory=set)
    local_counter: int = 0
    expanded_statements: int = 0

    def emit(
        self,
        instruction: dict[str, object],
        span: SourceSpan,
        source_id: str,
    ) -> int:
        index = len(self.instructions)
        self.instructions.append(instruction)
        self.source_map.append(
            {
                "instruction": index,
                "source_id": source_id,
                "span": _semantic_debug_span(span, source_id),
            }
        )
        if len(self.instructions) > MAX_INSTRUCTIONS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_LOWER_INSTRUCTION_BUDGET",
                f"lowered handler exceeds {MAX_INSTRUCTIONS_PER_HANDLER} IR instructions",
                span,
            )
        return index

    def allocate_local(
        self,
        type_ref: ResolvedTypeV1,
        span: SourceSpan,
    ) -> str:
        _require_v2_value_type(type_ref, span, "local")
        while True:
            candidate = f"_tev_l{self.local_counter}"
            self.local_counter += 1
            if candidate not in self.used_ir_names:
                break
        self.used_ir_names.add(candidate)
        self.locals[candidate] = type_ref
        if len(self.locals) > MAX_LOCALS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_LOWER_LOCAL_BUDGET",
                f"lowered handler exceeds {MAX_LOCALS_PER_HANDLER} locals",
                span,
            )
        return candidate

    def count_statement(self, span: SourceSpan) -> None:
        self.expanded_statements += 1
        if self.expanded_statements > MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER:
            raise TevScriptError(
                "TEVS_V1_LOWER_EXPANDED_STATEMENT_BUDGET",
                f"expanded handler exceeds {MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER} statement nodes",
                span,
            )

    @property
    def types(self) -> TypeEnvironmentV1:
        return self.semantics.types

    @property
    def plan(self) -> LinkPlanV1:
        return self.semantics.plan


def lower_v1_to_ir_v2(semantics: StaticSemanticsV1) -> V1IrV2LoweringBundle:
    boundary = analyze_ir_v2_lowering_boundary(semantics)
    if not boundary.lowerable:
        first = boundary.blockers[0]
        raise TevScriptError(
            "TEVS_V1_LOWER_IR3_REQUIRED",
            f"{len(boundary.blockers)} IR V3 blocker(s); first={first.code}: {first.message}",
        )

    constants = evaluate_v1_state_constants(semantics)
    summaries = {item.composite_id: item for item in semantics.composites}
    entities: list[dict[str, object]] = []
    debug_entities: list[dict[str, object]] = []

    for entity in sorted(semantics.plan.root.entities, key=lambda item: item.name):
        composite_id = f"{semantics.plan.program_id}.{entity.name}"
        model = semantics.behavior_model.composite(composite_id)
        summary = summaries[composite_id]
        semantic_entity, debug_entity = _lower_entity(
            semantics,
            model,
            summary,
            constants,
            entity.name,
        )
        entities.append(semantic_entity)
        debug_entities.append(debug_entity)

    semantic: dict[str, object] = {
        "schema": IR_SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "program_id": semantics.plan.program_id,
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
        "source_language_version": "1.0.0",
        "v1_static_semantic_hash": semantics.semantic_hash,
        "entities": debug_entities,
    }
    ir["debug"] = debug
    ir["debug_hash"] = canonical_hash(debug)
    validate_program_ir(ir)
    return V1IrV2LoweringBundle(
        ir=ir,
        canonical_json=canonical_json(ir),
        v1_static_semantic_hash=semantics.semantic_hash,
        lowering_boundary=boundary,
    )


def lower_v1_mapping_to_ir_v2(
    sources: dict[str, bytes],
) -> V1IrV2LoweringBundle:
    return lower_v1_to_ir_v2(
        analyze_v1_static_semantics(link_v1_mapping(sources))
    )


def lower_v1_sources_to_ir_v2(
    sources: Iterable[SourceInputV1],
) -> V1IrV2LoweringBundle:
    return lower_v1_to_ir_v2(
        analyze_v1_static_semantics(link_v1_sources(sources))
    )


def lower_v1_paths_to_ir_v2(
    paths: Iterable[str | Path],
) -> V1IrV2LoweringBundle:
    inputs = [
        SourceInputV1(Path(path).as_posix(), Path(path).read_bytes())
        for path in paths
    ]
    return lower_v1_sources_to_ir_v2(inputs)


def _lower_entity(
    semantics: StaticSemanticsV1,
    model: CompositeModelV1,
    summary: CompositeSummaryV1,
    constants: ConstantEvaluationV1,
    entity_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    states = []
    for state_source in sorted(
        model.visible_states,
        key=lambda item: item.declaration.name,
    ):
        type_ref = state_source.type_ref
        _require_v2_value_type(type_ref, state_source.declaration.span, "state")
        constant = constants.state(
            state_source.component_id,
            state_source.declaration.name,
        )
        states.append(
            {
                "name": state_source.declaration.name,
                "type": type_ref.type_id,
                "initial": encode_typed_value(type_ref.type_id, constant.value),
            }
        )

    handler_signatures = _handler_signatures(model)
    event_signatures = _all_event_signatures(summary, handler_signatures)
    handlers: list[dict[str, object]] = []
    debug_handlers: list[dict[str, object]] = []
    all_capabilities: dict[str, CallableSignatureV1] = {}

    for event_id in sorted(handler_signatures):
        fragments = tuple(
            item
            for item in model.handler_fragments
            if item.declaration.event_id == event_id
        )
        parameter_types = handler_signatures[event_id]
        state_names = {item.declaration.name for item in model.visible_states}
        parameter_names = _canonical_parameter_names(
            len(parameter_types),
            state_names,
        )
        emitter = _HandlerEmitterV1(
            semantics=semantics,
            model=model,
            summary=summary,
            constants=constants,
            event_id=event_id,
            parameter_names=parameter_names,
            parameter_types=parameter_types,
        )
        emitter.used_ir_names.update(state_names)
        emitter.used_ir_names.update(parameter_names)

        state_bindings = {
            item.declaration.name: _BindingV1(
                "state",
                item.type_ref,
                ir_name=item.declaration.name,
            )
            for item in model.visible_states
        }

        for fragment in fragments:
            scope = _LowerScopeV1(states=state_bindings)
            scope.push()
            for parameter, canonical_name, parameter_type in zip(
                fragment.declaration.parameters,
                parameter_names,
                parameter_types,
                strict=True,
            ):
                scope.declare(
                    parameter.name,
                    _BindingV1(
                        "param",
                        parameter_type,
                        ir_name=canonical_name,
                    ),
                    parameter.span,
                )
            _lower_statements(
                fragment.declaration.body,
                emitter,
                scope,
                owner_id=fragment.owner_id,
                source_id=fragment.component_id,
                event_signatures=event_signatures,
                call_depth=0,
            )

        if not emitter.instructions or emitter.instructions[-1]["op"] != "RETURN":
            span = fragments[-1].declaration.span
            emitter.emit({"op": "RETURN"}, span, fragments[-1].component_id)

        handler = {
            "event_id": event_id,
            "parameters": [
                {"name": name, "type": type_ref.type_id}
                for name, type_ref in zip(
                    parameter_names,
                    parameter_types,
                    strict=True,
                )
            ],
            "locals": [
                {"name": name, "type": type_ref.type_id}
                for name, type_ref in sorted(emitter.locals.items())
            ],
            "instructions": emitter.instructions,
            "instruction_budget": MAX_INSTRUCTIONS_PER_HANDLER,
        }
        handlers.append(handler)
        debug_handlers.append(
            {
                "event_id": event_id,
                "source_map": emitter.source_map,
            }
        )
        for capability_id, signature in emitter.capabilities.items():
            previous = all_capabilities.get(capability_id)
            if previous is not None and _signature_key(previous) != _signature_key(signature):
                raise TevScriptError(
                    "TEVS_V1_LOWER_CAPABILITY_CONFLICT",
                    f"lowering selected conflicting signatures for {capability_id!r}",
                )
            all_capabilities[capability_id] = signature

    capabilities = [
        {
            "capability_id": capability_id,
            "parameters": [item.type_id for item in signature.parameters],
            "return_type": signature.return_type.type_id,
            "kind": signature.kind,
        }
        for capability_id, signature in sorted(all_capabilities.items())
    ]
    emitted_events = [
        {"event_id": event_id, "parameters": list(signature)}
        for event_id, signature in sorted(
            _emitted_event_signatures(summary).items()
        )
    ]
    return (
        {
            "entity_id": entity_id,
            "states": states,
            "handlers": handlers,
            "capabilities": capabilities,
            "emitted_events": emitted_events,
        },
        {
            "entity_id": entity_id,
            "composite_id": model.composite_id,
            "flattened_behaviors": list(model.flattened_behaviors),
            "handlers": debug_handlers,
        },
    )


def _lower_statements(
    statements: tuple[object, ...],
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    event_signatures: dict[str, tuple[str, ...]],
    call_depth: int,
) -> None:
    for statement in statements:
        emitter.count_statement(statement.span)

        if isinstance(statement, LetStmt):
            expected = (
                resolve_type(emitter.plan, owner_id, statement.type_ref)
                if statement.type_ref is not None
                else None
            )
            if expected is not None:
                _require_v2_value_type(expected, statement.span, "local")
            actual = _emit_expr(
                statement.expression,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                expected=expected,
                call_depth=call_depth,
            )
            selected = expected or actual
            _require_v2_value_type(selected, statement.span, "local")
            local_name = emitter.allocate_local(selected, statement.span)
            emitter.emit(
                {"op": "STORE_LOCAL", "name": local_name, "type": selected.type_id},
                statement.span,
                source_id,
            )
            scope.declare(
                statement.name,
                _BindingV1("local", selected, ir_name=local_name),
                statement.span,
            )
            continue

        if isinstance(statement, AssignStmt):
            binding = scope.states.get(statement.name)
            if binding is None:
                raise TevScriptError(
                    "TEVS_V1_LOWER_STATE_UNKNOWN",
                    f"unknown lowered state {statement.name!r}",
                    statement.span,
                )
            _emit_expr(
                statement.expression,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                expected=binding.type_ref,
                call_depth=call_depth,
            )
            emitter.emit(
                {
                    "op": "STORE_STATE",
                    "name": binding.ir_name,
                    "type": binding.type_ref.type_id,
                },
                statement.span,
                source_id,
            )
            continue

        if isinstance(statement, CallStmt):
            signature = _resolve_capability_signature(
                emitter,
                owner_id,
                statement.capability_id,
                statement.span,
            )
            _require_v2_signature(signature, statement.span)
            if not signature.return_type.is_unit:
                raise TevScriptError(
                    "TEVS_V1_LOWER_CALL_RESULT_UNUSED",
                    f"call statement {signature.callable_id!r} does not return Unit",
                    statement.span,
                )
            _emit_arguments(
                statement.arguments,
                signature.parameters,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                call_depth=call_depth,
            )
            _register_capability(emitter, signature, statement.span)
            emitter.emit(
                {
                    "op": "CALL_CAPABILITY",
                    "capability_id": signature.callable_id,
                    "argc": len(statement.arguments),
                    "return_type": "Unit",
                    "kind": signature.kind,
                },
                statement.span,
                source_id,
            )
            continue

        if isinstance(statement, EmitStmt):
            expected_ids = event_signatures.get(statement.event_id)
            actual_ids: list[str] = []
            if expected_ids is not None:
                if len(expected_ids) != len(statement.arguments):
                    raise TevScriptError(
                        "TEVS_V1_LOWER_EVENT_SIGNATURE",
                        f"event {statement.event_id!r} expects {len(expected_ids)} arguments",
                        statement.span,
                    )
                for argument, type_id in zip(
                    statement.arguments,
                    expected_ids,
                    strict=True,
                ):
                    expected_type = primitive_type(type_id)
                    _emit_expr(
                        argument,
                        emitter,
                        scope,
                        owner_id=owner_id,
                        source_id=source_id,
                        expected=expected_type,
                        call_depth=call_depth,
                    )
                    actual_ids.append(type_id)
            else:
                for argument in statement.arguments:
                    actual = _emit_expr(
                        argument,
                        emitter,
                        scope,
                        owner_id=owner_id,
                        source_id=source_id,
                        expected=None,
                        call_depth=call_depth,
                    )
                    _require_v2_value_type(actual, argument.span, "event argument")
                    actual_ids.append(actual.type_id)
            signature = tuple(actual_ids)
            previous = emitter.emitted_events.get(statement.event_id)
            if previous is not None and previous != signature:
                raise TevScriptError(
                    "TEVS_V1_LOWER_EVENT_SIGNATURE",
                    f"event {statement.event_id!r} lowered with conflicting signatures",
                    statement.span,
                )
            emitter.emitted_events[statement.event_id] = signature
            emitter.emit(
                {
                    "op": "EMIT_EVENT",
                    "event_id": statement.event_id,
                    "argument_types": list(signature),
                    "argc": len(signature),
                },
                statement.span,
                source_id,
            )
            continue

        if isinstance(statement, LogStmt):
            _emit_sugar_capability(
                "debug.log",
                (statement.expression,),
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                span=statement.span,
                call_depth=call_depth,
            )
            continue

        if isinstance(statement, MoveStmt):
            _emit_sugar_capability(
                "motion.move2d",
                (statement.expression,),
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                span=statement.span,
                call_depth=call_depth,
            )
            continue

        if isinstance(statement, AnimateStmt):
            _emit_sugar_capability(
                "animation.play",
                (statement.expression,),
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                span=statement.span,
                call_depth=call_depth,
            )
            continue

        if isinstance(statement, IfStmt):
            _emit_expr(
                statement.condition,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                expected=primitive_type("Bool"),
                call_depth=call_depth,
            )
            jump_false = emitter.emit(
                {"op": "JUMP_IF_FALSE", "target": -1},
                statement.condition.span,
                source_id,
            )
            scope.push()
            try:
                _lower_statements(
                    statement.then_body,
                    emitter,
                    scope,
                    owner_id=owner_id,
                    source_id=source_id,
                    event_signatures=event_signatures,
                    call_depth=call_depth,
                )
            finally:
                scope.pop()

            if statement.else_body:
                jump_end = emitter.emit(
                    {"op": "JUMP", "target": -1},
                    statement.span,
                    source_id,
                )
                emitter.instructions[jump_false]["target"] = len(emitter.instructions)
                scope.push()
                try:
                    _lower_statements(
                        statement.else_body,
                        emitter,
                        scope,
                        owner_id=owner_id,
                        source_id=source_id,
                        event_signatures=event_signatures,
                        call_depth=call_depth,
                    )
                finally:
                    scope.pop()
                emitter.instructions[jump_end]["target"] = len(emitter.instructions)
            else:
                emitter.instructions[jump_false]["target"] = len(emitter.instructions)
            continue

        if isinstance(statement, ForStmt):
            for value in range(statement.lower, statement.upper):
                scope.push()
                try:
                    scope.declare(
                        statement.variable,
                        _BindingV1(
                            "constant",
                            primitive_type("Int"),
                            constant=ConstantValueV1(
                                primitive_type("Int"),
                                value,
                            ),
                        ),
                        statement.span,
                    )
                    _lower_statements(
                        statement.body,
                        emitter,
                        scope,
                        owner_id=owner_id,
                        source_id=source_id,
                        event_signatures=event_signatures,
                        call_depth=call_depth,
                    )
                finally:
                    scope.pop()
            continue

        if isinstance(statement, MatchStmt):
            _raise_ir3(statement.span, "runtime match")

        if isinstance(statement, ReturnStmt):
            emitter.emit({"op": "RETURN"}, statement.span, source_id)
            continue

        raise TypeError(f"unsupported V1 statement {type(statement).__name__}")


def _emit_expr(
    expression: Expr,
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    expected: ResolvedTypeV1 | None,
    call_depth: int,
) -> ResolvedTypeV1:
    kind = expression.kind

    if kind == "bool":
        actual = primitive_type("Bool")
        emitter.emit(
            {"op": "CONST", "type": "Bool", "value": bool(expression.value)},
            expression.span,
            source_id,
        )
    elif kind == "int":
        actual = primitive_type("Int")
        emitter.emit(
            {
                "op": "CONST",
                "type": "Int",
                "value": encode_typed_value("Int", int(expression.value)),
            },
            expression.span,
            source_id,
        )
    elif kind == "rat":
        actual = primitive_type("Rat")
        emitter.emit(
            {
                "op": "CONST",
                "type": "Rat",
                "value": encode_typed_value("Rat", expression.value),
            },
            expression.span,
            source_id,
        )
    elif kind == "text":
        actual = primitive_type("Text")
        emitter.emit(
            {"op": "CONST", "type": "Text", "value": str(expression.value)},
            expression.span,
            source_id,
        )
    elif kind == "group":
        actual = _emit_expr(
            expression.children[0],
            emitter,
            scope,
            owner_id=owner_id,
            source_id=source_id,
            expected=expected,
            call_depth=call_depth,
        )
        return actual
    elif kind == "name":
        binding = _lookup_lowered_value(scope, str(expression.value), expression.span)
        actual = binding.type_ref
        if binding.kind == "constant":
            assert binding.constant is not None
            emitter.emit(
                {
                    "op": "CONST",
                    "type": actual.type_id,
                    "value": encode_typed_value(actual.type_id, binding.constant.value),
                },
                expression.span,
                source_id,
            )
        else:
            op = {
                "state": "LOAD_STATE",
                "param": "LOAD_PARAM",
                "local": "LOAD_LOCAL",
            }.get(binding.kind)
            if op is None or binding.ir_name is None:
                raise AssertionError(f"invalid lowering binding {binding}")
            emitter.emit(
                {"op": op, "name": binding.ir_name, "type": actual.type_id},
                expression.span,
                source_id,
            )
    elif kind == "field":
        _raise_ir3(expression.span, "runtime record field access")
    elif kind in {"record", "enum", "some", "none", "ok", "err"}:
        _raise_ir3(expression.span, f"runtime {kind} value")
    elif kind == "unary":
        actual = _infer_expr(
            expression,
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
        operand = _infer_expr(
            expression.children[0],
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
        _emit_expr(
            expression.children[0],
            emitter,
            scope,
            owner_id=owner_id,
            source_id=source_id,
            expected=operand,
            call_depth=call_depth,
        )
        emitter.emit(
            {
                "op": "UNARY",
                "operator": _UNARY_TO_V02[str(expression.value)],
                "type": actual.type_id,
            },
            expression.span,
            source_id,
        )
    elif kind == "binary":
        if expression.value in {"and", "or"}:
            actual = _emit_short_circuit(
                expression,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                call_depth=call_depth,
            )
        else:
            actual = _emit_binary(
                expression,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                call_depth=call_depth,
            )
    elif kind == "call":
        actual = _emit_call_expr(
            expression,
            emitter,
            scope,
            owner_id=owner_id,
            source_id=source_id,
            call_depth=call_depth,
        )
    else:
        raise TevScriptError(
            "TEVS_V1_LOWER_EXPRESSION_KIND",
            f"unsupported lowering expression kind {kind!r}",
            expression.span,
        )

    _require_v2_value_type(actual, expression.span, "expression")
    if expected is not None:
        _require_v2_value_type(expected, expression.span, "expected expression")
        require_assignable(actual, expected, expression.span)
        if actual.type_id == "Int" and expected.type_id == "Rat":
            emitter.emit(
                {"op": "CONVERT_INT_TO_RAT"},
                expression.span,
                source_id,
            )
            return expected
    return actual


def _emit_binary(
    expression: Expr,
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    call_depth: int,
) -> ResolvedTypeV1:
    operator = _BINARY_TO_V02[str(expression.value)]
    left = _infer_expr(
        expression.children[0],
        emitter,
        scope,
        owner_id=owner_id,
        call_depth=call_depth,
    )
    right = _infer_expr(
        expression.children[1],
        emitter,
        scope,
        owner_id=owner_id,
        call_depth=call_depth,
    )
    result_id = _binary_result(
        operator,
        left.type_id,
        right.type_id,
        expression.span,
    )
    left_expected_id, right_expected_id = _binary_operand_expectations(
        operator,
        left.type_id,
        right.type_id,
        result_id,
    )
    left_expected = primitive_type(left_expected_id)
    right_expected = primitive_type(right_expected_id)
    _emit_expr(
        expression.children[0],
        emitter,
        scope,
        owner_id=owner_id,
        source_id=source_id,
        expected=left_expected,
        call_depth=call_depth,
    )
    _emit_expr(
        expression.children[1],
        emitter,
        scope,
        owner_id=owner_id,
        source_id=source_id,
        expected=right_expected,
        call_depth=call_depth,
    )
    emitter.emit(
        {
            "op": "BINARY",
            "operator": operator,
            "left_type": left_expected_id,
            "right_type": right_expected_id,
            "result_type": result_id,
        },
        expression.span,
        source_id,
    )
    return primitive_type(result_id)


def _emit_short_circuit(
    expression: Expr,
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    call_depth: int,
) -> ResolvedTypeV1:
    bool_type = primitive_type("Bool")
    temporary = emitter.allocate_local(bool_type, expression.span)
    _emit_expr(
        expression.children[0],
        emitter,
        scope,
        owner_id=owner_id,
        source_id=source_id,
        expected=bool_type,
        call_depth=call_depth,
    )
    emitter.emit(
        {"op": "STORE_LOCAL", "name": temporary, "type": "Bool"},
        expression.span,
        source_id,
    )
    emitter.emit(
        {"op": "LOAD_LOCAL", "name": temporary, "type": "Bool"},
        expression.span,
        source_id,
    )
    jump_false = emitter.emit(
        {"op": "JUMP_IF_FALSE", "target": -1},
        expression.span,
        source_id,
    )

    if expression.value == "and":
        _emit_expr(
            expression.children[1],
            emitter,
            scope,
            owner_id=owner_id,
            source_id=source_id,
            expected=bool_type,
            call_depth=call_depth,
        )
        emitter.emit(
            {"op": "STORE_LOCAL", "name": temporary, "type": "Bool"},
            expression.span,
            source_id,
        )
        emitter.instructions[jump_false]["target"] = len(emitter.instructions)
    else:
        jump_end = emitter.emit(
            {"op": "JUMP", "target": -1},
            expression.span,
            source_id,
        )
        emitter.instructions[jump_false]["target"] = len(emitter.instructions)
        _emit_expr(
            expression.children[1],
            emitter,
            scope,
            owner_id=owner_id,
            source_id=source_id,
            expected=bool_type,
            call_depth=call_depth,
        )
        emitter.emit(
            {"op": "STORE_LOCAL", "name": temporary, "type": "Bool"},
            expression.span,
            source_id,
        )
        emitter.instructions[jump_end]["target"] = len(emitter.instructions)

    emitter.emit(
        {"op": "LOAD_LOCAL", "name": temporary, "type": "Bool"},
        expression.span,
        source_id,
    )
    return bool_type


def _emit_call_expr(
    expression: Expr,
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    call_depth: int,
) -> ResolvedTypeV1:
    callee = expression.children[0]
    if callee.kind != "name":
        raise TevScriptError(
            "TEVS_V1_LOWER_CALLABLE",
            "IR V2 lowering requires named callables",
            callee.span,
        )
    arguments = tuple(expression.children[1:])
    kind, signature = _resolve_expression_callable(
        emitter,
        owner_id,
        str(callee.value),
        arguments,
        scope,
        callee.span,
        call_depth,
    )
    _require_v2_signature(signature, expression.span)

    if kind == "user_function":
        if call_depth >= MAX_PURE_FUNCTION_CALL_DEPTH:
            raise TevScriptError(
                "TEVS_V1_LOWER_FUNCTION_DEPTH",
                f"pure-function inlining exceeds depth {MAX_PURE_FUNCTION_CALL_DEPTH}",
                expression.span,
            )
        declaration = signature.declaration
        if not isinstance(declaration, FunctionDecl):
            raise AssertionError("source function signature lacks FunctionDecl")
        if len(arguments) != len(signature.parameters):
            raise TevScriptError(
                "TEVS_V1_LOWER_CALL_SIGNATURE",
                f"{signature.callable_id!r} expects {len(signature.parameters)} arguments",
                expression.span,
            )
        argument_temporaries: list[str] = []
        for argument, parameter_type in zip(
            arguments,
            signature.parameters,
            strict=True,
        ):
            _emit_expr(
                argument,
                emitter,
                scope,
                owner_id=owner_id,
                source_id=source_id,
                expected=parameter_type,
                call_depth=call_depth,
            )
            temporary = emitter.allocate_local(parameter_type, argument.span)
            emitter.emit(
                {
                    "op": "STORE_LOCAL",
                    "name": temporary,
                    "type": parameter_type.type_id,
                },
                argument.span,
                source_id,
            )
            argument_temporaries.append(temporary)

        function_scope = _LowerScopeV1(states={})
        function_scope.push()
        for parameter, parameter_type, temporary in zip(
            declaration.parameters,
            signature.parameters,
            argument_temporaries,
            strict=True,
        ):
            function_scope.declare(
                parameter.name,
                _BindingV1("local", parameter_type, ir_name=temporary),
                parameter.span,
            )
        return _emit_expr(
            declaration.expression,
            emitter,
            function_scope,
            owner_id=signature.owner_id,
            source_id=signature.callable_id,
            expected=signature.return_type,
            call_depth=call_depth + 1,
        )

    _emit_arguments(
        arguments,
        signature.parameters,
        emitter,
        scope,
        owner_id=owner_id,
        source_id=source_id,
        call_depth=call_depth,
    )
    if kind == "builtin_function":
        emitter.emit(
            {
                "op": "CALL_PURE",
                "function_id": signature.callable_id,
                "argc": len(arguments),
                "return_type": signature.return_type.type_id,
            },
            expression.span,
            source_id,
        )
        return signature.return_type

    if kind == "observation_capability":
        _register_capability(emitter, signature, expression.span)
        emitter.emit(
            {
                "op": "CALL_CAPABILITY",
                "capability_id": signature.callable_id,
                "argc": len(arguments),
                "return_type": signature.return_type.type_id,
                "kind": signature.kind,
            },
            expression.span,
            source_id,
        )
        return signature.return_type

    raise AssertionError(kind)


def _infer_expr(
    expression: Expr,
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    call_depth: int,
) -> ResolvedTypeV1:
    kind = expression.kind
    if kind == "bool":
        return primitive_type("Bool")
    if kind == "int":
        return primitive_type("Int")
    if kind == "rat":
        return primitive_type("Rat")
    if kind == "text":
        return primitive_type("Text")
    if kind == "group":
        return _infer_expr(
            expression.children[0],
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
    if kind == "name":
        return _lookup_lowered_value(
            scope,
            str(expression.value),
            expression.span,
        ).type_ref
    if kind in {"field", "record", "enum", "some", "none", "ok", "err"}:
        _raise_ir3(expression.span, f"runtime {kind} expression")
    if kind == "unary":
        operand = _infer_expr(
            expression.children[0],
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
        if expression.value == "not" and operand.type_id == "Bool":
            return primitive_type("Bool")
        if expression.value == "-" and operand.is_numeric:
            return operand
        raise TevScriptError(
            "TEVS_V1_LOWER_UNARY_TYPE",
            f"invalid unary operand {operand.type_id}",
            expression.span,
        )
    if kind == "binary":
        if expression.value in {"and", "or"}:
            return primitive_type("Bool")
        left = _infer_expr(
            expression.children[0],
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
        right = _infer_expr(
            expression.children[1],
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
        operator = _BINARY_TO_V02[str(expression.value)]
        return primitive_type(
            _binary_result(
                operator,
                left.type_id,
                right.type_id,
                expression.span,
            )
        )
    if kind == "call":
        callee = expression.children[0]
        if callee.kind != "name":
            raise TevScriptError(
                "TEVS_V1_LOWER_CALLABLE",
                "IR V2 lowering requires named callables",
                callee.span,
            )
        call_kind, signature = _resolve_expression_callable(
            emitter,
            owner_id,
            str(callee.value),
            tuple(expression.children[1:]),
            scope,
            callee.span,
            call_depth,
        )
        if call_kind == "effect_capability":
            raise TevScriptError(
                "TEVS_V1_LOWER_EFFECT_EXPRESSION",
                f"effect capability {signature.callable_id!r} cannot be a value",
                expression.span,
            )
        _require_v2_signature(signature, expression.span)
        return signature.return_type
    raise TevScriptError(
        "TEVS_V1_LOWER_EXPRESSION_KIND",
        f"cannot infer lowering type for {kind!r}",
        expression.span,
    )


def _resolve_expression_callable(
    emitter: _HandlerEmitterV1,
    owner_id: str,
    reference: str,
    arguments: tuple[Expr, ...],
    scope: _LowerScopeV1,
    span: SourceSpan,
    call_depth: int,
) -> tuple[str, CallableSignatureV1]:
    function_symbol, function_error = _try_resolve(
        emitter.plan,
        owner_id,
        reference,
        NAMESPACE_FUNCTION,
        span,
    )
    capability_symbol, capability_error = _try_resolve(
        emitter.plan,
        owner_id,
        reference,
        NAMESPACE_CAPABILITY,
        span,
    )
    if function_symbol is not None and capability_symbol is not None:
        raise TevScriptError(
            "TEVS_V1_LOWER_CALL_AMBIGUOUS",
            f"call {reference!r} resolves as both function and capability",
            span,
        )
    if function_symbol is not None:
        candidates = [
            item for item in emitter.types.functions
            if item.callable_id == function_symbol.semantic_id
        ]
        signature = _select_lowering_signature(
            candidates,
            arguments,
            emitter,
            scope,
            owner_id,
            span,
            call_depth,
        )
        return (
            "builtin_function" if signature.declaration is None else "user_function",
            signature,
        )
    if capability_symbol is not None:
        candidates = _dedupe_signatures(
            item for item in emitter.types.capabilities
            if item.callable_id == capability_symbol.semantic_id
        )
        if len(candidates) != 1:
            raise TevScriptError(
                "TEVS_V1_LOWER_CALL_SIGNATURE",
                f"capability {capability_symbol.semantic_id!r} lacks one canonical signature",
                span,
            )
        signature = candidates[0]
        return (
            "observation_capability"
            if signature.kind == "observation"
            else "effect_capability",
            signature,
        )
    for error in (function_error, capability_error):
        if error is not None and error.diagnostic.code == "TEVS_V1_LINK_PRIVATE_SYMBOL":
            raise error
    raise TevScriptError(
        "TEVS_V1_LOWER_CALL_UNKNOWN",
        f"unknown callable {reference!r}",
        span,
    )


def _select_lowering_signature(
    candidates: list[CallableSignatureV1],
    arguments: tuple[Expr, ...],
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    owner_id: str,
    span: SourceSpan,
    call_depth: int,
) -> CallableSignatureV1:
    if not candidates:
        raise TevScriptError(
            "TEVS_V1_LOWER_CALL_UNKNOWN",
            "missing callable signature",
            span,
        )
    if len(candidates) == 1:
        if len(arguments) != len(candidates[0].parameters):
            raise TevScriptError(
                "TEVS_V1_LOWER_CALL_SIGNATURE",
                f"expected {len(candidates[0].parameters)} arguments, got {len(arguments)}",
                span,
            )
        return candidates[0]
    actual = tuple(
        _infer_expr(
            argument,
            emitter,
            scope,
            owner_id=owner_id,
            call_depth=call_depth,
        )
        for argument in arguments
    )
    return select_callable(
        candidates,
        actual,
        callable_id=candidates[0].callable_id,
        span=span,
    )


def _resolve_capability_signature(
    emitter: _HandlerEmitterV1,
    owner_id: str,
    reference: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    symbol = resolve_symbol(
        emitter.plan,
        owner_id,
        reference,
        NAMESPACE_CAPABILITY,
        span=span,
    )
    candidates = _dedupe_signatures(
        item for item in emitter.types.capabilities
        if item.callable_id == symbol.semantic_id
    )
    if len(candidates) != 1:
        raise TevScriptError(
            "TEVS_V1_LOWER_CALL_SIGNATURE",
            f"capability {symbol.semantic_id!r} lacks one canonical signature",
            span,
        )
    return candidates[0]


def _emit_arguments(
    arguments: tuple[Expr, ...],
    parameter_types: tuple[ResolvedTypeV1, ...],
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    call_depth: int,
) -> None:
    if len(arguments) != len(parameter_types):
        raise TevScriptError(
            "TEVS_V1_LOWER_CALL_SIGNATURE",
            f"expected {len(parameter_types)} arguments, got {len(arguments)}",
        )
    for argument, expected in zip(arguments, parameter_types, strict=True):
        _emit_expr(
            argument,
            emitter,
            scope,
            owner_id=owner_id,
            source_id=source_id,
            expected=expected,
            call_depth=call_depth,
        )


def _emit_sugar_capability(
    capability_id: str,
    arguments: tuple[Expr, ...],
    emitter: _HandlerEmitterV1,
    scope: _LowerScopeV1,
    *,
    owner_id: str,
    source_id: str,
    span: SourceSpan,
    call_depth: int,
) -> None:
    signature = _resolve_capability_signature(
        emitter,
        owner_id,
        capability_id,
        span,
    )
    _require_v2_signature(signature, span)
    _emit_arguments(
        arguments,
        signature.parameters,
        emitter,
        scope,
        owner_id=owner_id,
        source_id=source_id,
        call_depth=call_depth,
    )
    _register_capability(emitter, signature, span)
    emitter.emit(
        {
            "op": "CALL_CAPABILITY",
            "capability_id": signature.callable_id,
            "argc": len(arguments),
            "return_type": signature.return_type.type_id,
            "kind": signature.kind,
        },
        span,
        source_id,
    )


def _register_capability(
    emitter: _HandlerEmitterV1,
    signature: CallableSignatureV1,
    span: SourceSpan,
) -> None:
    previous = emitter.capabilities.get(signature.callable_id)
    if previous is not None and _signature_key(previous) != _signature_key(signature):
        raise TevScriptError(
            "TEVS_V1_LOWER_CAPABILITY_CONFLICT",
            f"conflicting selected signatures for {signature.callable_id!r}",
            span,
        )
    emitter.capabilities[signature.callable_id] = signature


def _handler_signatures(
    model: CompositeModelV1,
) -> dict[str, tuple[ResolvedTypeV1, ...]]:
    result: dict[str, tuple[ResolvedTypeV1, ...]] = {}
    for fragment in model.handler_fragments:
        previous = result.get(fragment.declaration.event_id)
        if previous is not None and tuple(item.type_id for item in previous) != tuple(
            item.type_id for item in fragment.parameter_types
        ):
            raise TevScriptError(
                "TEVS_V1_LOWER_HANDLER_SIGNATURE",
                f"inconsistent composed signature for {fragment.declaration.event_id!r}",
                fragment.declaration.span,
            )
        result[fragment.declaration.event_id] = fragment.parameter_types
    return result


def _all_event_signatures(
    summary: CompositeSummaryV1,
    handler_signatures: dict[str, tuple[ResolvedTypeV1, ...]],
) -> dict[str, tuple[str, ...]]:
    result = {
        event_id: tuple(item.type_id for item in parameters)
        for event_id, parameters in handler_signatures.items()
    }
    for event_id, signature in _emitted_event_signatures(summary).items():
        previous = result.get(event_id)
        if previous is not None and previous != signature:
            raise TevScriptError(
                "TEVS_V1_LOWER_EVENT_SIGNATURE",
                f"event {event_id!r} static signature disagreement",
            )
        result[event_id] = signature
    return result


def _emitted_event_signatures(
    summary: CompositeSummaryV1,
) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for handler in summary.handlers:
        for event_id, signature in handler.emitted_events:
            previous = result.get(event_id)
            if previous is not None and previous != signature:
                raise TevScriptError(
                    "TEVS_V1_LOWER_EVENT_SIGNATURE",
                    f"event {event_id!r} has conflicting static summaries",
                )
            result[event_id] = signature
    return result


def _canonical_parameter_names(
    count: int,
    forbidden: set[str],
) -> tuple[str, ...]:
    names: list[str] = []
    used = set(forbidden)
    for index in range(count):
        suffix = index
        while True:
            candidate = f"_tev_p{suffix}"
            suffix += count + 1
            if candidate not in used:
                used.add(candidate)
                names.append(candidate)
                break
    return tuple(names)


def _lookup_lowered_value(
    scope: _LowerScopeV1,
    reference: str,
    span: SourceSpan,
) -> _BindingV1:
    parts = reference.split(".")
    binding = scope.lookup(parts[0])
    if binding is None:
        raise TevScriptError(
            "TEVS_V1_LOWER_VALUE_UNKNOWN",
            f"unknown lowered value {parts[0]!r}",
            span,
        )
    if len(parts) != 1:
        _raise_ir3(span, "runtime record field path")
    return binding


def _require_v2_value_type(
    type_ref: ResolvedTypeV1,
    span: SourceSpan,
    context: str,
) -> None:
    if type_ref.type_id not in IR_V2_VALUE_TYPES:
        raise TevScriptError(
            "TEVS_V1_LOWER_IR3_REQUIRED",
            f"{context} uses V1-only type {type_ref.type_id}",
            span,
        )


def _require_v2_signature(
    signature: CallableSignatureV1,
    span: SourceSpan,
) -> None:
    type_ids = [
        *(item.type_id for item in signature.parameters),
        signature.return_type.type_id,
    ]
    if any(type_id not in IR_V2_SIGNATURE_TYPES for type_id in type_ids):
        raise TevScriptError(
            "TEVS_V1_LOWER_IR3_REQUIRED",
            f"callable {signature.callable_id!r} uses V1-only signature types {type_ids}",
            span,
        )


def _signature_key(
    signature: CallableSignatureV1,
) -> tuple[object, ...]:
    return (
        signature.callable_id,
        tuple(item.type_id for item in signature.parameters),
        signature.return_type.type_id,
        signature.kind,
    )


def _dedupe_signatures(
    signatures: Iterable[CallableSignatureV1],
) -> list[CallableSignatureV1]:
    by_key: dict[tuple[object, ...], CallableSignatureV1] = {}
    for signature in signatures:
        key = _signature_key(signature)
        current = by_key.get(key)
        if current is None or signature.owner_id < current.owner_id:
            by_key[key] = signature
    return sorted(
        by_key.values(),
        key=lambda item: (_signature_key(item), item.owner_id),
    )


def _try_resolve(
    plan: LinkPlanV1,
    owner_id: str,
    reference: str,
    namespace: str,
    span: SourceSpan,
) -> tuple[SymbolV1 | None, TevScriptError | None]:
    try:
        return (
            resolve_symbol(
                plan,
                owner_id,
                reference,
                namespace,
                span=span,
            ),
            None,
        )
    except TevScriptError as exc:
        return None, exc


def _semantic_debug_span(
    span: SourceSpan,
    source_id: str,
) -> dict[str, int | str]:
    return {
        "path": source_id,
        "start_offset": span.start_offset,
        "end_offset": span.end_offset,
        "line": span.line,
        "column": span.column,
    }


def _raise_ir3(span: SourceSpan, feature: str) -> None:
    raise TevScriptError(
        "TEVS_V1_LOWER_IR3_REQUIRED",
        f"{feature} requires the future IR V3 runtime value profile",
        span,
    )
