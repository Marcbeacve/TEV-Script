from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping


RECEIPT_SCHEMA = "TEV_SCRIPT_DOCUMENTATION_VALIDATION_RECEIPT_V1"
CHECK_ORDER = (
    "VERSION_IDENTITY",
    "MANUAL_ROOT",
    "COVERAGE_MANIFEST",
    "INTERNAL_PATHS",
    "SOURCE_BINDINGS",
    "EXAMPLE_CASES",
    "DIAGNOSTIC_COVERAGE",
    "PUBLIC_SURFACE_COVERAGE",
    "HISTORICAL_CLASSIFICATION",
)
REQUIRED_DOMAINS = (
    "language_constructs",
    "cli_surface",
    "python_api",
    "source_profiles",
    "ir_runtime_profiles",
    "diagnostics",
    "integrations",
    "version_domains",
)
_EXPECTED_IDENTITY = {
    "package_version": "3.1.2",
    "language_version": "3.1.0",
    "profile": "total_core",
    "published_predecessor": "3.1.1",
}
_DIAG_RE = re.compile(r"TEVS_V31_[A-Z0-9_]+")
_SOURCE_DIRECTIVE_RE = re.compile(r"<!--\s*tevdoc-source:\s*([^>]+?)\s*-->")
_FENCE_RE = re.compile(r"```tevs\n(.*?)```", re.DOTALL)
_COVERAGE_PATH = Path("docs/manual/DOCUMENTATION_COVERAGE_V1.json")
_DIAGNOSTIC_SHARD = Path("docs/manual/DIAGNOSTIC_COVERAGE_V31.json")

FINAL_LANGUAGE_CONSTRUCTS = frozenset({
    "apply", "authority", "branch_fact", "capabilities", "comments", "composition",
    "continuations", "declarations", "effects", "entry", "events", "exact_values",
    "expressions", "field", "functions", "halt", "identifiers", "invoke_v4", "jump",
    "label", "literals", "modules", "operators", "process", "proof_admission",
    "quantum_steps", "recursion_bounds", "semantic_process", "source_to_ir", "state",
    "transformation", "types", "unit",
})
FINAL_SOURCE_PROFILES = frozenset({
    "2.0.0:v2-compatible",
    "3.0.0:semantic_process",
    "3.1.0:total_core",
})
FINAL_IR_RUNTIME_PROFILES = frozenset({
    "program_ir:2:linked",
    "program_ir:3:portable",
    "program_ir:4:effects",
    "program_ir:4:pure",
    "program_ir:4:recursive",
    "program_ir:5:semantic_process",
    "program_ir:5:total_core",
    "runtime_abi:v5-total-v1:total_core",
})
FINAL_INTEGRATIONS = frozenset({
    "browser-wasm", "csharp", "filesystem", "javascript", "python", "unity", "wasi",
})
FINAL_VERSION_DOMAINS = frozenset({
    "language", "source_profile", "linked_program", "program_ir", "runtime_abi",
    "checkpoint", "package",
})


def _final_required_paths() -> tuple[str, ...]:
    getting_started = [
        "README.md", "installation.md", "first-program.md", "cli-workflow.md",
        "project-layout.md", "editor-lsp.md", "mental-model.md",
    ]
    tutorial = ["README.md"] + [
        "01-values-exactness.md", "02-names-bindings-expressions.md", "03-control-bounds.md",
        "04-functions-types.md", "05-data-models.md", "06-state-events.md",
        "07-capabilities-effects.md", "08-modules-composition.md", "09-field-transformation-apply.md",
        "10-processes-continuations.md", "11-v4-units.md", "12-total-core.md",
        "13-proof-admissions.md", "14-checkpoints-replay.md", "15-complete-application.md",
    ]
    language = [
        "README.md", "lexical.md", "values-and-types.md", "expressions.md",
        "declarations-and-functions.md", "control-and-bounds.md", "state-events-effects.md",
        "modules.md", "semantic-process.md", "field-transformation-apply.md", "total-core.md",
        "proof-admissions.md", "source-to-ir.md",
    ]
    howto = [
        "README.md", "build-and-run.md", "multi-unit.md", "effects-capabilities.md",
        "diagnostics.md", "proof-admissions.md", "checkpoints-replay.md",
    ]
    integrations = [
        "README.md", "python.md", "javascript.md", "csharp.md", "unity.md",
        "browser-wasm.md", "wasi.md", "filesystem.md",
    ]
    internals = [
        "README.md", "pipeline.md", "semantic-identity.md", "ir-strata.md",
        "runtime-boundaries.md", "proof-capability-boundaries.md", "validation-architecture.md",
    ]
    result = ["docs/manual/README.md", "docs/manual/faq.md", "docs/manual/glossary.md"]
    result += [f"docs/manual/getting-started/{name}" for name in getting_started]
    result += [f"docs/manual/tutorial/{name}" for name in tutorial]
    result += [f"docs/manual/language-reference/{name}" for name in language]
    result += [f"docs/manual/howto/{name}" for name in howto]
    result += [f"docs/manual/integrations/{name}" for name in integrations]
    result += [f"docs/manual/internals/{name}" for name in internals]
    result += [f"docs/manual/versions/{name}" for name in ("v1.md", "v2.md", "v3.md", "v31.md", "deprecations.md")]
    return tuple(result)


def _pass(**values: Any) -> dict[str, Any]:
    return {"status": "PASS", **values}


def _fail(reason: str, **values: Any) -> dict[str, Any]:
    return {"status": "FAIL", "reason": reason, **values}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_rel(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise ValueError(f"missing literal assignment: {name}")


def _version_identity_check(root: Path) -> dict[str, Any]:
    version = root / "tev_script/version.py"
    platform = root / "spec/TEV_SCRIPT_3_1_PLATFORM.md"
    matrix = root / "spec/TEV_SCRIPT_VERSION_MATRIX.json"
    if not all(path.is_file() for path in (version, platform, matrix)):
        return _fail("MISSING_VERSION_AUTHORITY")
    mismatches: list[str] = []
    try:
        actual = {
            "PACKAGE_VERSION": _literal_assignment(version, "PACKAGE_VERSION"),
            "CURRENT_LANGUAGE_VERSION": _literal_assignment(version, "CURRENT_LANGUAGE_VERSION"),
            "CURRENT_PROFILE": _literal_assignment(version, "CURRENT_PROFILE"),
            "PUBLISHED_PREDECESSOR_PACKAGE_VERSION": _literal_assignment(version, "PUBLISHED_PREDECESSOR_PACKAGE_VERSION"),
        }
    except (OSError, SyntaxError, ValueError) as exc:
        return _fail("INVALID_VERSION_AUTHORITY", error=str(exc))
    expected = {
        "PACKAGE_VERSION": _EXPECTED_IDENTITY["package_version"],
        "CURRENT_LANGUAGE_VERSION": _EXPECTED_IDENTITY["language_version"],
        "CURRENT_PROFILE": _EXPECTED_IDENTITY["profile"],
        "PUBLISHED_PREDECESSOR_PACKAGE_VERSION": _EXPECTED_IDENTITY["published_predecessor"],
    }
    mismatches.extend(key for key in expected if actual.get(key) != expected[key])
    platform_text = platform.read_text(encoding="utf-8")
    for token in (
        "package_version = 3.1.2",
        "language_version = 3.1.0",
        "current_profile = total_core",
        "published_predecessor_package = 3.1.1",
    ):
        if token not in platform_text:
            mismatches.append(f"platform:{token}")
    try:
        matrix_value = _read_json(matrix)
        packages = matrix_value["domains"]["package"]
        by_version = {row["version"]: row for row in packages}
        if matrix_value.get("current_language") != "3.1.0":
            mismatches.append("matrix:current_language")
        if by_version.get("3.1.2", {}).get("status") != "current":
            mismatches.append("matrix:3.1.2")
        if by_version.get("3.1.1", {}).get("status") != "compatible":
            mismatches.append("matrix:3.1.1")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _fail("INVALID_VERSION_MATRIX", error=str(exc))
    if mismatches:
        return _fail("VERSION_IDENTITY_MISMATCH", mismatches=sorted(set(mismatches)))
    return _pass(package_version="3.1.2", language_version="3.1.0", profile="total_core")


def _manual_root_check(root: Path) -> dict[str, Any]:
    manual = root / "docs/manual"
    if not manual.is_dir() or not (manual / "README.md").is_file():
        return _fail("MISSING_MANUAL_ROOT")
    return _pass(path="docs/manual")


def _load_manifest(root: Path) -> dict[str, Any]:
    value = _read_json(root / _COVERAGE_PATH)
    if not isinstance(value, dict):
        raise ValueError("coverage manifest must be an object")
    expected_keys = {"schema", "package_version", "language_version", "profile", "phase", "domains"}
    if set(value) != expected_keys:
        raise ValueError("coverage manifest field set mismatch")
    if value["schema"] != "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1":
        raise ValueError("invalid coverage schema")
    for key, expected in (("package_version", "3.1.2"), ("language_version", "3.1.0"), ("profile", "total_core")):
        if value[key] != expected:
            raise ValueError(f"coverage {key} mismatch")
    domains = value.get("domains")
    if not isinstance(domains, dict):
        raise ValueError("coverage domains must be an object")
    missing = sorted(set(REQUIRED_DOMAINS) - set(domains))
    extra = sorted(set(domains) - set(REQUIRED_DOMAINS))
    if missing:
        raise ValueError("missing coverage domains: " + ", ".join(missing))
    if extra:
        raise ValueError("unknown coverage domains: " + ", ".join(extra))
    for domain in REQUIRED_DOMAINS:
        rows = domains[domain]
        if not isinstance(rows, list):
            raise ValueError(f"coverage domain must be a list: {domain}")
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"id", "status", "page", "authority"}:
                raise ValueError(f"invalid coverage row: {domain}")
            identifier = row.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError(f"invalid coverage id: {domain}")
            if identifier in seen:
                raise ValueError(f"duplicate coverage id: {domain}:{identifier}")
            seen.add(identifier)
            for field in ("page", "authority"):
                rel = row.get(field)
                if not _safe_rel(rel):
                    raise ValueError(f"unsafe coverage {field}: {domain}:{identifier}")
                if not (root / rel).is_file():
                    raise ValueError(f"coverage {field} missing: {rel}")
            if not isinstance(row.get("status"), str) or not row["status"]:
                raise ValueError(f"invalid coverage status: {domain}:{identifier}")
    return value


def _coverage_manifest_check(root: Path) -> dict[str, Any]:
    path = root / _COVERAGE_PATH
    if not path.is_file():
        return _fail("MISSING_COVERAGE_MANIFEST")
    try:
        manifest = _load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail("INVALID_COVERAGE_MANIFEST", error=str(exc))
    count = sum(len(manifest["domains"][domain]) for domain in REQUIRED_DOMAINS)
    return _pass(entry_count=count)


def _coverage_ids(root: Path, domain: str) -> set[str]:
    try:
        manifest = _load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError):
        return set()
    return {row["id"] for row in manifest["domains"].get(domain, [])}


def _coverage_rows(root: Path, domain: str) -> list[dict[str, str]]:
    try:
        manifest = _load_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return list(manifest["domains"].get(domain, []))


def _phase(root: Path) -> str:
    try:
        return str(_load_manifest(root).get("phase", ""))
    except Exception:
        return ""


def _placeholder_document(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if re.search(r"(?im)^\s*(?:[-*]\s*)?(?:TODO|TBD)\b", text):
        return True
    lowered = text.lower()
    return "se entrega en su fase dedicada" in lowered or "placeholder documentation" in lowered


def _coverage_delta(root: Path, domain: str, expected: frozenset[str]) -> tuple[list[str], list[str]]:
    actual = _coverage_ids(root, domain)
    return sorted(expected - actual), sorted(actual - expected)


def _internal_paths_check(root: Path) -> dict[str, Any]:
    try:
        manifest = _load_manifest(root)
    except Exception:
        return _fail("COVERAGE_UNAVAILABLE")
    if not str(manifest.get("phase", "")).startswith("H"):
        return _pass(required_count=0)
    required = _final_required_paths()
    missing = [rel for rel in required if not (root / rel).is_file()]
    if missing:
        return _fail("MISSING_INTERNAL_DOCUMENTATION_PATHS", missing=missing)
    placeholders = [rel for rel in required if _placeholder_document(root / rel)]
    if placeholders:
        return _fail("PLACEHOLDER_DOCUMENTATION", paths=placeholders)

    missing_language, extra_language = _coverage_delta(root, "language_constructs", FINAL_LANGUAGE_CONSTRUCTS)
    missing_sources, extra_sources = _coverage_delta(root, "source_profiles", FINAL_SOURCE_PROFILES)
    missing_ir, extra_ir = _coverage_delta(root, "ir_runtime_profiles", FINAL_IR_RUNTIME_PROFILES)
    missing_integrations, extra_integrations = _coverage_delta(root, "integrations", FINAL_INTEGRATIONS)
    missing_versions, extra_versions = _coverage_delta(root, "version_domains", FINAL_VERSION_DOMAINS)
    if any((missing_language, extra_language, missing_sources, extra_sources, missing_ir, extra_ir, missing_integrations, extra_integrations, missing_versions, extra_versions)):
        return _fail(
            "INCOMPLETE_FINAL_COVERAGE",
            missing_language_constructs=missing_language,
            extra_language_constructs=extra_language,
            missing_source_profiles=missing_sources,
            extra_source_profiles=extra_sources,
            missing_ir_runtime_profiles=missing_ir,
            extra_ir_runtime_profiles=extra_ir,
            missing_integrations=missing_integrations,
            extra_integrations=extra_integrations,
            missing_version_domains=missing_versions,
            extra_version_domains=extra_versions,
        )
    return _pass(required_count=len(required))


def _source_bindings_check(root: Path) -> dict[str, Any]:
    manual = root / "docs/manual"
    if not manual.is_dir():
        return _fail("MISSING_MANUAL_ROOT")
    count = 0
    errors: list[str] = []
    for page in sorted(manual.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        directives = list(_SOURCE_DIRECTIVE_RE.finditer(text))
        fences = list(_FENCE_RE.finditer(text))
        if not directives and not fences:
            continue
        used: set[int] = set()
        for fence in fences:
            preceding = [item for item in directives if item.end() <= fence.start() and item.start() not in used]
            if not preceding:
                errors.append(f"unbound tevs fence: {page.relative_to(root).as_posix()}")
                continue
            directive = preceding[-1]
            intervening = [item for item in directives if directive.end() <= item.start() < fence.start()]
            if intervening:
                errors.append(f"multiple source directives bind one fence: {page.relative_to(root).as_posix()}")
                continue
            used.add(directive.start())
            rel = directive.group(1).strip()
            if not _safe_rel(rel):
                errors.append(f"unsafe bound source: {rel}")
                continue
            source = root / rel
            if not source.is_file():
                errors.append(f"bound source missing: {rel}")
                continue
            if fence.group(1) != source.read_text(encoding="utf-8"):
                errors.append(f"source fence drift: {page.relative_to(root).as_posix()} -> {rel}")
                continue
            count += 1
        for directive in directives:
            if directive.start() not in used:
                errors.append(f"unbound source directive: {page.relative_to(root).as_posix()}")
    if errors:
        return _fail("INVALID_SOURCE_BINDINGS", error="; ".join(errors))
    return _pass(binding_count=count)


def _case_expected_fields() -> set[str]:
    return {"schema", "operation", "source", "units", "effect_inputs", "proof_admissions", "epochs", "expected_returncode", "expected_status", "expected_diagnostic_code"}


def _example_cases_check(root: Path) -> dict[str, Any]:
    base = root / "examples/docs/v31"
    if not base.is_dir():
        return _pass(case_count=0)
    mains = sorted(base.rglob("main.tevs"))
    errors: list[str] = []
    count = 0
    try:
        from tev_script.diagnostics import TevScriptError
        from tev_script.program_ir_v5_total import validate_verified_proof_admission
        from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
        from tev_script.source_total_core_v31 import compile_total_core_v31
    except Exception as exc:
        if mains:
            return _fail("CASE_RUNTIME_UNAVAILABLE", error=str(exc))
        return _pass(case_count=0)
    for main in mains:
        case_path = main.parent / "case.json"
        if not case_path.is_file():
            errors.append(f"case.json missing: {main.parent.relative_to(root).as_posix()}")
            continue
        try:
            case = _read_json(case_path)
            if not isinstance(case, dict) or set(case) != _case_expected_fields():
                raise ValueError("case field set mismatch")
            if case["schema"] != "TEV_SCRIPT_DOCUMENTATION_CASE_V1":
                raise ValueError("case schema mismatch")
            operation = case["operation"]
            if operation not in {"check", "compile", "run"}:
                raise ValueError("unsupported documentation case operation")
            if not isinstance(case["units"], dict) or not isinstance(case["effect_inputs"], dict):
                raise ValueError("case units/effect_inputs must be objects")
            if not isinstance(case["proof_admissions"], list):
                raise ValueError("case proof_admissions must be a list")
            epochs = case["epochs"]
            if isinstance(epochs, bool) or not isinstance(epochs, int) or not 1 <= epochs <= 1_000_000:
                raise ValueError("case epochs outside admitted bound")
            for rel in [case["source"], *case["units"].values(), *case["proof_admissions"]]:
                if not _safe_rel(rel) or len(PurePosixPath(rel).parts) != 1:
                    raise ValueError(f"unsafe case path: {rel}")
            process_source = (main.parent / case["source"]).read_text(encoding="utf-8")
            units = {unit_id: (main.parent / rel).read_text(encoding="utf-8") for unit_id, rel in case["units"].items()}
            proofs = []
            for rel in case["proof_admissions"]:
                raw = _read_json(main.parent / rel)
                if not isinstance(raw, Mapping):
                    raise ValueError(f"proof admission must be an object: {rel}")
                proofs.append(validate_verified_proof_admission(raw))
            expected_code = case["expected_diagnostic_code"]
            observed_code: str | None = None
            try:
                program = compile_total_core_v31(
                    process_source,
                    unit_sources=units,
                    effect_inputs=case["effect_inputs"],
                    proof_admissions=tuple(proofs),
                )
                observed_status = "PASS"
                observed_returncode = 0
                if operation == "run":
                    checkpoint = initial_total_core_checkpoint(program)
                    last = None
                    for _ in range(epochs):
                        last = run_total_core_quantum(program, checkpoint)
                        checkpoint = last.next_checkpoint
                        if last.status == "HALTED":
                            break
                    if last is None:
                        raise ValueError("run case executed zero epochs")
                    observed_status = last.status
            except TevScriptError as exc:
                observed_status = "FAIL"
                observed_returncode = 2
                observed_code = exc.diagnostic.code
            if observed_status != case["expected_status"] or observed_returncode != case["expected_returncode"]:
                raise ValueError(f"case status mismatch expected={case['expected_status']}/{case['expected_returncode']} observed={observed_status}/{observed_returncode}")
            if observed_code != expected_code:
                raise ValueError(f"diagnostic mismatch expected={expected_code!r} observed={observed_code!r}")
            count += 1
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{case_path.relative_to(root).as_posix()}: {exc}")
    if errors:
        return _fail("INVALID_EXAMPLE_CASES", error="; ".join(errors))
    return _pass(case_count=count)


def _diagnostic_shard(root: Path) -> tuple[set[str], set[str], list[str]]:
    path = root / _DIAGNOSTIC_SHARD
    if not path.is_file():
        return set(), set(), []
    value = _read_json(path)
    if not isinstance(value, dict) or set(value) != {"schema", "language_version", "families"}:
        raise ValueError("diagnostic shard field set mismatch")
    if value["schema"] != "TEV_SCRIPT_DIAGNOSTIC_COVERAGE_V31" or value["language_version"] != "3.1.0":
        raise ValueError("diagnostic shard identity mismatch")
    families = value["families"]
    if not isinstance(families, list):
        raise ValueError("diagnostic families must be a list")
    covered: set[str] = set()
    authorities: set[str] = set()
    undocumented: set[str] = set()
    previous_key = ""
    for family in families:
        if not isinstance(family, dict) or set(family) != {"prefix", "codes", "page", "authority"}:
            raise ValueError("diagnostic family field set mismatch")
        prefix, codes, page, authority = family["prefix"], family["codes"], family["page"], family["authority"]
        if not isinstance(prefix, str) or not prefix.startswith("TEVS_V31_") or not prefix.endswith("_"):
            raise ValueError("invalid diagnostic prefix")
        key = f"{prefix}\x00{authority}\x00{page}"
        if key < previous_key:
            raise ValueError("diagnostic families must be sorted")
        previous_key = key
        if not _safe_rel(page) or not (root / page).is_file():
            raise ValueError(f"diagnostic page missing: {page}")
        if not _safe_rel(authority) or not (root / authority).is_file():
            raise ValueError(f"diagnostic authority missing: {authority}")
        authorities.add(authority)
        if not isinstance(codes, list) or not codes:
            raise ValueError(f"diagnostic codes must be nonempty: {prefix}")
        if codes == ["*"]:
            authority_text = (root / authority).read_text(encoding="utf-8")
            discovered = sorted({code for code in _DIAG_RE.findall(authority_text) if code.startswith(prefix)})
            if not discovered:
                raise ValueError(f"wildcard diagnostic family is empty: {authority}:{prefix}")
            page_text = (root / page).read_text(encoding="utf-8")
            for identifier in discovered:
                covered.add(identifier)
                if identifier not in page_text:
                    undocumented.add(identifier)
            continue
        if codes != sorted(set(codes)):
            raise ValueError(f"diagnostic codes must be sorted unique: {prefix}")
        for suffix in codes:
            if not isinstance(suffix, str) or re.fullmatch(r"[A-Z0-9_]+", suffix) is None:
                raise ValueError(f"invalid diagnostic suffix: {suffix!r}")
            covered.add(prefix + suffix)
    return covered, authorities, sorted(undocumented)


def _current_diagnostic_authorities(root: Path) -> set[str]:
    if not _phase(root).startswith(("F", "G", "H")):
        return set()
    result: set[str] = set()
    package = root / "tev_script"
    if package.is_dir():
        for path in sorted(package.glob("*v31.py")):
            result.add(path.relative_to(root).as_posix())
        for name in ("program_ir_v5_total.py", "runtime_v5_total.py"):
            path = package / name
            if path.is_file():
                result.add(path.relative_to(root).as_posix())
    tools = root / "tools"
    if tools.is_dir():
        for path in sorted(tools.glob("*v31.py")):
            result.add(path.relative_to(root).as_posix())
    return result


def _diag_inventory_check(root: Path) -> dict[str, Any]:
    manifest_rows = _coverage_rows(root, "diagnostics")
    covered = {row["id"] for row in manifest_rows}
    authorities = {row["authority"] for row in manifest_rows}
    try:
        shard_codes, shard_authorities, undocumented = _diagnostic_shard(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail("INVALID_DIAGNOSTIC_COVERAGE", error=str(exc), diagnostic_count=0, missing_diagnostics=[], extra_diagnostics=[])
    covered |= shard_codes
    authorities |= shard_authorities
    authorities |= _current_diagnostic_authorities(root)
    actual: set[str] = set()
    for rel in sorted(authorities):
        path = root / rel
        if not path.is_file():
            continue
        try:
            actual.update(_DIAG_RE.findall(path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    missing = sorted(actual - covered)
    extra = sorted(covered - actual)
    payload: dict[str, Any] = {
        "diagnostic_count": len(actual),
        "missing_diagnostics": missing,
        "extra_diagnostics": extra,
    }
    if undocumented:
        payload["undocumented_diagnostics"] = undocumented
        return _fail("UNDOCUMENTED_DIAGNOSTICS", **payload)
    return _pass(**payload) if not missing and not extra else _fail("DIAGNOSTIC_COVERAGE_MISMATCH", **payload)


def _cli_surface(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or not node.args:
            continue
        if not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        value = node.args[0].value
        if node.func.attr == "add_parser":
            result.add("command:" + value)
        elif node.func.attr == "add_argument" and value.startswith("-"):
            result.add("option:" + value)
    return result


def _python_surface(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        names = _literal_assignment(path, "__all__")
    except ValueError:
        return set()
    if not isinstance(names, (list, tuple)):
        return set()
    return {"symbol:" + str(name) for name in names}


def _public_surface_check(root: Path) -> dict[str, Any]:
    actual_cli = _cli_surface(root / "tev_script/cli.py")
    actual_py = _python_surface(root / "tev_script/__init__.py")
    covered_cli = _coverage_ids(root, "cli_surface")
    covered_py = _coverage_ids(root, "python_api")
    missing_cli = sorted(actual_cli - covered_cli)
    extra_cli = sorted(covered_cli - actual_cli)
    missing_py = sorted(actual_py - covered_py)
    extra_py = sorted(covered_py - actual_py)
    payload = {
        "cli_surface_count": len(actual_cli),
        "python_api_count": len(actual_py),
        "missing_cli_surface": missing_cli,
        "extra_cli_surface": extra_cli,
        "missing_python_api": missing_py,
        "extra_python_api": extra_py,
    }
    return _pass(**payload) if not any((missing_cli, extra_cli, missing_py, extra_py)) else _fail("PUBLIC_SURFACE_COVERAGE_MISMATCH", **payload)


def _historical_classification_check(root: Path) -> dict[str, Any]:
    try:
        manifest = _load_manifest(root)
    except Exception:
        return _fail("COVERAGE_UNAVAILABLE")
    if not str(manifest.get("phase", "")).startswith("H"):
        return _pass(classified_versions=0)
    required = {
        "v1.md": ("HISTORICAL", "compat"),
        "v2.md": ("HISTORICAL", "compat"),
        "v3.md": ("HISTORICAL", "compat"),
        "v31.md": ("CURRENT", "3.1.0"),
        "deprecations.md": ("DEPRECATION", "compat"),
    }
    missing: list[str] = []
    invalid: list[str] = []
    for name, tokens in required.items():
        path = root / "docs/manual/versions" / name
        if not path.is_file():
            missing.append(name)
            continue
        text = path.read_text(encoding="utf-8")
        if not all(token.lower() in text.lower() for token in tokens):
            invalid.append(name)
    if missing or invalid:
        return _fail("INVALID_HISTORICAL_CLASSIFICATION", missing=missing, invalid=invalid)
    return _pass(classified_versions=len(required))


def validate_documentation(root: Path | str) -> dict[str, Any]:
    root = Path(root).resolve()
    checks: dict[str, dict[str, Any]] = {}
    checks["VERSION_IDENTITY"] = _version_identity_check(root)
    checks["MANUAL_ROOT"] = _manual_root_check(root)
    checks["COVERAGE_MANIFEST"] = _coverage_manifest_check(root)
    checks["INTERNAL_PATHS"] = _internal_paths_check(root)
    checks["SOURCE_BINDINGS"] = _source_bindings_check(root)
    checks["EXAMPLE_CASES"] = _example_cases_check(root)
    checks["DIAGNOSTIC_COVERAGE"] = _diag_inventory_check(root)
    checks["PUBLIC_SURFACE_COVERAGE"] = _public_surface_check(root)
    checks["HISTORICAL_CLASSIFICATION"] = _historical_classification_check(root)
    ordered = {name: checks[name] for name in CHECK_ORDER}
    status = "PASS" if all(check["status"] == "PASS" for check in ordered.values()) else "FAIL"
    return {"schema": RECEIPT_SCHEMA, "status": status, "checks": ordered}


def validate_repository(root: Path | str) -> dict[str, Any]:
    return validate_documentation(root)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate TEVScript 3.1 documentation deterministically")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    receipt = validate_documentation(Path(args.root))
    rendered = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
