from __future__ import annotations
from collections import defaultdict, deque
from typing import Callable, Iterable, Mapping

from .semantic_kernel_v0 import FactV0, SemanticFieldV0

TRACE_DECLS = (
    ("tev.trace.event", 3),  # event_id, center_id, label
    ("tev.trace.hb", 2),
)

def trace_field(events: Iterable[tuple[str, str, str]], happens_before: Iterable[tuple[str, str]]) -> SemanticFieldV0:
    facts = [FactV0("tev.trace.event", tuple(e)) for e in events]
    facts += [FactV0("tev.trace.hb", tuple(e)) for e in happens_before]
    field = SemanticFieldV0.build(TRACE_DECLS, facts)
    if not is_acyclic(field):
        raise ValueError("causal trace cycle")
    return field

def _graph(field: SemanticFieldV0) -> tuple[set[str], dict[str, set[str]]]:
    nodes = {str(f.arguments[0]) for f in field.facts_for("tev.trace.event")}
    g = {n: set() for n in nodes}
    for f in field.facts_for("tev.trace.hb"):
        a, b = map(str, f.arguments)
        if a not in nodes or b not in nodes:
            raise ValueError("happens-before references unknown event")
        g[a].add(b)
    return nodes, g

def is_acyclic(field: SemanticFieldV0) -> bool:
    nodes, g = _graph(field)
    indeg = {n: 0 for n in nodes}
    for a in nodes:
        for b in g[a]:
            indeg[b] += 1
    q = deque(sorted(n for n, d in indeg.items() if d == 0))
    count = 0
    while q:
        n = q.popleft()
        count += 1
        for m in sorted(g[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)
    return count == len(nodes)

def happens_before(field: SemanticFieldV0, left: str, right: str) -> bool:
    nodes, g = _graph(field)
    if left not in nodes or right not in nodes:
        return False
    q = deque([left]); seen = set()
    while q:
        n = q.popleft()
        if n in seen:
            continue
        seen.add(n)
        if n == right and n != left:
            return True
        q.extend(g[n])
    return False

def concurrent(field: SemanticFieldV0, left: str, right: str) -> bool:
    return left != right and not happens_before(field, left, right) and not happens_before(field, right, left)

def bounded_response(field: SemanticFieldV0, request_label: str, response_label: str, max_edges: int) -> bool:
    nodes, g = _graph(field)
    labels = {str(f.arguments[0]): str(f.arguments[2]) for f in field.facts_for("tev.trace.event")}
    responses = {n for n, label in labels.items() if label == response_label}
    for start, label in labels.items():
        if label != request_label:
            continue
        q = deque([(start, 0)])
        seen = set()
        found = False
        while q:
            n, d = q.popleft()
            if (n, d) in seen or d > max_edges:
                continue
            seen.add((n, d))
            if n in responses and n != start:
                found = True
                break
            for m in g[n]:
                q.append((m, d + 1))
        if not found:
            return False
    return True

def finite_ranking_witness(ranks: Iterable[int], goal: Callable[[int], bool]) -> bool:
    vals = tuple(ranks)
    if not vals or not goal(vals[-1]):
        return False
    return all(b < a for a, b in zip(vals, vals[1:]))

__all__ = ["trace_field", "is_acyclic", "happens_before", "concurrent", "bounded_response", "finite_ranking_witness"]
