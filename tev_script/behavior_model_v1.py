from __future__ import annotations

from dataclasses import dataclass

from .ast_v1 import BehaviorDecl, EntityDecl, HandlerDecl, StateDecl, UseDecl
from .contracts_v1 import MAX_FLATTENED_BEHAVIORS_PER_ENTITY
from .diagnostics import SourceSpan, TevScriptError
from .linker_v1 import LinkPlanV1, NAMESPACE_BEHAVIOR, SymbolV1, resolve_symbol
from .semantic_types_v1 import ResolvedTypeV1, TypeEnvironmentV1, resolve_type


@dataclass(frozen=True, slots=True)
class StateSourceV1:
    component_id: str
    owner_id: str
    declaration: StateDecl
    type_ref: ResolvedTypeV1


@dataclass(frozen=True, slots=True)
class HandlerFragmentSourceV1:
    component_id: str
    owner_id: str
    declaration: HandlerDecl
    parameter_types: tuple[ResolvedTypeV1, ...]


@dataclass(frozen=True, slots=True)
class CompositeModelV1:
    composite_id: str
    kind: str
    owner_id: str
    flattened_behaviors: tuple[str, ...]
    visible_states: tuple[StateSourceV1, ...]
    handler_fragments: tuple[HandlerFragmentSourceV1, ...]
    local_handler_fragments: tuple[HandlerFragmentSourceV1, ...]

    @property
    def state_types(self) -> dict[str, ResolvedTypeV1]:
        return {item.declaration.name: item.type_ref for item in self.visible_states}


@dataclass(frozen=True, slots=True)
class BehaviorModelIndexV1:
    composites: tuple[CompositeModelV1, ...]

    def composite(self, composite_id: str) -> CompositeModelV1:
        for item in self.composites:
            if item.composite_id == composite_id:
                return item
        raise KeyError(composite_id)


def build_behavior_model(
    plan: LinkPlanV1,
    types: TypeEnvironmentV1,
) -> BehaviorModelIndexV1:
    behaviors: dict[str, SymbolV1] = {}
    for unit in plan.units:
        for symbol in unit.symbols:
            if symbol.namespace == NAMESPACE_BEHAVIOR:
                behaviors[symbol.semantic_id] = symbol

    models: list[CompositeModelV1] = []
    for behavior_id in sorted(behaviors):
        symbol = behaviors[behavior_id]
        declaration = symbol.declaration
        assert isinstance(declaration, BehaviorDecl)
        flattened = _flatten_behavior_dependencies(
            plan,
            behavior_id,
            declaration.uses,
            owner_id=symbol.owner_id,
            behaviors=behaviors,
        )
        models.append(
            _build_composite_model(
                plan,
                types,
                behavior_id,
                "behavior",
                symbol.owner_id,
                flattened,
                declaration.states,
                declaration.handlers,
                behaviors,
            )
        )

    root_owner = plan.root.program_id
    for entity in plan.root.entities:
        entity_id = f"{root_owner}.{entity.name}"
        flattened = _flatten_entity_behaviors(
            plan,
            entity,
            owner_id=root_owner,
            behaviors=behaviors,
        )
        models.append(
            _build_composite_model(
                plan,
                types,
                entity_id,
                "entity",
                root_owner,
                flattened,
                entity.states,
                entity.handlers,
                behaviors,
            )
        )

    models.sort(key=lambda item: (item.kind, item.composite_id))
    return BehaviorModelIndexV1(tuple(models))


def _flatten_behavior_dependencies(
    plan: LinkPlanV1,
    behavior_id: str,
    uses: tuple[UseDecl, ...],
    *,
    owner_id: str,
    behaviors: dict[str, SymbolV1],
) -> tuple[str, ...]:
    roots = tuple(
        (
            resolve_symbol(
                plan,
                owner_id,
                use.behavior_id,
                NAMESPACE_BEHAVIOR,
                span=use.span,
            ).semantic_id,
            use.span,
        )
        for use in uses
    )
    return _flatten_dependency_roots(
        plan,
        roots,
        behaviors=behaviors,
        initial_active=(behavior_id,),
        maximum=None,
        owner_label=f"behavior {behavior_id!r}",
    )


def _flatten_entity_behaviors(
    plan: LinkPlanV1,
    entity: EntityDecl,
    *,
    owner_id: str,
    behaviors: dict[str, SymbolV1],
) -> tuple[str, ...]:
    roots = tuple(
        (
            resolve_symbol(
                plan,
                owner_id,
                use.behavior_id,
                NAMESPACE_BEHAVIOR,
                span=use.span,
            ).semantic_id,
            use.span,
        )
        for use in entity.uses
    )
    return _flatten_dependency_roots(
        plan,
        roots,
        behaviors=behaviors,
        initial_active=(),
        maximum=MAX_FLATTENED_BEHAVIORS_PER_ENTITY,
        owner_label=f"entity {entity.name!r}",
    )


def _flatten_dependency_roots(
    plan: LinkPlanV1,
    roots: tuple[tuple[str, SourceSpan], ...],
    *,
    behaviors: dict[str, SymbolV1],
    initial_active: tuple[str, ...],
    maximum: int | None,
    owner_label: str,
) -> tuple[str, ...]:
    """Iterative dependency-first DFS preserving explicit `use` order.

    Iteration avoids coupling accepted language depth to the Python recursion
    limit. `seen` is deliberately global across all roots so diamonds and
    repeated explicit uses fail closed instead of being silently deduplicated.
    """

    result: list[str] = []
    seen: set[str] = set()
    active: list[str] = list(initial_active)
    active_set: set[str] = set(initial_active)

    for root_id, root_span in roots:
        if root_id in active_set:
            cycle = _cycle_witness(active, root_id)
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_CYCLE",
                "behavior dependency cycle: " + " -> ".join(cycle),
                root_span,
            )
        if root_id in seen:
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_DUPLICATE_INCLUSION",
                f"behavior {root_id!r} appears more than once in {owner_label}",
                root_span,
            )

        # Frame: [behavior_id, incoming_span, next_use_index, resolved_uses]
        stack: list[list[object]] = []
        _push_behavior_frame(
            plan,
            stack,
            active,
            active_set,
            root_id,
            root_span,
            behaviors,
        )

        while stack:
            frame = stack[-1]
            behavior_id = str(frame[0])
            incoming_span = frame[1]
            next_index = int(frame[2])
            resolved_uses = frame[3]
            assert isinstance(incoming_span, SourceSpan)
            assert isinstance(resolved_uses, tuple)

            if next_index < len(resolved_uses):
                dependency_id, dependency_span = resolved_uses[next_index]
                frame[2] = next_index + 1
                if dependency_id in active_set:
                    cycle = _cycle_witness(active, dependency_id)
                    raise TevScriptError(
                        "TEVS_V1_BEHAVIOR_CYCLE",
                        "behavior dependency cycle: " + " -> ".join(cycle),
                        dependency_span,
                    )
                if dependency_id in seen:
                    raise TevScriptError(
                        "TEVS_V1_BEHAVIOR_DUPLICATE_INCLUSION",
                        f"behavior {dependency_id!r} appears more than once in {owner_label}",
                        dependency_span,
                    )
                _push_behavior_frame(
                    plan,
                    stack,
                    active,
                    active_set,
                    dependency_id,
                    dependency_span,
                    behaviors,
                )
                continue

            stack.pop()
            popped = active.pop()
            active_set.remove(popped)
            assert popped == behavior_id
            if behavior_id in seen:
                raise AssertionError("behavior closure duplicated after DFS completion")
            seen.add(behavior_id)
            result.append(behavior_id)
            if maximum is not None and len(result) > maximum:
                raise TevScriptError(
                    "TEVS_V1_BEHAVIOR_FLATTENED_BUDGET",
                    f"flattened behavior count exceeds {maximum} in {owner_label}",
                    incoming_span,
                )

    return tuple(result)


def _push_behavior_frame(
    plan: LinkPlanV1,
    stack: list[list[object]],
    active: list[str],
    active_set: set[str],
    behavior_id: str,
    incoming_span: SourceSpan,
    behaviors: dict[str, SymbolV1],
) -> None:
    symbol = behaviors.get(behavior_id)
    if symbol is None or not isinstance(symbol.declaration, BehaviorDecl):
        raise TevScriptError(
            "TEVS_V1_BEHAVIOR_SYMBOL",
            f"resolved behavior {behavior_id!r} has no behavior declaration",
            incoming_span,
        )
    declaration = symbol.declaration
    resolved_uses = tuple(
        (
            resolve_symbol(
                plan,
                symbol.owner_id,
                use.behavior_id,
                NAMESPACE_BEHAVIOR,
                span=use.span,
            ).semantic_id,
            use.span,
        )
        for use in declaration.uses
    )
    active.append(behavior_id)
    active_set.add(behavior_id)
    stack.append([behavior_id, incoming_span, 0, resolved_uses])


def _cycle_witness(active: list[str], target_id: str) -> list[str]:
    start = active.index(target_id) if target_id in active else 0
    return [*active[start:], target_id]


def _build_composite_model(
    plan: LinkPlanV1,
    types: TypeEnvironmentV1,
    composite_id: str,
    kind: str,
    owner_id: str,
    flattened_behaviors: tuple[str, ...],
    local_states: tuple[StateDecl, ...],
    local_handlers: tuple[HandlerDecl, ...],
    behaviors: dict[str, SymbolV1],
) -> CompositeModelV1:
    states: list[StateSourceV1] = []
    state_names: dict[str, StateSourceV1] = {}
    fragments: list[HandlerFragmentSourceV1] = []

    for behavior_id in flattened_behaviors:
        symbol = behaviors[behavior_id]
        declaration = symbol.declaration
        assert isinstance(declaration, BehaviorDecl)
        for state in declaration.states:
            resolved = resolve_type(plan, symbol.owner_id, state.type_ref)
            source = StateSourceV1(behavior_id, symbol.owner_id, state, resolved)
            _add_state(state_names, states, source, composite_id)
        for handler in declaration.handlers:
            fragments.append(
                _handler_fragment(plan, symbol.owner_id, behavior_id, handler)
            )

    local_component_id = composite_id
    for state in local_states:
        resolved = resolve_type(plan, owner_id, state.type_ref)
        source = StateSourceV1(local_component_id, owner_id, state, resolved)
        _add_state(state_names, states, source, composite_id)

    local_fragments = tuple(
        _handler_fragment(plan, owner_id, local_component_id, handler)
        for handler in local_handlers
    )
    fragments.extend(local_fragments)
    _validate_fragment_signatures(fragments, composite_id)

    return CompositeModelV1(
        composite_id,
        kind,
        owner_id,
        flattened_behaviors,
        tuple(states),
        tuple(fragments),
        local_fragments,
    )


def _add_state(
    state_names: dict[str, StateSourceV1],
    states: list[StateSourceV1],
    source: StateSourceV1,
    composite_id: str,
) -> None:
    name = source.declaration.name
    previous = state_names.get(name)
    if previous is not None:
        if previous.component_id == source.component_id:
            raise TevScriptError(
                "TEVS_V1_TYPE_STATE_DUPLICATE",
                f"duplicate state {name!r} in {source.component_id}",
                source.declaration.span,
            )
        raise TevScriptError(
            "TEVS_V1_BEHAVIOR_STATE_CONFLICT",
            f"state {name!r} conflicts in {composite_id}: {previous.component_id} vs {source.component_id}",
            source.declaration.span,
        )
    state_names[name] = source
    states.append(source)


def _handler_fragment(
    plan: LinkPlanV1,
    owner_id: str,
    component_id: str,
    handler: HandlerDecl,
) -> HandlerFragmentSourceV1:
    return HandlerFragmentSourceV1(
        component_id,
        owner_id,
        handler,
        tuple(resolve_type(plan, owner_id, parameter.type_ref) for parameter in handler.parameters),
    )


def _validate_fragment_signatures(
    fragments: list[HandlerFragmentSourceV1],
    composite_id: str,
) -> None:
    signatures: dict[str, tuple[str, ...]] = {}
    for fragment in fragments:
        signature = tuple(item.type_id for item in fragment.parameter_types)
        previous = signatures.get(fragment.declaration.event_id)
        if previous is not None and previous != signature:
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_HANDLER_SIGNATURE_CONFLICT",
                f"event {fragment.declaration.event_id!r} has conflicting handler signatures in {composite_id}: {previous} vs {signature}",
                fragment.declaration.span,
            )
        signatures[fragment.declaration.event_id] = signature
