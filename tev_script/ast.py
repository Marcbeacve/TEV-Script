from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class Expr:
    kind: str
    value: object
    children: tuple["Expr", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ParameterDecl:
    name: str
    type_name: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class StateDecl:
    name: str
    type_name: str
    initial: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class LetStmt:
    name: str
    type_name: str | None
    expression: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class AssignStmt:
    name: str
    expression: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class CallStmt:
    capability_id: str
    arguments: tuple[Expr, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class EmitStmt:
    event_id: str
    arguments: tuple[Expr, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IfStmt:
    condition: Expr
    then_body: tuple["Statement", ...]
    else_body: tuple["Statement", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ReturnStmt:
    span: SourceSpan


Statement = LetStmt | AssignStmt | CallStmt | EmitStmt | IfStmt | ReturnStmt


@dataclass(frozen=True, slots=True)
class HandlerDecl:
    event_id: str
    parameters: tuple[ParameterDecl, ...]
    body: tuple[Statement, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class EntityDecl:
    name: str
    states: tuple[StateDecl, ...]
    handlers: tuple[HandlerDecl, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ScriptDecl:
    name: str
    language_version: str
    entities: tuple[EntityDecl, ...]
    span: SourceSpan


LiteralValue = bool | int | Fraction | str
