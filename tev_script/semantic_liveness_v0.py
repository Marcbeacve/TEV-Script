from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .canonical import canonical_hash


@dataclass(frozen=True, slots=True)
class LivenessJudgmentV0:
    status: str
    reason: str
    scope_hash: str
    witness: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FiniteTransitionSystemV0:
    states: tuple[str, ...]
    initial: str
    edges: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        state_set = set(self.states)
        if len(state_set) != len(self.states):
            raise ValueError("duplicate_state")
        if self.initial not in state_set:
            raise ValueError("initial_state")
        if any(
            left not in state_set or right not in state_set
            for left, right in self.edges
        ):
            raise ValueError("edge_state")

    @property
    def graph(self) -> dict[str, tuple[str, ...]]:
        graph: dict[str, list[str]] = {
            state: [] for state in self.states
        }
        for left, right in self.edges:
            graph[left].append(right)
        return {
            state: tuple(sorted(targets))
            for state, targets in graph.items()
        }


def liveness_scope_hash(
    system: FiniteTransitionSystemV0,
    goals,
    justice_sets,
) -> str:
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_LIVENESS_SCOPE_V0",
            "states": list(system.states),
            "initial": system.initial,
            "edges": [list(edge) for edge in sorted(system.edges)],
            "goals": sorted(goals),
            "justice_sets": [
                sorted(justice)
                for justice in justice_sets
            ],
        }
    )


def _reachable_without_goal(
    system: FiniteTransitionSystemV0,
    goals: set[str],
) -> set[str]:
    graph = system.graph
    queue = deque([system.initial])
    seen: set[str] = set()
    while queue:
        state = queue.popleft()
        if state in seen or state in goals:
            continue
        seen.add(state)
        queue.extend(graph[state])
    return seen


def _sccs(
    system: FiniteTransitionSystemV0,
    allowed: set[str],
) -> tuple[tuple[str, ...], ...]:
    graph = system.graph
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    result: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in graph[node]:
            if target not in allowed:
                continue
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], indices[target])

        if low[node] == indices[node]:
            component: list[str] = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            result.append(tuple(sorted(component)))

    for node in sorted(allowed):
        if node not in indices:
            visit(node)

    return tuple(result)


def finite_fair_eventually(
    system: FiniteTransitionSystemV0,
    goal_states,
    justice_sets=(),
) -> LivenessJudgmentV0:
    goals = set(goal_states)
    justice = tuple(set(group) for group in justice_sets)
    states = set(system.states)

    if not goals <= states:
        raise ValueError("unknown_goal_state")
    if any(not group or not group <= states for group in justice):
        raise ValueError("invalid_justice_set")

    scope_hash = liveness_scope_hash(
        system,
        goals,
        justice,
    )
    reachable = _reachable_without_goal(system, goals)
    graph = system.graph

    deadlocks = tuple(
        sorted(
            state
            for state in reachable
            if not graph[state]
        )
    )
    if deadlocks:
        return LivenessJudgmentV0(
            "REJECT",
            "non_goal_deadlock",
            scope_hash,
            deadlocks,
        )

    edge_set = set(system.edges)
    for component in _sccs(system, reachable):
        component_set = set(component)
        cyclic = (
            len(component) > 1
            or (component[0], component[0]) in edge_set
        )
        fair = all(
            component_set & group
            for group in justice
        )
        if cyclic and fair:
            return LivenessJudgmentV0(
                "REJECT",
                "fair_non_goal_cycle",
                scope_hash,
                component,
            )

    return LivenessJudgmentV0(
        "PASS",
        "finite_fair_eventually_exhaustive",
        scope_hash,
    )


def verify_lasso_witness(
    system: FiniteTransitionSystemV0,
    prefix,
    cycle,
    justice_sets=(),
) -> LivenessJudgmentV0:
    justice = tuple(set(group) for group in justice_sets)
    if any(not group for group in justice):
        raise ValueError("invalid_justice_set")

    scope_hash = liveness_scope_hash(
        system,
        (),
        justice,
    )
    prefix = tuple(prefix)
    cycle = tuple(cycle)

    if not prefix or prefix[0] != system.initial or not cycle:
        return LivenessJudgmentV0(
            "REJECT",
            "invalid_lasso_shape",
            scope_hash,
        )

    edges = set(system.edges)
    path = prefix + cycle
    if any(
        (left, right) not in edges
        for left, right in zip(path, path[1:])
    ):
        return LivenessJudgmentV0(
            "REJECT",
            "invalid_lasso_edge",
            scope_hash,
        )
    if (cycle[-1], cycle[0]) not in edges:
        return LivenessJudgmentV0(
            "REJECT",
            "cycle_not_closed",
            scope_hash,
        )

    cycle_set = set(cycle)
    if any(
        not (cycle_set & group)
        for group in justice
    ):
        return LivenessJudgmentV0(
            "REJECT",
            "lasso_not_fair",
            scope_hash,
        )

    return LivenessJudgmentV0(
        "PASS",
        "lasso_verified",
        scope_hash,
        cycle,
    )


def general_liveness(
    *,
    scope_hash: str,
    proof_witness=None,
    trust_policy=None,
) -> LivenessJudgmentV0:
    if (
        proof_witness is not None
        and trust_policy is not None
        and trust_policy.accepts(
            proof_witness,
            scope_hash,
        )
    ):
        return LivenessJudgmentV0(
            "PASS",
            "trusted_external_proof",
            scope_hash,
            (proof_witness.witness_hash,),
        )

    return LivenessJudgmentV0(
        "PROOF_REQUIRED",
        "infinite_or_unbounded_liveness",
        scope_hash,
    )


__all__ = [
    "LivenessJudgmentV0",
    "FiniteTransitionSystemV0",
    "liveness_scope_hash",
    "finite_fair_eventually",
    "verify_lasso_witness",
    "general_liveness",
]
