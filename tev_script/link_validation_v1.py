from __future__ import annotations

from .ast_v1 import (
    AnimateStmt,
    AssignStmt,
    BehaviorDecl,
    CallStmt,
    CapabilityDecl,
    EmitStmt,
    EntityDecl,
    EnumPattern,
    Expr,
    ForStmt,
    FunctionDecl,
    HandlerDecl,
    IfStmt,
    LetStmt,
    LogStmt,
    MatchStmt,
    MoveStmt,
    RecordDecl,
    ReturnStmt,
    StateDecl,
    TypeRef,
)
from .diagnostics import TevScriptError
from .linker_v1 import (
    LinkPlanV1,
    NAMESPACE_BEHAVIOR,
    NAMESPACE_CAPABILITY,
    NAMESPACE_FUNCTION,
    NAMESPACE_TYPE,
    canonical_type_id,
    resolve_symbol,
)


def validate_v1_link_names(plan: LinkPlanV1) -> None:
    """Resolve references whose namespace can be constrained before typing.

    Value names remain for static semantics. Named call expressions are probed in
    both callable namespaces only to surface namespace-internal ambiguity or
    conflicting capability contracts deterministically; cross-namespace
    function-vs-capability ambiguity is classified by the type checker.
    """

    _validate_capability_contracts(plan)

    for unit in plan.units:
        owner_id = unit.unit_id
        declaration = unit.declaration
        for top in declaration.declarations:
            _validate_top_decl(plan, owner_id, top)
        if hasattr(declaration, "entities"):
            for entity in declaration.entities:
                _validate_composite(plan, owner_id, entity)


def _validate_top_decl(plan: LinkPlanV1, owner_id: str, declaration: object) -> None:
    if isinstance(declaration, CapabilityDecl):
        for type_ref in declaration.parameter_types:
            _validate_type(plan, owner_id, type_ref)
        _validate_type(plan, owner_id, declaration.return_type)
        return
    if isinstance(declaration, RecordDecl):
        for field in declaration.fields:
            _validate_type(plan, owner_id, field.type_ref)
        return
    if isinstance(declaration, FunctionDecl):
        for parameter in declaration.parameters:
            _validate_type(plan, owner_id, parameter.type_ref)
        _validate_type(plan, owner_id, declaration.return_type)
        _validate_expression(plan, owner_id, declaration.expression)
        return
    if isinstance(declaration, BehaviorDecl):
        _validate_composite(plan, owner_id, declaration)
        return
    # Enum declarations have no referenced names in V1.0.


def _validate_composite(plan: LinkPlanV1, owner_id: str, value: BehaviorDecl | EntityDecl) -> None:
    for use in value.uses:
        resolve_symbol(
            plan,
            owner_id,
            use.behavior_id,
            NAMESPACE_BEHAVIOR,
            span=use.span,
        )
    for state in value.states:
        _validate_state(plan, owner_id, state)
    for handler in value.handlers:
        _validate_handler(plan, owner_id, handler)


def _validate_state(plan: LinkPlanV1, owner_id: str, state: StateDecl) -> None:
    _validate_type(plan, owner_id, state.type_ref)
    _validate_expression(plan, owner_id, state.initial)


def _validate_handler(plan: LinkPlanV1, owner_id: str, handler: HandlerDecl) -> None:
    for parameter in handler.parameters:
        _validate_type(plan, owner_id, parameter.type_ref)
    _validate_statements(plan, owner_id, handler.body)


def _validate_statements(plan: LinkPlanV1, owner_id: str, statements: tuple[object, ...]) -> None:
    for statement in statements:
        if isinstance(statement, (LetStmt, AssignStmt, LogStmt, MoveStmt, AnimateStmt)):
            if isinstance(statement, LetStmt) and statement.type_ref is not None:
                _validate_type(plan, owner_id, statement.type_ref)
            _validate_expression(plan, owner_id, statement.expression)
        elif isinstance(statement, CallStmt):
            resolve_symbol(
                plan,
                owner_id,
                statement.capability_id,
                NAMESPACE_CAPABILITY,
                span=statement.span,
            )
            for argument in statement.arguments:
                _validate_expression(plan, owner_id, argument)
        elif isinstance(statement, EmitStmt):
            for argument in statement.arguments:
                _validate_expression(plan, owner_id, argument)
        elif isinstance(statement, IfStmt):
            _validate_expression(plan, owner_id, statement.condition)
            _validate_statements(plan, owner_id, statement.then_body)
            _validate_statements(plan, owner_id, statement.else_body)
        elif isinstance(statement, ForStmt):
            _validate_statements(plan, owner_id, statement.body)
        elif isinstance(statement, MatchStmt):
            _validate_expression(plan, owner_id, statement.expression)
            for arm in statement.arms:
                if isinstance(arm.pattern, EnumPattern):
                    resolve_symbol(
                        plan,
                        owner_id,
                        arm.pattern.type_name,
                        NAMESPACE_TYPE,
                        span=arm.pattern.span,
                    )
                _validate_statements(plan, owner_id, arm.body)
        elif isinstance(statement, ReturnStmt):
            continue
        else:
            raise TypeError(f"unsupported V1 statement {type(statement).__name__}")


def _validate_type(plan: LinkPlanV1, owner_id: str, type_ref: TypeRef) -> None:
    canonical_type_id(plan, owner_id, type_ref)


def _validate_expression(plan: LinkPlanV1, owner_id: str, expression: Expr) -> None:
    stack = [expression]
    while stack:
        current = stack.pop()
        if current.kind == "record":
            type_name, field_inits = current.value
            resolve_symbol(
                plan,
                owner_id,
                type_name,
                NAMESPACE_TYPE,
                span=current.span,
            )
            stack.extend(field.expression for field in field_inits)
        elif current.kind == "enum":
            type_name, _variant = current.value
            resolve_symbol(
                plan,
                owner_id,
                type_name,
                NAMESPACE_TYPE,
                span=current.span,
            )
        elif current.kind == "call" and current.children:
            callee = current.children[0]
            if callee.kind == "name":
                _probe_callable_namespace_ambiguity(
                    plan,
                    owner_id,
                    str(callee.value),
                    callee.span,
                )
        stack.extend(current.children)


def _probe_callable_namespace_ambiguity(
    plan: LinkPlanV1,
    owner_id: str,
    reference: str,
    span,
) -> None:
    for namespace in (NAMESPACE_FUNCTION, NAMESPACE_CAPABILITY):
        try:
            resolve_symbol(plan, owner_id, reference, namespace, span=span)
        except TevScriptError as exc:
            if exc.diagnostic.code in {
                "TEVS_V1_LINK_NAME_AMBIGUOUS",
                "TEVS_V1_LINK_CAPABILITY_CONFLICT",
            }:
                raise
            # Unknown/private in one callable namespace can coexist with a valid
            # candidate in the other namespace. Static semantics decides the
            # aggregate callable result.


def _validate_capability_contracts(plan: LinkPlanV1) -> None:
    seen: dict[str, tuple[tuple[str, ...], str, str]] = {}
    for unit in plan.units:
        for symbol in unit.symbols:
            if symbol.namespace != NAMESPACE_CAPABILITY:
                continue
            declaration = symbol.declaration
            if not isinstance(declaration, CapabilityDecl):
                raise TypeError("source capability symbol lacks CapabilityDecl")
            signature = (
                tuple(canonical_type_id(plan, unit.unit_id, item) for item in declaration.parameter_types),
                canonical_type_id(plan, unit.unit_id, declaration.return_type),
                declaration.capability_kind,
            )
            previous = seen.get(symbol.semantic_id)
            if previous is not None and previous != signature:
                raise TevScriptError(
                    "TEVS_V1_LINK_CAPABILITY_CONFLICT",
                    f"conflicting declarations for capability {symbol.semantic_id!r}",
                    declaration.span,
                )
            seen[symbol.semantic_id] = signature
