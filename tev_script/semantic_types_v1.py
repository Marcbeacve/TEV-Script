from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ast_v1 import (
    CapabilityDecl,
    EnumDecl,
    FunctionDecl,
    RecordDecl,
    TypeRef,
)
from .diagnostics import SourceSpan, TevScriptError
from .linker_v1 import (
    LinkPlanV1,
    NAMESPACE_CAPABILITY,
    NAMESPACE_FUNCTION,
    NAMESPACE_TYPE,
    SymbolV1,
    canonical_type_id,
    resolve_symbol,
)
from .types import CAPABILITIES, PURE_FUNCTIONS, Signature, SUPPORTED_TYPES


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
        if self.is_unit:
            return False
        return all(item.is_storable for item in self.arguments)


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
        raise TevScriptError(
            code,
            f"expected {expected.type_id}, got {actual.type_id}",
            span,
        )


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
                parameters = tuple(resolve_type(plan, owner_id, p.type_ref) for p in declaration.parameters)
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
                parameters = tuple(resolve_type(plan, owner_id, p) for p in declaration.parameter_types)
                return_type = resolve_type(plan, owner_id, declaration.return_type)
                for parameter, resolved in zip(declaration.parameter_types, parameters, strict=True):
                    _require_storable(resolved, parameter.span, "capability parameter")
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
    functions.sort(key=lambda item: (item.callable_id, tuple(x.type_id for x in item.parameters)))
    capabilities.sort(key=lambda item: (item.callable_id, tuple(x.type_id for x in item.parameters)))

    environment = TypeEnvironmentV1(tuple(records), tuple(enums), tuple(functions), tuple(capabilities))
    _validate_record_acyclic(environment)
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
        if tuple(x.type_id for x in item.parameters) == tuple(x.type_id for x in actual)
    ]
    if len(exact) == 1:
        return exact[0]
    widened = [
        item
        for item in candidates
        if len(item.parameters) == len(actual)
        and all(can_assign(a, e) for a, e in zip(actual, item.parameters, strict=True))
    ]
    if len(widened) == 1:
        return widened[0]
    raise TevScriptError(
        "TEVS_V1_TYPE_CALL_SIGNATURE",
        f"{callable_id} does not accept ({', '.join(x.type_id for x in actual)})",
        span,
    )


def record_dependencies(type_ref: ResolvedTypeV1) -> tuple[str, ...]:
    if type_ref.kind == "record":
        return (type_ref.type_id,)
    result: list[str] = []
    for argument in type_ref.arguments:
        result.extend(record_dependencies(argument))
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
    stack: list[str] = []

    def visit(type_id: str) -> None:
        mark = state.get(type_id, 0)
        if mark == 2:
            return
        if mark == 1:
            start = stack.index(type_id) if type_id in stack else 0
            cycle = [*stack[start:], type_id]
            declaration = environment.record(type_id)
            raise TevScriptError(
                "TEVS_V1_TYPE_RECORD_RECURSION",
                "recursive record dependency: " + " -> ".join(cycle),
                declaration.declaration.span if declaration is not None else None,
            )
        state[type_id] = 1
        stack.append(type_id)
        for dependency in graph.get(type_id, ()):
            if dependency in graph:
                visit(dependency)
        stack.pop()
        state[type_id] = 2

    for type_id in sorted(graph):
        visit(type_id)


def _builtin_functions() -> list[CallableSignatureV1]:
    result: list[CallableSignatureV1] = []
    for callable_id, signatures in PURE_FUNCTIONS.items():
        for signature in signatures:
            result.append(_from_builtin_signature(callable_id, signature))
    return result


def _builtin_capabilities() -> list[CallableSignatureV1]:
    result: list[CallableSignatureV1] = []
    for callable_id, signatures in CAPABILITIES.items():
        for signature in signatures:
            result.append(_from_builtin_signature(callable_id, signature))
    return result


def _from_builtin_signature(callable_id: str, signature: Signature) -> CallableSignatureV1:
    return CallableSignatureV1(
        callable_id,
        tuple(primitive_type(item) for item in signature.parameters),
        primitive_type(signature.return_type),
        signature.kind,
        "<builtin>",
        None,
    )
