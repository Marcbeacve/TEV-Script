from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json

FIELD_SCHEMA_V0 = "TEV_SCRIPT_SEMANTIC_FIELD_V0"
META_RELATION = "tev.meta.relation"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")

class SemanticKernelError(ValueError):
    pass

def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise SemanticKernelError(f"{what} must be a stable id")
    return text

@dataclass(frozen=True, slots=True)
class FactV0:
    relation: str
    arguments: tuple[Any, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "relation", _stable(self.relation, "relation"))
        canonical_json(list(self.arguments))

    def to_object(self) -> dict[str, Any]:
        return {"relation": self.relation, "arguments": list(self.arguments)}

    @property
    def fact_hash(self) -> str:
        return canonical_hash(self.to_object())

@dataclass(frozen=True, slots=True)
class SemanticFieldV0:
    facts: tuple[FactV0, ...]

    def __post_init__(self) -> None:
        unique: dict[str, FactV0] = {}
        for fact in self.facts:
            unique[canonical_json(fact.to_object())] = fact
        facts = tuple(unique[k] for k in sorted(unique))
        declarations: dict[str, int] = {META_RELATION: 2}
        for fact in facts:
            if fact.relation != META_RELATION:
                continue
            if len(fact.arguments) != 2:
                raise SemanticKernelError("meta relation declaration arity")
            name = _stable(str(fact.arguments[0]), "declared relation")
            arity = fact.arguments[1]
            if not isinstance(arity, int) or isinstance(arity, bool) or arity < 0:
                raise SemanticKernelError("declared relation arity")
            if name in declarations and declarations[name] != arity:
                raise SemanticKernelError("conflicting relation declarations")
            declarations[name] = arity
        for fact in facts:
            if fact.relation not in declarations:
                raise SemanticKernelError(f"undeclared relation {fact.relation}")
            if len(fact.arguments) != declarations[fact.relation]:
                raise SemanticKernelError(f"arity mismatch for {fact.relation}")
        object.__setattr__(self, "facts", facts)

    @classmethod
    def build(
        cls,
        declarations: Iterable[tuple[str, int]],
        facts: Iterable[FactV0],
    ) -> "SemanticFieldV0":
        meta = tuple(FactV0(META_RELATION, (_stable(n, "relation"), int(a))) for n, a in declarations)
        return cls(meta + tuple(facts))

    @property
    def declarations(self) -> tuple[tuple[str, int], ...]:
        return tuple(sorted(
            (str(f.arguments[0]), int(f.arguments[1]))
            for f in self.facts
            if f.relation == META_RELATION
        ))

    def facts_for(self, relation: str) -> tuple[FactV0, ...]:
        return tuple(f for f in self.facts if f.relation == relation)

    def has(self, relation: str, arguments: tuple[Any, ...] | None = None) -> bool:
        if arguments is None:
            return bool(self.facts_for(relation))
        return any(f.arguments == arguments for f in self.facts_for(relation))

    def without(self, relation: str, arguments: tuple[Any, ...] | None = None) -> "SemanticFieldV0":
        kept = []
        for f in self.facts:
            if f.relation == META_RELATION:
                kept.append(f)
                continue
            if f.relation != relation:
                kept.append(f)
                continue
            if arguments is not None and f.arguments != arguments:
                kept.append(f)
        return SemanticFieldV0(tuple(kept))

    def with_fact(self, fact: FactV0) -> "SemanticFieldV0":
        return SemanticFieldV0(self.facts + (fact,))

    def merge(self, other: "SemanticFieldV0") -> "SemanticFieldV0":
        decls = dict(self.declarations)
        for name, arity in other.declarations:
            if name in decls and decls[name] != arity:
                raise SemanticKernelError(f"declaration conflict: {name}")
            decls[name] = arity
        body = tuple(f for f in self.facts + other.facts if f.relation != META_RELATION)
        return SemanticFieldV0.build(decls.items(), body)

    def to_object(self) -> dict[str, Any]:
        return {
            "schema": FIELD_SCHEMA_V0,
            "facts": [f.to_object() for f in self.facts],
        }

    @property
    def field_hash(self) -> str:
        return canonical_hash(self.to_object())

def empty_field() -> SemanticFieldV0:
    return SemanticFieldV0((FactV0(META_RELATION, (META_RELATION, 2)),))

def field_from_mapping(profile: str, mapping: Mapping[str, Any]) -> SemanticFieldV0:
    declarations = [("tev.profile", 1), ("tev.kv", 2)]
    facts = [FactV0("tev.profile", (_stable(profile, "profile"),))]
    for key, value in sorted(mapping.items()):
        facts.append(FactV0("tev.kv", (str(key), value)))
    return SemanticFieldV0.build(declarations, facts)

def field_delta(before: SemanticFieldV0, after: SemanticFieldV0) -> tuple[tuple[FactV0, ...], tuple[FactV0, ...]]:
    b = {f.fact_hash: f for f in before.facts if f.relation != META_RELATION}
    a = {f.fact_hash: f for f in after.facts if f.relation != META_RELATION}
    return (
        tuple(a[k] for k in sorted(set(a) - set(b))),
        tuple(b[k] for k in sorted(set(b) - set(a))),
    )

__all__ = [
    "FIELD_SCHEMA_V0", "META_RELATION", "SemanticKernelError",
    "FactV0", "SemanticFieldV0", "empty_field", "field_from_mapping", "field_delta",
]
