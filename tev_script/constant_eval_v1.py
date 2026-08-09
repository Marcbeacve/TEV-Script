from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .ast_v1 import BehaviorDecl, EntityDecl, Expr, FunctionDecl, StateDecl
from .contracts_v1 import MAX_CONSTANT_EVAL_STEPS, MAX_PURE_FUNCTION_CALL_DEPTH
from .diagnostics import SourceSpan, TevScriptError
from .linker_v1 import (
    NAMESPACE_CAPABILITY,
    NAMESPACE_FUNCTION,
    NAMESPACE_TYPE,
    LinkPlanV1,
    resolve_symbol,
)
from .semantic_types_v1 import (
    CallableSignatureV1,
    ResolvedTypeV1,
    TypeEnvironmentV1,
    can_assign,
    primitive_type,
    require_assignable,
    resolve_type,
    select_callable,
)
from .static_semantics_v1 import FunctionSummaryV1, StaticSemanticsV1


@dataclass(frozen=True, slots=True)
class ConstantValueV1:
    type_ref: ResolvedTypeV1
    value: object


@dataclass(frozen=True, slots=True)
class StateConstantV1:
    composite_id: str
    state_name: str
    value: ConstantValueV1


@dataclass(frozen=True, slots=True)
class ConstantEvaluationV1:
    states: tuple[StateConstantV1, ...]

    def state(self, composite_id: str, state_name: str) -> ConstantValueV1:
        for item in self.states:
            if item.composite_id == composite_id and item.state_name == state_name:
                return item.value
        raise KeyError((composite_id, state_name))


@dataclass(slots=True)
class _EvaluatorV1:
    semantics: StaticSemanticsV1
    steps: int = 0

    @property
    def plan(self) -> LinkPlanV1:
        return self.semantics.plan

    @property
    def types(self) -> TypeEnvironmentV1:
        return self.semantics.types

    def step(self, span: SourceSpan) -> None:
        self.steps += 1
        if self.steps > MAX_CONSTANT_EVAL_STEPS:
            raise TevScriptError(
                "TEVS_V1_CONSTANT_STEP_BUDGET",
                f"constant evaluation exceeds {MAX_CONSTANT_EVAL_STEPS} steps",
                span,
            )


def evaluate_v1_state_constants(semantics: StaticSemanticsV1) -> ConstantEvaluationV1:
    _validate_function_depth(semantics)
    values: list[StateConstantV1] = []
    for unit in semantics.plan.units:
        owner_id = unit.unit_id
        declaration = unit.declaration
        for top in declaration.declarations:
            if isinstance(top, BehaviorDecl):
                values.extend(
                    _evaluate_composite_states(
                        semantics,
                        owner_id,
                        f"{owner_id}.{top.name}",
                        top.states,
                    )
                )
        if hasattr(declaration, "entities"):
            for entity in declaration.entities:
                values.extend(
                    _evaluate_composite_states(
                        semantics,
                        owner_id,
                        f"{owner_id}.{entity.name}",
                        entity.states,
                    )
                )
    values.sort(key=lambda item: (item.composite_id, item.state_name))
    return ConstantEvaluationV1(tuple(values))


def _evaluate_composite_states(
    semantics: StaticSemanticsV1,
    owner_id: str,
    composite_id: str,
    states: tuple[StateDecl, ...],
) -> list[StateConstantV1]:
    result: list[StateConstantV1] = []
    for state in states:
        expected = resolve_type(semantics.plan, owner_id, state.type_ref)
        evaluator = _EvaluatorV1(semantics)
        _reject_nonconstant_root_dependencies(state.initial, semantics.plan, owner_id)
        value = _evaluate_expr(
            evaluator,
            owner_id,
            state.initial,
            bindings={},
            expected=expected,
            call_depth=0,
        )
        require_assignable(value.type_ref, expected, state.initial.span)
        if value.type_ref.type_id != expected.type_id:
            value = _coerce_constant(value, expected, state.initial.span)
        result.append(StateConstantV1(composite_id, state.name, value))
    return result


def _reject_nonconstant_root_dependencies(
    expression: Expr,
    plan: LinkPlanV1,
    owner_id: str,
) -> None:
    stack = [expression]
    while stack:
        current = stack.pop()
        if current.kind == "name":
            # A root initializer has no lexical bindings. A bare/dotted name is
            # therefore non-constant unless it occurs as the callee of a pure
            # function, which is handled by the parent call below.
            raise TevScriptError(
                "TEVS_V1_CONSTANT_VALUE_REFERENCE",
                f"state initializer cannot read value {current.value!r}",
                current.span,
            )
        if current.kind == "call" and current.children:
            callee = current.children[0]
            if callee.kind != "name":
                raise TevScriptError(
                    "TEVS_V1_CONSTANT_CALLABLE",
                    "constant calls require a named pure function",
                    callee.span,
                )
            reference = str(callee.value)
            try:
                resolve_symbol(plan, owner_id, reference, NAMESPACE_FUNCTION, span=callee.span)
            except TevScriptError as function_error:
                try:
                    capability = resolve_symbol(
                        plan,
                        owner_id,
                        reference,
                        NAMESPACE_CAPABILITY,
                        span=callee.span,
                    )
                except TevScriptError:
                    raise function_error
                raise TevScriptError(
                    "TEVS_V1_CONSTANT_CAPABILITY",
                    f"state initializer cannot call capability {capability.semantic_id!r}",
                    callee.span,
                )
            # Do not traverse the callee name as a value reference.
            stack.extend(current.children[1:])
            continue
        if current.kind == "record":
            _type_name, fields = current.value
            stack.extend(field.expression for field in fields)
        stack.extend(current.children)


def _evaluate_expr(
    evaluator: _EvaluatorV1,
    owner_id: str,
    expression: Expr,
    *,
    bindings: dict[str, ConstantValueV1],
    expected: ResolvedTypeV1 | None,
    call_depth: int,
) -> ConstantValueV1:
    evaluator.step(expression.span)
    kind = expression.kind

    if kind == "bool":
        value = ConstantValueV1(primitive_type("Bool"), bool(expression.value))
    elif kind == "int":
        value = ConstantValueV1(primitive_type("Int"), int(expression.value))
    elif kind == "rat":
        value = ConstantValueV1(primitive_type("Rat"), Fraction(expression.value))
    elif kind == "text":
        value = ConstantValueV1(primitive_type("Text"), str(expression.value))
    elif kind == "group":
        value = _evaluate_expr(
            evaluator,
            owner_id,
            expression.children[0],
            bindings=bindings,
            expected=expected,
            call_depth=call_depth,
        )
    elif kind == "name":
        value = _constant_binding_path(str(expression.value), bindings, evaluator.types, expression.span)
    elif kind == "field":
        target = _evaluate_expr(
            evaluator,
            owner_id,
            expression.children[0],
            bindings=bindings,
            expected=None,
            call_depth=call_depth,
        )
        value = _constant_record_field(target, str(expression.value), expression.span)
    elif kind == "enum":
        type_name, variant = expression.value
        symbol = resolve_symbol(
            evaluator.plan,
            owner_id,
            type_name,
            NAMESPACE_TYPE,
            span=expression.span,
        )
        enum = evaluator.types.enum(symbol.semantic_id)
        if enum is None or variant not in enum.variants:
            raise TevScriptError(
                "TEVS_V1_CONSTANT_ENUM",
                f"invalid enum constant {type_name}::{variant}",
                expression.span,
            )
        value = ConstantValueV1(
            ResolvedTypeV1("enum", enum.type_id),
            variant,
        )
    elif kind == "record":
        type_name, field_inits = expression.value
        symbol = resolve_symbol(
            evaluator.plan,
            owner_id,
            type_name,
            NAMESPACE_TYPE,
            span=expression.span,
        )
        record = evaluator.types.record(symbol.semantic_id)
        if record is None:
            raise TevScriptError(
                "TEVS_V1_CONSTANT_RECORD",
                f"{type_name!r} is not a record type",
                expression.span,
            )
        by_name = {field.name: field.expression for field in field_inits}
        fields: list[tuple[str, ConstantValueV1]] = []
        for field_name, field_type in record.fields:
            field_expr = by_name[field_name]
            field_value = _evaluate_expr(
                evaluator,
                owner_id,
                field_expr,
                bindings=bindings,
                expected=field_type,
                call_depth=call_depth,
            )
            fields.append((field_name, _coerce_constant(field_value, field_type, field_expr.span)))
        value = ConstantValueV1(
            ResolvedTypeV1("record", record.type_id),
            tuple(fields),
        )
    elif kind == "some":
        if expected is not None:
            if expected.kind != "option":
                raise TevScriptError(
                    "TEVS_V1_CONSTANT_CONSTRUCTOR_CONTEXT",
                    f"Some requires Option<T>, got {expected.type_id}",
                    expression.span,
                )
            inner_type = expected.arguments[0]
            inner = _evaluate_expr(
                evaluator,
                owner_id,
                expression.children[0],
                bindings=bindings,
                expected=inner_type,
                call_depth=call_depth,
            )
            value = ConstantValueV1(expected, ("Some", _coerce_constant(inner, inner_type, expression.span)))
        else:
            inner = _evaluate_expr(
                evaluator,
                owner_id,
                expression.children[0],
                bindings=bindings,
                expected=None,
                call_depth=call_depth,
            )
            option = ResolvedTypeV1("option", f"Option<{inner.type_ref.type_id}>", (inner.type_ref,))
            value = ConstantValueV1(option, ("Some", inner))
    elif kind == "none":
        if expected is None or expected.kind != "option":
            raise TevScriptError(
                "TEVS_V1_CONSTANT_CONSTRUCTOR_CONTEXT",
                "None requires an expected Option<T> type",
                expression.span,
            )
        value = ConstantValueV1(expected, ("None", None))
    elif kind in {"ok", "err"}:
        if expected is None or expected.kind != "result":
            raise TevScriptError(
                "TEVS_V1_CONSTANT_CONSTRUCTOR_CONTEXT",
                f"{kind.title()} requires an expected Result<T,E> type",
                expression.span,
            )
        index = 0 if kind == "ok" else 1
        payload_type = expected.arguments[index]
        payload = _evaluate_expr(
            evaluator,
            owner_id,
            expression.children[0],
            bindings=bindings,
            expected=payload_type,
            call_depth=call_depth,
        )
        tag = "Ok" if kind == "ok" else "Err"
        value = ConstantValueV1(expected, (tag, _coerce_constant(payload, payload_type, expression.span)))
    elif kind == "unary":
        operand = _evaluate_expr(
            evaluator,
            owner_id,
            expression.children[0],
            bindings=bindings,
            expected=None,
            call_depth=call_depth,
        )
        operator = str(expression.value)
        if operator == "not":
            value = ConstantValueV1(primitive_type("Bool"), not bool(operand.value))
        elif operator == "-":
            value = ConstantValueV1(operand.type_ref, -operand.value)
        else:
            raise TevScriptError("TEVS_V1_CONSTANT_UNARY", f"unsupported operator {operator}", expression.span)
    elif kind == "binary":
        value = _evaluate_binary(
            evaluator,
            owner_id,
            expression,
            bindings=bindings,
            call_depth=call_depth,
        )
    elif kind == "call":
        value = _evaluate_call(
            evaluator,
            owner_id,
            expression,
            bindings=bindings,
            call_depth=call_depth,
        )
    else:
        raise TevScriptError(
            "TEVS_V1_CONSTANT_EXPRESSION_KIND",
            f"expression kind {kind!r} is not constant-evaluable",
            expression.span,
        )

    if expected is not None:
        require_assignable(value.type_ref, expected, expression.span)
    return value


def _evaluate_call(
    evaluator: _EvaluatorV1,
    owner_id: str,
    expression: Expr,
    *,
    bindings: dict[str, ConstantValueV1],
    call_depth: int,
) -> ConstantValueV1:
    callee = expression.children[0]
    if callee.kind != "name":
        raise TevScriptError(
            "TEVS_V1_CONSTANT_CALLABLE",
            "constant calls require a named pure function",
            callee.span,
        )
    if call_depth >= MAX_PURE_FUNCTION_CALL_DEPTH:
        raise TevScriptError(
            "TEVS_V1_CONSTANT_CALL_DEPTH",
            f"pure-function call depth exceeds {MAX_PURE_FUNCTION_CALL_DEPTH}",
            expression.span,
        )
    symbol = resolve_symbol(
        evaluator.plan,
        owner_id,
        str(callee.value),
        NAMESPACE_FUNCTION,
        span=callee.span,
    )
    candidates = [
        item for item in evaluator.types.functions
        if item.callable_id == symbol.semantic_id
    ]
    arguments = tuple(expression.children[1:])

    if len(candidates) == 1:
        signature = candidates[0]
        if len(arguments) != len(signature.parameters):
            raise TevScriptError(
                "TEVS_V1_CONSTANT_CALL_SIGNATURE",
                f"{signature.callable_id} expects {len(signature.parameters)} arguments, got {len(arguments)}",
                expression.span,
            )
        values = tuple(
            _coerce_constant(
                _evaluate_expr(
                    evaluator,
                    owner_id,
                    argument,
                    bindings=bindings,
                    expected=expected,
                    call_depth=call_depth,
                ),
                expected,
                argument.span,
            )
            for argument, expected in zip(arguments, signature.parameters, strict=True)
        )
    else:
        raw_values = tuple(
            _evaluate_expr(
                evaluator,
                owner_id,
                argument,
                bindings=bindings,
                expected=None,
                call_depth=call_depth,
            )
            for argument in arguments
        )
        signature = select_callable(
            candidates,
            tuple(item.type_ref for item in raw_values),
            callable_id=symbol.semantic_id,
            span=expression.span,
        )
        values = tuple(
            _coerce_constant(value, expected, argument.span)
            for value, expected, argument in zip(raw_values, signature.parameters, arguments, strict=True)
        )

    if signature.owner_id == "<builtin>":
        return _evaluate_builtin(signature, values, expression.span)

    declaration = signature.declaration
    if not isinstance(declaration, FunctionDecl):
        raise TevScriptError(
            "TEVS_V1_CONSTANT_FUNCTION_DECLARATION",
            f"missing pure-function body for {signature.callable_id}",
            expression.span,
        )
    if len(declaration.parameters) != len(values):
        raise AssertionError("validated function signature/body arity mismatch")
    function_bindings = {
        parameter.name: value
        for parameter, value in zip(declaration.parameters, values, strict=True)
    }
    result = _evaluate_expr(
        evaluator,
        signature.owner_id,
        declaration.expression,
        bindings=function_bindings,
        expected=signature.return_type,
        call_depth=call_depth + 1,
    )
    return _coerce_constant(result, signature.return_type, declaration.expression.span)


def _evaluate_builtin(
    signature: CallableSignatureV1,
    values: tuple[ConstantValueV1, ...],
    span: SourceSpan,
) -> ConstantValueV1:
    if signature.callable_id == "vec2":
        return ConstantValueV1(
            primitive_type("Vec2"),
            tuple(Fraction(item.value) for item in values),
        )
    if signature.callable_id == "vec3":
        return ConstantValueV1(
            primitive_type("Vec3"),
            tuple(Fraction(item.value) for item in values),
        )
    if signature.callable_id == "max":
        return ConstantValueV1(signature.return_type, max(item.value for item in values))
    if signature.callable_id == "min":
        return ConstantValueV1(signature.return_type, min(item.value for item in values))
    raise TevScriptError(
        "TEVS_V1_CONSTANT_BUILTIN",
        f"pure builtin {signature.callable_id!r} is not constant-foldable",
        span,
    )


def _evaluate_binary(
    evaluator: _EvaluatorV1,
    owner_id: str,
    expression: Expr,
    *,
    bindings: dict[str, ConstantValueV1],
    call_depth: int,
) -> ConstantValueV1:
    operator = str(expression.value)
    left = _evaluate_expr(
        evaluator,
        owner_id,
        expression.children[0],
        bindings=bindings,
        expected=None,
        call_depth=call_depth,
    )

    if operator == "and" and left.type_ref.type_id == "Bool" and not left.value:
        return ConstantValueV1(primitive_type("Bool"), False)
    if operator == "or" and left.type_ref.type_id == "Bool" and left.value:
        return ConstantValueV1(primitive_type("Bool"), True)

    right = _evaluate_expr(
        evaluator,
        owner_id,
        expression.children[1],
        bindings=bindings,
        expected=None,
        call_depth=call_depth,
    )

    if operator == "and":
        return ConstantValueV1(primitive_type("Bool"), bool(left.value and right.value))
    if operator == "or":
        return ConstantValueV1(primitive_type("Bool"), bool(left.value or right.value))
    if operator == "==":
        return ConstantValueV1(primitive_type("Bool"), _constant_equal(left, right))
    if operator == "!=":
        return ConstantValueV1(primitive_type("Bool"), not _constant_equal(left, right))
    if operator in {"<", "<=", ">", ">="}:
        a = Fraction(left.value)
        b = Fraction(right.value)
        result = {
            "<": a < b,
            "<=": a <= b,
            ">": a > b,
            ">=": a >= b,
        }[operator]
        return ConstantValueV1(primitive_type("Bool"), result)
    if operator in {"+", "-", "*", "/"}:
        return _constant_arithmetic(operator, left, right, expression.span)
    raise TevScriptError(
        "TEVS_V1_CONSTANT_BINARY",
        f"unsupported constant operator {operator!r}",
        expression.span,
    )


def _constant_arithmetic(
    operator: str,
    left: ConstantValueV1,
    right: ConstantValueV1,
    span: SourceSpan,
) -> ConstantValueV1:
    if left.type_ref.is_vector or right.type_ref.is_vector:
        if operator in {"+", "-"}:
            operation = (lambda a, b: a + b) if operator == "+" else (lambda a, b: a - b)
            return ConstantValueV1(
                left.type_ref,
                tuple(operation(Fraction(a), Fraction(b)) for a, b in zip(left.value, right.value, strict=True)),
            )
        if operator == "*":
            if left.type_ref.is_vector:
                scalar = Fraction(right.value)
                return ConstantValueV1(left.type_ref, tuple(Fraction(x) * scalar for x in left.value))
            scalar = Fraction(left.value)
            return ConstantValueV1(right.type_ref, tuple(scalar * Fraction(x) for x in right.value))
        if operator == "/":
            scalar = Fraction(right.value)
            if scalar == 0:
                raise TevScriptError("TEVS_V1_CONSTANT_DIV_ZERO", "division by zero", span)
            return ConstantValueV1(left.type_ref, tuple(Fraction(x) / scalar for x in left.value))

    if left.type_ref.type_id == right.type_ref.type_id == "Int" and operator in {"+", "-", "*"}:
        result = {
            "+": left.value + right.value,
            "-": left.value - right.value,
            "*": left.value * right.value,
        }[operator]
        return ConstantValueV1(primitive_type("Int"), result)

    a = Fraction(left.value)
    b = Fraction(right.value)
    if operator == "+":
        result = a + b
    elif operator == "-":
        result = a - b
    elif operator == "*":
        result = a * b
    elif operator == "/":
        if b == 0:
            raise TevScriptError("TEVS_V1_CONSTANT_DIV_ZERO", "division by zero", span)
        result = a / b
    else:
        raise AssertionError(operator)
    return ConstantValueV1(primitive_type("Rat"), result)


def _constant_equal(left: ConstantValueV1, right: ConstantValueV1) -> bool:
    if left.type_ref.is_numeric and right.type_ref.is_numeric:
        return Fraction(left.value) == Fraction(right.value)
    if left.type_ref.type_id != right.type_ref.type_id:
        return False
    return _raw_equal(left.value, right.value)


def _raw_equal(left: object, right: object) -> bool:
    if isinstance(left, ConstantValueV1) and isinstance(right, ConstantValueV1):
        return _constant_equal(left, right)
    if isinstance(left, tuple) and isinstance(right, tuple):
        if len(left) != len(right):
            return False
        return all(_raw_equal(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def _constant_binding_path(
    reference: str,
    bindings: dict[str, ConstantValueV1],
    types: TypeEnvironmentV1,
    span: SourceSpan,
) -> ConstantValueV1:
    parts = reference.split(".")
    value = bindings.get(parts[0])
    if value is None:
        raise TevScriptError(
            "TEVS_V1_CONSTANT_VALUE_REFERENCE",
            f"unknown constant binding {parts[0]!r}",
            span,
        )
    for field in parts[1:]:
        value = _constant_record_field(value, field, span)
    return value


def _constant_record_field(
    value: ConstantValueV1,
    field_name: str,
    span: SourceSpan,
) -> ConstantValueV1:
    if value.type_ref.kind != "record" or not isinstance(value.value, tuple):
        raise TevScriptError(
            "TEVS_V1_CONSTANT_FIELD_TARGET",
            f"constant field access requires a record, got {value.type_ref.type_id}",
            span,
        )
    for name, field_value in value.value:
        if name == field_name:
            return field_value
    raise TevScriptError(
        "TEVS_V1_CONSTANT_FIELD_UNKNOWN",
        f"record constant {value.type_ref.type_id} has no field {field_name!r}",
        span,
    )


def _coerce_constant(
    value: ConstantValueV1,
    expected: ResolvedTypeV1,
    span: SourceSpan,
) -> ConstantValueV1:
    require_assignable(value.type_ref, expected, span)
    if value.type_ref.type_id == expected.type_id:
        return value
    if value.type_ref.type_id == "Int" and expected.type_id == "Rat":
        return ConstantValueV1(expected, Fraction(value.value, 1))
    raise TevScriptError(
        "TEVS_V1_CONSTANT_COERCION",
        f"cannot coerce {value.type_ref.type_id} to {expected.type_id}",
        span,
    )


def _validate_function_depth(semantics: StaticSemanticsV1) -> None:
    user_ids = {
        item.callable_id
        for item in semantics.types.functions
        if isinstance(item.declaration, FunctionDecl)
    }
    graph = {
        summary.function_id: tuple(call for call in summary.calls if call in user_ids)
        for summary in semantics.functions
    }
    memo: dict[str, int] = {}

    def depth(function_id: str) -> int:
        if function_id in memo:
            return memo[function_id]
        children = graph.get(function_id, ())
        value = 1 if not children else 1 + max(depth(child) for child in children)
        memo[function_id] = value
        return value

    for function_id in sorted(graph):
        value = depth(function_id)
        if value > MAX_PURE_FUNCTION_CALL_DEPTH:
            signature = next(
                item for item in semantics.types.functions
                if item.callable_id == function_id and isinstance(item.declaration, FunctionDecl)
            )
            raise TevScriptError(
                "TEVS_V1_PURITY_CALL_DEPTH",
                f"pure-function call-graph depth exceeds {MAX_PURE_FUNCTION_CALL_DEPTH}: got {value}",
                signature.declaration.span,
            )
