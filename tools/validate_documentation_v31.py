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
    for key, expected in (
        ("package_version", "3.1.2"),
        ("language_version", "3.1.0"),
        ("profile", "total_core"),
    ):
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


def _load_diagnostic_shard(root: Path) -> set[str]:
    path = root / _DIAGNOSTIC_SHARD
    if not path.is_file():
        return set()
    value = _read_json(path)
    if not isinstance(value, dict) or set(value) != {"schema", "language_version", "families"}:
        raise ValueError("diagnostic shard field set mismatch")
    if value["schema"] != "TEV_SCRIPT_DIAGNOSTIC_COVERAGE_V31" or value["language_version"] != "3.1.0":
        raise ValueError("diagnostic shard identity mismatch")
    families = value["families"]
    if not isinstance(families, list):
        raise ValueError("diagnostic families must be a list")
    expanded: set[str] = set()
    previous_prefix = ""
    for family in families:
        if not isinstance(family, dict) or set(family) != {"prefix", "codes", "page", "authority"}:
            raise ValueError("diagnostic family field set mismatch")
        prefix = family["prefix"]
        codes = family["codes"]
        page = family["page"]
        authority = family["authority"]
        if not isinstance(prefix, str) or not prefix.startswith("TEVS_V31_") or not prefix.endswith("_"):
            raise ValueError("invalid diagnostic prefix")
        if prefix < previous_prefix:
            raise ValueError("diagnostic families must be sorted by prefix")
        previous_prefix = prefix
        if not isinstance(codes, list) or not codes or codes != sorted(set(codes)):
            raise ValueError(f"diagnostic codes must be nonempty sorted unique: {prefix}")
        if not _safe_rel(page) or not (root / page).is_file():
            raise ValueError(f"diagnostic page missing: {page}")
        if not _safe_rel(authority) or not (root / authority).is_file():
            raise ValueError(f"diagnostic authority missing: {authority}")
        for suffix in codes:
            if not isinstance(suffix, str) or re.fullmatch(r"[A-Z0-9_]+", suffix) is None:
                raise ValueError(f"invalid diagnostic suffix: {suffix!r}")
            identifier = prefix + suffix
            if identifier in expanded:
                raise ValueError(f"duplicate diagnostic id: {identifier}")
            expanded.add(identifier)
    return expanded


def _diagnostic_coverage_ids(root: Path) -> set[str]:
    return _coverage_ids(root, "diagnostics") | _load_diagnostic_shard(root)


def _diag_inventory_check(root: Path) -> dict[str, Any]:
    actual: set[str] = set()
    for base in (root / "tev_script", root / "tools"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                actual.update(_DIAG_RE.findall(path.read_text(encoding="utf-8")))
            except UnicodeDecodeError:
                continue
    try:
        covered = _diagnostic_coverage_ids(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _fail("INVALID_DIAGNOSTIC_COVERAGE", error=str(exc), diagnostic_count=len(actual), missing_diagnostics=sorted(actual), extra_diagnostics=[])
    missing = sorted(actual - covered)
    extra = sorted(covered - actual)
    payload = {
        "diagnostic_count": len(actual),
        "missing_diagnostics": missing,
        "extra_diagnostics": extra,
    }
    return _pass(**payload) if not missing and not extra else _fail("DIAGNOSTIC_COVERAGE_MISMATCH", **payload)


def _internal_paths_check(root: Path) -> dict[str, Any]:
    try:
        manifest = _load_manifest(root)
    except Exception:
        return _fail("COVERAGE_UNAVAILABLE")
    phase = str(manifest.get("phase", ""))
    if not phase.startswith("H"):
        return _pass(required_count=0)
    required = (
        "docs/manual/tutorial/README.md",
        "docs/manual/language-reference/README.md",
        "docs/manual/howto/README.md",
        "docs/manual/integrations/README.md",
        "docs/manual/internals/README.md",
        "docs/manual/faq.md",
        "docs/manual/versions/v1.md",
        "docs/manual/versions/v2.md",
        "docs/manual/versions/v3.md",
        "docs/manual/versions/v31.md",
        "docs/manual/versions/deprecations.md",
    )
    missing = [rel for rel in required if not (root / rel).is_file()]
    if missing:
        return _fail("MISSING_INTERNAL_DOCUMENTATION_PATHS", missing=missing)
    placeholder_hits: list[str] = []
    for rel in required:
        text = (root / rel).read_text(encoding="utf-8").lower()
        if any(token in text for token in ("todo", "tbd", "se entrega en su fase dedicada", "placeholder")):
            placeholder_hits.append(rel)
    if placeholder_hits:
        return _fail("PLACEHOLDER_DOCUMENTATION", paths=placeholder_hits)
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
            expected = source.read_text(encoding="utf-8")
            observed = fence.group(1)
            if observed != expected:
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
            for rel in [case["source"], *case["units"].values()]:
                if not _safe_rel(rel) or len(PurePosixPath(rel).parts) != 1:
                    raise ValueError(f"unsafe case path: {rel}")
            process_source = (main.parent / case["source"]).read_text(encoding="utf-8")
            units = {unit_id: (main.parent / rel).read_text(encoding="utf-8") for unit_id, rel in case["units"].items()}
            expected_code = case["expected_diagnostic_code"]
            observed_code: str | None = None
            try:
                compile_total_core_v31(process_source, unit_sources=units, effect_inputs=case["effect_inputs"], proof_admissions=())
                observed_status = "PASS"
                observed_returncode = 0
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
    phase = str(manifest.get("phase", ""))
    if not phase.startswith("H"):
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
