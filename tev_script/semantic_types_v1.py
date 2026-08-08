from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ast_v1 import CapabilityDecl, EnumDecl, Expr, FunctionDecl, RecordDecl, TypeRef
from .contracts_v1 import MAX_PURE_FUNCTION_CALL_DEPTH
from .diagnostics import SourceSpan, TevScriptError
from .graph_validation_v1 import validate_bounded_dag_v1
from .linker_v1 import (
    LinkPlanV1,
    NAMESPACE_FUNCTION,
    NAMESPACE_TYPE,
    resolve_symbol,
)
from .types import CAPABILITIES, PURE_FUNCTIONS, SUPPORTED_TYPES, Signature


@dataclass(frozen=True, slots=True)
class ResolvedTypeV1:
    kind: str
    type_id: str
    arguments: tuple["ResolvedTypeV1", ...] = ()

    @property
    def is_unit(self) -> bool:
        return self.type_id == "Unit"

    @property
    def is_numeric(self) -> bool:
        return self.type_id in {"Int", "Rat"}

    @property
    def is_vector(self) -> bool:
        return self.type_id in {"Vec2", "Vec3"}

    @property
    def is_storable(self) -> bool:
        return not self.is_unit and all(item.is_storable for item in self.arguments)


@dataclass(frozen=True, slots=True)
class RecordInfoV1:
    type_id: str
    owner_id: str
    declaration: RecordDecl
    fields: tuple[tuple[str, ResolvedTypeV1], ...]

    def field(self, name: str) -> ResolvedTypeV1 | None:
        for field_name, type_ref in self.fields:
            if field_name == name:
                return type_ref
        return None


@dataclass(frozen=True, slots=True)
class EnumInfoV1:
    type_id: str
    owner_id: str
    declaration: EnumDecl
    variants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CallableSignatureV1:
    callable_id: str
    parameters: tuple[ResolvedTypeV1, ...]
    return_type: ResolvedTypeV1
    kind: str
    owner_id: str
    declaration: object | None


@dataclass(frozen=True, slots=True)
class TypeEnvironmentV1:
    records: tuple[RecordInfoV1, ...]
    enums: tuple[EnumInfoV1, ...]
    functions: tuple[CallableSignatureV1, ...]
    capabilities: tuple[CallableSignatureV1, ...]

    def record(self, type_id: str) -> RecordInfoV1 | None:
        return next((item for item in self.records if item.type_id == type_id), None)

    def enum(self, type_id: str) -> EnumInfoV1 | None:
        return next((item for item in self.enums if item.type_id == type_id), None)

    def function(self, callable_id: str) -> CallableSignatureV1 | None:
        return next((item for item in self.functions if item.callable_id == callable_id), None)

    def capability(self, callable_id: str) -> CallableSignatureV1 | None:
        return next((item for item in self.capabilities if item.callable_id == callable_id), None)


def primitive_type(type_id: str) -> ResolvedTypeV1:
    if type_id not in SUPPORTED_TYPES:
        raise ValueError(type_id)
    return ResolvedTypeV1("primitive", type_id)


def resolve_type(plan: LinkPlanV1, owner_id: str, type_ref: TypeRef) -> ResolvedTypeV1:
    if type_ref.kind == "option":
        argument = resolve_type(plan, owner_id, type_ref.arguments[0])
        return ResolvedTypeV1("option", f"Option<{argument.type_id}>", (argument,))
    if type_ref.kind == "result":
        ok = resolve_type(plan, owner_id, type_ref.arguments[0])
        err = resolve_type(plan, owner_id, type_ref.arguments[1])
        return ResolvedTypeV1("result", f"Result<{ok.type_id},{err.type_id}>", (ok, err))
    if type_ref.kind != "named" or type_ref.name is None:
        raise TevScriptError(
            "TEVS_V1_TYPE_REFERENCE_KIND",
            f"unsupported type reference kind {type_ref.kind!r}",
            type_ref.span,
        )
    symbol = resolve_symbol(plan, owner_id, type_ref.name, NAMESPACE_TYPE, span=type_ref.span)
    if symbol.origin == "builtin":
        if symbol.semantic_id in {"Option", "Result"}:
            raise TevScriptError(
                "TEVS_V1_TYPE_GENERIC_ARGUMENTS",
                f"{symbol.semantic_id} requires type arguments",
                type_ref.span,
            )
        return primitive_type(symbol.semantic_id)
    if isinstance(symbol.declaration, RecordDecl):
        return ResolvedTypeV1("record", symbol.semantic_id)
    if isinstance(symbol.declaration, EnumDecl):
        return ResolvedTypeV1("enum", symbol.semantic_id)
    raise TevScriptError(
        "TEVS_V1_TYPE_SYMBOL_KIND",
        f"symbol {symbol.semantic_id!r} is not a V1 type declaration",
        type_ref.span,
    )


def can_assign(actual: ResolvedTypeV1, expected: ResolvedTypeV1) -> bool:
    return actual.type_id == expected.type_id or (
        actual.type_id == "Int" and expected.type_id == "Rat"
    )


def require_assignable(
    actual: ResolvedTypeV1,
    expected: ResolvedTypeV1,
    span: SourceSpan,
    *,
    code: str = "TEVS_V1_TYPE_MISMATCH",
) -> None:
    if not can_assign(actual, expected):
        raise TevScriptError(code, f"expected {expected.type_id}, got {actual.type_id}", span)


def build_type_environment(plan: LinkPlanV1) -> TypeEnvironmentV1:
    records: list[RecordInfoV1] = []
    enums: list[EnumInfoV1] = []
    functions: list[CallableSignatureV1] = []
    capabilities: list[CallableSignatureV1] = []

    for unit in plan.units:
        owner_id = unit.unit_id
        for symbol in unit.symbols:
            declaration = symbol.declaration
            if isinstance(declaration, RecordDecl):
                seen_fields: set[str] = set()
                fields: list[tuple[str, ResolvedTypeV1]] = []
                for field in declaration.fields:
                    if field.name in seen_fields:
                        raise TevScriptError(
                            "TEVS_V1_TYPE_RECORD_FIELD_DUPLICATE",
                            f"duplicate record field {field.name!r} in {symbol.semantic_id}",
                            field.span,
                        )
                    seen_fields.add(field.name)
                    field_type = resolve_type(plan, owner_id, field.type_ref)
                    _require_storable(field_type, field.span, "record field")
                    fields.append((field.name, field_type))
                records.append(
                    RecordInfoV1(
                        symbol.semantic_id,
                        owner_id,
                        declaration,
                        tuple(sorted(fields, key=lambda item: item[0])),
                    )
                )
            elif isinstance(declaration, EnumDecl):
                seen_variants: set[str] = set()
                for variant in declaration.variants:
                    if variant in seen_variants:
                        raise TevScriptError(
                            "TEVS_V1_TYPE_ENUM_VARIANT_DUPLICATE",
                            f"duplicate enum variant {variant!r} in {symbol.semantic_id}",
                            declaration.span,
                        )
                    seen_variants.add(variant)
                enums.append(
                    EnumInfoV1(
                        symbol.semantic_id,
                        owner_id,
                        declaration,
                        tuple(sorted(declaration.variants)),
                    )
                )
            elif isinstance(declaration, FunctionDecl):
                parameters = tuple(
                    resolve_type(plan, owner_id, parameter.type_ref)
                    for parameter in declaration.parameters
                )
                return_type = resolve_type(plan, owner_id, declaration.return_type)
                for parameter, resolved in zip(declaration.parameters, parameters, strict=True):
                    _require_storable(resolved, parameter.span, "function parameter")
                _require_storable(return_type, declaration.return_type.span, "function return")
                functions.append(
                    CallableSignatureV1(
                        symbol.semantic_id,
                        parameters,
                        return_type,
                        "pure",
                        owner_id,
                        declaration,
                    )
                )
            elif isinstance(declaration, CapabilityDecl):
                parameters = tuple(
                    resolve_type(plan, owner_id, parameter)
                    for parameter in declaration.parameter_types
                )
                return_type = resolve_type(plan, owner_id, declaration.return_type)
                for parameter, resolved in zip(declaration.parameter_types, parameters, strict=True):
                    _require_storable(resolved, parameter.span, "capability parameter")
                if not return_type.is_unit:
                    _require_storable(return_type, declaration.return_type.span, "capability return")
                capabilities.append(
                    CallableSignatureV1(
                        symbol.semantic_id,
                        parameters,
                        return_type,
                        declaration.capability_kind,
                        owner_id,
                        declaration,
                    )
                )

    functions.extend(_builtin_functions())
    capabilities.extend(_builtin_capabilities())
    records.sort(key=lambda item: item.type_id)
    enums.sort(key=lambda item: item.type_id)
    functions.sort(
        key=lambda item: (
            item.callable_id,
            tuple(parameter.type_id for parameter in item.parameters),
        )
    )
    capabilities = _dedupe_capability_signatures(capabilities)
    environment = TypeEnvironmentV1(
        tuple(records), tuple(enums), tuple(functions), tuple(capabilities)
    )
    _validate_record_acyclic(environment)
    _validate_pure_function_graph_precheck(plan, environment)
    return environment


def select_callable(
    signatures: Iterable[CallableSignatureV1],
    actual: tuple[ResolvedTypeV1, ...],
    *,
    callable_id: str,
    span: SourceSpan,
) -> CallableSignatureV1:
    candidates = [item for item in signatures if item.callable_id == callable_id]
    exact = [
        item
        for item in candidates
        if tuple(parameter.type_id for parameter in item.parameters)
        == tuple(parameter.type_id for parameter in actual)
    ]
    if len(exact) == 1:
        return exact[0]
    widened = [
        item
        for item in candidates
        if len(item.parameters) == len(actual)
        and all(
            can_assign(actual_type, expected_type)
            for actual_type, expected_type in zip(actual, item.parameters, strict=True)
        )
    ]
    if len(widened) == 1:
        return widened[0]
    raise TevScriptError(
        "TEVS_V1_TYPE_CALL_SIGNATURE",
        f"{callable_id} does not accept ({', '.join(item.type_id for item in actual)})",
        span,
    )


def record_dependencies(type_ref: ResolvedTypeV1) -> tuple[str, ...]:
    if type_ref.kind == "record":
        return (type_ref.type_id,)
    result: list[str] = []
    stack = list(type_ref.arguments)
    while stack:
        current = stack.pop()
        if current.kind == "record":
            result.append(current.type_id)
        else:
            stack.extend(current.arguments)
    return tuple(result)


def _require_storable(type_ref: ResolvedTypeV1, span: SourceSpan, context: str) -> None:
    if not type_ref.is_storable:
        raise TevScriptError(
            "TEVS_V1_TYPE_UNIT_PLACEMENT",
            f"Unit is not permitted in {context}: {type_ref.type_id}",
            span,
        )


def _validate_record_acyclic(environment: TypeEnvironmentV1) -> None:
    graph: dict[str, tuple[str, ...]] = {
        record.type_id: tuple(
            sorted(
                {
                    dependency
                    for _name, field_type in record.fields
                    for dependency in record_dependencies(field_type)
                }
            )
        )
        for record in environment.records
    }
    state: dict[str, int] = {}

    for start_id in sorted(graph):
        if state.get(start_id, 0) == 2:
            continue
        frames: list[list[object]] = [[start_id, 0]]
        path: list[str] = []
        while frames:
            type_id = str(frames[-1][0])
            next_index = int(frames[-1][1])
            if state.get(type_id, 0) == 0:
                state[type_id] = 1
                path.append(type_id)
            dependencies = graph[type_id]
            if next_index < len(dependencies):
                dependency = dependencies[next_index]
                frames[-1][1] = next_index + 1
                if dependency not in graph:
                    continue
                mark = state.get(dependency, 0)
                if mark == 0:
                    frames.append([dependency, 0])
                    continue
                if mark == 1:
                    cycle_start = path.index(dependency) if dependency in path else 0
                    cycle = [*path[cycle_start:], dependency]
                    declaration = environment.record(dependency)
                    raise TevScriptError(
                        "TEVS_V1_TYPE_RECORD_RECURSION",
                        "recursive record dependency: " + " -> ".join(cycle),
                        declaration.declaration.span if declaration is not None else None,
                    )
                continue
            frames.pop()
            popped = path.pop()
            assert popped == type_id
            state[type_id] = 2


def _validate_pure_function_graph_precheck(
    plan: LinkPlanV1,
    environment: TypeEnvironmentV1,
) -> None:
    source_functions = {
        item.callable_id: item
        for item in environment.functions
        if isinstance(item.declaration, FunctionDecl)
    }
    graph: dict[str, tuple[str, ...]] = {}

    for function_id, signature in source_functions.items():
        declaration = signature.declaration
        assert isinstance(declaration, FunctionDecl)
        calls: set[str] = set()
        stack: list[Expr] = [declaration.expression]
        while stack:
            expression = stack.pop()
            if expression.kind == "call" and expression.children:
                callee = expression.children[0]
                if callee.kind == "name":
                    try:
                        symbol = resolve_symbol(
                            plan,
                            signature.owner_id,
                            str(callee.value),
                            NAMESPACE_FUNCTION,
                            span=callee.span,
                        )
                    except TevScriptError as exc:
                        if exc.diagnostic.code == "TEVS_V1_LINK_NAME_AMBIGUOUS":
                            raise
                    else:
                        if isinstance(symbol.declaration, FunctionDecl):
                            calls.add(symbol.semantic_id)
                stack.extend(expression.children[1:])
                continue
            if expression.kind == "record":
                _type_name, field_inits = expression.value
                stack.extend(field.expression for field in field_inits)
            stack.extend(expression.children)
        graph[function_id] = tuple(sorted(calls))

    validate_bounded_dag_v1(
        graph,
        maximum_depth=MAX_PURE_FUNCTION_CALL_DEPTH,
        cycle_code="TEVS_V1_PURITY_RECURSION",
        depth_code="TEVS_V1_PURITY_CALL_DEPTH",
        span_for_node=lambda node_id: (
            source_functions[node_id].declaration.span
            if node_id in source_functions
            and isinstance(source_functions[node_id].declaration, FunctionDecl)
            else None
        ),
        graph_name="pure-function call graph",
    )


def _dedupe_capability_signatures(
    capabilities: list[CallableSignatureV1],
) -> list[CallableSignatureV1]:
    by_contract: dict[tuple[object, ...], CallableSignatureV1] = {}
    for item in capabilities:
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
        key=lambda item: (
            item.callable_id,
            tuple(parameter.type_id for parameter in item.parameters),
            item.return_type.type_id,
            item.kind,
        ),
    )


def _builtin_functions() -> list[CallableSignatureV1]:
    return [
        _from_builtin_signature(callable_id, signature)
        for callable_id, signatures in PURE_FUNCTIONS.items()
        for signature in signatures
    ]


def _builtin_capabilities() -> list[CallableSignatureV1]:
    return [
        _from_builtin_signature(callable_id, signature)
        for callable_id, signatures in CAPABILITIES.items()
        for signature in signatures
    ]


def _from_builtin_signature(
    callable_id: str,
    signature: Signature,
) -> CallableSignatureV1:
    return CallableSignatureV1(
        callable_id,
        tuple(primitive_type(item) for item in signature.parameters),
        primitive_type(signature.return_type),
        signature.kind,
        "<builtin>",
        None,
    )
