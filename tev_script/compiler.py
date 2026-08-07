from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from collections.abc import Mapping
from typing import Any

from .ast import (
    AssignStmt,
    CallStmt,
    EmitStmt,
    EntityDecl,
    Expr,
    HandlerDecl,
    IfStmt,
    LetStmt,
    ReturnStmt,
    ScriptDecl,
    Statement,
)
from .canonical import canonical_hash, canonical_json
from .contracts import (
    IR_SCHEMA,
    LANGUAGE_VERSION,
    MAX_ARGUMENTS,
    MAX_ENTITIES,
    MAX_EVENT_CHAIN,
    MAX_HANDLERS_PER_ENTITY,
    MAX_INSTRUCTIONS_PER_HANDLER,
    MAX_LOCALS_PER_HANDLER,
    MAX_SOURCE_BYTES,
    MAX_STATES_PER_ENTITY,
)
from .values import encode_typed_value
from .diagnostics import SourceSpan, TevScriptError
from .lexer import Lexer
from .parser import Parser
from .ir_validation import validate_program_ir
from .capability_catalog import merge_capability_catalogs
from .source import SourceUnit
from .types import (
    CAPABILITIES,
    PURE_FUNCTIONS,
    SUPPORTED_TYPES,
    Signature,
    can_widen,
    is_numeric,
    select_signature,
)

@dataclass(slots=True)
class HandlerContext:
    state_types: dict[str, str]
    parameter_types: dict[str, str]
    handler_signatures: dict[str, tuple[str, ...]]
    capability_catalog: Mapping[str, tuple[Signature, ...]]
    local_types: dict[str, str] = field(default_factory=dict)
    capability_requirements: dict[str, Signature] = field(default_factory=dict)
    emitted_events: dict[str, tuple[str, ...]] = field(default_factory=dict)
    instructions: list[dict[str, Any]] = field(default_factory=list)
    source_map: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, instruction: dict[str, Any], span: SourceSpan) -> int:
        index = len(self.instructions)
        self.instructions.append(instruction)
        self.source_map.append({"instruction": index, "span": span.to_dict()})
        if len(self.instructions) > MAX_INSTRUCTIONS_PER_HANDLER:
            raise TevScriptError(
                "TEVS_COMPILE_INSTRUCTION_BUDGET",
                f"handler exceeds {MAX_INSTRUCTIONS_PER_HANDLER} instructions",
                span,
            )
        return index


@dataclass(frozen=True, slots=True)
class CompilationBundle:
    ir: dict[str, Any]
    canonical_json: str


def compile_bytes(
    path: str,
    data: bytes,
    *,
    debug_source_name: str | None = None,
    capability_catalog: Mapping[str, tuple[Signature, ...]] | None = None,
) -> CompilationBundle:
    if len(data) > MAX_SOURCE_BYTES:
        raise TevScriptError(
            "TEVS_SOURCE_BUDGET",
            f"source exceeds {MAX_SOURCE_BYTES} bytes",
        )
    source = SourceUnit.from_bytes(path, data)
    tokens = Lexer(source).tokenize()
    declaration = Parser(tokens).parse_script()
    ir = compile_declaration(
        declaration,
        debug_source_name=debug_source_name or path,
        capability_catalog=capability_catalog,
    )
    return CompilationBundle(ir=ir, canonical_json=canonical_json(ir))


def compile_path(
    path: str | Path,
    *,
    debug_source_name: str | None = None,
    capability_catalog: Mapping[str, tuple[Signature, ...]] | None = None,
) -> CompilationBundle:
    selected = Path(path)
    return compile_bytes(
        selected.as_posix(),
        selected.read_bytes(),
        debug_source_name=debug_source_name or selected.name,
        capability_catalog=capability_catalog,
    )


def compile_declaration(
    declaration: ScriptDecl,
    *,
    debug_source_name: str | None = None,
    capability_catalog: Mapping[str, tuple[Signature, ...]] | None = None,
) -> dict[str, Any]:
    if declaration.language_version != LANGUAGE_VERSION:
        raise TevScriptError(
            "TEVS_COMPILE_LANGUAGE_VERSION",
            f"expected language version {LANGUAGE_VERSION}",
            declaration.span,
        )
    if len(declaration.entities) > MAX_ENTITIES:
        raise TevScriptError(
            "TEVS_COMPILE_ENTITY_BUDGET",
            f"script exceeds {MAX_ENTITIES} entities",
            declaration.span,
        )

    resolved_capabilities = merge_capability_catalogs(CAPABILITIES, capability_catalog)
    entity_names: set[str] = set()
    entities: list[dict[str, Any]] = []
    debug_entities: list[dict[str, Any]] = []
    for entity in declaration.entities:
        if entity.name in entity_names:
            raise TevScriptError(
                "TEVS_COMPILE_ENTITY_DUPLICATE",
                f"duplicate entity {entity.name}",
                entity.span,
            )
        entity_names.add(entity.name)
        semantic, debug = _compile_entity(entity, resolved_capabilities)
        entities.append(semantic)
        debug_entities.append(debug)

    entities.sort(key=lambda item: item["entity_id"])
    debug_entities.sort(key=lambda item: item["entity_id"])
    semantic = {
        "schema": IR_SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "program_id": declaration.name,
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
    result = dict(semantic)
    result["semantic_hash"] = canonical_hash(semantic)
    source_name = debug_source_name or declaration.span.path
    debug = {
        "source_path": source_name,
        "entities": _replace_debug_paths(debug_entities, source_name),
    }
    result["debug"] = debug
    result["debug_hash"] = canonical_hash(debug)
    validate_program_ir(result)
    return result



def _replace_debug_paths(value: Any, source_name: str) -> Any:
    if isinstance(value, list):
        return [_replace_debug_paths(item, source_name) for item in value]
    if isinstance(value, dict):
        return {
            key: source_name if key == "path" else _replace_debug_paths(item, source_name)
            for key, item in value.items()
        }
    return value


def _compile_entity(
    entity: EntityDecl,
    capability_catalog: Mapping[str, tuple[Signature, ...]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(entity.states) > MAX_STATES_PER_ENTITY:
        raise TevScriptError(
            "TEVS_COMPILE_STATE_BUDGET",
            f"entity exceeds {MAX_STATES_PER_ENTITY} states",
            entity.span,
        )
    if len(entity.handlers) > MAX_HANDLERS_PER_ENTITY:
        raise TevScriptError(
            "TEVS_COMPILE_HANDLER_BUDGET",
            f"entity exceeds {MAX_HANDLERS_PER_ENTITY} handlers",
            entity.span,
        )

    state_types: dict[str, str] = {}
    states: list[dict[str, Any]] = []
    for state in entity.states:
        _require_type(state.type_name, state.span)
        if state.name in state_types:
            raise TevScriptError(
                "TEVS_COMPILE_STATE_DUPLICATE",
                f"duplicate state {state.name}",
                state.span,
            )
        value_type, value = _constant_value(state.initial)
        if not can_widen(value_type, state.type_name):
            raise TevScriptError(
                "TEVS_COMPILE_STATE_TYPE",
                f"state {state.name} expects {state.type_name}, got {value_type}",
                state.initial.span,
            )
        value = _widen_constant(value, value_type, state.type_name)
        state_types[state.name] = state.type_name
        states.append(
            {
                "name": state.name,
                "type": state.type_name,
                "initial": encode_typed_value(state.type_name, value),
            }
        )

    handler_signatures: dict[str, tuple[str, ...]] = {}
    for handler in entity.handlers:
        if len(handler.parameters) > MAX_ARGUMENTS:
            raise TevScriptError(
                "TEVS_COMPILE_PARAMETER_BUDGET",
                f"handler exceeds {MAX_ARGUMENTS} parameters",
                handler.span,
            )
        if handler.event_id in handler_signatures:
            raise TevScriptError(
                "TEVS_COMPILE_HANDLER_DUPLICATE",
                f"duplicate handler for event {handler.event_id}",
                handler.span,
            )
        parameter_names: set[str] = set()
        signature: list[str] = []
        for parameter in handler.parameters:
            _require_type(parameter.type_name, parameter.span)
            if parameter.type_name == "Unit":
                raise TevScriptError(
                    "TEVS_COMPILE_PARAMETER_UNIT",
                    "event parameters cannot use Unit",
                    parameter.span,
                )
            if parameter.name in parameter_names:
                raise TevScriptError(
                    "TEVS_COMPILE_PARAMETER_DUPLICATE",
                    f"duplicate parameter {parameter.name}",
                    parameter.span,
                )
            if parameter.name in state_types:
                raise TevScriptError(
                    "TEVS_COMPILE_PARAMETER_SHADOWS_STATE",
                    f"parameter {parameter.name} shadows a state",
                    parameter.span,
                )
            parameter_names.add(parameter.name)
            signature.append(parameter.type_name)
        if handler.event_id in {"start", "update"} and signature:
            raise TevScriptError(
                "TEVS_COMPILE_BUILTIN_EVENT_SIGNATURE",
                f"built-in event {handler.event_id} takes no parameters",
                handler.span,
            )
        handler_signatures[handler.event_id] = tuple(signature)

    handlers: list[dict[str, Any]] = []
    debug_handlers: list[dict[str, Any]] = []
    all_capabilities: dict[str, Signature] = {}
    all_emitted: dict[str, tuple[str, ...]] = {}
    for handler in entity.handlers:
        semantic, debug, capabilities, emitted = _compile_handler(
            handler,
            state_types,
            handler_signatures,
            capability_catalog,
        )
        handlers.append(semantic)
        debug_handlers.append(debug)
        for capability_id, signature in capabilities.items():
            existing = all_capabilities.get(capability_id)
            if existing is not None and existing != signature:
                raise TevScriptError(
                    "TEVS_COMPILE_CAPABILITY_SIGNATURE_CONFLICT",
                    f"capability {capability_id} used with conflicting signatures",
                    handler.span,
                )
            all_capabilities[capability_id] = signature
        for event_id, signature in emitted.items():
            existing = all_emitted.get(event_id)
            if existing is not None and existing != signature:
                raise TevScriptError(
                    "TEVS_COMPILE_EVENT_SIGNATURE_CONFLICT",
                    f"event {event_id} emitted with conflicting signatures",
                    handler.span,
                )
            declared = handler_signatures.get(event_id)
            if declared is not None and declared != signature:
                raise TevScriptError(
                    "TEVS_COMPILE_EVENT_HANDLER_SIGNATURE",
                    f"event {event_id} handler expects {declared}, emitted {signature}",
                    handler.span,
                )
            all_emitted[event_id] = signature

    states.sort(key=lambda item: item["name"])
    handlers.sort(key=lambda item: item["event_id"])
    debug_handlers.sort(key=lambda item: item["event_id"])
    capabilities = [
        {
            "capability_id": capability_id,
            "parameters": list(signature.parameters),
            "return_type": signature.return_type,
            "kind": signature.kind,
        }
        for capability_id, signature in sorted(all_capabilities.items())
    ]
    emitted_events = [
        {"event_id": event_id, "parameters": list(signature)}
        for event_id, signature in sorted(all_emitted.items())
    ]
    semantic = {
        "entity_id": entity.name,
        "states": states,
        "handlers": handlers,
        "capabilities": capabilities,
        "emitted_events": emitted_events,
    }
    debug = {
        "entity_id": entity.name,
        "span": entity.span.to_dict(),
        "handlers": debug_handlers,
    }
    return semantic, debug


def _compile_handler(
    handler: HandlerDecl,
    state_types: dict[str, str],
    handler_signatures: dict[str, tuple[str, ...]],
    capability_catalog: Mapping[str, tuple[Signature, ...]],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Signature],
    dict[str, tuple[str, ...]],
]:
    parameter_types = {
        parameter.name: parameter.type_name for parameter in handler.parameters
    }
    context = HandlerContext(
        state_types=state_types,
        parameter_types=parameter_types,
        handler_signatures=handler_signatures,
        capability_catalog=capability_catalog,
    )
    for statement in handler.body:
        _compile_statement(statement, context, allow_local_declaration=True)
    if not context.instructions or context.instructions[-1]["op"] != "RETURN":
        context.emit({"op": "RETURN"}, handler.span)

    if len(context.local_types) > MAX_LOCALS_PER_HANDLER:
        raise TevScriptError(
            "TEVS_COMPILE_LOCAL_BUDGET",
            f"handler exceeds {MAX_LOCALS_PER_HANDLER} locals",
            handler.span,
        )

    semantic = {
        "event_id": handler.event_id,
        "parameters": [
            {"name": item.name, "type": item.type_name}
            for item in handler.parameters
        ],
        "locals": [
            {"name": name, "type": type_name}
            for name, type_name in sorted(context.local_types.items())
        ],
        "instructions": context.instructions,
        "instruction_budget": MAX_INSTRUCTIONS_PER_HANDLER,
    }
    debug = {
        "event_id": handler.event_id,
        "span": handler.span.to_dict(),
        "source_map": context.source_map,
    }
    return (
        semantic,
        debug,
        context.capability_requirements,
        context.emitted_events,
    )


def _compile_statement(
    statement: Statement,
    context: HandlerContext,
    *,
    allow_local_declaration: bool,
) -> None:
    if isinstance(statement, LetStmt):
        if not allow_local_declaration:
            raise TevScriptError(
                "TEVS_COMPILE_LOCAL_CONTROL_SCOPE",
                "let declarations are allowed only in the handler top-level block in V0.2",
                statement.span,
            )
        if (
            statement.name in context.local_types
            or statement.name in context.parameter_types
            or statement.name in context.state_types
        ):
            raise TevScriptError(
                "TEVS_COMPILE_NAME_DUPLICATE",
                f"name {statement.name} is already declared",
                statement.span,
            )
        actual = _infer_expr(statement.expression, context)
        expected = statement.type_name or actual
        _require_type(expected, statement.span)
        _emit_expr(statement.expression, context, expected)
        context.local_types[statement.name] = expected
        context.emit(
            {"op": "STORE_LOCAL", "name": statement.name, "type": expected},
            statement.span,
        )
        return
    if isinstance(statement, AssignStmt):
        expected = context.state_types.get(statement.name)
        if expected is None:
            if statement.name in context.local_types:
                raise TevScriptError(
                    "TEVS_COMPILE_LOCAL_IMMUTABLE",
                    f"local {statement.name} is immutable; declare a state to mutate it",
                    statement.span,
                )
            raise TevScriptError(
                "TEVS_COMPILE_ASSIGN_UNKNOWN",
                f"unknown state {statement.name}",
                statement.span,
            )
        _emit_expr(statement.expression, context, expected)
        context.emit(
            {"op": "STORE_STATE", "name": statement.name, "type": expected},
            statement.span,
        )
        return
    if isinstance(statement, CallStmt):
        return_type = _emit_call(
            statement.capability_id,
            statement.arguments,
            context,
            statement.span,
            allow_pure=False,
        )
        if return_type != "Unit":
            raise TevScriptError(
                "TEVS_COMPILE_CALL_RESULT_UNUSED",
                f"call {statement.capability_id} returns {return_type}; bind it with let",
                statement.span,
            )
        return
    if isinstance(statement, EmitStmt):
        if len(statement.arguments) > MAX_ARGUMENTS:
            raise TevScriptError(
                "TEVS_COMPILE_ARGUMENT_BUDGET",
                f"emit exceeds {MAX_ARGUMENTS} arguments",
                statement.span,
            )
        types = tuple(_infer_expr(item, context) for item in statement.arguments)
        for expression, type_name in zip(
            statement.arguments, types, strict=True
        ):
            _emit_expr(expression, context, type_name)
        existing = context.emitted_events.get(statement.event_id)
        if existing is not None and existing != types:
            raise TevScriptError(
                "TEVS_COMPILE_EVENT_SIGNATURE_CONFLICT",
                f"event {statement.event_id} emitted with conflicting signatures",
                statement.span,
            )
        declared = context.handler_signatures.get(statement.event_id)
        if declared is not None and declared != types:
            raise TevScriptError(
                "TEVS_COMPILE_EVENT_HANDLER_SIGNATURE",
                f"event {statement.event_id} handler expects {declared}, emitted {types}",
                statement.span,
            )
        context.emitted_events[statement.event_id] = types
        context.emit(
            {
                "op": "EMIT_EVENT",
                "event_id": statement.event_id,
                "argument_types": list(types),
                "argc": len(types),
            },
            statement.span,
        )
        return
    if isinstance(statement, IfStmt):
        _emit_expr(statement.condition, context, "Bool")
        jump_false = context.emit(
            {"op": "JUMP_IF_FALSE", "target": -1}, statement.condition.span
        )
        for item in statement.then_body:
            _compile_statement(item, context, allow_local_declaration=False)
        jump_end = context.emit({"op": "JUMP", "target": -1}, statement.span)
        context.instructions[jump_false]["target"] = len(context.instructions)
        for item in statement.else_body:
            _compile_statement(item, context, allow_local_declaration=False)
        context.instructions[jump_end]["target"] = len(context.instructions)
        return
    if isinstance(statement, ReturnStmt):
        context.emit({"op": "RETURN"}, statement.span)
        return
    raise TypeError(type(statement).__name__)


def _infer_expr(expression: Expr, context: HandlerContext) -> str:
    if expression.kind == "bool":
        return "Bool"
    if expression.kind == "int":
        return "Int"
    if expression.kind == "rat":
        return "Rat"
    if expression.kind == "text":
        return "Text"
    if expression.kind == "name":
        name = str(expression.value)
        if name in context.local_types:
            return context.local_types[name]
        if name in context.parameter_types:
            return context.parameter_types[name]
        if name in context.state_types:
            return context.state_types[name]
        raise TevScriptError(
            "TEVS_COMPILE_NAME_UNKNOWN",
            f"unknown name {name}",
            expression.span,
        )
    if expression.kind == "unary":
        child_type = _infer_expr(expression.children[0], context)
        operator = str(expression.value)
        if operator == "NOT" and child_type == "Bool":
            return "Bool"
        if operator == "MINUS" and is_numeric(child_type):
            return child_type
        raise TevScriptError(
            "TEVS_COMPILE_UNARY_TYPE",
            f"operator {operator} does not accept {child_type}",
            expression.span,
        )
    if expression.kind == "binary":
        left = _infer_expr(expression.children[0], context)
        right = _infer_expr(expression.children[1], context)
        return _binary_result(str(expression.value), left, right, expression.span)
    if expression.kind == "call":
        name = str(expression.value)
        actual = tuple(_infer_expr(item, context) for item in expression.children)
        signatures = PURE_FUNCTIONS.get(name) or context.capability_catalog.get(name)
        if signatures is None:
            raise TevScriptError(
                "TEVS_COMPILE_CALL_UNKNOWN",
                f"unknown function or capability {name}",
                expression.span,
            )
        signature = select_signature(signatures, actual)
        if signature is None:
            raise TevScriptError(
                "TEVS_COMPILE_CALL_SIGNATURE",
                f"{name} does not accept {actual}",
                expression.span,
            )
        if signature.return_type == "Unit":
            raise TevScriptError(
                "TEVS_COMPILE_UNIT_EXPRESSION",
                f"{name} returns Unit and cannot be used as a value",
                expression.span,
            )
        return signature.return_type
    raise TevScriptError(
        "TEVS_COMPILE_EXPRESSION_KIND",
        f"unknown expression kind {expression.kind}",
        expression.span,
    )


def _emit_expr(
    expression: Expr,
    context: HandlerContext,
    expected: str | None = None,
) -> str:
    actual = _infer_expr(expression, context)
    if expected is not None and not can_widen(actual, expected):
        raise TevScriptError(
            "TEVS_COMPILE_TYPE_MISMATCH",
            f"expected {expected}, got {actual}",
            expression.span,
        )
    if expression.kind in {"bool", "int", "rat", "text"}:
        context.emit(
            {
                "op": "CONST",
                "type": actual,
                "value": encode_typed_value(actual, expression.value),
            },
            expression.span,
        )
    elif expression.kind == "name":
        name = str(expression.value)
        if name in context.local_types:
            op = "LOAD_LOCAL"
        elif name in context.parameter_types:
            op = "LOAD_PARAM"
        else:
            op = "LOAD_STATE"
        context.emit({"op": op, "name": name, "type": actual}, expression.span)
    elif expression.kind == "unary":
        _emit_expr(expression.children[0], context)
        context.emit(
            {"op": "UNARY", "operator": str(expression.value), "type": actual},
            expression.span,
        )
    elif expression.kind == "binary":
        left_type = _infer_expr(expression.children[0], context)
        right_type = _infer_expr(expression.children[1], context)
        operator = str(expression.value)
        left_expected, right_expected = _binary_operand_expectations(
            operator, left_type, right_type, actual
        )
        _emit_expr(expression.children[0], context, left_expected)
        _emit_expr(expression.children[1], context, right_expected)
        context.emit(
            {
                "op": "BINARY",
                "operator": operator,
                "left_type": left_expected,
                "right_type": right_expected,
                "result_type": actual,
            },
            expression.span,
        )
    elif expression.kind == "call":
        actual = _emit_call(
            str(expression.value),
            expression.children,
            context,
            expression.span,
            allow_pure=True,
        )
    else:
        raise TypeError(expression.kind)
    if expected is not None and actual == "Int" and expected == "Rat":
        context.emit(
            {"op": "CONVERT_INT_TO_RAT"},
            expression.span,
        )
        return "Rat"
    return actual


def _emit_call(
    name: str,
    arguments: tuple[Expr, ...],
    context: HandlerContext,
    span: SourceSpan,
    *,
    allow_pure: bool,
) -> str:
    if len(arguments) > MAX_ARGUMENTS:
        raise TevScriptError(
            "TEVS_COMPILE_ARGUMENT_BUDGET",
            f"call exceeds {MAX_ARGUMENTS} arguments",
            span,
        )
    actual_types = tuple(_infer_expr(item, context) for item in arguments)
    signatures = PURE_FUNCTIONS.get(name)
    pure = signatures is not None
    if not pure:
        signatures = context.capability_catalog.get(name)
    if signatures is None:
        raise TevScriptError(
            "TEVS_COMPILE_CALL_UNKNOWN",
            f"unknown function or capability {name}",
            span,
        )
    if pure and not allow_pure:
        raise TevScriptError(
            "TEVS_COMPILE_PURE_CALL_STATEMENT",
            f"pure function {name} must be used as a value",
            span,
        )
    signature = select_signature(signatures, actual_types)
    if signature is None:
        raise TevScriptError(
            "TEVS_COMPILE_CALL_SIGNATURE",
            f"{name} does not accept {actual_types}",
            span,
        )
    for expression, expected in zip(
        arguments, signature.parameters, strict=True
    ):
        _emit_expr(expression, context, expected)
    if pure:
        context.emit(
            {
                "op": "CALL_PURE",
                "function_id": name,
                "argc": len(arguments),
                "return_type": signature.return_type,
            },
            span,
        )
    else:
        existing = context.capability_requirements.get(name)
        if existing is not None and existing != signature:
            raise TevScriptError(
                "TEVS_COMPILE_CAPABILITY_SIGNATURE_CONFLICT",
                f"capability {name} used with conflicting signatures",
                span,
            )
        context.capability_requirements[name] = signature
        context.emit(
            {
                "op": "CALL_CAPABILITY",
                "capability_id": name,
                "argc": len(arguments),
                "return_type": signature.return_type,
                "kind": signature.kind,
            },
            span,
        )
    return signature.return_type


def _binary_result(
    operator: str,
    left: str,
    right: str,
    span: SourceSpan,
) -> str:
    if operator in {"AND", "OR"}:
        if left == right == "Bool":
            return "Bool"
    elif operator in {"EQEQ", "NE"}:
        if left == right or (is_numeric(left) and is_numeric(right)):
            return "Bool"
    elif operator in {"LT", "LE", "GT", "GE"}:
        if is_numeric(left) and is_numeric(right):
            return "Bool"
    elif operator in {"PLUS", "MINUS"}:
        if left == right == "Int":
            return "Int"
        if is_numeric(left) and is_numeric(right):
            return "Rat"
        if left == right and left in {"Vec2", "Vec3"}:
            return left
    elif operator == "STAR":
        if left == right == "Int":
            return "Int"
        if is_numeric(left) and is_numeric(right):
            return "Rat"
        if left in {"Vec2", "Vec3"} and is_numeric(right):
            return left
        if right in {"Vec2", "Vec3"} and is_numeric(left):
            return right
    elif operator == "SLASH":
        if is_numeric(left) and is_numeric(right):
            return "Rat"
        if left in {"Vec2", "Vec3"} and is_numeric(right):
            return left
    raise TevScriptError(
        "TEVS_COMPILE_BINARY_TYPE",
        f"operator {operator} does not accept {left} and {right}",
        span,
    )


def _binary_operand_expectations(
    operator: str,
    left: str,
    right: str,
    result: str,
) -> tuple[str, str]:
    if is_numeric(left) and is_numeric(right):
        if result == "Int" and operator != "SLASH":
            return "Int", "Int"
        return "Rat", "Rat"
    if left in {"Vec2", "Vec3"} and is_numeric(right):
        return left, "Rat"
    if right in {"Vec2", "Vec3"} and is_numeric(left):
        return "Rat", right
    return left, right


def _constant_value(expression: Expr) -> tuple[str, Any]:
    if expression.kind == "bool":
        return "Bool", bool(expression.value)
    if expression.kind == "int":
        return "Int", int(expression.value)
    if expression.kind == "rat":
        return "Rat", expression.value
    if expression.kind == "text":
        return "Text", str(expression.value)
    if expression.kind == "unary" and expression.value == "MINUS":
        child_type, child = _constant_value(expression.children[0])
        if not is_numeric(child_type):
            raise TevScriptError(
                "TEVS_COMPILE_STATE_CONSTANT",
                "state initializer unary minus requires a numeric literal",
                expression.span,
            )
        return child_type, -child
    if expression.kind == "call" and expression.value in {"vec2", "vec3"}:
        expected_count = 2 if expression.value == "vec2" else 3
        if len(expression.children) != expected_count:
            raise TevScriptError(
                "TEVS_COMPILE_STATE_VECTOR_ARITY",
                f"{expression.value} requires {expected_count} values",
                expression.span,
            )
        values: list[Fraction] = []
        for child in expression.children:
            child_type, child_value = _constant_value(child)
            if not is_numeric(child_type):
                raise TevScriptError(
                    "TEVS_COMPILE_STATE_VECTOR_TYPE",
                    "vector initializers require numeric constants",
                    child.span,
                )
            values.append(Fraction(child_value))
        return "Vec2" if expected_count == 2 else "Vec3", tuple(values)
    raise TevScriptError(
        "TEVS_COMPILE_STATE_CONSTANT",
        "state initializer must be a literal or vec2/vec3 literal",
        expression.span,
    )


def _widen_constant(value: Any, actual: str, expected: str) -> Any:
    if actual == "Int" and expected == "Rat":
        return Fraction(value, 1)
    return value


def _require_type(type_name: str, span: SourceSpan) -> None:
    if type_name not in SUPPORTED_TYPES:
        raise TevScriptError(
            "TEVS_COMPILE_TYPE_UNKNOWN",
            f"unknown type {type_name}",
            span,
            "Supported types: " + ", ".join(sorted(SUPPORTED_TYPES)),
        )
