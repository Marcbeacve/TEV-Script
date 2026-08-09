from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .diagnostics import SourceSpan


@dataclass(frozen=True, slots=True)
class TypeRef:
    """Syntactic V1 type reference. Name resolution happens in the linker."""

    kind: str
    name: str | None
    arguments: tuple["TypeRef", ...]
    span: SourceSpan

    @classmethod
    def named(cls, name: str, span: SourceSpan) -> "TypeRef":
        return cls("named", name, (), span)

    @classmethod
    def option(cls, argument: "TypeRef", span: SourceSpan) -> "TypeRef":
        return cls("option", "Option", (argument,), span)

    @classmethod
    def result(cls, ok: "TypeRef", err: "TypeRef", span: SourceSpan) -> "TypeRef":
        return cls("result", "Result", (ok, err), span)


@dataclass(frozen=True, slots=True)
class Expr:
    kind: str
    value: object
    children: tuple["Expr", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class FieldInit:
    name: str
    expression: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ParameterDecl:
    name: str
    type_ref: TypeRef
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ImportDecl:
    module_id: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class CapabilityDecl:
    capability_id: str
    parameter_types: tuple[TypeRef, ...]
    return_type: TypeRef
    capability_kind: str
    exported: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class RecordFieldDecl:
    name: str
    type_ref: TypeRef
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class RecordDecl:
    name: str
    fields: tuple[RecordFieldDecl, ...]
    exported: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class EnumDecl:
    name: str
    variants: tuple[str, ...]
    exported: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class FunctionDecl:
    name: str
    parameters: tuple[ParameterDecl, ...]
    return_type: TypeRef
    expression: Expr
    exported: bool
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class StateDecl:
    name: str
    type_ref: TypeRef
    initial: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class UseDecl:
    behavior_id: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class LetStmt:
    name: str
    type_ref: TypeRef | None
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
class LogStmt:
    expression: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MoveStmt:
    expression: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class AnimateStmt:
    expression: Expr
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class IfStmt:
    condition: Expr
    then_body: tuple["Statement", ...]
    else_body: tuple["Statement", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ForStmt:
    variable: str
    lower: int
    upper: int
    body: tuple["Statement", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class EnumPattern:
    type_name: str
    variant: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class SomePattern:
    binding: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class NonePattern:
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class OkPattern:
    binding: str
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ErrPattern:
    binding: str
    span: SourceSpan


Pattern = EnumPattern | SomePattern | NonePattern | OkPattern | ErrPattern


@dataclass(frozen=True, slots=True)
class MatchArm:
    pattern: Pattern
    body: tuple["Statement", ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class MatchStmt:
    expression: Expr
    arms: tuple[MatchArm, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ReturnStmt:
    span: SourceSpan


Statement = (
    LetStmt
    | AssignStmt
    | CallStmt
    | EmitStmt
    | LogStmt
    | MoveStmt
    | AnimateStmt
    | IfStmt
    | ForStmt
    | MatchStmt
    | ReturnStmt
)


@dataclass(frozen=True, slots=True)
class HandlerDecl:
    event_id: str
    parameters: tuple[ParameterDecl, ...]
    body: tuple[Statement, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class BehaviorDecl:
    name: str
    uses: tuple[UseDecl, ...]
    states: tuple[StateDecl, ...]
    handlers: tuple[HandlerDecl, ...]
    exported: bool
    span: SourceSpan


TopDecl = CapabilityDecl | RecordDecl | EnumDecl | FunctionDecl | BehaviorDecl


@dataclass(frozen=True, slots=True)
class EntityDecl:
    name: str
    uses: tuple[UseDecl, ...]
    states: tuple[StateDecl, ...]
    handlers: tuple[HandlerDecl, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ScriptUnit:
    program_id: str
    language_version: str
    imports: tuple[ImportDecl, ...]
    declarations: tuple[TopDecl, ...]
    entities: tuple[EntityDecl, ...]
    span: SourceSpan


@dataclass(frozen=True, slots=True)
class ModuleUnit:
    module_id: str
    language_version: str
    imports: tuple[ImportDecl, ...]
    declarations: tuple[TopDecl, ...]
    span: SourceSpan


SourceFile = ScriptUnit | ModuleUnit
LiteralValue = bool | int | Fraction | str
