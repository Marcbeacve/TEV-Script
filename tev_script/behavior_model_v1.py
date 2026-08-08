from __future__ import annotations

from dataclasses import dataclass

from .ast_v1 import BehaviorDecl, EntityDecl, HandlerDecl, StateDecl
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
        flattened = _flatten_behavior_closure(
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


def _flatten_behavior_closure(
    plan: LinkPlanV1,
    behavior_id: str,
    uses,
    *,
    owner_id: str,
    behaviors: dict[str, SymbolV1],
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    active: list[str] = []

    def expand(target_id: str, span: SourceSpan) -> None:
        if target_id in active:
            start = active.index(target_id)
            cycle = [*active[start:], target_id]
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_CYCLE",
                "behavior dependency cycle: " + " -> ".join(cycle),
                span,
            )
        if target_id in seen:
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_DUPLICATE_INCLUSION",
                f"behavior {target_id!r} appears more than once in one composition closure",
                span,
            )
        symbol = behaviors[target_id]
        declaration = symbol.declaration
        assert isinstance(declaration, BehaviorDecl)
        active.append(target_id)
        for use in declaration.uses:
            dependency = resolve_symbol(
                plan,
                symbol.owner_id,
                use.behavior_id,
                NAMESPACE_BEHAVIOR,
                span=use.span,
            )
            expand(dependency.semantic_id, use.span)
        active.pop()
        seen.add(target_id)
        result.append(target_id)

    # A behavior model contains its dependency closure followed by itself.
    active.append(behavior_id)
    for use in uses:
        dependency = resolve_symbol(
            plan,
            owner_id,
            use.behavior_id,
            NAMESPACE_BEHAVIOR,
            span=use.span,
        )
        expand(dependency.semantic_id, use.span)
    active.pop()
    result.append(behavior_id)
    return tuple(result)


def _flatten_entity_behaviors(
    plan: LinkPlanV1,
    entity: EntityDecl,
    *,
    owner_id: str,
    behaviors: dict[str, SymbolV1],
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    active: list[str] = []

    def expand(target_id: str, span: SourceSpan) -> None:
        if target_id in active:
            start = active.index(target_id)
            cycle = [*active[start:], target_id]
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_CYCLE",
                "behavior dependency cycle: " + " -> ".join(cycle),
                span,
            )
        if target_id in seen:
            raise TevScriptError(
                "TEVS_V1_BEHAVIOR_DUPLICATE_INCLUSION",
                f"behavior {target_id!r} appears more than once in entity {entity.name!r}",
                span,
            )
        symbol = behaviors[target_id]
        declaration = symbol.declaration
        assert isinstance(declaration, BehaviorDecl)
        active.append(target_id)
        for use in declaration.uses:
            dependency = resolve_symbol(
                plan,
                symbol.owner_id,
                use.behavior_id,
                NAMESPACE_BEHAVIOR,
                span=use.span,
            )
            expand(dependency.semantic_id, use.span)
        active.pop()
        seen.add(target_id)
        result.append(target_id)

    for use in entity.uses:
        dependency = resolve_symbol(
            plan,
            owner_id,
            use.behavior_id,
            NAMESPACE_BEHAVIOR,
            span=use.span,
        )
        expand(dependency.semantic_id, use.span)
    return tuple(result)


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
