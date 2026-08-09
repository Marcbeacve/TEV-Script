from __future__ import annotations

from .ast_v1 import (
    BehaviorDecl,
    CapabilityDecl,
    EntityDecl,
    EnumDecl,
    Expr,
    ForStmt,
    FunctionDecl,
    HandlerDecl,
    IfStmt,
    LetStmt,
    MatchStmt,
    RecordDecl,
    ScriptUnit,
    SourceFile,
)
from .contracts_v1 import (
    MAX_ARGUMENTS,
    MAX_BEHAVIOR_USES,
    MAX_ENTITIES,
    MAX_ENUM_VARIANTS,
    MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER,
    MAX_HANDLERS_PER_ENTITY,
    MAX_IMPORTS_PER_SOURCE,
    MAX_LOCALS_PER_HANDLER,
    MAX_MATCH_ARMS,
    MAX_NESTED_STATIC_LOOPS,
    MAX_PARAMETERS,
    MAX_RECORD_FIELDS,
    MAX_STATES_PER_ENTITY,
    MAX_STATIC_LOOP_ITERATIONS,
    MAX_TOP_DECLARATIONS_PER_SOURCE,
)
from .diagnostics import TevScriptError


def validate_v1_syntax_budgets(source: SourceFile) -> None:
    _limit("IMPORTS", len(source.imports), MAX_IMPORTS_PER_SOURCE, source.span)
    _limit("TOP_DECLARATIONS", len(source.declarations), MAX_TOP_DECLARATIONS_PER_SOURCE, source.span)
    if isinstance(source, ScriptUnit):
        _limit("ENTITIES", len(source.entities), MAX_ENTITIES, source.span)

    for declaration in source.declarations:
        if isinstance(declaration, RecordDecl):
            _limit("RECORD_FIELDS", len(declaration.fields), MAX_RECORD_FIELDS, declaration.span)
        elif isinstance(declaration, EnumDecl):
            _limit("ENUM_VARIANTS", len(declaration.variants), MAX_ENUM_VARIANTS, declaration.span)
        elif isinstance(declaration, FunctionDecl):
            _limit("FUNCTION_PARAMETERS", len(declaration.parameters), MAX_PARAMETERS, declaration.span)
            _validate_expression_arguments(declaration.expression)
        elif isinstance(declaration, CapabilityDecl):
            _limit("CAPABILITY_PARAMETERS", len(declaration.parameter_types), MAX_PARAMETERS, declaration.span)
        elif isinstance(declaration, BehaviorDecl):
            _validate_composite(declaration)

    if isinstance(source, ScriptUnit):
        for entity in source.entities:
            _validate_composite(entity)


def _validate_composite(value: BehaviorDecl | EntityDecl) -> None:
    _limit("BEHAVIOR_USES", len(value.uses), MAX_BEHAVIOR_USES, value.span)
    _limit("STATES", len(value.states), MAX_STATES_PER_ENTITY, value.span)
    _limit("HANDLERS", len(value.handlers), MAX_HANDLERS_PER_ENTITY, value.span)
    for state in value.states:
        _validate_expression_arguments(state.initial)
    for handler in value.handlers:
        _validate_handler(handler)


def _validate_handler(handler: HandlerDecl) -> None:
    _limit("EVENT_PARAMETERS", len(handler.parameters), MAX_PARAMETERS, handler.span)
    statement_count = 0
    local_count = 0
    stack: list[tuple[object, int]] = [(item, 0) for item in reversed(handler.body)]
    while stack:
        node, loop_depth = stack.pop()
        statement_count += 1
        if isinstance(node, LetStmt):
            local_count += 1
        if isinstance(node, ForStmt):
            local_count += 1  # immutable loop variable
            iterations = node.upper - node.lower
            if iterations < 0:
                raise TevScriptError(
                    "TEVS_V1_FOR_RANGE_ORDER",
                    f"for range upper bound must be >= lower bound: {node.lower} .. {node.upper}",
                    node.span,
                )
            _limit("STATIC_LOOP_ITERATIONS", iterations, MAX_STATIC_LOOP_ITERATIONS, node.span)
            next_depth = loop_depth + 1
            _limit("NESTED_STATIC_LOOPS", next_depth, MAX_NESTED_STATIC_LOOPS, node.span)
            stack.extend((item, next_depth) for item in reversed(node.body))
        elif isinstance(node, IfStmt):
            stack.extend((item, loop_depth) for item in reversed(node.else_body))
            stack.extend((item, loop_depth) for item in reversed(node.then_body))
            _validate_expression_arguments(node.condition)
        elif isinstance(node, MatchStmt):
            _limit("MATCH_ARMS", len(node.arms), MAX_MATCH_ARMS, node.span)
            _validate_expression_arguments(node.expression)
            local_count += sum(1 for arm in node.arms if getattr(arm.pattern, "binding", None) is not None)
            for arm in reversed(node.arms):
                stack.extend((item, loop_depth) for item in reversed(arm.body))
        else:
            expression = getattr(node, "expression", None)
            if isinstance(expression, Expr):
                _validate_expression_arguments(expression)
            arguments = getattr(node, "arguments", None)
            if arguments is not None:
                _limit("CALL_ARGUMENTS", len(arguments), MAX_ARGUMENTS, node.span)
                for expression in arguments:
                    _validate_expression_arguments(expression)
        _limit(
            "RAW_STATEMENT_NODES",
            statement_count,
            MAX_EXPANDED_STATEMENT_NODES_PER_HANDLER,
            handler.span,
        )
        _limit("LOCALS", local_count, MAX_LOCALS_PER_HANDLER, handler.span)


def _validate_expression_arguments(root: Expr) -> None:
    stack = [root]
    while stack:
        expression = stack.pop()
        if expression.kind == "call":
            # child 0 is the callable expression.
            _limit("CALL_ARGUMENTS", max(0, len(expression.children) - 1), MAX_ARGUMENTS, expression.span)
        if expression.kind == "record":
            _, field_inits = expression.value
            _limit("RECORD_CONSTRUCTOR_FIELDS", len(field_inits), MAX_RECORD_FIELDS, expression.span)
            stack.extend(field.expression for field in field_inits)
        stack.extend(expression.children)


def _limit(name: str, actual: int, maximum: int, span) -> None:
    if actual > maximum:
        raise TevScriptError(
            f"TEVS_V1_BUDGET_{name}",
            f"{name.lower().replace('_', ' ')} exceeds {maximum}: got {actual}",
            span,
        )
