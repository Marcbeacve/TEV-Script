from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .ast_v1 import (
    AnimateStmt,
    AssignStmt,
    CallStmt,
    EmitStmt,
    EnumPattern,
    ErrPattern,
    Expr,
    ForStmt,
    FunctionDecl,
    IfStmt,
    LetStmt,
    LogStmt,
    MatchStmt,
    MoveStmt,
    NonePattern,
    OkPattern,
    ReturnStmt,
    SomePattern,
)
from .behavior_model_v1 import (
    BehaviorModelIndexV1,
    CompositeModelV1,
    build_behavior_model,
)
from .canonical import canonical_hash, canonical_json
from .diagnostics import SourceSpan, TevScriptError
from .linker_v1 import (
    LinkPlanV1,
    NAMESPACE_CAPABILITY,
    NAMESPACE_FUNCTION,
    NAMESPACE_TYPE,
    SymbolV1,
    resolve_symbol,
)
from .semantic_types_v1 import (
    CallableSignatureV1,
    ResolvedTypeV1,
    TypeEnvironmentV1,
    build_type_environment,
    primitive_type,
    require_assignable,
    resolve_type,
    select_callable,
)


@dataclass(frozen=True, slots=True)
class FunctionSummaryV1:
    function_id: str
    calls: tuple[str, ...]

    def semantic_surface(self) -> dict[str, object]:
        return {"function_id": self.function_id, "calls": list(self.calls)}


@dataclass(frozen=True, slots=True)
class HandlerSummaryV1:
    event_id: str
    parameters: tuple[tuple[str, str], ...]
    capabilities: tuple[str, ...]
    emitted_events: tuple[tuple[str, tuple[str, ...]], ...]

    def semantic_surface(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "parameters": [{"name": name, "type": type_id} for name, type_id in self.parameters],
            "capabilities": list(self.capabilities),
            "emitted_events": [
                {"event_id": event_id, "parameters": list(parameters)}
                for event_id, parameters in self.emitted_events
            ],
        }


@dataclass(frozen=True, slots=True)
class CompositeSummaryV1:
    composite_id: str
    kind: str
    states: tuple[tuple[str, str], ...]
    handlers: tuple[HandlerSummaryV1, ...]

    def semantic_surface(self) -> dict[str, object]:
        return {
            "composite_id": self.composite_id,
            "kind": self.kind,
            "states": [{"name": name, "type": type_id} for name, type_id in self.states],
            "handlers": [item.semantic_surface() for item in self.handlers],
        }


@dataclass(frozen=True, slots=True)
class StaticSemanticsV1:
    plan: LinkPlanV1
    types: TypeEnvironmentV1
    behavior_model: BehaviorModelIndexV1
    functions: tuple[FunctionSummaryV1, ...]
    composites: tuple[CompositeSummaryV1, ...]

    def semantic_index(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_STATIC_SEMANTICS_INDEX_V2",
            "language_version": "1.0.0",
            "program_id": self.plan.program_id,
            "link_index_hash": self.plan.index_hash,
            "types": _type_environment_surface(self.types),
            "behavior_closures": _behavior_model_surface(self.behavior_model),
            "functions": [item.semantic_surface() for item in self.functions],
            "composites": [item.semantic_surface() for item in self.composites],
        }

    @property
    def canonical_json(self) -> str:
        return canonical_json(self.semantic_index())

    @property
    def semantic_hash(self) -> str:
        return canonical_hash(self.semantic_index())


@dataclass(frozen=True, slots=True)
class _LocalCompositeCheckV1:
    composite_id: str
    handlers: tuple[HandlerSummaryV1, ...]

    def handler(self, event_id: str) -> HandlerSummaryV1 | None:
        for item in self.handlers:
            if item.event_id == event_id:
                return item
        return None


@dataclass(slots=True)
class _ScopeV1:
    states: dict[str, ResolvedTypeV1]
    frames: list[dict[str, ResolvedTypeV1]] = field(default_factory=list)

    def push(self) -> None:
        self.frames.append({})

    def pop(self) -> None:
        self.frames.pop()

    def declare(self, name: str, type_ref: ResolvedTypeV1, span: SourceSpan) -> None:
        if name in self.states or any(name in frame for frame in self.frames):
            raise TevScriptError(
                "TEVS_V1_SCOPE_SHADOWING",
                f"name {name!r} would shadow an existing state, parameter, or local",
                span,
            )
        if not self.frames:
            self.push()
        self.frames[-1][name] = type_ref

    def lookup(self, name: str) -> ResolvedTypeV1 | None:
        for frame in reversed(self.frames):
            if name in frame:
                return frame[name]
        return self.states.get(name)


@dataclass(slots=True)
class _CheckContextV1:
    plan: LinkPlanV1
    types: TypeEnvironmentV1
    owner_id: str
    scope: _ScopeV1
    mode: str
    capabilities: set[str] = field(default_factory=set)
    function_calls: set[str] = field(default_factory=set)
    emitted_events: dict[str, tuple[str, ...]] = field(default_factory=dict)
    handler_signatures: dict[str, tuple[ResolvedTypeV1, ...]] = field(default_factory=dict)


def analyze_v1_static_semantics(plan: LinkPlanV1) -> StaticSemanticsV1:
    types = build_type_environment(plan)
    behavior_model = build_behavior_model(plan, types)
    function_summaries = _check_functions(plan, types)
    _validate_function_call_graph(types, function_summaries)

    local_checks = {
        model.composite_id: _check_local_composite(plan, types, model)
        for model in behavior_model.composites
    }
    composites = tuple(
        sorted(
            (
                _aggregate_composite_summary(model, local_checks)
                for model in behavior_model.composites
            ),
            key=lambda item: (item.kind, item.composite_id),
        )
    )
    return StaticSemanticsV1(
        plan,
        types,
        behavior_model,
        tuple(sorted(function_summaries, key=lambda item: item.function_id)),
        composites,
    )


def _type_environment_surface(types: TypeEnvironmentV1) -> dict[str, object]:
    return {
        "records": [
            {
                "type_id": item.type_id,
                "fields": [
                    {"name": name, "type": type_ref.type_id}
                    for name, type_ref in item.fields
                ],
            }
            for item in types.records
        ],
        "enums": [
            {"type_id": item.type_id, "variants": list(item.variants)}
            for item in types.enums
        ],
        "functions": [
            {
                "function_id": item.callable_id,
                "parameters": [parameter.type_id for parameter in item.parameters],
                "return_type": item.return_type.type_id,
                "origin": "builtin" if item.declaration is None else "source",
            }
            for item in types.functions
        ],
        "capabilities": [
            {
                "capability_id": item.callable_id,
                "parameters": [parameter.type_id for parameter in item.parameters],
                "return_type": item.return_type.type_id,
                "kind": item.kind,
                "origin": "builtin" if item.declaration is None else "source",
            }
            for item in types.capabilities
        ],
    }


def _behavior_model_surface(model: BehaviorModelIndexV1) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for composite in model.composites:
        result.append(
            {
                "composite_id": composite.composite_id,
                "kind": composite.kind,
                "flattened_behaviors": list(composite.flattened_behaviors),
                "visible_states": [
                    {
                        "name": item.declaration.name,
                        "type": item.type_ref.type_id,
                        "component_id": item.component_id,
                    }
                    for item in sorted(
                        composite.visible_states,
                        key=lambda value: value.declaration.name,
                    )
                ],
                # Fragment order is semantic and therefore deliberately unsorted.
                "handler_fragments": [
                    {
                        "event_id": item.declaration.event_id,
                        "component_id": item.component_id,
                        "parameters": [type_ref.type_id for type_ref in item.parameter_types],
                    }
                    for item in composite.handler_fragments
                ],
            }
        )
    return result


def _check_functions(
    plan: LinkPlanV1,
    types: TypeEnvironmentV1,
) -> list[FunctionSummaryV1]:
    summaries: list[FunctionSummaryV1] = []
    for unit in plan.units:
        for symbol in unit.symbols:
            declaration = symbol.declaration
            if not isinstance(declaration, FunctionDecl):
                continue
            signature = _unique_user_function(types, symbol.semantic_id, declaration.span)
            scope = _ScopeV1(states={})
            scope.push()
            seen: set[str] = set()
            for parameter, parameter_type in zip(
                declaration.parameters,
                signature.parameters,
                strict=True,
            ):
                if parameter.name in seen:
                    raise TevScriptError(
                        "TEVS_V1_TYPE_PARAMETER_DUPLICATE",
                        f"duplicate function parameter {parameter.name!r}",
                        parameter.span,
                    )
                seen.add(parameter.name)
                scope.declare(parameter.name, parameter_type, parameter.span)
            context = _CheckContextV1(plan, types, unit.unit_id, scope, "pure")
            actual = _check_expr(
                declaration.expression,
                context,
                expected=signature.return_type,
            )
            require_assignable(actual, signature.return_type, declaration.expression.span)
            summaries.append(
                FunctionSummaryV1(
                    symbol.semantic_id,
                    tuple(sorted(context.function_calls)),
                )
            )
    return summaries


def _check_local_composite(
    plan: LinkPlanV1,
    types: TypeEnvironmentV1,
    model: CompositeModelV1,
) -> _LocalCompositeCheckV1:
    state_types = model.state_types
    for state_source in model.visible_states:
        if not state_source.type_ref.is_storable:
            raise TevScriptError(
                "TEVS_V1_TYPE_UNIT_PLACEMENT",
                f"state {state_source.declaration.name!r} cannot use {state_source.type_ref.type_id}",
                state_source.declaration.span,
            )

    # Every declaration is checked exactly once in its owning component. Used
    # behavior declarations are validated in their own model and merely become
    # visible state/handler fragments in consumers.
    for state_source in model.visible_states:
        if state_source.component_id != model.composite_id:
            continue
        init_context = _CheckContextV1(
            plan,
            types,
            state_source.owner_id,
            _ScopeV1(states={}),
            "initializer",
        )
        actual = _check_expr(
            state_source.declaration.initial,
            init_context,
            expected=state_source.type_ref,
        )
        require_assignable(
            actual,
            state_source.type_ref,
            state_source.declaration.initial.span,
        )

    composed_signatures = _composed_handler_signatures(model)
    local_seen: set[str] = set()
    local_emitted: dict[str, tuple[str, ...]] = {}
    summaries: list[HandlerSummaryV1] = []

    for fragment in model.local_handler_fragments:
        handler = fragment.declaration
        if handler.event_id in local_seen:
            raise TevScriptError(
                "TEVS_V1_TYPE_HANDLER_DUPLICATE",
                f"duplicate local handler for event {handler.event_id!r} in {model.composite_id}",
                handler.span,
            )
        local_seen.add(handler.event_id)
        if handler.event_id in {"start", "update"} and fragment.parameter_types:
            raise TevScriptError(
                "TEVS_V1_TYPE_BUILTIN_EVENT_SIGNATURE",
                f"built-in event {handler.event_id!r} takes no parameters",
                handler.span,
            )

        scope = _ScopeV1(states=state_types)
        scope.push()
        names: list[str] = []
        seen_names: set[str] = set()
        for parameter, parameter_type in zip(
            handler.parameters,
            fragment.parameter_types,
            strict=True,
        ):
            if parameter.name in seen_names:
                raise TevScriptError(
                    "TEVS_V1_TYPE_PARAMETER_DUPLICATE",
                    f"duplicate event parameter {parameter.name!r}",
                    parameter.span,
                )
            if not parameter_type.is_storable:
                raise TevScriptError(
                    "TEVS_V1_TYPE_UNIT_PLACEMENT",
                    f"event parameter {parameter.name!r} cannot use {parameter_type.type_id}",
                    parameter.span,
                )
            seen_names.add(parameter.name)
            names.append(parameter.name)
            scope.declare(parameter.name, parameter_type, parameter.span)

        context = _CheckContextV1(
            plan,
            types,
            fragment.owner_id,
            scope,
            "behavior" if model.kind == "behavior" else "handler",
            handler_signatures=composed_signatures,
        )
        _check_statements(handler.body, context)

        for event_id, signature in context.emitted_events.items():
            previous = local_emitted.get(event_id)
            if previous is not None and previous != signature:
                raise TevScriptError(
                    "TEVS_V1_TYPE_EVENT_SIGNATURE_CONFLICT",
                    f"event {event_id!r} emitted with conflicting signatures {previous} and {signature}",
                    handler.span,
                )
            local_emitted[event_id] = signature

        summaries.append(
            HandlerSummaryV1(
                handler.event_id,
                tuple(
                    (name, type_ref.type_id)
                    for name, type_ref in zip(
                        names,
                        fragment.parameter_types,
                        strict=True,
                    )
                ),
                tuple(sorted(context.capabilities)),
                tuple(sorted(context.emitted_events.items())),
            )
        )

    return _LocalCompositeCheckV1(
        model.composite_id,
        tuple(sorted(summaries, key=lambda item: item.event_id)),
    )


def _aggregate_composite_summary(
    model: CompositeModelV1,
    local_checks: dict[str, _LocalCompositeCheckV1],
) -> CompositeSummaryV1:
    signatures = _composed_handler_signatures(model)
    by_event: dict[str, list[HandlerSummaryV1]] = {}

    for fragment in model.handler_fragments:
        checked = local_checks[fragment.component_id].handler(fragment.declaration.event_id)
        if checked is None:
            raise AssertionError(
                f"missing local static summary for {fragment.component_id}:{fragment.declaration.event_id}"
            )
        by_event.setdefault(fragment.declaration.event_id, []).append(checked)

    global_emitted: dict[str, tuple[str, ...]] = {}
    handlers: list[HandlerSummaryV1] = []
    for event_id in sorted(by_event):
        parts = by_event[event_id]
        capability_union = sorted(
            {capability for part in parts for capability in part.capabilities}
        )
        event_emitted: dict[str, tuple[str, ...]] = {}
        for part in parts:
            for emitted_event, emitted_signature in part.emitted_events:
                normalized = _normalize_emitted_signature(
                    emitted_event,
                    emitted_signature,
                    signatures.get(emitted_event),
                )
                previous = event_emitted.get(emitted_event)
                if previous is not None and previous != normalized:
                    raise TevScriptError(
                        "TEVS_V1_TYPE_EVENT_SIGNATURE_CONFLICT",
                        f"event {emitted_event!r} emitted with conflicting signatures {previous} and {normalized} in {model.composite_id}",
                    )
                event_emitted[emitted_event] = normalized

                global_previous = global_emitted.get(emitted_event)
                if global_previous is not None and global_previous != normalized:
                    raise TevScriptError(
                        "TEVS_V1_TYPE_EVENT_SIGNATURE_CONFLICT",
                        f"event {emitted_event!r} emitted with conflicting signatures {global_previous} and {normalized} in {model.composite_id}",
                    )
                global_emitted[emitted_event] = normalized

        parameter_names = _canonical_composed_parameter_names(model, event_id)
        parameter_types = signatures[event_id]
        handlers.append(
            HandlerSummaryV1(
                event_id,
                tuple(
                    (name, type_ref.type_id)
                    for name, type_ref in zip(
                        parameter_names,
                        parameter_types,
                        strict=True,
                    )
                ),
                tuple(capability_union),
                tuple(sorted(event_emitted.items())),
            )
        )

    return CompositeSummaryV1(
        model.composite_id,
        model.kind,
        tuple(
            sorted(
                (name, type_ref.type_id)
                for name, type_ref in model.state_types.items()
            )
        ),
        tuple(handlers),
    )


def _composed_handler_signatures(
    model: CompositeModelV1,
) -> dict[str, tuple[ResolvedTypeV1, ...]]:
    signatures: dict[str, tuple[ResolvedTypeV1, ...]] = {}
    for fragment in model.handler_fragments:
        event_id = fragment.declaration.event_id
        previous = signatures.get(event_id)
        if previous is not None:
            previous_ids = tuple(item.type_id for item in previous)
            current_ids = tuple(item.type_id for item in fragment.parameter_types)
            if previous_ids != current_ids:
                raise TevScriptError(
                    "TEVS_V1_BEHAVIOR_HANDLER_SIGNATURE_CONFLICT",
                    f"event {event_id!r} has conflicting signatures in {model.composite_id}: {previous_ids} vs {current_ids}",
                    fragment.declaration.span,
                )
        signatures[event_id] = fragment.parameter_types
    return signatures


def _canonical_composed_parameter_names(
    model: CompositeModelV1,
    event_id: str,
) -> tuple[str, ...]:
    fragments = [
        item for item in model.handler_fragments
        if item.declaration.event_id == event_id
    ]
    if not fragments:
        return ()
    # Prefer the entity/behavior-local fragment when one exists. Otherwise the
    # first dependency fragment in semantic composition order supplies names.
    local = next(
        (item for item in fragments if item.component_id == model.composite_id),
        fragments[0],
    )
    return tuple(parameter.name for parameter in local.declaration.parameters)


def _normalize_emitted_signature(
    event_id: str,
    actual: tuple[str, ...],
    expected: tuple[ResolvedTypeV1, ...] | None,
) -> tuple[str, ...]:
    if expected is None:
        return actual
    if len(actual) != len(expected):
        raise TevScriptError(
            "TEVS_V1_TYPE_EVENT_HANDLER_SIGNATURE",
            f"event {event_id!r} expects {len(expected)} parameters, emitted {len(actual)}",
        )
    expected_ids = tuple(item.type_id for item in expected)
    for actual_id, expected_id in zip(actual, expected_ids, strict=True):
        if actual_id != expected_id and not (
            actual_id == "Int" and expected_id == "Rat"
        ):
            raise TevScriptError(
                "TEVS_V1_TYPE_EVENT_HANDLER_SIGNATURE",
                f"event {event_id!r} expects {expected_ids}, emitted {actual}",
            )
    return expected_ids


def _check_statements(
    statements: tuple[object, ...],
    context: _CheckContextV1,
) -> None:
    for statement in statements:
        if isinstance(statement, LetStmt):
            expected = (
                resolve_type(context.plan, context.owner_id, statement.type_ref)
                if statement.type_ref is not None
                else None
            )
            if expected is not None and not expected.is_storable:
                raise TevScriptError(
                    "TEVS_V1_TYPE_UNIT_PLACEMENT",
                    f"local {statement.name!r} cannot use {expected.type_id}",
                    statement.span,
                )
            actual = _check_expr(statement.expression, context, expected=expected)
            selected = expected or actual
            if expected is not None:
                require_assignable(actual, expected, statement.expression.span)
            if not selected.is_storable:
                raise TevScriptError(
                    "TEVS_V1_TYPE_UNIT_PLACEMENT",
                    f"local {statement.name!r} cannot use {selected.type_id}",
                    statement.span,
                )
            context.scope.declare(statement.name, selected, statement.span)
            continue

        if isinstance(statement, AssignStmt):
            expected = context.scope.states.get(statement.name)
            if expected is None:
                if context.scope.lookup(statement.name) is not None:
                    raise TevScriptError(
                        "TEVS_V1_TYPE_IMMUTABLE_ASSIGNMENT",
                        f"{statement.name!r} is immutable; assignment targets state only",
                        statement.span,
                    )
                raise TevScriptError(
                    "TEVS_V1_TYPE_STATE_UNKNOWN",
                    f"unknown state {statement.name!r}",
                    statement.span,
                )
            actual = _check_expr(statement.expression, context, expected=expected)
            require_assignable(actual, expected, statement.expression.span)
            continue

        if isinstance(statement, CallStmt):
            signature = _resolve_capability_statement(
                context,
                statement.capability_id,
                statement.span,
            )
            if not signature.return_type.is_unit:
                raise TevScriptError(
                    "TEVS_V1_TYPE_CALL_RESULT_UNUSED",
                    f"capability {signature.callable_id!r} returns {signature.return_type.type_id}; use it as an expression",
                    statement.span,
                )
            _check_arguments(
                statement.arguments,
                signature.parameters,
                context,
                statement.span,
            )
            context.capabilities.add(signature.callable_id)
            continue

        if isinstance(statement, EmitStmt):
            declared = context.handler_signatures.get(statement.event_id)
            if declared is not None:
                _check_arguments(statement.arguments, declared, context, statement.span)
                signature = tuple(item.type_id for item in declared)
            else:
                signature = tuple(
                    _check_expr(argument, context).type_id
                    for argument in statement.arguments
                )
            previous = context.emitted_events.get(statement.event_id)
            if previous is not None and previous != signature:
                raise TevScriptError(
                    "TEVS_V1_TYPE_EVENT_SIGNATURE_CONFLICT",
                    f"event {statement.event_id!r} emitted with conflicting signatures {previous} and {signature}",
                    statement.span,
                )
            context.emitted_events[statement.event_id] = signature
            continue

        if isinstance(statement, LogStmt):
            _check_expected(statement.expression, primitive_type("Text"), context)
            context.capabilities.add("debug.log")
            continue

        if isinstance(statement, MoveStmt):
            _check_expected(statement.expression, primitive_type("Vec2"), context)
            context.capabilities.add("motion.move2d")
            continue

        if isinstance(statement, AnimateStmt):
            _check_expected(statement.expression, primitive_type("Text"), context)
            context.capabilities.add("animation.play")
            continue

        if isinstance(statement, IfStmt):
            _check_expected(statement.condition, primitive_type("Bool"), context)
            context.scope.push()
            try:
                _check_statements(statement.then_body, context)
            finally:
                context.scope.pop()
            context.scope.push()
            try:
                _check_statements(statement.else_body, context)
            finally:
                context.scope.pop()
            continue

        if isinstance(statement, ForStmt):
            context.scope.push()
            try:
                context.scope.declare(
                    statement.variable,
                    primitive_type("Int"),
                    statement.span,
                )
                _check_statements(statement.body, context)
            finally:
                context.scope.pop()
            continue

        if isinstance(statement, MatchStmt):
            _check_match(statement, context)
            continue

        if isinstance(statement, ReturnStmt):
            if context.mode == "behavior":
                raise TevScriptError(
                    "TEVS_V1_BEHAVIOR_RETURN",
                    "behavior handler fragments cannot contain return",
                    statement.span,
                )
            continue

        raise TypeError(f"unsupported V1 statement {type(statement).__name__}")


def _check_expr(
    expression: Expr,
    context: _CheckContextV1,
    expected: ResolvedTypeV1 | None = None,
) -> ResolvedTypeV1:
    kind = expression.kind
    if kind == "bool":
        result = primitive_type("Bool")
    elif kind == "int":
        result = primitive_type("Int")
    elif kind == "rat":
        result = primitive_type("Rat")
    elif kind == "text":
        result = primitive_type("Text")
    elif kind == "group":
        result = _check_expr(
            expression.children[0],
            context,
            expected=expected,
        )
    elif kind == "name":
        result = _resolve_value_path(
            str(expression.value),
            context,
            expression.span,
        )
    elif kind == "field":
        target = _check_expr(expression.children[0], context)
        result = _record_field_type(
            target,
            str(expression.value),
            context,
            expression.span,
        )
    elif kind == "enum":
        type_name, variant = expression.value
        type_symbol = resolve_symbol(
            context.plan,
            context.owner_id,
            type_name,
            NAMESPACE_TYPE,
            span=expression.span,
        )
        result = _type_from_symbol(type_symbol, expression.span)
        enum = context.types.enum(result.type_id)
        if enum is None:
            raise TevScriptError(
                "TEVS_V1_TYPE_ENUM_EXPECTED",
                f"{type_name!r} is not an enum type",
                expression.span,
            )
        if variant not in enum.variants:
            raise TevScriptError(
                "TEVS_V1_TYPE_ENUM_VARIANT_UNKNOWN",
                f"unknown variant {variant!r} for {enum.type_id}",
                expression.span,
            )
    elif kind == "record":
        type_name, field_inits = expression.value
        type_symbol = resolve_symbol(
            context.plan,
            context.owner_id,
            type_name,
            NAMESPACE_TYPE,
            span=expression.span,
        )
        result = _type_from_symbol(type_symbol, expression.span)
        record = context.types.record(result.type_id)
        if record is None:
            raise TevScriptError(
                "TEVS_V1_TYPE_RECORD_EXPECTED",
                f"{type_name!r} is not a record type",
                expression.span,
            )
        expected_fields = {
            name: field_type for name, field_type in record.fields
        }
        seen: set[str] = set()
        for field in field_inits:
            if field.name in seen:
                raise TevScriptError(
                    "TEVS_V1_TYPE_RECORD_INIT_DUPLICATE",
                    f"duplicate initializer for field {field.name!r}",
                    field.span,
                )
            seen.add(field.name)
            field_type = expected_fields.get(field.name)
            if field_type is None:
                raise TevScriptError(
                    "TEVS_V1_TYPE_RECORD_FIELD_UNKNOWN",
                    f"unknown field {field.name!r} for {record.type_id}",
                    field.span,
                )
            actual = _check_expr(
                field.expression,
                context,
                expected=field_type,
            )
            require_assignable(actual, field_type, field.expression.span)
        missing = sorted(set(expected_fields) - seen)
        if missing:
            raise TevScriptError(
                "TEVS_V1_TYPE_RECORD_FIELD_MISSING",
                f"missing required fields for {record.type_id}: {missing}",
                expression.span,
            )
    elif kind == "some":
        if expected is not None:
            if expected.kind != "option":
                raise TevScriptError(
                    "TEVS_V1_TYPE_CONSTRUCTOR_CONTEXT",
                    f"Some requires Option<T> context, got {expected.type_id}",
                    expression.span,
                )
            inner_expected = expected.arguments[0]
            actual = _check_expr(
                expression.children[0],
                context,
                expected=inner_expected,
            )
            require_assignable(
                actual,
                inner_expected,
                expression.children[0].span,
            )
            result = expected
        else:
            inner = _check_expr(expression.children[0], context)
            result = ResolvedTypeV1(
                "option",
                f"Option<{inner.type_id}>",
                (inner,),
            )
    elif kind == "none":
        if expected is None or expected.kind != "option":
            raise TevScriptError(
                "TEVS_V1_TYPE_UNDERCONSTRAINED_NONE",
                "None requires an expected Option<T> type",
                expression.span,
            )
        result = expected
    elif kind in {"ok", "err"}:
        if expected is None or expected.kind != "result":
            raise TevScriptError(
                "TEVS_V1_TYPE_UNDERCONSTRAINED_RESULT",
                f"{kind.title()} requires an expected Result<T,E> type",
                expression.span,
            )
        index = 0 if kind == "ok" else 1
        payload_expected = expected.arguments[index]
        actual = _check_expr(
            expression.children[0],
            context,
            expected=payload_expected,
        )
        require_assignable(
            actual,
            payload_expected,
            expression.children[0].span,
        )
        result = expected
    elif kind == "unary":
        operand = _check_expr(expression.children[0], context)
        operator = str(expression.value)
        if operator == "not" and operand.type_id == "Bool":
            result = primitive_type("Bool")
        elif operator == "-" and operand.is_numeric:
            result = operand
        else:
            raise TevScriptError(
                "TEVS_V1_TYPE_UNARY",
                f"operator {operator!r} does not accept {operand.type_id}",
                expression.span,
            )
    elif kind == "binary":
        result = _check_binary(expression, context)
    elif kind == "call":
        result = _check_call_expression(expression, context)
    else:
        raise TevScriptError(
            "TEVS_V1_TYPE_EXPRESSION_KIND",
            f"unsupported expression kind {kind!r}",
            expression.span,
        )

    if expected is not None and kind not in {
        "some",
        "none",
        "ok",
        "err",
        "group",
    }:
        require_assignable(result, expected, expression.span)
    return result


def _check_binary(
    expression: Expr,
    context: _CheckContextV1,
) -> ResolvedTypeV1:
    operator = str(expression.value)
    left = _check_expr(expression.children[0], context)
    right = _check_expr(expression.children[1], context)

    if operator in {"and", "or"}:
        if left.type_id == right.type_id == "Bool":
            return primitive_type("Bool")
    elif operator in {"==", "!="}:
        if left.type_id == right.type_id or (
            left.is_numeric and right.is_numeric
        ):
            return primitive_type("Bool")
    elif operator in {"<", "<=", ">", ">="}:
        if left.is_numeric and right.is_numeric:
            return primitive_type("Bool")
    elif operator in {"+", "-"}:
        if left.type_id == right.type_id == "Int":
            return primitive_type("Int")
        if left.is_numeric and right.is_numeric:
            return primitive_type("Rat")
        if left.type_id == right.type_id and left.is_vector:
            return left
    elif operator == "*":
        if left.type_id == right.type_id == "Int":
            return primitive_type("Int")
        if left.is_numeric and right.is_numeric:
            return primitive_type("Rat")
        if left.is_vector and right.is_numeric:
            return left
        if right.is_vector and left.is_numeric:
            return right
    elif operator == "/":
        if left.is_numeric and right.is_numeric:
            return primitive_type("Rat")
        if left.is_vector and right.is_numeric:
            return left

    raise TevScriptError(
        "TEVS_V1_TYPE_BINARY",
        f"operator {operator!r} does not accept {left.type_id} and {right.type_id}",
        expression.span,
    )


def _check_call_expression(
    expression: Expr,
    context: _CheckContextV1,
) -> ResolvedTypeV1:
    callee = expression.children[0]
    arguments = tuple(expression.children[1:])
    if callee.kind != "name":
        raise TevScriptError(
            "TEVS_V1_TYPE_CALLABLE_EXPRESSION",
            "V1 calls require a named pure function or observation capability",
            callee.span,
        )
    reference = str(callee.value)
    function_symbol, function_error = _try_resolve(
        context,
        reference,
        NAMESPACE_FUNCTION,
        callee.span,
    )
    capability_symbol, capability_error = _try_resolve(
        context,
        reference,
        NAMESPACE_CAPABILITY,
        callee.span,
    )

    for error in (function_error, capability_error):
        if error is not None and error.diagnostic.code in {
            "TEVS_V1_LINK_NAME_AMBIGUOUS",
            "TEVS_V1_LINK_CAPABILITY_CONFLICT",
        }:
            raise error

    if function_symbol is not None and capability_symbol is not None:
        raise TevScriptError(
            "TEVS_V1_TYPE_CALL_AMBIGUOUS",
            f"call {reference!r} is visible as both a pure function and a capability",
            callee.span,
        )

    if function_symbol is not None:
        candidates = [
            item for item in context.types.functions
            if item.callable_id == function_symbol.semantic_id
        ]
        signature = _select_expression_signature(
            candidates,
            arguments,
            context,
            function_symbol.semantic_id,
            expression.span,
        )
        context.function_calls.add(signature.callable_id)
        return signature.return_type

    if capability_symbol is not None:
        if context.mode == "pure":
            raise TevScriptError(
                "TEVS_V1_PURITY_CAPABILITY",
                f"pure function cannot call capability {capability_symbol.semantic_id!r}",
                expression.span,
            )
        candidates = _dedupe_callable_contracts(
            item for item in context.types.capabilities
            if item.callable_id == capability_symbol.semantic_id
        )
        if len(candidates) != 1:
            raise TevScriptError(
                "TEVS_V1_TYPE_CALL_SIGNATURE",
                f"capability {capability_symbol.semantic_id!r} does not have one canonical V1 signature",
                expression.span,
            )
        signature = candidates[0]
        if signature.kind != "observation":
            raise TevScriptError(
                "TEVS_V1_EFFECT_EXPRESSION",
                f"effect capability {signature.callable_id!r} cannot be used as an expression",
                expression.span,
            )
        if signature.return_type.is_unit:
            raise TevScriptError(
                "TEVS_V1_TYPE_UNIT_EXPRESSION",
                f"capability {signature.callable_id!r} returns Unit",
                expression.span,
            )
        _check_arguments(
            arguments,
            signature.parameters,
            context,
            expression.span,
        )
        context.capabilities.add(signature.callable_id)
        return signature.return_type

    errors = [
        error for error in (function_error, capability_error)
        if error is not None
    ]
    for error in errors:
        if error.diagnostic.code == "TEVS_V1_LINK_PRIVATE_SYMBOL":
            raise error
    raise TevScriptError(
        "TEVS_V1_TYPE_CALL_UNKNOWN",
        f"unknown callable {reference!r}",
        expression.span,
    )


def _select_expression_signature(
    candidates: list[CallableSignatureV1],
    arguments: tuple[Expr, ...],
    context: _CheckContextV1,
    callable_id: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    if not candidates:
        raise TevScriptError(
            "TEVS_V1_TYPE_CALL_UNKNOWN",
            f"missing callable signature for {callable_id!r}",
            span,
        )
    if len(candidates) == 1:
        signature = candidates[0]
        _check_arguments(arguments, signature.parameters, context, span)
        return signature

    actual = tuple(
        _check_expr(argument, context)
        for argument in arguments
    )
    return select_callable(
        candidates,
        actual,
        callable_id=callable_id,
        span=span,
    )


def _resolve_capability_statement(
    context: _CheckContextV1,
    reference: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    symbol = resolve_symbol(
        context.plan,
        context.owner_id,
        reference,
        NAMESPACE_CAPABILITY,
        span=span,
    )
    candidates = _dedupe_callable_contracts(
        item for item in context.types.capabilities
        if item.callable_id == symbol.semantic_id
    )
    if len(candidates) != 1:
        raise TevScriptError(
            "TEVS_V1_TYPE_CALL_SIGNATURE",
            f"capability {symbol.semantic_id!r} does not have one canonical signature",
            span,
        )
    return candidates[0]


def _check_arguments(
    arguments: tuple[Expr, ...],
    expected: tuple[ResolvedTypeV1, ...],
    context: _CheckContextV1,
    span: SourceSpan,
) -> None:
    if len(arguments) != len(expected):
        raise TevScriptError(
            "TEVS_V1_TYPE_CALL_SIGNATURE",
            f"expected {len(expected)} arguments, got {len(arguments)}",
            span,
        )
    for expression, type_ref in zip(arguments, expected, strict=True):
        actual = _check_expr(
            expression,
            context,
            expected=type_ref,
        )
        require_assignable(actual, type_ref, expression.span)


def _check_expected(
    expression: Expr,
    expected: ResolvedTypeV1,
    context: _CheckContextV1,
) -> None:
    actual = _check_expr(expression, context, expected=expected)
    require_assignable(actual, expected, expression.span)


def _resolve_value_path(
    reference: str,
    context: _CheckContextV1,
    span: SourceSpan,
) -> ResolvedTypeV1:
    parts = reference.split(".")
    base = context.scope.lookup(parts[0])
    if base is None:
        raise TevScriptError(
            "TEVS_V1_TYPE_VALUE_UNKNOWN",
            f"unknown value name {parts[0]!r}",
            span,
        )
    current = base
    for field in parts[1:]:
        current = _record_field_type(current, field, context, span)
    return current


def _record_field_type(
    target: ResolvedTypeV1,
    field_name: str,
    context: _CheckContextV1,
    span: SourceSpan,
) -> ResolvedTypeV1:
    record = context.types.record(target.type_id)
    if record is None:
        raise TevScriptError(
            "TEVS_V1_TYPE_FIELD_TARGET",
            f"field access requires a record, got {target.type_id}",
            span,
        )
    field_type = record.field(field_name)
    if field_type is None:
        raise TevScriptError(
            "TEVS_V1_TYPE_RECORD_FIELD_UNKNOWN",
            f"record {record.type_id} has no field {field_name!r}",
            span,
        )
    return field_type


def _type_from_symbol(
    symbol: SymbolV1,
    span: SourceSpan,
) -> ResolvedTypeV1:
    from .ast_v1 import EnumDecl, RecordDecl

    if isinstance(symbol.declaration, RecordDecl):
        return ResolvedTypeV1("record", symbol.semantic_id)
    if isinstance(symbol.declaration, EnumDecl):
        return ResolvedTypeV1("enum", symbol.semantic_id)
    raise TevScriptError(
        "TEVS_V1_TYPE_SYMBOL_KIND",
        f"{symbol.semantic_id!r} is not a nominal V1 type",
        span,
    )


def _check_match(
    statement: MatchStmt,
    context: _CheckContextV1,
) -> None:
    target = _check_expr(statement.expression, context)
    seen: set[str] = set()
    expected_keys: set[str]

    if target.kind == "enum":
        enum = context.types.enum(target.type_id)
        assert enum is not None
        expected_keys = set(enum.variants)
        for arm in statement.arms:
            pattern = arm.pattern
            if not isinstance(pattern, EnumPattern):
                raise TevScriptError(
                    "TEVS_V1_TYPE_MATCH_PATTERN",
                    f"enum match {target.type_id} requires enum variant patterns",
                    pattern.span,
                )
            symbol = resolve_symbol(
                context.plan,
                context.owner_id,
                pattern.type_name,
                NAMESPACE_TYPE,
                span=pattern.span,
            )
            pattern_type = _type_from_symbol(symbol, pattern.span)
            if pattern_type.type_id != target.type_id:
                raise TevScriptError(
                    "TEVS_V1_TYPE_MATCH_PATTERN",
                    f"pattern type {pattern_type.type_id} does not match {target.type_id}",
                    pattern.span,
                )
            key = pattern.variant
            if key not in expected_keys:
                raise TevScriptError(
                    "TEVS_V1_TYPE_ENUM_VARIANT_UNKNOWN",
                    f"unknown variant {key!r} for {target.type_id}",
                    pattern.span,
                )
            _check_match_arm(
                key,
                None,
                arm.body,
                seen,
                context,
                pattern.span,
            )
    elif target.kind == "option":
        expected_keys = {"Some", "None"}
        for arm in statement.arms:
            pattern = arm.pattern
            if isinstance(pattern, SomePattern):
                _check_match_arm(
                    "Some",
                    (pattern.binding, target.arguments[0]),
                    arm.body,
                    seen,
                    context,
                    pattern.span,
                )
            elif isinstance(pattern, NonePattern):
                _check_match_arm(
                    "None",
                    None,
                    arm.body,
                    seen,
                    context,
                    pattern.span,
                )
            else:
                raise TevScriptError(
                    "TEVS_V1_TYPE_MATCH_PATTERN",
                    f"Option match requires Some/None patterns, got {type(pattern).__name__}",
                    pattern.span,
                )
    elif target.kind == "result":
        expected_keys = {"Ok", "Err"}
        for arm in statement.arms:
            pattern = arm.pattern
            if isinstance(pattern, OkPattern):
                _check_match_arm(
                    "Ok",
                    (pattern.binding, target.arguments[0]),
                    arm.body,
                    seen,
                    context,
                    pattern.span,
                )
            elif isinstance(pattern, ErrPattern):
                _check_match_arm(
                    "Err",
                    (pattern.binding, target.arguments[1]),
                    arm.body,
                    seen,
                    context,
                    pattern.span,
                )
            else:
                raise TevScriptError(
                    "TEVS_V1_TYPE_MATCH_PATTERN",
                    f"Result match requires Ok/Err patterns, got {type(pattern).__name__}",
                    pattern.span,
                )
    else:
        raise TevScriptError(
            "TEVS_V1_TYPE_MATCH_TARGET",
            f"match requires enum, Option, or Result; got {target.type_id}",
            statement.expression.span,
        )

    missing = sorted(expected_keys - seen)
    if missing:
        raise TevScriptError(
            "TEVS_V1_TYPE_MATCH_NONEXHAUSTIVE",
            f"non-exhaustive match for {target.type_id}; missing {missing}",
            statement.span,
        )


def _check_match_arm(
    key: str,
    binding: tuple[str, ResolvedTypeV1] | None,
    body: tuple[object, ...],
    seen: set[str],
    context: _CheckContextV1,
    span: SourceSpan,
) -> None:
    if key in seen:
        raise TevScriptError(
            "TEVS_V1_TYPE_MATCH_DUPLICATE_ARM",
            f"duplicate match arm {key!r}",
            span,
        )
    seen.add(key)
    context.scope.push()
    try:
        if binding is not None:
            context.scope.declare(binding[0], binding[1], span)
        _check_statements(body, context)
    finally:
        context.scope.pop()


def _try_resolve(
    context: _CheckContextV1,
    reference: str,
    namespace: str,
    span: SourceSpan,
) -> tuple[SymbolV1 | None, TevScriptError | None]:
    try:
        return (
            resolve_symbol(
                context.plan,
                context.owner_id,
                reference,
                namespace,
                span=span,
            ),
            None,
        )
    except TevScriptError as exc:
        return None, exc


def _dedupe_callable_contracts(
    signatures: Iterable[CallableSignatureV1],
) -> list[CallableSignatureV1]:
    by_contract: dict[tuple[object, ...], CallableSignatureV1] = {}
    for item in signatures:
        key = (
            item.callable_id,
            tuple(parameter.type_id for parameter in item.parameters),
            item.return_type.type_id,
            item.kind,
        )
        current = by_contract.get(key)
        if current is None or item.owner_id < current.owner_id:
            by_contract[key] = item
    return sorted(
        by_contract.values(),
        key=lambda item: (item.callable_id, item.owner_id),
    )


def _unique_user_function(
    types: TypeEnvironmentV1,
    function_id: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    candidates = [
        item for item in types.functions
        if item.callable_id == function_id and item.declaration is not None
    ]
    if len(candidates) != 1:
        raise TevScriptError(
            "TEVS_V1_TYPE_FUNCTION_SIGNATURE",
            f"function {function_id!r} does not have exactly one V1 signature",
            span,
        )
    return candidates[0]


def _validate_function_call_graph(
    types: TypeEnvironmentV1,
    summaries: list[FunctionSummaryV1],
) -> None:
    user_functions = {
        item.callable_id
        for item in types.functions
        if item.declaration is not None
    }
    graph = {
        summary.function_id: tuple(
            sorted(
                call for call in summary.calls
                if call in user_functions
            )
        )
        for summary in summaries
    }
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(function_id: str) -> None:
        mark = state.get(function_id, 0)
        if mark == 2:
            return
        if mark == 1:
            start = stack.index(function_id) if function_id in stack else 0
            cycle = [*stack[start:], function_id]
            signature = next(
                item for item in types.functions
                if item.callable_id == function_id
                and item.declaration is not None
            )
            raise TevScriptError(
                "TEVS_V1_PURITY_RECURSION",
                "recursive pure-function call graph: " + " -> ".join(cycle),
                signature.declaration.span,
            )
        state[function_id] = 1
        stack.append(function_id)
        for dependency in graph.get(function_id, ()):
            visit(dependency)
        stack.pop()
        state[function_id] = 2

    for function_id in sorted(graph):
        visit(function_id)
