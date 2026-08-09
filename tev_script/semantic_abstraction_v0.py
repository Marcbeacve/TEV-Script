from __future__ import annotations
from itertools import combinations
from typing import Callable, Iterable

from .semantic_kernel_v0 import FactV0, SemanticFieldV0, META_RELATION

def project_relations(field: SemanticFieldV0, relations: Iterable[str]) -> SemanticFieldV0:
    keep = set(relations)
    decls = [(n, a) for n, a in field.declarations if n in keep]
    facts = [f for f in field.facts if f.relation in keep]
    return SemanticFieldV0.build(decls, facts)

def decision_sufficient(fields: Iterable[SemanticFieldV0], decision: Callable[[SemanticFieldV0], str]) -> bool:
    vals = tuple(fields)
    return len({decision(f) for f in vals}) <= 1

def coarsest_decision_sufficient_relation_sets(
    fields: Iterable[SemanticFieldV0],
    candidate_relations: Iterable[str],
    decision_from_projection: Callable[[SemanticFieldV0], str],
) -> tuple[tuple[str, ...], ...]:
    vals = tuple(fields)
    rels = tuple(sorted(set(candidate_relations)))
    winners: list[tuple[str, ...]] = []
    for size in range(len(rels) + 1):
        for subset in combinations(rels, size):
            projected = tuple(project_relations(f, subset) for f in vals)
            # A relation set is sufficient only if every pair with the same projection has the same decision.
            groups: dict[str, set[str]] = {}
            for original, coarse in zip(vals, projected):
                groups.setdefault(coarse.field_hash, set()).add(decision_from_projection(original))
            if all(len(labels) <= 1 for labels in groups.values()):
                winners.append(tuple(subset))
        if winners:
            break
    return tuple(winners)

def verify_commuting_square(
    fine_before: SemanticFieldV0,
    fine_after: SemanticFieldV0,
    coarse_before: SemanticFieldV0,
    coarse_after: SemanticFieldV0,
    abstraction: Callable[[SemanticFieldV0], SemanticFieldV0],
    judgment: Callable[[SemanticFieldV0], str],
) -> bool:
    return (
        abstraction(fine_before).field_hash == coarse_before.field_hash
        and abstraction(fine_after).field_hash == coarse_after.field_hash
        and judgment(fine_before) == judgment(coarse_before)
        and judgment(fine_after) == judgment(coarse_after)
    )

__all__ = [
    "project_relations", "decision_sufficient",
    "coarsest_decision_sufficient_relation_sets", "verify_commuting_square",
]
