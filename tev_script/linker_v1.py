from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable, Mapping
from typing import Any

from .ast_v1 import (
    BehaviorDecl,
    CapabilityDecl,
    EntityDecl,
    EnumDecl,
    FunctionDecl,
    ModuleUnit,
    RecordDecl,
    ScriptUnit,
    SourceFile,
    TypeRef,
)
from .canonical import canonical_hash, canonical_json
from .contracts_v1 import (
    MAX_LINKED_TOP_DECLARATIONS,
    MAX_PURE_FUNCTIONS,
    MAX_REACHABLE_MODULES,
    MAX_REACHABLE_SOURCE_BYTES,
    V1_LANGUAGE_VERSION,
)
from .diagnostics import SourceSpan, TevScriptError
from .frontend_v1 import parse_v1_bytes
from .types import CAPABILITIES, PURE_FUNCTIONS, SUPPORTED_TYPES

NAMESPACE_TYPE = "type"
NAMESPACE_FUNCTION = "function"
NAMESPACE_BEHAVIOR = "behavior"
NAMESPACE_CAPABILITY = "capability"
NAMESPACE_ENTITY = "entity"
NAMESPACES = frozenset(
    {
        NAMESPACE_TYPE,
        NAMESPACE_FUNCTION,
        NAMESPACE_BEHAVIOR,
        NAMESPACE_CAPABILITY,
        NAMESPACE_ENTITY,
    }
)

_PREDECLARED_TYPE_IDS = frozenset((*SUPPORTED_TYPES, "Option", "Result"))


@dataclass(frozen=True, slots=True)
class SourceInputV1:
    path: str
    data: bytes


@dataclass(frozen=True, slots=True)
class SymbolV1:
    namespace: str
    local_name: str
    semantic_id: str
    owner_id: str
    exported: bool
    declaration: object | None
    origin: str = "source"

    def semantic_surface(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "local_name": self.local_name,
            "semantic_id": self.semantic_id,
            "exported": self.exported,
        }


@dataclass(frozen=True, slots=True)
class UnitIndexV1:
    unit_id: str
    kind: str
    imports: tuple[str, ...]
    symbols: tuple[SymbolV1, ...]
    declaration: SourceFile

    def symbols_in(self, namespace: str) -> tuple[SymbolV1, ...]:
        return tuple(item for item in self.symbols if item.namespace == namespace)

    def semantic_surface(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "kind": self.kind,
            "imports": list(self.imports),
            "symbols": [item.semantic_surface() for item in self.symbols],
        }


@dataclass(frozen=True, slots=True)
class LinkPlanV1:
    root: ScriptUnit
    modules: tuple[ModuleUnit, ...]
    units: tuple[UnitIndexV1, ...]
    module_topological_order: tuple[str, ...]
    reachable_source_bytes: int

    @property
    def program_id(self) -> str:
        return self.root.program_id

    @property
    def root_unit_id(self) -> str:
        return self.root.program_id

    def unit(self, unit_id: str) -> UnitIndexV1:
        for unit in self.units:
            if unit.unit_id == unit_id:
                return unit
        raise TevScriptError(
            "TEVS_V1_LINK_UNIT_UNKNOWN",
            f"unit {unit_id!r} is not in the reachable linked program",
        )

    def semantic_index(self) -> dict[str, Any]:
        # This is deliberately a name/link index, not the final linked-program
        # semantic object. Function bodies, handler bodies and values are added
        # by later semantic phases before TEV_SCRIPT_LINKED_PROGRAM_V1 hashing.
        return {
            "schema": "TEV_SCRIPT_LINK_INDEX_V1",
            "language_version": V1_LANGUAGE_VERSION,
            "program_id": self.root.program_id,
            "module_topological_order": list(self.module_topological_order),
            "units": [unit.semantic_surface() for unit in self.units],
        }

    @property
    def index_hash(self) -> str:
        return canonical_hash(self.semantic_index())

    @property
    def canonical_index_json(self) -> str:
        return canonical_json(self.semantic_index())


@dataclass(frozen=True, slots=True)
class _ParsedInput:
    source: SourceInputV1
    declaration: SourceFile


_BUILTINS: dict[str, tuple[SymbolV1, ...]] = {
    NAMESPACE_TYPE: tuple(
        SymbolV1(NAMESPACE_TYPE, name, name, "<builtin>", True, None, "builtin")
        for name in sorted(_PREDECLARED_TYPE_IDS)
    ),
    NAMESPACE_FUNCTION: tuple(
        SymbolV1(NAMESPACE_FUNCTION, name, name, "<builtin>", True, None, "builtin")
        for name in sorted(PURE_FUNCTIONS)
    ),
    NAMESPACE_CAPABILITY: tuple(
        SymbolV1(
            NAMESPACE_CAPABILITY,
            capability_id.rsplit(".", 1)[-1],
            capability_id,
            "<builtin>",
            True,
            None,
            "builtin",
        )
        for capability_id in sorted(CAPABILITIES)
    ),
    NAMESPACE_BEHAVIOR: (),
    NAMESPACE_ENTITY: (),
}


def link_v1_sources(sources: Iterable[SourceInputV1]) -> LinkPlanV1:
    parsed = tuple(_parse_inputs(sources))
    roots = [item for item in parsed if isinstance(item.declaration, ScriptUnit)]
    if not roots:
        raise TevScriptError("TEVS_V1_LINK_ROOT_MISSING", "exactly one script root is required")
    if len(roots) != 1:
        details = sorted(item.declaration.program_id for item in roots)
        raise TevScriptError(
            "TEVS_V1_LINK_ROOT_MULTIPLE",
            f"exactly one script root is required, got {details}",
            roots[0].declaration.span,
        )
    root_input = roots[0]
    root = root_input.declaration
    assert isinstance(root, ScriptUnit)

    module_inputs: dict[str, _ParsedInput] = {}
    for item in parsed:
        declaration = item.declaration
        if not isinstance(declaration, ModuleUnit):
            continue
        previous = module_inputs.get(declaration.module_id)
        if previous is not None:
            raise TevScriptError(
                "TEVS_V1_LINK_MODULE_DUPLICATE",
                f"duplicate module id {declaration.module_id!r}",
                declaration.span,
            )
        module_inputs[declaration.module_id] = item

    if root.program_id in module_inputs:
        raise TevScriptError(
            "TEVS_V1_LINK_ROOT_MODULE_ID_COLLISION",
            f"program id {root.program_id!r} collides with a module id",
            root.span,
        )

    _validate_duplicate_imports(root)

    order = _reachable_topological_order(root, module_inputs)
    if len(order) > MAX_REACHABLE_MODULES:
        raise TevScriptError(
            "TEVS_V1_LINK_MODULE_BUDGET",
            f"reachable module count exceeds {MAX_REACHABLE_MODULES}: got {len(order)}",
            root.span,
        )

    reachable_module_inputs = tuple(module_inputs[module_id] for module_id in order)
    reachable_bytes = len(root_input.source.data) + sum(
        len(item.source.data) for item in reachable_module_inputs
    )
    if reachable_bytes > MAX_REACHABLE_SOURCE_BYTES:
        raise TevScriptError(
            "TEVS_V1_LINK_SOURCE_BUDGET",
            f"reachable source closure exceeds {MAX_REACHABLE_SOURCE_BYTES} bytes: got {reachable_bytes}",
            root.span,
        )

    linked_declarations = len(root.declarations) + sum(
        len(item.declaration.declarations) for item in reachable_module_inputs
    )
    if linked_declarations > MAX_LINKED_TOP_DECLARATIONS:
        raise TevScriptError(
            "TEVS_V1_LINK_DECLARATION_BUDGET",
            f"linked top-level declarations exceed {MAX_LINKED_TOP_DECLARATIONS}: got {linked_declarations}",
            root.span,
        )

    pure_functions = sum(
        isinstance(declaration, FunctionDecl)
        for declaration in root.declarations
    ) + sum(
        isinstance(declaration, FunctionDecl)
        for item in reachable_module_inputs
        for declaration in item.declaration.declarations
    )
    if pure_functions > MAX_PURE_FUNCTIONS:
        raise TevScriptError(
            "TEVS_V1_LINK_FUNCTION_BUDGET",
            f"pure function declarations exceed {MAX_PURE_FUNCTIONS}: got {pure_functions}",
            root.span,
        )

    modules_sorted = tuple(
        module_inputs[module_id].declaration for module_id in sorted(order)
    )
    root_index = _index_unit(root)
    module_indexes = tuple(_index_unit(module) for module in modules_sorted)
    plan = LinkPlanV1(
        root=root,
        modules=modules_sorted,
        units=(root_index, *module_indexes),
        module_topological_order=tuple(order),
        reachable_source_bytes=reachable_bytes,
    )
    # Resolve every reference whose grammar determines a unique semantic
    # namespace. Contextual value/call resolution belongs to static semantics.
    from .link_validation_v1 import validate_v1_link_names

    validate_v1_link_names(plan)
    return plan


def link_v1_mapping(sources: Mapping[str, bytes]) -> LinkPlanV1:
    return link_v1_sources(SourceInputV1(path, data) for path, data in sources.items())


def resolve_symbol(
    plan: LinkPlanV1,
    from_unit_id: str,
    reference: str,
    namespace: str,
    *,
    span: SourceSpan | None = None,
) -> SymbolV1:
    if namespace not in NAMESPACES:
        raise ValueError(f"unknown TEV Script namespace {namespace!r}")
    unit = plan.unit(from_unit_id)
    local = unit.symbols_in(namespace)
    direct_import_ids = unit.imports
    direct_units = [plan.unit(module_id) for module_id in direct_import_ids]

    # 1. Exact current-unit semantic id always remains locally addressable.
    exact_local = [item for item in local if item.semantic_id == reference]
    if len(exact_local) == 1:
        return exact_local[0]
    if len(exact_local) > 1:
        _ambiguous(reference, namespace, exact_local, span)

    # Capability ids are global semantic ids and are not derived from module ids.
    # Therefore an exact visible capability id is resolved before interpreting
    # dotted text as a module-qualified symbol reference.
    if namespace == NAMESPACE_CAPABILITY:
        builtin_exact = [item for item in _BUILTINS[namespace] if item.semantic_id == reference]
        if len(builtin_exact) == 1:
            return builtin_exact[0]

        all_exact_imported = [
            item
            for imported in direct_units
            for item in imported.symbols_in(namespace)
            if item.semantic_id == reference
        ]
        exported_exact = [item for item in all_exact_imported if item.exported]
        exported_exact = _dedupe_visible_candidates(plan, exported_exact, span)
        if len(exported_exact) == 1:
            return exported_exact[0]
        if len(exported_exact) > 1:
            _ambiguous(reference, namespace, exported_exact, span)
        if all_exact_imported:
            owners = sorted({item.owner_id for item in all_exact_imported})
            raise TevScriptError(
                "TEVS_V1_LINK_PRIVATE_SYMBOL",
                f"capability {reference!r} is private in directly imported module(s) {owners}",
                span,
            )

    # 2. For module-owned namespaces, a qualified reference chooses the longest
    # directly imported module prefix. Capability ids deliberately skip this.
    if namespace != NAMESPACE_CAPABILITY:
        matching_prefixes = [
            module_id
            for module_id in direct_import_ids
            if reference.startswith(module_id + ".")
        ]
        if matching_prefixes:
            target_id = max(
                matching_prefixes,
                key=lambda item: (item.count("."), len(item), item),
            )
            target = plan.unit(target_id)
            all_exact = [
                item
                for item in target.symbols_in(namespace)
                if item.semantic_id == reference
            ]
            if all_exact:
                exported = [item for item in all_exact if item.exported]
                if len(exported) == 1:
                    return exported[0]
                if len(exported) > 1:
                    _ambiguous(reference, namespace, exported, span)
                raise TevScriptError(
                    "TEVS_V1_LINK_PRIVATE_SYMBOL",
                    f"{namespace} {reference!r} is private in directly imported module {target_id!r}",
                    span,
                )
            raise TevScriptError(
                "TEVS_V1_LINK_NAME_UNKNOWN",
                f"unknown exported {namespace} {reference!r} in directly imported module {target_id!r}",
                span,
            )

    # 3. Unqualified local declarations precede ambient/imported leaf names.
    if "." not in reference:
        short_local = [item for item in local if item.local_name == reference]
        if len(short_local) == 1:
            return short_local[0]
        if len(short_local) > 1:
            _ambiguous(reference, namespace, short_local, span)

    # 4. Predeclared type/function names are unqualified. Qualified portable
    # capabilities require their full id (for example time.delta).
    builtin = [
        item
        for item in _BUILTINS[namespace]
        if item.semantic_id == reference
        or (
            namespace != NAMESPACE_CAPABILITY
            and "." not in reference
            and item.local_name == reference
        )
    ]
    if len(builtin) == 1:
        return builtin[0]

    # 5. Exact exported semantic id from any directly imported module. For
    # capability ids this has already been attempted above, but keeping the
    # generic path is harmless and keeps the namespace algorithm explicit.
    exact_imported = [
        item
        for imported in direct_units
        for item in imported.symbols_in(namespace)
        if item.exported and item.semantic_id == reference
    ]
    exact_imported = _dedupe_visible_candidates(plan, exact_imported, span)
    if len(exact_imported) == 1:
        return exact_imported[0]
    if len(exact_imported) > 1:
        _ambiguous(reference, namespace, exact_imported, span)

    # 6. Unique exported leaf-name fallback across direct imports only.
    leaf = reference.rsplit(".", 1)[-1]
    candidates = [
        item
        for imported in direct_units
        for item in imported.symbols_in(namespace)
        if item.exported and item.local_name == leaf
    ]
    candidates = _dedupe_visible_candidates(plan, candidates, span)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        _ambiguous(reference, namespace, candidates, span)
    raise TevScriptError(
        "TEVS_V1_LINK_NAME_UNKNOWN",
        f"unknown visible {namespace} {reference!r} from unit {from_unit_id!r}",
        span,
    )


def canonical_type_id(
    plan: LinkPlanV1,
    from_unit_id: str,
    type_ref: TypeRef,
) -> str:
    if type_ref.kind == "named":
        assert type_ref.name is not None
        return resolve_symbol(
            plan,
            from_unit_id,
            type_ref.name,
            NAMESPACE_TYPE,
            span=type_ref.span,
        ).semantic_id
    if type_ref.kind == "option":
        return f"Option<{canonical_type_id(plan, from_unit_id, type_ref.arguments[0])}>"
    if type_ref.kind == "result":
        ok = canonical_type_id(plan, from_unit_id, type_ref.arguments[0])
        err = canonical_type_id(plan, from_unit_id, type_ref.arguments[1])
        return f"Result<{ok},{err}>"
    raise TevScriptError(
        "TEVS_V1_LINK_TYPE_KIND",
        f"unsupported type reference kind {type_ref.kind!r}",
        type_ref.span,
    )


def _parse_inputs(sources: Iterable[SourceInputV1]) -> Iterable[_ParsedInput]:
    for source in sources:
        declaration = parse_v1_bytes(source.path, source.data)
        yield _ParsedInput(source, declaration)


def _validate_duplicate_imports(unit: SourceFile) -> None:
    seen: set[str] = set()
    for import_decl in unit.imports:
        if import_decl.module_id in seen:
            raise TevScriptError(
                "TEVS_V1_LINK_IMPORT_DUPLICATE",
                f"duplicate import {import_decl.module_id!r}",
                import_decl.span,
            )
        seen.add(import_decl.module_id)


def _reachable_topological_order(
    root: ScriptUnit,
    modules: Mapping[str, _ParsedInput],
) -> list[str]:
    state: dict[str, int] = {}
    stack: list[str] = []
    order: list[str] = []
    discovered = 0

    def visit(module_id: str, span: SourceSpan) -> None:
        nonlocal discovered
        item = modules.get(module_id)
        if item is None:
            raise TevScriptError(
                "TEVS_V1_LINK_IMPORT_MISSING",
                f"missing imported module {module_id!r}",
                span,
            )
        mark = state.get(module_id, 0)
        if mark == 2:
            return
        if mark == 1:
            try:
                start = stack.index(module_id)
            except ValueError:
                start = 0
            cycle = [*stack[start:], module_id]
            raise TevScriptError(
                "TEVS_V1_LINK_IMPORT_CYCLE",
                "import cycle: " + " -> ".join(cycle),
                span,
            )
        if discovered >= MAX_REACHABLE_MODULES:
            raise TevScriptError(
                "TEVS_V1_LINK_MODULE_BUDGET",
                f"reachable module count exceeds {MAX_REACHABLE_MODULES}",
                span,
            )
        discovered += 1
        state[module_id] = 1
        stack.append(module_id)
        module = item.declaration
        assert isinstance(module, ModuleUnit)
        _validate_duplicate_imports(module)
        for import_decl in sorted(module.imports, key=lambda value: value.module_id):
            visit(import_decl.module_id, import_decl.span)
        stack.pop()
        state[module_id] = 2
        order.append(module_id)

    for import_decl in sorted(root.imports, key=lambda value: value.module_id):
        visit(import_decl.module_id, import_decl.span)
    return order


def _index_unit(unit: ScriptUnit | ModuleUnit) -> UnitIndexV1:
    if isinstance(unit, ScriptUnit):
        unit_id = unit.program_id
        kind = "script"
    else:
        unit_id = unit.module_id
        kind = "module"

    symbols: list[SymbolV1] = []
    local_keys: set[tuple[str, str]] = set()
    exact_capability_ids: set[str] = set()

    for declaration in unit.declarations:
        symbol = _symbol_for_declaration(unit_id, declaration)
        key = (symbol.namespace, symbol.local_name)
        if symbol.namespace != NAMESPACE_CAPABILITY and key in local_keys:
            raise TevScriptError(
                "TEVS_V1_LINK_SYMBOL_DUPLICATE",
                f"duplicate {symbol.namespace} name {symbol.local_name!r} in unit {unit_id!r}",
                declaration.span,
            )
        if symbol.namespace == NAMESPACE_CAPABILITY:
            if symbol.semantic_id in exact_capability_ids:
                raise TevScriptError(
                    "TEVS_V1_LINK_SYMBOL_DUPLICATE",
                    f"duplicate capability id {symbol.semantic_id!r} in unit {unit_id!r}",
                    declaration.span,
                )
            exact_capability_ids.add(symbol.semantic_id)
        local_keys.add(key)
        _reject_predeclared_collision(symbol, declaration.span)
        symbols.append(symbol)

    if isinstance(unit, ScriptUnit):
        for entity in unit.entities:
            key = (NAMESPACE_ENTITY, entity.name)
            if key in local_keys:
                raise TevScriptError(
                    "TEVS_V1_LINK_SYMBOL_DUPLICATE",
                    f"duplicate entity name {entity.name!r} in root {unit_id!r}",
                    entity.span,
                )
            local_keys.add(key)
            symbols.append(
                SymbolV1(
                    NAMESPACE_ENTITY,
                    entity.name,
                    f"{unit_id}.{entity.name}",
                    unit_id,
                    False,
                    entity,
                )
            )

    symbols.sort(key=lambda item: (item.namespace, item.semantic_id, item.local_name))
    return UnitIndexV1(
        unit_id=unit_id,
        kind=kind,
        imports=tuple(sorted(item.module_id for item in unit.imports)),
        symbols=tuple(symbols),
        declaration=unit,
    )


def _symbol_for_declaration(unit_id: str, declaration: object) -> SymbolV1:
    exported = bool(getattr(declaration, "exported", False))
    if isinstance(declaration, (RecordDecl, EnumDecl)):
        return SymbolV1(
            NAMESPACE_TYPE,
            declaration.name,
            f"{unit_id}.{declaration.name}",
            unit_id,
            exported,
            declaration,
        )
    if isinstance(declaration, FunctionDecl):
        return SymbolV1(
            NAMESPACE_FUNCTION,
            declaration.name,
            f"{unit_id}.{declaration.name}",
            unit_id,
            exported,
            declaration,
        )
    if isinstance(declaration, BehaviorDecl):
        return SymbolV1(
            NAMESPACE_BEHAVIOR,
            declaration.name,
            f"{unit_id}.{declaration.name}",
            unit_id,
            exported,
            declaration,
        )
    if isinstance(declaration, CapabilityDecl):
        return SymbolV1(
            NAMESPACE_CAPABILITY,
            declaration.capability_id.rsplit(".", 1)[-1],
            declaration.capability_id,
            unit_id,
            exported,
            declaration,
        )
    raise TypeError(f"unsupported V1 top declaration {type(declaration).__name__}")


def _reject_predeclared_collision(symbol: SymbolV1, span: SourceSpan) -> None:
    if symbol.namespace == NAMESPACE_TYPE and symbol.local_name in _PREDECLARED_TYPE_IDS:
        raise TevScriptError(
            "TEVS_V1_LINK_PREDECLARED_COLLISION",
            f"type name {symbol.local_name!r} collides with a predeclared type",
            span,
        )
    if symbol.namespace == NAMESPACE_FUNCTION and symbol.local_name in PURE_FUNCTIONS:
        raise TevScriptError(
            "TEVS_V1_LINK_PREDECLARED_COLLISION",
            f"function name {symbol.local_name!r} collides with a predeclared pure function",
            span,
        )
    if symbol.namespace == NAMESPACE_CAPABILITY and symbol.semantic_id in CAPABILITIES:
        raise TevScriptError(
            "TEVS_V1_LINK_PREDECLARED_COLLISION",
            f"capability id {symbol.semantic_id!r} collides with a predeclared capability",
            span,
        )


def _ambiguous(
    reference: str,
    namespace: str,
    candidates: list[SymbolV1],
    span: SourceSpan | None,
) -> None:
    ids = sorted({item.semantic_id for item in candidates})
    raise TevScriptError(
        "TEVS_V1_LINK_NAME_AMBIGUOUS",
        f"ambiguous {namespace} {reference!r}; candidates={ids}",
        span,
    )


def _dedupe_visible_candidates(
    plan: LinkPlanV1,
    candidates: list[SymbolV1],
    span: SourceSpan | None,
) -> list[SymbolV1]:
    if not candidates:
        return []
    if all(item.namespace == NAMESPACE_CAPABILITY for item in candidates):
        grouped: dict[str, list[SymbolV1]] = {}
        for item in candidates:
            grouped.setdefault(item.semantic_id, []).append(item)
        collapsed: list[SymbolV1] = []
        for capability_id, group in grouped.items():
            signatures = {_capability_contract_key(plan, item) for item in group}
            if len(signatures) != 1:
                raise TevScriptError(
                    "TEVS_V1_LINK_CAPABILITY_CONFLICT",
                    f"conflicting declarations for capability {capability_id!r}",
                    span,
                )
            collapsed.append(min(group, key=lambda item: item.owner_id))
        return sorted(collapsed, key=lambda item: (item.semantic_id, item.owner_id))

    by_key: dict[tuple[str, str, str], SymbolV1] = {}
    for item in candidates:
        by_key[(item.namespace, item.semantic_id, item.owner_id)] = item
    return list(by_key.values())


def _capability_contract_key(plan: LinkPlanV1, symbol: SymbolV1) -> tuple[tuple[str, ...], str, str]:
    declaration = symbol.declaration
    if not isinstance(declaration, CapabilityDecl):
        raise TypeError("source capability symbol lacks CapabilityDecl")
    parameters = tuple(
        canonical_type_id(plan, symbol.owner_id, type_ref)
        for type_ref in declaration.parameter_types
    )
    return_type = canonical_type_id(plan, symbol.owner_id, declaration.return_type)
    return parameters, return_type, declaration.capability_kind
