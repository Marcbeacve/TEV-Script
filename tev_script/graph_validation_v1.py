from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from .diagnostics import SourceSpan, TevScriptError


@dataclass(frozen=True, slots=True)
class GraphValidationV1:
    topological_order: tuple[str, ...]
    longest_depth: int
    depths: tuple[tuple[str, int], ...]

    def depth(self, node_id: str) -> int:
        for key, value in self.depths:
            if key == node_id:
                return value
        raise KeyError(node_id)


def validate_bounded_dag_v1(
    graph: Mapping[str, tuple[str, ...]],
    *,
    maximum_depth: int,
    cycle_code: str,
    depth_code: str,
    span_for_node: Callable[[str], SourceSpan | None],
    graph_name: str,
) -> GraphValidationV1:
    """Validate a finite directed graph without Python recursion.

    Edge direction is `node -> dependency`. The returned topological order is
    dependency-first. Ties are lexical by node id. Any dependency outside the
    supplied graph is ignored by the depth/cycle calculation; callers should
    validate unresolved references separately.
    """

    normalized = {
        node_id: tuple(sorted(set(dependency for dependency in dependencies if dependency in graph)))
        for node_id, dependencies in graph.items()
    }

    state: dict[str, int] = {}
    dependency_first: list[str] = []

    for start_id in sorted(normalized):
        if state.get(start_id, 0) == 2:
            continue

        frames: list[list[object]] = [[start_id, 0]]
        path: list[str] = []
        path_positions: dict[str, int] = {}

        while frames:
            node_id = str(frames[-1][0])
            next_index = int(frames[-1][1])
            if state.get(node_id, 0) == 0:
                state[node_id] = 1
                path_positions[node_id] = len(path)
                path.append(node_id)

            dependencies = normalized[node_id]
            if next_index < len(dependencies):
                dependency = dependencies[next_index]
                frames[-1][1] = next_index + 1
                mark = state.get(dependency, 0)
                if mark == 0:
                    frames.append([dependency, 0])
                    continue
                if mark == 1:
                    cycle_start = path_positions.get(dependency, 0)
                    cycle = [*path[cycle_start:], dependency]
                    raise TevScriptError(
                        cycle_code,
                        f"{graph_name} cycle: " + " -> ".join(cycle),
                        span_for_node(dependency),
                    )
                continue

            frames.pop()
            popped = path.pop()
            path_positions.pop(popped, None)
            assert popped == node_id
            state[node_id] = 2
            dependency_first.append(node_id)

    depth_by_node: dict[str, int] = {}
    longest_depth = 0
    # dependency_first already guarantees every dependency depth is available.
    for node_id in dependency_first:
        dependencies = normalized[node_id]
        depth = 1 + max((depth_by_node[item] for item in dependencies), default=0)
        depth_by_node[node_id] = depth
        if depth > maximum_depth:
            raise TevScriptError(
                depth_code,
                f"{graph_name} depth exceeds {maximum_depth}: got {depth} at {node_id}",
                span_for_node(node_id),
            )
        longest_depth = max(longest_depth, depth)

    return GraphValidationV1(
        topological_order=tuple(dependency_first),
        longest_depth=longest_depth,
        depths=tuple(sorted(depth_by_node.items())),
    )
