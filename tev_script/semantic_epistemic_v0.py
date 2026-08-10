from __future__ import annotations
from collections import defaultdict, deque
from typing import Any, Iterable

from .semantic_kernel_v0 import FactV0, SemanticFieldV0

EVIDENCE_DECLS = (
    ("tev.evidence", 8),  # id, proposition, polarity, source, event_time, knowledge_time, support_id, status
    ("tev.evidence.depends", 2),
    ("tev.evidence.invalidated", 2),
    ("tev.unknown", 2),
)
_STATUSES = {"active", "invalidated"}
_POLARITY = {"support", "refute"}

def evidence_field(
    rows: Iterable[tuple[str, str, str, str, int, int, str, str]],
    dependencies: Iterable[tuple[str, str]] = (),
    unknowns: Iterable[tuple[str, str]] = (),
    invalidated: Iterable[tuple[str, str]] = (),
) -> SemanticFieldV0:
    facts = []
    for row in rows:
        if row[2] not in _POLARITY or row[7] not in _STATUSES:
            raise ValueError("invalid evidence row")
        facts.append(FactV0("tev.evidence", tuple(row)))
    facts += [FactV0("tev.evidence.depends", tuple(x)) for x in dependencies]
    facts += [FactV0("tev.evidence.invalidated", tuple(x)) for x in invalidated]
    facts += [FactV0("tev.unknown", tuple(x)) for x in unknowns]
    return SemanticFieldV0.build(EVIDENCE_DECLS, facts)

def proposition_status(field: SemanticFieldV0, proposition: str) -> str:
    invalid = {str(f.arguments[0]) for f in field.facts_for("tev.evidence.invalidated")}
    support = False
    refute = False
    for f in field.facts_for("tev.evidence"):
        eid, prop, polarity, _, _, _, _, status = f.arguments
        if str(prop) != proposition or str(status) != "active" or str(eid) in invalid:
            continue
        support |= str(polarity) == "support"
        refute |= str(polarity) == "refute"
    if support and refute:
        return "BOTH"
    if support:
        return "TRUE_ONLY"
    if refute:
        return "FALSE_ONLY"
    return "NEITHER"

def invalidate_transitively(field: SemanticFieldV0, evidence_id: str, reason: str) -> SemanticFieldV0:
    reverse: dict[str, list[str]] = defaultdict(list)
    for f in field.facts_for("tev.evidence.depends"):
        child, parent = map(str, f.arguments)
        reverse[parent].append(child)
    seen = set()
    q = deque([evidence_id])
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        q.extend(reverse.get(cur, ()))
    out = field
    for eid in sorted(seen):
        out = out.with_fact(FactV0("tev.evidence.invalidated", (eid, reason)))
    return out

def unknown_reasons(field: SemanticFieldV0, subject: str) -> tuple[str, ...]:
    return tuple(sorted(str(f.arguments[1]) for f in field.facts_for("tev.unknown") if str(f.arguments[0]) == subject))

__all__ = ["evidence_field", "proposition_status", "invalidate_transitively", "unknown_reasons"]
