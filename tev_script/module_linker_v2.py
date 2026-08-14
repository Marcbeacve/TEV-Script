from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .source_program_v2 import (
    CompiledProgramV2,
    EntrySourceV2,
    GenericFunctionSourceV2,
    SourceExprV2,
    SourceProgramV2,
    compile_parsed_program_v2,
    parse_program_v2,
    tokenize_source_v2,
)

LANGUAGE_VERSION_MODULE_V2 = "2.0.0"
MAX_MODULES_V2 = 256
MAX_MODULE_IMPORTS_V2 = 128
MAX_MODULE_GRAPH_DEPTH_V2 = 64
MAX_MODULE_SOURCE_BYTES_V2 = 2 * 1024 * 1024
MAX_MODULE_BUNDLE_BYTES_V2 = 64 * 1024 * 1024
_MODULE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ModuleImportV2:
    module_id: str
    alias: str


@dataclass(frozen=True, slots=True)
class ParsedPureModuleV2:
    module_id: str
    language_version: str
    imports: tuple[ModuleImportV2, ...]
    functions: tuple[GenericFunctionSourceV2, ...]
    exports: tuple[str, ...]
    source_sha256: str


@dataclass(frozen=True, slots=True)
class LinkedPureModuleV2:
    module_id: str
    language_version: str
    source_sha256: str
    dependency_lock_hash: str
    export_surface_hash: str
    semantic_hash: str
    functions: tuple[GenericFunctionSourceV2, ...]
    exports: tuple[tuple[str, str], ...]
    own_template_hashes: tuple[tuple[str, str], ...]
    dependency_entries: tuple[dict[str, str], ...]


@dataclass(frozen=True, slots=True)
class LinkedProgramV2:
    schema: str
    compiled: CompiledProgramV2
    base_program_semantic_hash: str
    dependency_lock_hash: str
    module_lock_hash: str
    imported_modules: tuple[dict[str, str], ...]
    link_receipt_hash: str


def parse_pure_module_v2(source: str) -> ParsedPureModuleV2:
    if not isinstance(source, str):
        _fail("TEVS_V2_MODULE_SOURCE", "module source must be text")
    tokens = list(tokenize_source_v2(source))
    if len(tokens) < 6 or tokens[0].kind != "IDENT" or tokens[0].text != "module":
        _fail("TEVS_V2_MODULE_HEADER", "pure module source must begin with 'module'")
    module_id = tokens[1].text if tokens[1].kind == "IDENT" else ""
    if _MODULE_ID.fullmatch(module_id) is None:
        _fail("TEVS_V2_MODULE_ID", f"invalid module id {module_id!r}")
    if tokens[2].kind != "IDENT" or tokens[2].text != "version" or tokens[3].kind != "STRING" or tokens[4].kind != "SEMI":
        _fail("TEVS_V2_MODULE_HEADER", "module header must be: module <id> version \"2.0.0\";")
    version = str(tokens[3].value)
    if version != LANGUAGE_VERSION_MODULE_V2:
        _fail("TEVS_V2_MODULE_VERSION", f"module linker requires version {LANGUAGE_VERSION_MODULE_V2!r}")

    imports, cursor = _parse_import_tokens(tokens, 5)
    body_start = tokens[cursor].start if tokens[cursor].kind != "EOF" else tokens[4].end
    body = source[body_start:]
    exports, body = _strip_export_markers(body)
    synthetic_id = _module_owner_id(module_id)
    anchor = _unique_anchor_name(body, module_id, "Anchor")
    entry_name = _unique_anchor_name(body, module_id, "Entry")
    transformed = (
        f'script {synthetic_id} version "{version}";\n'
        + body
        + f'\nfn {anchor}() -> Int = 0;\nentry {entry_name}: Int = {anchor}();\n'
    )
    parsed = parse_program_v2(transformed)
    functions = tuple(item for item in parsed.functions if item.name != anchor)
    if parsed.records or parsed.recursive_functions:
        _fail("TEVS_V2_MODULE_PROFILE", "module R1 permits only plain/generic pure functions")
    names = {item.name for item in functions}
    if not functions:
        _fail("TEVS_V2_MODULE_EXPORT", "module R1 requires at least one pure function")
    if not exports:
        _fail("TEVS_V2_MODULE_EXPORT", "module R1 requires at least one export")
    missing = sorted(set(exports) - names)
    if missing:
        _fail("TEVS_V2_MODULE_EXPORT", f"exports do not name pure functions: {missing}")
    return ParsedPureModuleV2(
        module_id,
        version,
        imports,
        functions,
        tuple(sorted(exports)),
        hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )


def build_module_lock_v2(module_sources: Mapping[str, str]) -> dict[str, Any]:
    linked = _link_modules(module_sources)
    modules = []
    for module_id in sorted(linked):
        item = linked[module_id]
        modules.append({
            "module_id": item.module_id,
            "language_version": item.language_version,
            "source_sha256": item.source_sha256,
            "module_semantic_hash": item.semantic_hash,
            "dependency_lock_hash": item.dependency_lock_hash,
            "export_surface_hash": item.export_surface_hash,
            "dependencies": list(item.dependency_entries),
            "exports": [
                {"symbol": symbol, "internal_name": internal, "template_hash": dict(item.own_template_hashes)[internal]}
                for symbol, internal in item.exports
            ],
        })
    payload = {"schema": "TEV_SCRIPT_MODULE_LOCK_V2_R1", "modules": modules}
    return {**payload, "lock_hash": _hash(payload)}


def build_module_bundle_v2(module_sources: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(module_sources, Mapping) or not 1 <= len(module_sources) <= MAX_MODULES_V2:
        _fail("TEVS_V2_MODULE_BUNDLE", f"module bundle requires 1..{MAX_MODULES_V2} sources")
    modules = []
    total_bytes = 0
    normalized: dict[str, str] = {}
    for module_id, source in module_sources.items():
        if not isinstance(module_id, str) or not isinstance(source, str):
            _fail("TEVS_V2_MODULE_BUNDLE", "module bundle sources must be Text->Text")
        encoded = source.encode("utf-8")
        if len(encoded) > MAX_MODULE_SOURCE_BYTES_V2:
            _fail("TEVS_V2_MODULE_BUNDLE_BUDGET", f"module {module_id!r} exceeds {MAX_MODULE_SOURCE_BYTES_V2} UTF-8 bytes")
        total_bytes += len(encoded)
        if total_bytes > MAX_MODULE_BUNDLE_BYTES_V2:
            _fail("TEVS_V2_MODULE_BUNDLE_BUDGET", f"module bundle exceeds {MAX_MODULE_BUNDLE_BYTES_V2} UTF-8 bytes")
        declared = parse_pure_module_v2(source)
        if declared.module_id != module_id:
            _fail("TEVS_V2_MODULE_ID", f"module source key {module_id!r} disagrees with declared id {declared.module_id!r}")
        normalized[module_id] = source
        modules.append({
            "module_id": module_id,
            "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "source": source,
        })
    modules.sort(key=lambda item: item["module_id"])
    lock = build_module_lock_v2(normalized)
    payload = {
        "schema": "TEV_SCRIPT_MODULE_BUNDLE_V2_R1",
        "lock": lock,
        "modules": modules,
    }
    return {**payload, "bundle_hash": _hash(payload)}


def validate_module_bundle_v2(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        _fail("TEVS_V2_MODULE_BUNDLE", "module bundle root must be an object")
    item = dict(raw)
    if set(item) != {"schema", "lock", "modules", "bundle_hash"}:
        _fail("TEVS_V2_MODULE_BUNDLE", "module bundle field set mismatch")
    if item["schema"] != "TEV_SCRIPT_MODULE_BUNDLE_V2_R1":
        _fail("TEVS_V2_MODULE_BUNDLE", "unsupported module bundle schema")
    raw_modules = item["modules"]
    if not isinstance(raw_modules, list) or not 1 <= len(raw_modules) <= MAX_MODULES_V2:
        _fail("TEVS_V2_MODULE_BUNDLE", "module bundle modules must be a bounded non-empty array")
    sources: dict[str, str] = {}
    total_bytes = 0
    previous: str | None = None
    for index, raw_module in enumerate(raw_modules):
        if not isinstance(raw_module, Mapping) or set(raw_module) != {"module_id", "source_sha256", "source"}:
            _fail("TEVS_V2_MODULE_BUNDLE", f"module bundle entry {index} field set mismatch")
        module_id = raw_module["module_id"]
        source = raw_module["source"]
        source_sha = raw_module["source_sha256"]
        if not isinstance(module_id, str) or _MODULE_ID.fullmatch(module_id) is None or not isinstance(source, str):
            _fail("TEVS_V2_MODULE_BUNDLE", f"invalid module bundle entry {index}")
        if previous is not None and module_id <= previous:
            _fail("TEVS_V2_MODULE_BUNDLE_ORDER", "module bundle entries must be strictly sorted by module id")
        previous = module_id
        encoded = source.encode("utf-8")
        if len(encoded) > MAX_MODULE_SOURCE_BYTES_V2:
            _fail("TEVS_V2_MODULE_BUNDLE_BUDGET", f"module {module_id!r} exceeds per-source budget")
        total_bytes += len(encoded)
        if total_bytes > MAX_MODULE_BUNDLE_BYTES_V2:
            _fail("TEVS_V2_MODULE_BUNDLE_BUDGET", "module bundle exceeds total source budget")
        if source_sha != hashlib.sha256(encoded).hexdigest():
            _fail("TEVS_V2_MODULE_BUNDLE_SOURCE_HASH", f"module {module_id!r} source hash mismatch")
        sources[module_id] = source
    expected_lock = build_module_lock_v2(sources)
    if item["lock"] != expected_lock:
        _fail("TEVS_V2_MODULE_BUNDLE_LOCK", "module bundle lock does not match embedded sources")
    payload = {"schema": item["schema"], "lock": expected_lock, "modules": [dict(m) for m in raw_modules]}
    if item["bundle_hash"] != _hash(payload):
        _fail("TEVS_V2_MODULE_BUNDLE_HASH", "module bundle hash mismatch")
    return {**payload, "bundle_hash": item["bundle_hash"]}


def module_sources_from_bundle_v2(raw: Mapping[str, Any]) -> dict[str, str]:
    bundle = validate_module_bundle_v2(raw)
    return {item["module_id"]: item["source"] for item in bundle["modules"]}


def compile_program_from_module_bundle_v2(source: str, bundle_raw: Mapping[str, Any]) -> LinkedProgramV2:
    bundle = validate_module_bundle_v2(bundle_raw)
    sources = {item["module_id"]: item["source"] for item in bundle["modules"]}
    linked = compile_program_with_modules_v2(source, sources, expected_lock=bundle["lock"])
    if linked.module_lock_hash != bundle["lock"]["lock_hash"]:
        _fail("TEVS_V2_MODULE_BUNDLE_LOCK", "linked program module lock hash diverged from bundle")
    return linked


def validate_module_lock_v2(lock: Mapping[str, Any], module_sources: Mapping[str, str]) -> dict[str, Any]:
    if not isinstance(lock, Mapping):
        _fail("TEVS_V2_MODULE_LOCK", "module lock must be an object")
    expected = build_module_lock_v2(module_sources)
    if dict(lock) != expected:
        _fail("TEVS_V2_MODULE_LOCK_MISMATCH", "module lock does not exactly match supplied module sources and semantics")
    return expected


def compile_program_with_modules_v2(
    source: str,
    module_sources: Mapping[str, str],
    *,
    expected_lock: Mapping[str, Any] | None = None,
) -> LinkedProgramV2:
    imports, stripped_source = _strip_program_imports(source)
    if not imports:
        _fail("TEVS_V2_MODULE_IMPORT", "module linker requires at least one import")
    linked = _link_modules(module_sources)
    lock = build_module_lock_v2(module_sources)
    if expected_lock is not None:
        validate_module_lock_v2(expected_lock, module_sources)
    parsed = parse_program_v2(stripped_source)
    if parsed.language_version != LANGUAGE_VERSION_MODULE_V2:
        _fail("TEVS_V2_MODULE_VERSION", "module-linked program must use V2 language version")

    alias_map: dict[str, LinkedPureModuleV2] = {}
    module_ids: set[str] = set()
    for imp in imports:
        if imp.alias in alias_map:
            _fail("TEVS_V2_MODULE_ALIAS", f"duplicate import alias {imp.alias!r}")
        if imp.module_id in module_ids:
            _fail("TEVS_V2_MODULE_IMPORT", f"module {imp.module_id!r} imported more than once")
        target = linked.get(imp.module_id)
        if target is None:
            _fail("TEVS_V2_MODULE_MISSING", f"imported module {imp.module_id!r} is absent from module sources")
        alias_map[imp.alias] = target
        module_ids.add(imp.module_id)

    injected: dict[str, GenericFunctionSourceV2] = {}
    imported_entries: list[dict[str, str]] = []
    for imp in imports:
        target = alias_map[imp.alias]
        for fn in target.functions:
            existing = injected.get(fn.name)
            if existing is not None and existing != fn:
                _fail("TEVS_V2_MODULE_INTERNAL_COLLISION", f"internal linked function collision {fn.name!r}")
            injected[fn.name] = fn
        imported_entries.append({
            "module_id": target.module_id,
            "module_semantic_hash": target.semantic_hash,
            "dependency_lock_hash": target.dependency_lock_hash,
            "export_surface_hash": target.export_surface_hash,
        })

    app_names = {item.name for item in parsed.functions}
    collision = sorted(app_names & set(injected))
    if collision:
        _fail("TEVS_V2_MODULE_INTERNAL_COLLISION", f"program declarations collide with linked internal symbols {collision}")
    rewritten_app = tuple(
        replace(fn, body=_rewrite_expression(fn.body, local_names=app_names, imports=alias_map))
        for fn in parsed.functions
    )
    rewritten_recursive = tuple(
        replace(fn, body=_rewrite_expression(fn.body, local_names=app_names, imports=alias_map))
        for fn in parsed.recursive_functions
    )
    rewritten_methods = tuple(
        replace(method, body=_rewrite_expression(method.body, local_names=app_names, imports=alias_map))
        for method in parsed.methods
    )
    rewritten_generic_protocol_impls = tuple(
        replace(
            impl,
            methods=tuple(
                replace(method, body=_rewrite_expression(method.body, local_names=app_names, imports=alias_map))
                for method in impl.methods
            ),
        )
        for impl in parsed.generic_protocol_impls
    )
    rewritten_entry = parsed.entry
    if parsed.entry.expression is not None:
        rewritten_entry = replace(
            parsed.entry,
            expression=_rewrite_expression(parsed.entry.expression, local_names=app_names, imports=alias_map),
        )
    linked_program = SourceProgramV2(
        program_id=parsed.program_id,
        language_version=parsed.language_version,
        records=parsed.records,
        functions=tuple(sorted((*injected.values(), *rewritten_app), key=lambda item: item.name)),
        recursive_functions=rewritten_recursive,
        entry=rewritten_entry,
        methods=rewritten_methods,
        protocols=parsed.protocols,
        associated_type_bindings=parsed.associated_type_bindings,
        generic_protocol_impls=rewritten_generic_protocol_impls,
    )
    compiled = compile_parsed_program_v2(linked_program)
    imported_entries = sorted(imported_entries, key=lambda item: item["module_id"])
    dependency_payload = {"schema": "TEV_SCRIPT_PROGRAM_MODULE_DEPENDENCY_LOCK_V2_R1", "modules": imported_entries}
    dependency_lock_hash = _hash(dependency_payload)
    semantic_payload = {
        "schema": "TEV_SCRIPT_MODULE_LINKED_PROGRAM_SEMANTIC_IDENTITY_V2_R1",
        "base_linked_program_semantic_hash": compiled.semantic_hash,
        "dependency_lock_hash": dependency_lock_hash,
        "modules": imported_entries,
    }
    linked_semantic_hash = _hash(semantic_payload)
    compiled = replace(compiled, semantic_hash=linked_semantic_hash)
    receipt_payload = {
        "schema": "TEV_SCRIPT_MODULE_LINK_RECEIPT_V2_R1",
        "program_semantic_hash": linked_semantic_hash,
        "dependency_lock_hash": dependency_lock_hash,
        "module_lock_hash": lock["lock_hash"],
        "modules": imported_entries,
    }
    return LinkedProgramV2(
        "TEV_SCRIPT_LINKED_PROGRAM_V2_R1",
        compiled,
        semantic_payload["base_linked_program_semantic_hash"],
        dependency_lock_hash,
        lock["lock_hash"],
        tuple(imported_entries),
        _hash(receipt_payload),
    )


def _link_modules(module_sources: Mapping[str, str]) -> dict[str, LinkedPureModuleV2]:
    if not isinstance(module_sources, Mapping) or not 1 <= len(module_sources) <= MAX_MODULES_V2:
        _fail("TEVS_V2_MODULE_BUDGET", f"module source map requires 1..{MAX_MODULES_V2} modules")
    parsed: dict[str, ParsedPureModuleV2] = {}
    for key, source in module_sources.items():
        if not isinstance(key, str) or not isinstance(source, str):
            _fail("TEVS_V2_MODULE_SOURCE", "module source map must be Text->Text")
        module = parse_pure_module_v2(source)
        if module.module_id != key:
            _fail("TEVS_V2_MODULE_ID", f"module source key {key!r} disagrees with declared id {module.module_id!r}")
        parsed[key] = module
    linked: dict[str, LinkedPureModuleV2] = {}
    visiting: list[str] = []

    def visit(module_id: str) -> LinkedPureModuleV2:
        if module_id in linked:
            return linked[module_id]
        if module_id in visiting:
            cycle = visiting[visiting.index(module_id):] + [module_id]
            _fail("TEVS_V2_MODULE_CYCLE", "module import cycle: " + " -> ".join(cycle))
        if len(visiting) >= MAX_MODULE_GRAPH_DEPTH_V2:
            _fail("TEVS_V2_MODULE_DEPTH", f"module graph depth exceeds {MAX_MODULE_GRAPH_DEPTH_V2}")
        module = parsed.get(module_id)
        if module is None:
            _fail("TEVS_V2_MODULE_MISSING", f"module dependency {module_id!r} is absent")
        if len(module.imports) > MAX_MODULE_IMPORTS_V2:
            _fail("TEVS_V2_MODULE_BUDGET", f"module {module_id!r} exceeds import budget")
        aliases: dict[str, LinkedPureModuleV2] = {}
        seen_modules: set[str] = set()
        visiting.append(module_id)
        for imp in module.imports:
            if imp.alias in aliases:
                _fail("TEVS_V2_MODULE_ALIAS", f"duplicate alias {imp.alias!r} in {module_id!r}")
            if imp.module_id in seen_modules:
                _fail("TEVS_V2_MODULE_IMPORT", f"module {imp.module_id!r} imported more than once by {module_id!r}")
            aliases[imp.alias] = visit(imp.module_id)
            seen_modules.add(imp.module_id)
        visiting.pop()
        linked[module_id] = _link_one_module(module, aliases)
        return linked[module_id]

    for module_id in sorted(parsed):
        visit(module_id)
    return linked


def _link_one_module(module: ParsedPureModuleV2, imports: Mapping[str, LinkedPureModuleV2]) -> LinkedPureModuleV2:
    own_names = {item.name for item in module.functions}
    own_internal = {name: _internal_symbol(module.module_id, name) for name in own_names}
    flattened: dict[str, GenericFunctionSourceV2] = {}
    for dependency in imports.values():
        for fn in dependency.functions:
            existing = flattened.get(fn.name)
            if existing is not None and existing != fn:
                _fail("TEVS_V2_MODULE_INTERNAL_COLLISION", f"transitive internal symbol collision {fn.name!r}")
            flattened[fn.name] = fn
    own_functions: list[GenericFunctionSourceV2] = []
    for fn in module.functions:
        rewritten = replace(
            fn,
            name=own_internal[fn.name],
            body=_rewrite_expression(fn.body, local_names=own_names, imports=imports, own_internal=own_internal),
        )
        if rewritten.name in flattened:
            _fail("TEVS_V2_MODULE_INTERNAL_COLLISION", f"module internal symbol collision {rewritten.name!r}")
        flattened[rewritten.name] = rewritten
        own_functions.append(rewritten)

    anchor_name = _internal_symbol(module.module_id, "Anchor")
    while anchor_name in flattened:
        anchor_name += "X"
    anchor = GenericFunctionSourceV2(anchor_name, (), (), "Int", SourceExprV2("number", "0"))
    compile_functions = tuple(sorted((*flattened.values(), anchor), key=lambda item: item.name))
    owner_id = _module_owner_id(module.module_id)
    parsed_program = SourceProgramV2(
        owner_id,
        module.language_version,
        (),
        compile_functions,
        (),
        EntrySourceV2("ModuleEntry", "Int", anchor_name, (), ()),
    )
    compiled = compile_parsed_program_v2(parsed_program)
    all_hashes = {
        qualified.rsplit(".", 1)[-1]: template_hash
        for qualified, template_hash in compiled.function_template_hashes
    }
    own_hashes = tuple(sorted((fn.name, all_hashes[fn.name]) for fn in own_functions))
    export_pairs = tuple(sorted((symbol, own_internal[symbol]) for symbol in module.exports))
    export_items = []
    by_original = {fn.name: fn for fn in module.functions}
    own_hash_map = dict(own_hashes)
    for symbol, internal in export_pairs:
        fn = by_original[symbol]
        export_items.append({
            "symbol": symbol,
            "kind": "pure_function",
            "type_parameter_count": len(fn.type_parameters),
            "parameters": [{"name": name, "type": type_text} for name, type_text in fn.parameters],
            "return_type": fn.return_type,
            "template_hash": own_hash_map[internal],
        })
    export_surface_payload = {"schema": "TEV_SCRIPT_MODULE_EXPORT_SURFACE_V2_R1", "module_id": module.module_id, "exports": export_items}
    export_surface_hash = _hash(export_surface_payload)
    dependencies = tuple(sorted(({
        "module_id": dep.module_id,
        "module_semantic_hash": dep.semantic_hash,
        "dependency_lock_hash": dep.dependency_lock_hash,
        "export_surface_hash": dep.export_surface_hash,
    } for dep in imports.values()), key=lambda item: item["module_id"]))
    dependency_payload = {"schema": "TEV_SCRIPT_MODULE_DEPENDENCY_LOCK_V2_R1", "dependencies": list(dependencies)}
    dependency_lock_hash = _hash(dependency_payload)
    semantic_payload = {
        "schema": "TEV_SCRIPT_PURE_MODULE_SEMANTIC_IDENTITY_V2_R1",
        "module_id": module.module_id,
        "language_version": module.language_version,
        "dependency_lock_hash": dependency_lock_hash,
        "export_surface_hash": export_surface_hash,
        "functions": [{"internal_name": name, "template_hash": h} for name, h in own_hashes],
    }
    return LinkedPureModuleV2(
        module.module_id,
        module.language_version,
        module.source_sha256,
        dependency_lock_hash,
        export_surface_hash,
        _hash(semantic_payload),
        tuple(sorted(flattened.values(), key=lambda item: item.name)),
        export_pairs,
        own_hashes,
        dependencies,
    )


def _rewrite_expression(
    expr: SourceExprV2,
    *,
    local_names: set[str],
    imports: Mapping[str, LinkedPureModuleV2],
    own_internal: Mapping[str, str] | None = None,
) -> SourceExprV2:
    value = expr.value
    if expr.kind == "call":
        name, type_arguments, named_fields = value
        name = str(name)
        rewritten_name = name
        if own_internal is not None and name in own_internal:
            rewritten_name = own_internal[name]
        elif "." in name:
            alias, symbol = name.split(".", 1)
            dependency = imports.get(alias)
            if dependency is not None:
                exports = dict(dependency.exports)
                target = exports.get(symbol)
                if target is None:
                    _fail("TEVS_V2_MODULE_EXPORT", f"module alias {alias!r} does not export {symbol!r}")
                rewritten_name = target
        value = (rewritten_name, type_arguments, named_fields)
    children = tuple(
        _rewrite_expression(child, local_names=local_names, imports=imports, own_internal=own_internal)
        for child in expr.children
    )
    return SourceExprV2(expr.kind, value, children)


def _strip_program_imports(source: str) -> tuple[tuple[ModuleImportV2, ...], str]:
    tokens = list(tokenize_source_v2(source))
    if len(tokens) < 6 or tokens[0].kind != "IDENT" or tokens[0].text != "script" or tokens[4].kind != "SEMI":
        _fail("TEVS_V2_MODULE_PROGRAM", "module-linked program must begin with normal script header")
    imports, cursor = _parse_import_tokens(tokens, 5)
    if not imports:
        return (), source
    start = tokens[5].start
    end = tokens[cursor - 1].end
    return imports, source[:start] + (" " * (end - start)) + source[end:]


def _parse_import_tokens(tokens: Sequence[Any], cursor: int) -> tuple[tuple[ModuleImportV2, ...], int]:
    imports: list[ModuleImportV2] = []
    while cursor < len(tokens) and tokens[cursor].kind == "IDENT" and tokens[cursor].text == "import":
        if cursor + 4 >= len(tokens):
            _fail("TEVS_V2_MODULE_IMPORT", "truncated import declaration")
        module_token, as_token, alias_token, semi = tokens[cursor + 1: cursor + 5]
        if module_token.kind != "IDENT" or _MODULE_ID.fullmatch(module_token.text) is None:
            _fail("TEVS_V2_MODULE_IMPORT", "import requires a qualified module id")
        if as_token.kind != "IDENT" or as_token.text != "as" or alias_token.kind != "IDENT" or _LOCAL.fullmatch(alias_token.text) is None or semi.kind != "SEMI":
            _fail("TEVS_V2_MODULE_IMPORT", "import syntax is: import <module.id> as <alias>;")
        if alias_token.text.startswith("__tev_"):
            _fail("TEVS_V2_MODULE_ALIAS", "module alias uses reserved compiler prefix")
        imports.append(ModuleImportV2(module_token.text, alias_token.text))
        cursor += 5
    if len(imports) > MAX_MODULE_IMPORTS_V2:
        _fail("TEVS_V2_MODULE_BUDGET", f"imports exceed {MAX_MODULE_IMPORTS_V2}")
    return tuple(imports), cursor


def _strip_export_markers(body: str) -> tuple[set[str], str]:
    tokens = list(tokenize_source_v2(body))
    exports: set[str] = set()
    spans: list[tuple[int, int]] = []
    brace_depth = 0
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.kind == "LBRACE":
            brace_depth += 1
        elif token.kind == "RBRACE":
            brace_depth -= 1
        elif brace_depth == 0 and token.kind == "IDENT" and token.text == "export":
            if index + 2 < len(tokens) and tokens[index + 1].kind == "IDENT" and tokens[index + 1].text == "fn" and tokens[index + 2].kind == "IDENT":
                name = tokens[index + 2].text
            elif index + 3 < len(tokens) and tokens[index + 1].kind == "IDENT" and tokens[index + 1].text == "generic" and tokens[index + 2].kind == "IDENT" and tokens[index + 2].text == "fn" and tokens[index + 3].kind == "IDENT":
                name = tokens[index + 3].text
            else:
                _fail("TEVS_V2_MODULE_EXPORT", "export may introduce only fn or generic fn in module R1")
            if name in exports:
                _fail("TEVS_V2_MODULE_EXPORT", f"duplicate export {name!r}")
            exports.add(name)
            spans.append((token.start, token.end))
        index += 1
    chars = list(body)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return exports, "".join(chars)


def _module_owner_id(module_id: str) -> str:
    return "Module_" + hashlib.sha256(module_id.encode("utf-8")).hexdigest()[:16]


def _internal_symbol(module_id: str, symbol: str) -> str:
    return "m_" + hashlib.sha256(module_id.encode("utf-8")).hexdigest()[:16] + "_" + symbol


def _unique_anchor_name(body: str, module_id: str, role: str) -> str:
    base = "Module" + role + hashlib.sha256(module_id.encode("utf-8")).hexdigest()[:16]
    name = base
    counter = 0
    tokens = {token.text for token in tokenize_source_v2(body) if token.kind == "IDENT"}
    while name in tokens:
        counter += 1
        name = base + str(counter)
    return name


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
