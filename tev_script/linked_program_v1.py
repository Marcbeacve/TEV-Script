from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable

from .ast_v1 import (
    AnimateStmt,
    AssignStmt,
    BehaviorDecl,
    CallStmt,
    CapabilityDecl,
    EmitStmt,
    EnumDecl,
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
    RecordDecl,
    ReturnStmt,
    SomePattern,
)
from .canonical import canonical_hash, canonical_json
from .constant_eval_v1 import (
    ConstantEvaluationV1,
    ConstantValueV1,
    evaluate_v1_state_constants,
)
from .contracts_v1 import MAX_LINKED_CANONICAL_JSON_BYTES
from .diagnostics import SourceSpan, TevScriptError
from .linker_v1 import (
    LinkPlanV1,
    NAMESPACE_BEHAVIOR,
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
    primitive_type,
    resolve_type,
    select_callable,
)
from .static_semantics_v1 import (
    CompositeSummaryV1,
    StaticSemanticsV1,
    _CheckContextV1,
    _ScopeV1,
    _check_expr,
)


@dataclass(frozen=True, slots=True)
class LinkedProgramBundleV1:
    program: dict[str, object]
    canonical_json: str
    semantic_hash: str
    static_semantic_hash: str


@dataclass(frozen=True, slots=True)
class _AlphaBindingV1:
    canonical_name: str
    type_ref: ResolvedTypeV1


@dataclass(slots=True)
class _AlphaScopeV1:
    states: dict[str, _AlphaBindingV1]
    frames: list[dict[str, _AlphaBindingV1]] = field(default_factory=list)

    def push(self) -> None:
        self.frames.append({})

    def pop(self) -> None:
        self.frames.pop()

    def declare(
        self,
        source_name: str,
        binding: _AlphaBindingV1,
        span: SourceSpan,
    ) -> None:
        if source_name in self.states or any(
            source_name in frame for frame in self.frames
        ):
            raise TevScriptError(
                "TEVS_V1_LINKED_ALPHA_SHADOW",
                f"alpha normalization encountered invalid shadowing {source_name!r}",
                span,
            )
        if not self.frames:
            self.push()
        self.frames[-1][source_name] = binding

    def lookup(self, source_name: str) -> _AlphaBindingV1 | None:
        for frame in reversed(self.frames):
            if source_name in frame:
                return frame[source_name]
        return self.states.get(source_name)


@dataclass(slots=True)
class _NormalizerV1:
    semantics: StaticSemanticsV1
    owner_id: str
    type_scope: _ScopeV1
    alpha_scope: _AlphaScopeV1
    mode: str
    handler_signatures: dict[str, tuple[ResolvedTypeV1, ...]] = field(
        default_factory=dict
    )
    used_canonical_names: set[str] = field(default_factory=set)
    local_counter: int = 0
    check_context: _CheckContextV1 = field(init=False)

    def __post_init__(self) -> None:
        self.check_context = _CheckContextV1(
            self.semantics.plan,
            self.semantics.types,
            self.owner_id,
            self.type_scope,
            self.mode,
            handler_signatures=self.handler_signatures,
        )

    @property
    def plan(self) -> LinkPlanV1:
        return self.semantics.plan

    @property
    def types(self) -> TypeEnvironmentV1:
        return self.semantics.types

    def push(self) -> None:
        self.type_scope.push()
        self.alpha_scope.push()

    def pop(self) -> None:
        self.type_scope.pop()
        self.alpha_scope.pop()

    def declare(
        self,
        source_name: str,
        type_ref: ResolvedTypeV1,
        canonical_name: str,
        span: SourceSpan,
    ) -> None:
        self.type_scope.declare(source_name, type_ref, span)
        self.alpha_scope.declare(
            source_name,
            _AlphaBindingV1(canonical_name, type_ref),
            span,
        )
        self.used_canonical_names.add(canonical_name)

    def allocate_local(self) -> str:
        while True:
            candidate = f"_l{self.local_counter}"
            self.local_counter += 1
            if candidate not in self.used_canonical_names:
                self.used_canonical_names.add(candidate)
                return candidate


def emit_linked_program_v1(
    semantics: StaticSemanticsV1,
) -> LinkedProgramBundleV1:
    constants = evaluate_v1_state_constants(semantics)
    semantic = {
        "schema": "TEV_SCRIPT_LINKED_PROGRAM_V1",
        "language_version": "1.0.0",
        "program_id": semantics.plan.program_id,
        "modules": _normalize_modules(semantics),
        "capabilities": _normalize_capabilities(semantics),
        "records": _normalize_records(semantics),
        "enums": _normalize_enums(semantics),
        "functions": _normalize_functions(semantics),
        "behaviors": _normalize_behaviors(semantics, constants),
        "entities": _normalize_entities(semantics, constants),
    }
    semantic_hash = canonical_hash(semantic)
    program = dict(semantic)
    program["semantic_hash"] = semantic_hash
    payload = canonical_json(program)
    payload_bytes = len(payload.encode("utf-8"))
    if payload_bytes > MAX_LINKED_CANONICAL_JSON_BYTES:
        raise TevScriptError(
            "TEVS_V1_LINKED_JSON_BUDGET",
            f"canonical linked program exceeds {MAX_LINKED_CANONICAL_JSON_BYTES} bytes: got {payload_bytes}",
        )
    return LinkedProgramBundleV1(
        program=program,
        canonical_json=payload,
        semantic_hash=semantic_hash,
        static_semantic_hash=semantics.semantic_hash,
    )


def _normalize_modules(semantics: StaticSemanticsV1) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for unit in semantics.plan.units:
        if unit.unit_kind != "module":
            continue
        exports = [
            {
                "namespace": _schema_namespace(symbol.namespace),
                "semantic_id": symbol.semantic_id,
            }
            for symbol in unit.symbols
            if symbol.exported and symbol.origin == "source"
        ]
        exports.sort(key=lambda item: (str(item["namespace"]), str(item["semantic_id"])))
        result.append(
            {
                "module_id": unit.unit_id,
                "version": unit.declaration.language_version,
                "imports": sorted(item.module_id for item in unit.declaration.imports),
                "exports": exports,
            }
        )
    result.sort(key=lambda item: str(item["module_id"]))
    return result


def _normalize_capabilities(
    semantics: StaticSemanticsV1,
) -> list[dict[str, object]]:
    groups: dict[str, list[tuple[str, bool, CapabilityDecl]]] = {}
    for unit in semantics.plan.units:
        for symbol in unit.symbols:
            if not isinstance(symbol.declaration, CapabilityDecl):
                continue
            groups.setdefault(symbol.semantic_id, []).append(
                (unit.unit_id, symbol.exported, symbol.declaration)
            )

    result: list[dict[str, object]] = []
    for capability_id in sorted(groups):
        declarations = sorted(groups[capability_id], key=lambda item: item[0])
        owner_id, _exported, declaration = declarations[0]
        parameters = [
            resolve_type(semantics.plan, owner_id, item).type_id
            for item in declaration.parameter_types
        ]
        return_type = resolve_type(
            semantics.plan,
            owner_id,
            declaration.return_type,
        ).type_id
        result.append(
            {
                "capability_id": capability_id,
                "parameters": parameters,
                "return_type": return_type,
                "kind": declaration.capability_kind,
                "declared_in": owner_id,
                "exported": any(item[1] for item in declarations),
            }
        )
    return result


def _normalize_records(semantics: StaticSemanticsV1) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for unit in semantics.plan.units:
        by_id = {symbol.semantic_id: symbol for symbol in unit.symbols}
        for record in semantics.types.records:
            if record.owner_id != unit.unit_id:
                continue
            symbol = by_id[record.type_id]
            result.append(
                {
                    "type_id": record.type_id,
                    "declared_in": record.owner_id,
                    "exported": symbol.exported,
                    "fields": [
                        {"name": name, "type": type_ref.type_id}
                        for name, type_ref in record.fields
                    ],
                }
            )
    result.sort(key=lambda item: str(item["type_id"]))
    return result


def _normalize_enums(semantics: StaticSemanticsV1) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for unit in semantics.plan.units:
        by_id = {symbol.semantic_id: symbol for symbol in unit.symbols}
        for enum in semantics.types.enums:
            if enum.owner_id != unit.unit_id:
                continue
            symbol = by_id[enum.type_id]
            result.append(
                {
                    "type_id": enum.type_id,
                    "declared_in": enum.owner_id,
                    "exported": symbol.exported,
                    "variants": list(enum.variants),
                }
            )
    result.sort(key=lambda item: str(item["type_id"]))
    return result


def _normalize_functions(semantics: StaticSemanticsV1) -> list[dict[str, object]]:
    summaries = {item.function_id: item for item in semantics.functions}
    result: list[dict[str, object]] = []
    for unit in semantics.plan.units:
        for symbol in unit.symbols:
            declaration = symbol.declaration
            if not isinstance(declaration, FunctionDecl):
                continue
            signature = _source_function_signature(
                semantics.types,
                symbol.semantic_id,
                declaration.span,
            )
            type_scope = _ScopeV1(states={})
            alpha_scope = _AlphaScopeV1(states={})
            normalizer = _NormalizerV1(
                semantics,
                unit.unit_id,
                type_scope,
                alpha_scope,
                "pure",
            )
            normalizer.push()
            parameters: list[dict[str, str]] = []
            for index, (parameter, type_ref) in enumerate(
                zip(declaration.parameters, signature.parameters, strict=True)
            ):
                canonical = f"_p{index}"
                normalizer.declare(
                    parameter.name,
                    type_ref,
                    canonical,
                    parameter.span,
                )
                parameters.append(
                    {"name": canonical, "type": type_ref.type_id}
                )
            body = _normalize_expr(
                declaration.expression,
                normalizer,
                expected=signature.return_type,
            )
            normalizer.pop()
            result.append(
                {
                    "function_id": symbol.semantic_id,
                    "declared_in": unit.unit_id,
                    "exported": symbol.exported,
                    "parameters": parameters,
                    "return_type": signature.return_type.type_id,
                    "body": body,
                    "calls": list(summaries[symbol.semantic_id].calls),
                }
            )
    result.sort(key=lambda item: str(item["function_id"]))
    return result


def _normalize_behaviors(
    semantics: StaticSemanticsV1,
    constants: ConstantEvaluationV1,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for unit in semantics.plan.units:
        for symbol in unit.symbols:
            declaration = symbol.declaration
            if not isinstance(declaration, BehaviorDecl):
                continue
            model = semantics.behavior_model.composite(symbol.semantic_id)
            handler_signatures = _handler_signatures(model)
            states = [
                _normalize_state(
                    semantics,
                    constants,
                    symbol.semantic_id,
                    state.name,
                    resolve_type(semantics.plan, unit.unit_id, state.type_ref),
                )
                for state in sorted(declaration.states, key=lambda item: item.name)
            ]
            handlers = [
                _normalize_local_handler(
                    semantics,
                    model,
                    handler,
                    owner_id=unit.unit_id,
                    mode="behavior",
                    handler_signatures=handler_signatures,
                )
                for handler in sorted(
                    declaration.handlers,
                    key=lambda item: item.event_id,
                )
            ]
            uses = [
                resolve_symbol(
                    semantics.plan,
                    unit.unit_id,
                    use.behavior_id,
                    NAMESPACE_BEHAVIOR,
                    span=use.span,
                ).semantic_id
                for use in declaration.uses
            ]
            result.append(
                {
                    "behavior_id": symbol.semantic_id,
                    "declared_in": unit.unit_id,
                    "exported": symbol.exported,
                    "uses": uses,
                    "states": states,
                    "handlers": handlers,
                }
            )
    result.sort(key=lambda item: str(item["behavior_id"]))
    return result


def _normalize_entities(
    semantics: StaticSemanticsV1,
    constants: ConstantEvaluationV1,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    summaries = {item.composite_id: item for item in semantics.composites}
    owner_id = semantics.plan.program_id
    for entity in sorted(semantics.plan.root.entities, key=lambda item: item.name):
        composite_id = f"{owner_id}.{entity.name}"
        model = semantics.behavior_model.composite(composite_id)
        handler_signatures = _handler_signatures(model)
        states = [
            _normalize_state(
                semantics,
                constants,
                composite_id,
                state.name,
                resolve_type(semantics.plan, owner_id, state.type_ref),
            )
            for state in sorted(entity.states, key=lambda item: item.name)
        ]
        handlers = [
            _normalize_local_handler(
                semantics,
                model,
                handler,
                owner_id=owner_id,
                mode="handler",
                handler_signatures=handler_signatures,
            )
            for handler in sorted(entity.handlers, key=lambda item: item.event_id)
        ]
        uses = [
            resolve_symbol(
                semantics.plan,
                owner_id,
                use.behavior_id,
                NAMESPACE_BEHAVIOR,
                span=use.span,
            ).semantic_id
            for use in entity.uses
        ]
        summary = summaries[composite_id]
        capabilities = sorted(
            {
                capability
                for handler in summary.handlers
                for capability in handler.capabilities
            }
        )
        result.append(
            {
                "entity_id": entity.name,
                "uses": uses,
                "states": states,
                "handlers": handlers,
                "capabilities": capabilities,
            }
        )
    return result


def _normalize_state(
    semantics: StaticSemanticsV1,
    constants: ConstantEvaluationV1,
    composite_id: str,
    state_name: str,
    type_ref: ResolvedTypeV1,
) -> dict[str, object]:
    value = constants.state(composite_id, state_name)
    if value.type_ref.type_id != type_ref.type_id:
        raise TevScriptError(
            "TEVS_V1_LINKED_STATE_CONSTANT_TYPE",
            f"constant for {composite_id}.{state_name} has {value.type_ref.type_id}, expected {type_ref.type_id}",
        )
    return {
        "name": state_name,
        "type": type_ref.type_id,
        "initial": _constant_to_expr(value),
    }


def _normalize_local_handler(
    semantics: StaticSemanticsV1,
    model,
    handler,
    *,
    owner_id: str,
    mode: str,
    handler_signatures: dict[str, tuple[ResolvedTypeV1, ...]],
) -> dict[str, object]:
    fragment = next(
        item
        for item in model.local_handler_fragments
        if item.declaration is handler
    )
    state_types = model.state_types
    type_scope = _ScopeV1(states=state_types)
    alpha_states = {
        name: _AlphaBindingV1(name, type_ref)
        for name, type_ref in state_types.items()
    }
    alpha_scope = _AlphaScopeV1(states=alpha_states)
    normalizer = _NormalizerV1(
        semantics,
        owner_id,
        type_scope,
        alpha_scope,
        mode,
        handler_signatures=handler_signatures,
    )
    normalizer.used_canonical_names.update(state_types)
    normalizer.push()
    parameter_names = _canonical_parameter_names(
        len(fragment.parameter_types),
        normalizer.used_canonical_names,
    )
    parameters: list[dict[str, str]] = []
    for source_parameter, type_ref, canonical in zip(
        handler.parameters,
        fragment.parameter_types,
        parameter_names,
        strict=True,
    ):
        normalizer.declare(
            source_parameter.name,
            type_ref,
            canonical,
            source_parameter.span,
        )
        parameters.append({"name": canonical, "type": type_ref.type_id})

    body = _normalize_statements(handler.body, normalizer)
    capabilities = sorted(normalizer.check_context.capabilities)
    normalizer.pop()
    return {
        "event_id": handler.event_id,
        "parameters": parameters,
        "body": body,
        "capabilities": capabilities,
    }


def _normalize_statements(
    statements: tuple[object, ...],
    normalizer: _NormalizerV1,
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for statement in statements:
        if isinstance(statement, LetStmt):
            expected = (
                resolve_type(
                    normalizer.plan,
                    normalizer.owner_id,
                    statement.type_ref,
                )
                if statement.type_ref is not None
                else None
            )
            actual = _check_expr(
                statement.expression,
                normalizer.check_context,
                expected=expected,
            )
            selected = expected or actual
            value = _normalize_expr(
                statement.expression,
                normalizer,
                expected=expected,
            )
            canonical = normalizer.allocate_local()
            normalizer.declare(
                statement.name,
                selected,
                canonical,
                statement.span,
            )
            result.append(
                {
                    "kind": "let",
                    "name": canonical,
                    "type": selected.type_id,
                    "value": value,
                }
            )
            continue

        if isinstance(statement, AssignStmt):
            expected = normalizer.type_scope.states.get(statement.name)
            if expected is None:
                raise TevScriptError(
                    "TEVS_V1_LINKED_STATE_UNKNOWN",
                    f"unknown state {statement.name!r}",
                    statement.span,
                )
            result.append(
                {
                    "kind": "assign",
                    "state": statement.name,
                    "value": _normalize_expr(
                        statement.expression,
                        normalizer,
                        expected=expected,
                    ),
                }
            )
            continue

        if isinstance(statement, CallStmt):
            signature = _resolve_capability_signature(
                normalizer,
                statement.capability_id,
                statement.span,
            )
            arguments = _normalize_arguments(
                statement.arguments,
                signature.parameters,
                normalizer,
            )
            normalizer.check_context.capabilities.add(signature.callable_id)
            result.append(
                {
                    "kind": "call",
                    "capability_id": signature.callable_id,
                    "arguments": arguments,
                }
            )
            continue

        if isinstance(statement, EmitStmt):
            expected = normalizer.handler_signatures.get(statement.event_id)
            arguments = (
                _normalize_arguments(statement.arguments, expected, normalizer)
                if expected is not None
                else [
                    _normalize_expr(item, normalizer, expected=None)
                    for item in statement.arguments
                ]
            )
            result.append(
                {
                    "kind": "emit",
                    "event_id": statement.event_id,
                    "arguments": arguments,
                }
            )
            continue

        if isinstance(statement, LogStmt):
            result.append(
                _normalize_sugar_call(
                    "debug.log",
                    (statement.expression,),
                    normalizer,
                    statement.span,
                )
            )
            continue

        if isinstance(statement, MoveStmt):
            result.append(
                _normalize_sugar_call(
                    "motion.move2d",
                    (statement.expression,),
                    normalizer,
                    statement.span,
                )
            )
            continue

        if isinstance(statement, AnimateStmt):
            result.append(
                _normalize_sugar_call(
                    "animation.play",
                    (statement.expression,),
                    normalizer,
                    statement.span,
                )
            )
            continue

        if isinstance(statement, IfStmt):
            condition = _normalize_expr(
                statement.condition,
                normalizer,
                expected=primitive_type("Bool"),
            )
            normalizer.push()
            try:
                then_body = _normalize_statements(
                    statement.then_body,
                    normalizer,
                )
            finally:
                normalizer.pop()
            normalizer.push()
            try:
                else_body = _normalize_statements(
                    statement.else_body,
                    normalizer,
                )
            finally:
                normalizer.pop()
            result.append(
                {
                    "kind": "if",
                    "condition": condition,
                    "then": then_body,
                    "else": else_body,
                }
            )
            continue

        if isinstance(statement, ForStmt):
            canonical = normalizer.allocate_local()
            normalizer.push()
            try:
                normalizer.declare(
                    statement.variable,
                    primitive_type("Int"),
                    canonical,
                    statement.span,
                )
                body = _normalize_statements(statement.body, normalizer)
            finally:
                normalizer.pop()
            result.append(
                {
                    "kind": "for",
                    "variable": canonical,
                    "lower": str(statement.lower),
                    "upper": str(statement.upper),
                    "body": body,
                }
            )
            continue

        if isinstance(statement, MatchStmt):
            target_type = _check_expr(
                statement.expression,
                normalizer.check_context,
            )
            value = _normalize_expr(
                statement.expression,
                normalizer,
                expected=None,
            )
            arms: list[dict[str, object]] = []
            for arm in statement.arms:
                normalizer.push()
                try:
                    pattern = _normalize_pattern(
                        arm.pattern,
                        target_type,
                        normalizer,
                    )
                    body = _normalize_statements(arm.body, normalizer)
                finally:
                    normalizer.pop()
                arms.append({"pattern": pattern, "body": body})
            result.append(
                {"kind": "match", "value": value, "arms": arms}
            )
            continue

        if isinstance(statement, ReturnStmt):
            result.append({"kind": "return"})
            continue

        raise TypeError(f"unsupported V1 statement {type(statement).__name__}")
    return result


def _normalize_expr(
    expression: Expr,
    normalizer: _NormalizerV1,
    *,
    expected: ResolvedTypeV1 | None,
) -> dict[str, object]:
    actual = _check_expr(
        expression,
        normalizer.check_context,
        expected=expected,
    )
    kind = expression.kind

    if kind == "bool":
        return {"kind": "bool", "type": "Bool", "value": bool(expression.value)}
    if kind == "int":
        return {"kind": "int", "type": "Int", "value": str(int(expression.value))}
    if kind == "rat":
        value = Fraction(expression.value)
        return {
            "kind": "rat",
            "type": "Rat",
            "numerator": str(value.numerator),
            "denominator": str(value.denominator),
        }
    if kind == "text":
        return {"kind": "text", "type": "Text", "value": str(expression.value)}
    if kind == "group":
        return _normalize_expr(
            expression.children[0],
            normalizer,
            expected=expected,
        )
    if kind == "name":
        return _normalize_value_path(
            str(expression.value),
            actual,
            normalizer,
            expression.span,
        )
    if kind == "field":
        target = _normalize_expr(
            expression.children[0],
            normalizer,
            expected=None,
        )
        return {
            "kind": "field",
            "type": actual.type_id,
            "target": target,
            "field": str(expression.value),
        }
    if kind == "enum":
        type_name, variant = expression.value
        symbol = resolve_symbol(
            normalizer.plan,
            normalizer.owner_id,
            type_name,
            NAMESPACE_TYPE,
            span=expression.span,
        )
        return {
            "kind": "enum",
            "type": symbol.semantic_id,
            "variant": variant,
        }
    if kind == "record":
        type_name, field_inits = expression.value
        symbol = resolve_symbol(
            normalizer.plan,
            normalizer.owner_id,
            type_name,
            NAMESPACE_TYPE,
            span=expression.span,
        )
        record = normalizer.types.record(symbol.semantic_id)
        if record is None:
            raise TevScriptError(
                "TEVS_V1_LINKED_RECORD_EXPECTED",
                f"{symbol.semantic_id!r} is not a record",
                expression.span,
            )
        field_types = {name: type_ref for name, type_ref in record.fields}
        return {
            "kind": "record",
            "type": symbol.semantic_id,
            "fields": [
                {
                    "name": field.name,
                    "value": _normalize_expr(
                        field.expression,
                        normalizer,
                        expected=field_types[field.name],
                    ),
                }
                for field in field_inits
            ],
        }
    if kind == "some":
        if actual.kind != "option":
            raise AssertionError(actual.type_id)
        return {
            "kind": "some",
            "type": actual.type_id,
            "value": _normalize_expr(
                expression.children[0],
                normalizer,
                expected=actual.arguments[0],
            ),
        }
    if kind == "none":
        return {"kind": "none", "type": actual.type_id}
    if kind in {"ok", "err"}:
        if actual.kind != "result":
            raise AssertionError(actual.type_id)
        index = 0 if kind == "ok" else 1
        return {
            "kind": kind,
            "type": actual.type_id,
            "value": _normalize_expr(
                expression.children[0],
                normalizer,
                expected=actual.arguments[index],
            ),
        }
    if kind == "unary":
        return {
            "kind": "unary",
            "type": actual.type_id,
            "operator": str(expression.value),
            "operand": _normalize_expr(
                expression.children[0],
                normalizer,
                expected=None,
            ),
        }
    if kind == "binary":
        return {
            "kind": "binary",
            "type": actual.type_id,
            "operator": str(expression.value),
            "left": _normalize_expr(
                expression.children[0],
                normalizer,
                expected=None,
            ),
            "right": _normalize_expr(
                expression.children[1],
                normalizer,
                expected=None,
            ),
        }
    if kind == "call":
        callee = expression.children[0]
        if callee.kind != "name":
            raise TevScriptError(
                "TEVS_V1_LINKED_CALLABLE",
                "canonical V1 call requires a named callable",
                callee.span,
            )
        arguments = tuple(expression.children[1:])
        callable_kind, signature = _resolve_expression_callable(
            normalizer,
            str(callee.value),
            arguments,
            callee.span,
        )
        return {
            "kind": "call",
            "type": actual.type_id,
            "callable_kind": callable_kind,
            "callable_id": signature.callable_id,
            "arguments": _normalize_arguments(
                arguments,
                signature.parameters,
                normalizer,
            ),
        }
    raise TevScriptError(
        "TEVS_V1_LINKED_EXPRESSION_KIND",
        f"unsupported expression kind {kind!r}",
        expression.span,
    )


def _normalize_value_path(
    reference: str,
    final_type: ResolvedTypeV1,
    normalizer: _NormalizerV1,
    span: SourceSpan,
) -> dict[str, object]:
    parts = reference.split(".")
    binding = normalizer.alpha_scope.lookup(parts[0])
    if binding is None:
        raise TevScriptError(
            "TEVS_V1_LINKED_VALUE_UNKNOWN",
            f"unknown value {parts[0]!r}",
            span,
        )
    node: dict[str, object] = {
        "kind": "name",
        "type": binding.type_ref.type_id,
        "symbol_id": binding.canonical_name,
    }
    current = binding.type_ref
    for field_name in parts[1:]:
        record = normalizer.types.record(current.type_id)
        if record is None:
            raise TevScriptError(
                "TEVS_V1_LINKED_FIELD_TARGET",
                f"{current.type_id} is not a record",
                span,
            )
        field_type = record.field(field_name)
        if field_type is None:
            raise TevScriptError(
                "TEVS_V1_LINKED_FIELD_UNKNOWN",
                f"record {record.type_id} has no field {field_name!r}",
                span,
            )
        node = {
            "kind": "field",
            "type": field_type.type_id,
            "target": node,
            "field": field_name,
        }
        current = field_type
    if current.type_id != final_type.type_id:
        raise AssertionError((reference, current.type_id, final_type.type_id))
    return node


def _normalize_pattern(
    pattern,
    target_type: ResolvedTypeV1,
    normalizer: _NormalizerV1,
) -> dict[str, object]:
    if isinstance(pattern, EnumPattern):
        symbol = resolve_symbol(
            normalizer.plan,
            normalizer.owner_id,
            pattern.type_name,
            NAMESPACE_TYPE,
            span=pattern.span,
        )
        return {
            "kind": "enum",
            "type": symbol.semantic_id,
            "variant": pattern.variant,
        }
    if isinstance(pattern, SomePattern):
        canonical = normalizer.allocate_local()
        normalizer.declare(
            pattern.binding,
            target_type.arguments[0],
            canonical,
            pattern.span,
        )
        return {
            "kind": "some",
            "type": target_type.type_id,
            "binding": canonical,
        }
    if isinstance(pattern, NonePattern):
        return {"kind": "none", "type": target_type.type_id}
    if isinstance(pattern, OkPattern):
        canonical = normalizer.allocate_local()
        normalizer.declare(
            pattern.binding,
            target_type.arguments[0],
            canonical,
            pattern.span,
        )
        return {
            "kind": "ok",
            "type": target_type.type_id,
            "binding": canonical,
        }
    if isinstance(pattern, ErrPattern):
        canonical = normalizer.allocate_local()
        normalizer.declare(
            pattern.binding,
            target_type.arguments[1],
            canonical,
            pattern.span,
        )
        return {
            "kind": "err",
            "type": target_type.type_id,
            "binding": canonical,
        }
    raise TypeError(type(pattern).__name__)


def _constant_to_expr(value: ConstantValueV1) -> dict[str, object]:
    type_ref = value.type_ref
    if type_ref.type_id == "Bool":
        return {"kind": "bool", "type": "Bool", "value": bool(value.value)}
    if type_ref.type_id == "Int":
        return {"kind": "int", "type": "Int", "value": str(int(value.value))}
    if type_ref.type_id == "Rat":
        rational = Fraction(value.value)
        return {
            "kind": "rat",
            "type": "Rat",
            "numerator": str(rational.numerator),
            "denominator": str(rational.denominator),
        }
    if type_ref.type_id == "Text":
        return {"kind": "text", "type": "Text", "value": str(value.value)}
    if type_ref.type_id in {"Vec2", "Vec3"}:
        function_id = "vec2" if type_ref.type_id == "Vec2" else "vec3"
        return {
            "kind": "call",
            "type": type_ref.type_id,
            "callable_kind": "pure_function",
            "callable_id": function_id,
            "arguments": [
                _constant_to_expr(
                    ConstantValueV1(primitive_type("Rat"), Fraction(item))
                )
                for item in value.value
            ],
        }
    if type_ref.kind == "record":
        return {
            "kind": "record",
            "type": type_ref.type_id,
            "fields": [
                {"name": name, "value": _constant_to_expr(field_value)}
                for name, field_value in value.value
            ],
        }
    if type_ref.kind == "enum":
        return {
            "kind": "enum",
            "type": type_ref.type_id,
            "variant": str(value.value),
        }
    if type_ref.kind == "option":
        tag, payload = value.value
        if tag == "None":
            return {"kind": "none", "type": type_ref.type_id}
        return {
            "kind": "some",
            "type": type_ref.type_id,
            "value": _constant_to_expr(payload),
        }
    if type_ref.kind == "result":
        tag, payload = value.value
        return {
            "kind": "ok" if tag == "Ok" else "err",
            "type": type_ref.type_id,
            "value": _constant_to_expr(payload),
        }
    raise TevScriptError(
        "TEVS_V1_LINKED_CONSTANT_TYPE",
        f"cannot serialize constant type {type_ref.type_id}",
    )


def _normalize_sugar_call(
    capability_id: str,
    arguments: tuple[Expr, ...],
    normalizer: _NormalizerV1,
    span: SourceSpan,
) -> dict[str, object]:
    signature = _resolve_capability_signature(
        normalizer,
        capability_id,
        span,
    )
    normalizer.check_context.capabilities.add(signature.callable_id)
    return {
        "kind": "call",
        "capability_id": signature.callable_id,
        "arguments": _normalize_arguments(
            arguments,
            signature.parameters,
            normalizer,
        ),
    }


def _normalize_arguments(
    arguments: tuple[Expr, ...],
    parameters: tuple[ResolvedTypeV1, ...],
    normalizer: _NormalizerV1,
) -> list[dict[str, object]]:
    if len(arguments) != len(parameters):
        raise TevScriptError(
            "TEVS_V1_LINKED_CALL_SIGNATURE",
            f"expected {len(parameters)} arguments, got {len(arguments)}",
        )
    return [
        _normalize_expr(argument, normalizer, expected=expected)
        for argument, expected in zip(arguments, parameters, strict=True)
    ]


def _resolve_expression_callable(
    normalizer: _NormalizerV1,
    reference: str,
    arguments: tuple[Expr, ...],
    span: SourceSpan,
) -> tuple[str, CallableSignatureV1]:
    function_symbol, function_error = _try_resolve(
        normalizer.plan,
        normalizer.owner_id,
        reference,
        NAMESPACE_FUNCTION,
        span,
    )
    capability_symbol, capability_error = _try_resolve(
        normalizer.plan,
        normalizer.owner_id,
        reference,
        NAMESPACE_CAPABILITY,
        span,
    )
    if function_symbol is not None and capability_symbol is not None:
        raise TevScriptError(
            "TEVS_V1_LINKED_CALL_AMBIGUOUS",
            f"call {reference!r} resolves as both function and capability",
            span,
        )
    if function_symbol is not None:
        candidates = [
            item
            for item in normalizer.types.functions
            if item.callable_id == function_symbol.semantic_id
        ]
        signature = _select_signature_for_ast(
            candidates,
            arguments,
            normalizer,
            span,
        )
        return "pure_function", signature
    if capability_symbol is not None:
        candidates = _dedupe_signatures(
            item
            for item in normalizer.types.capabilities
            if item.callable_id == capability_symbol.semantic_id
        )
        if len(candidates) != 1:
            raise TevScriptError(
                "TEVS_V1_LINKED_CALL_SIGNATURE",
                f"capability {capability_symbol.semantic_id!r} lacks one canonical signature",
                span,
            )
        signature = candidates[0]
        if signature.kind != "observation":
            raise TevScriptError(
                "TEVS_V1_LINKED_EFFECT_EXPRESSION",
                f"effect capability {signature.callable_id!r} cannot be an expression",
                span,
            )
        return "observation_capability", signature
    for error in (function_error, capability_error):
        if error is not None and error.diagnostic.code == "TEVS_V1_LINK_PRIVATE_SYMBOL":
            raise error
    raise TevScriptError(
        "TEVS_V1_LINKED_CALL_UNKNOWN",
        f"unknown callable {reference!r}",
        span,
    )


def _resolve_capability_signature(
    normalizer: _NormalizerV1,
    reference: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    symbol = resolve_symbol(
        normalizer.plan,
        normalizer.owner_id,
        reference,
        NAMESPACE_CAPABILITY,
        span=span,
    )
    candidates = _dedupe_signatures(
        item
        for item in normalizer.types.capabilities
        if item.callable_id == symbol.semantic_id
    )
    if len(candidates) != 1:
        raise TevScriptError(
            "TEVS_V1_LINKED_CALL_SIGNATURE",
            f"capability {symbol.semantic_id!r} lacks one canonical signature",
            span,
        )
    return candidates[0]


def _select_signature_for_ast(
    candidates: list[CallableSignatureV1],
    arguments: tuple[Expr, ...],
    normalizer: _NormalizerV1,
    span: SourceSpan,
) -> CallableSignatureV1:
    if not candidates:
        raise TevScriptError(
            "TEVS_V1_LINKED_CALL_UNKNOWN",
            "missing callable signature",
            span,
        )
    if len(candidates) == 1:
        if len(arguments) != len(candidates[0].parameters):
            raise TevScriptError(
                "TEVS_V1_LINKED_CALL_SIGNATURE",
                f"expected {len(candidates[0].parameters)} arguments, got {len(arguments)}",
                span,
            )
        return candidates[0]
    actual = tuple(
        _check_expr(argument, normalizer.check_context)
        for argument in arguments
    )
    return select_callable(
        candidates,
        actual,
        callable_id=candidates[0].callable_id,
        span=span,
    )


def _source_function_signature(
    types: TypeEnvironmentV1,
    function_id: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    candidates = [
        item
        for item in types.functions
        if item.callable_id == function_id
        and isinstance(item.declaration, FunctionDecl)
    ]
    if len(candidates) != 1:
        raise TevScriptError(
            "TEVS_V1_LINKED_FUNCTION_SIGNATURE",
            f"function {function_id!r} lacks one canonical source signature",
            span,
        )
    return candidates[0]


def _handler_signatures(model) -> dict[str, tuple[ResolvedTypeV1, ...]]:
    result: dict[str, tuple[ResolvedTypeV1, ...]] = {}
    for fragment in model.handler_fragments:
        result[fragment.declaration.event_id] = fragment.parameter_types
    return result


def _canonical_parameter_names(
    count: int,
    forbidden: set[str],
) -> tuple[str, ...]:
    result: list[str] = []
    used = set(forbidden)
    for index in range(count):
        candidate_index = index
        while True:
            candidate = f"_p{candidate_index}"
            candidate_index += count + 1
            if candidate not in used:
                used.add(candidate)
                result.append(candidate)
                break
    return tuple(result)


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


def _dedupe_signatures(
    signatures: Iterable[CallableSignatureV1],
) -> list[CallableSignatureV1]:
    by_key: dict[tuple[object, ...], CallableSignatureV1] = {}
    for item in signatures:
        key = (
            item.callable_id,
            tuple(parameter.type_id for parameter in item.parameters),
            item.return_type.type_id,
            item.kind,
        )
        current = by_key.get(key)
        if current is None or item.owner_id < current.owner_id:
            by_key[key] = item
    return sorted(
        by_key.values(),
        key=lambda item: (
            item.callable_id,
            tuple(parameter.type_id for parameter in item.parameters),
            item.return_type.type_id,
            item.kind,
            item.owner_id,
        ),
    )


def _schema_namespace(namespace: str) -> str:
    mapping = {
        NAMESPACE_TYPE: "type",
        NAMESPACE_FUNCTION: "function",
        NAMESPACE_BEHAVIOR: "behavior",
        NAMESPACE_CAPABILITY: "capability",
    }
    if namespace not in mapping:
        raise TevScriptError(
            "TEVS_V1_LINKED_EXPORT_NAMESPACE",
            f"unsupported exported namespace {namespace!r}",
        )
    return mapping[namespace]
