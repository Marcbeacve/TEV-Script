from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .causal_model_v1 import (
    CapabilityLawCatalogV1,
    CapabilityOccurrenceV1,
    IndependenceResultV1,
    PreparabilityResultV1,
    ReactionFootprintV1,
    ResourceAccessV1,
)
from .ir_v3_validation import validate_program_ir_v3


@dataclass(frozen=True, slots=True)
class _DirectHandlerV1:
    event_id: str
    reads: frozenset[str]
    writes: frozenset[str]
    observations: frozenset[str]
    effects: frozenset[str]
    emitted: frozenset[str]
    occurrences: tuple[CapabilityOccurrenceV1, ...]
    instruction_budget: int


def _direct_handlers(entity: Mapping[str, Any]) -> dict[str, _DirectHandlerV1]:
    result: dict[str, _DirectHandlerV1] = {}
    for raw_handler in entity["handlers"]:
        event_id = str(raw_handler["event_id"])
        reads: set[str] = set()
        writes: set[str] = set()
        observations: set[str] = set()
        effects: set[str] = set()
        emitted: set[str] = set()
        occurrences: list[CapabilityOccurrenceV1] = []
        for index, instruction in enumerate(raw_handler["instructions"]):
            op = str(instruction["op"])
            if op == "LOAD_STATE":
                reads.add(str(instruction["name"]))
            elif op == "STORE_STATE":
                writes.add(str(instruction["name"]))
            elif op == "CALL_CAPABILITY":
                capability_id = str(instruction["capability_id"])
                kind = str(instruction["kind"])
                occurrences.append(CapabilityOccurrenceV1(event_id, index, capability_id, kind))
                (observations if kind == "observation" else effects).add(capability_id)
            elif op == "EMIT_EVENT":
                emitted.add(str(instruction["event_id"]))
        result[event_id] = _DirectHandlerV1(
            event_id,
            frozenset(reads),
            frozenset(writes),
            frozenset(observations),
            frozenset(effects),
            frozenset(emitted),
            tuple(occurrences),
            int(raw_handler["instruction_budget"]),
        )
    return result


def _graph(handlers: Mapping[str, _DirectHandlerV1]) -> dict[str, tuple[str, ...]]:
    known = set(handlers)
    return {
        event: tuple(sorted(target for target in handler.emitted if target in known))
        for event, handler in handlers.items()
    }


def _reachable(graph: Mapping[str, tuple[str, ...]], start: str) -> tuple[str, ...]:
    seen: set[str] = set()
    pending = [start]
    while pending:
        event = pending.pop()
        if event in seen:
            continue
        seen.add(event)
        pending.extend(reversed(graph.get(event, ())))
    return tuple(sorted(seen))


def _has_reachable_cycle(graph: Mapping[str, tuple[str, ...]], reachable: set[str]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for target in graph.get(node, ()):
            if target in reachable and visit(target):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in sorted(reachable) if node not in visited)


def _path_exists(graph: Mapping[str, tuple[str, ...]], start: str, target: str) -> bool:
    pending = list(graph.get(start, ()))
    seen: set[str] = set()
    while pending:
        node = pending.pop()
        if node == target:
            return True
        if node in seen:
            continue
        seen.add(node)
        pending.extend(graph.get(node, ()))
    return False


def derive_reaction_footprints(ir: Mapping[str, Any]) -> tuple[ReactionFootprintV1, ...]:
    program = dict(ir)
    validate_program_ir_v3(program)
    program_hash = str(program["semantic_hash"])
    source_hash = str(program["source_semantic_hash"])
    maximum_event_chain = int(program["boundary"]["maximum_event_chain"])
    footprints: list[ReactionFootprintV1] = []
    for entity in program["entities"]:
        entity_id = str(entity["entity_id"])
        handlers = _direct_handlers(entity)
        graph = _graph(handlers)
        for trigger in sorted(handlers):
            reachable_events = _reachable(graph, trigger)
            reachable = set(reachable_events)
            selected = [handlers[event] for event in reachable_events]
            maximum_handler_budget = max(item.instruction_budget for item in selected)
            footprints.append(
                ReactionFootprintV1(
                    program_semantic_hash=program_hash,
                    source_semantic_hash=source_hash,
                    entity_id=entity_id,
                    trigger_event=trigger,
                    reachable_events=reachable_events,
                    state_reads=tuple(sorted(set().union(*(item.reads for item in selected)))),
                    state_writes=tuple(sorted(set().union(*(item.writes for item in selected)))),
                    observations=tuple(sorted(set().union(*(item.observations for item in selected)))),
                    effects=tuple(sorted(set().union(*(item.effects for item in selected)))),
                    emitted_events=tuple(sorted(set().union(*(item.emitted for item in selected)))),
                    capability_occurrences=tuple(
                        occurrence for item in selected for occurrence in item.occurrences
                    ),
                    reachable_handler_count=len(reachable_events),
                    maximum_event_chain=maximum_event_chain,
                    instruction_ceiling=maximum_event_chain * maximum_handler_budget,
                    cyclic_event_graph=_has_reachable_cycle(graph, reachable),
                )
            )
    footprints.sort(key=lambda item: (item.entity_id, item.trigger_event))
    return tuple(footprints)


def find_reaction_footprint(
    ir: Mapping[str, Any], entity_id: str, trigger_event: str
) -> ReactionFootprintV1:
    for footprint in derive_reaction_footprints(ir):
        if footprint.entity_id == entity_id and footprint.trigger_event == trigger_event:
            return footprint
    raise KeyError(f"reaction {entity_id}.{trigger_event} not found")


def reaction_resources(
    footprint: ReactionFootprintV1, catalog: CapabilityLawCatalogV1
) -> tuple[str, ...]:
    resources: set[str] = set()
    for capability_id in (*footprint.observations, *footprint.effects):
        law = catalog.law(capability_id)
        if law is None:
            continue
        for access in law.accesses:
            resources.add(catalog.canonical_resource(access.resource_id) or access.resource_id)
    return tuple(sorted(resources))


def _explicitly_commute(left, right) -> bool:
    return (
        right.capability_id in left.commutes_with
        and left.capability_id in right.commutes_with
    )


def _same_resource_safe(left_law, left_access: ResourceAccessV1, right_law, right_access: ResourceAccessV1) -> bool:
    if _explicitly_commute(left_law, right_law):
        return True
    if left_access.mode == right_access.mode == "read":
        return (
            left_law.kind == right_law.kind == "observation"
            and left_law.observation_semantics in {"snapshot", "stable"}
            and right_law.observation_semantics in {"snapshot", "stable"}
        )
    return False



def _law_binding_reasons(footprint: ReactionFootprintV1, catalog: CapabilityLawCatalogV1) -> tuple[str, ...]:
    reasons: list[str] = []
    for capability_id in footprint.observations:
        law = catalog.law(capability_id)
        if law is not None and law.kind != "observation":
            reasons.append(f"capability_kind_mismatch:{capability_id}:expected_observation:law_{law.kind}")
    for capability_id in footprint.effects:
        law = catalog.law(capability_id)
        if law is not None and law.kind != "effect":
            reasons.append(f"capability_kind_mismatch:{capability_id}:expected_effect:law_{law.kind}")
    return tuple(sorted(reasons))


def reaction_authority_lease(
    footprint: ReactionFootprintV1,
    catalog: CapabilityLawCatalogV1,
) -> tuple[ResourceAccessV1, ...]:
    lease: set[ResourceAccessV1] = set()
    for capability_id in (*footprint.observations, *footprint.effects):
        law = catalog.law(capability_id)
        if law is None:
            continue
        for access in law.accesses:
            resource = catalog.resource_law(access.resource_id)
            if resource is not None and resource.kind == "authority":
                lease.add(ResourceAccessV1(resource.resource_id, access.mode))
    return tuple(sorted(lease, key=lambda item: (item.resource_id, item.mode)))


def prove_authority_capacity(
    footprints: tuple[ReactionFootprintV1, ...],
    catalog: CapabilityLawCatalogV1,
) -> IndependenceResultV1:
    reasons: list[str] = []
    if footprints and not catalog.complete:
        reasons.append("deployment_catalog_not_complete")
    demands: dict[str, int] = {}
    for footprint in footprints:
        missing = [
            capability_id
            for capability_id in (*footprint.observations, *footprint.effects)
            if catalog.law(capability_id) is None
        ]
        if missing:
            reasons.append("missing_capability_law:" + ",".join(sorted(set(missing))))
        reasons.extend(_law_binding_reasons(footprint, catalog))
        for access in reaction_authority_lease(footprint, catalog):
            if access.mode in {"consume", "reserve"}:
                demands[access.resource_id] = demands.get(access.resource_id, 0) + 1
    for resource_id, demand in sorted(demands.items()):
        resource = catalog.resource_law(resource_id)
        if resource is None:
            reasons.append(f"authority_resource_unknown:{resource_id}")
        elif resource.capacity is not None and demand > resource.capacity:
            reasons.append(f"authority_capacity_exceeded:{resource_id}:{demand}>{resource.capacity}")
    return IndependenceResultV1(not reasons, tuple(sorted(set(reasons))))

def prove_independence(
    left: ReactionFootprintV1,
    right: ReactionFootprintV1,
    catalog: CapabilityLawCatalogV1,
) -> IndependenceResultV1:
    reasons: list[str] = [*_law_binding_reasons(left, catalog), *_law_binding_reasons(right, catalog)]
    left_reads = {f"state:{left.entity_id}:{name}" for name in left.state_reads}
    left_writes = {f"state:{left.entity_id}:{name}" for name in left.state_writes}
    right_reads = {f"state:{right.entity_id}:{name}" for name in right.state_reads}
    right_writes = {f"state:{right.entity_id}:{name}" for name in right.state_writes}
    if left_writes & (right_reads | right_writes):
        reasons.append("internal_state_left_write_conflict")
    if right_writes & (left_reads | left_writes):
        reasons.append("internal_state_right_write_conflict")

    left_caps = tuple(sorted(set((*left.observations, *left.effects))))
    right_caps = tuple(sorted(set((*right.observations, *right.effects))))
    if left_caps or right_caps:
        if not catalog.complete:
            reasons.append("deployment_catalog_not_complete")
        missing = sorted(
            capability_id
            for capability_id in set((*left_caps, *right_caps))
            if catalog.law(capability_id) is None
        )
        if missing:
            reasons.append("missing_capability_law:" + ",".join(missing))
        for left_id in left_caps:
            left_law = catalog.law(left_id)
            if left_law is None:
                continue
            for right_id in right_caps:
                right_law = catalog.law(right_id)
                if right_law is None:
                    continue
                for left_access in left_law.accesses:
                    for right_access in right_law.accesses:
                        relation = catalog.alias_relation(left_access.resource_id, right_access.resource_id)
                        if relation == "unknown":
                            reasons.append(f"resource_alias_unknown:{left_id}:{right_id}")
                        elif relation == "same" and not _same_resource_safe(
                            left_law, left_access, right_law, right_access
                        ):
                            reasons.append(
                                f"resource_conflict:{left_id}:{left_access.resource_id}:"
                                f"{right_id}:{right_access.resource_id}"
                            )
    return IndependenceResultV1(not reasons, tuple(sorted(set(reasons))))


def _event_graph_for(ir: Mapping[str, Any], entity_id: str) -> dict[str, tuple[str, ...]]:
    for entity in ir["entities"]:
        if str(entity["entity_id"]) == entity_id:
            return _graph(_direct_handlers(entity))
    raise KeyError(entity_id)


def _effect_may_precede_observation(
    effect: CapabilityOccurrenceV1,
    observation: CapabilityOccurrenceV1,
    graph: Mapping[str, tuple[str, ...]],
) -> bool:
    if effect.event_id == observation.event_id:
        if effect.instruction_index < observation.instruction_index:
            return True
        return _path_exists(graph, effect.event_id, effect.event_id)
    return _path_exists(graph, effect.event_id, observation.event_id)


def _effect_observation_interfere(effect_law, observation_law, catalog: CapabilityLawCatalogV1) -> bool:
    if _explicitly_commute(effect_law, observation_law):
        return False
    for effect_access in effect_law.accesses:
        for observation_access in observation_law.accesses:
            relation = catalog.alias_relation(effect_access.resource_id, observation_access.resource_id)
            if relation in {"same", "unknown"}:
                return True
    return False


def prove_preparability(
    ir: Mapping[str, Any],
    footprint: ReactionFootprintV1,
    catalog: CapabilityLawCatalogV1,
) -> PreparabilityResultV1:
    if not footprint.effects:
        return PreparabilityResultV1(True, "state_atomic", (), ())

    reasons: list[str] = list(_law_binding_reasons(footprint, catalog))
    hazards: list[tuple[str, str]] = []
    used = tuple(sorted(set((*footprint.observations, *footprint.effects))))
    if not catalog.complete:
        reasons.append("deployment_catalog_not_complete")
    missing = tuple(capability_id for capability_id in used if catalog.law(capability_id) is None)
    if missing:
        reasons.append("missing_capability_law:" + ",".join(missing))
    if reasons:
        return PreparabilityResultV1(False, "interleaved", tuple(reasons), ())

    graph = _event_graph_for(ir, footprint.entity_id)
    effects = [item for item in footprint.capability_occurrences if item.kind == "effect"]
    observations = [item for item in footprint.capability_occurrences if item.kind == "observation"]
    for effect in effects:
        effect_law = catalog.law(effect.capability_id)
        assert effect_law is not None
        for observation in observations:
            if not _effect_may_precede_observation(effect, observation, graph):
                continue
            observation_law = catalog.law(observation.capability_id)
            assert observation_law is not None
            if _effect_observation_interfere(effect_law, observation_law, catalog):
                hazards.append((effect.capability_id, observation.capability_id))

    if hazards:
        return PreparabilityResultV1(
            False,
            "interleaved",
            ("effect_observation_staging_hazard",),
            tuple(sorted(set(hazards))),
        )

    concrete = [catalog.law(capability_id) for capability_id in footprint.effects]
    assert all(item is not None for item in concrete)
    laws = [item for item in concrete if item is not None]
    if all(item.effect_protocol == "prepare_commit_abort" and item.commit_total_after_prepare for item in laws):
        atomicity = (
            "durable_transactional"
            if all(item.durable_recovery for item in laws)
            else "transactional"
        )
    else:
        atomicity = "state_atomic_external_partial_possible"
    return PreparabilityResultV1(True, atomicity, (), ())


__all__ = [
    "derive_reaction_footprints",
    "find_reaction_footprint",
    "reaction_resources",
    "reaction_authority_lease",
    "prove_authority_capacity",
    "prove_independence",
    "prove_preparability",
]
