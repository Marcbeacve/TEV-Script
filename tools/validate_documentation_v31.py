from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any


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

_EXPECTED_VERSION_ASSIGNMENTS = {
    "PACKAGE_VERSION": "3.1.2",
    "CURRENT_LANGUAGE_VERSION": "3.1.0",
    "CURRENT_PROFILE": "total_core",
    "PUBLISHED_PREDECESSOR_PACKAGE_VERSION": "3.1.1",
    "ARCHIVED_V31_PACKAGE_VERSION": "3.1.0",
}
_EXPECTED_SPEC_IDENTITIES = {
    "package_version": "3.1.2",
    "language_version": "3.1.0",
    "current_profile": "total_core",
    "published_predecessor_package": "3.1.1",
}
_COVERAGE_SCHEMA = "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1"
_REQUIRED_COVERAGE_DOMAINS = frozenset(
    {
        "language_constructs",
        "cli_surface",
        "python_api",
        "source_profiles",
        "ir_runtime_profiles",
        "diagnostics",
        "integrations",
        "version_domains",
    }
)
_EXPECTED_COVERAGE_IDENTITIES = {
    "package_version": "3.1.2",
    "language_version": "3.1.0",
    "profile": "total_core",
}
_TEVDOC_SOURCE_RE = re.compile(r"^<!-- tevdoc-source: ([^\s]+) -->$")
_TEVDOC_EXPECT_RE = re.compile(r"^<!-- tevdoc-expect-diagnostic: ([A-Z0-9_]+) -->$")
_FENCE_OPEN_RE = re.compile(r"^```([^`]*)$")
_CASE_SCHEMA = "TEV_SCRIPT_DOCUMENTATION_CASE_V1"
_CASE_FIELDS = frozenset(
    {
        "schema",
        "operation",
        "source",
        "units",
        "effect_inputs",
        "proof_admissions",
        "epochs",
        "expected_returncode",
        "expected_status",
        "expected_diagnostic_code",
    }
)
_CASE_OPERATIONS = frozenset({"check", "compile", "run"})
_CASE_BINDING_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_MAX_DOCUMENTATION_EPOCHS = 64


def _literal_assignment(path: Path, name: str) -> object:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            return ast.literal_eval(node.value)
    raise ValueError(f"missing literal assignment: {name}:{path.as_posix()}")


def _string_assignments(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    result: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (TypeError, ValueError):
            continue
        if isinstance(value, str):
            result[target.id] = value
    return result


def _spec_identity(text: str, name: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\s]+)\s*$",
        text,
    )
    return None if match is None else match.group(1)


def _version_identity_check(root: Path) -> dict[str, object]:
    mismatches: list[str] = []
    try:
        version = _string_assignments(root / "tev_script" / "version.py")
        for name, expected in sorted(_EXPECTED_VERSION_ASSIGNMENTS.items()):
            if version.get(name) != expected:
                mismatches.append(name)

        spec_text = (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").read_text(
            encoding="utf-8"
        )
        for name, expected in sorted(_EXPECTED_SPEC_IDENTITIES.items()):
            if _spec_identity(spec_text, name) != expected:
                mismatches.append(f"spec.{name}")

        matrix = json.loads(
            (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").read_text(
                encoding="utf-8"
            )
        )
        if matrix.get("current_language") != "3.1.0":
            mismatches.append("matrix.current_language")
        domains = matrix.get("domains")
        package_rows = domains.get("package") if isinstance(domains, dict) else None
        if not isinstance(package_rows, list):
            mismatches.append("matrix.package_rows")
        else:
            current = [
                row
                for row in package_rows
                if isinstance(row, dict)
                and row.get("version") == "3.1.2"
                and row.get("status") == "current"
            ]
            immediate = [
                row
                for row in package_rows
                if isinstance(row, dict)
                and row.get("version") == "3.1.1"
                and "immediate predecessor" in str(row.get("note", ""))
            ]
            archived = [
                row
                for row in package_rows
                if isinstance(row, dict)
                and row.get("version") == "3.1.0"
                and "predecessor" in str(row.get("note", ""))
            ]
            if len(current) != 1:
                mismatches.append("matrix.package.current")
            if len(immediate) != 1:
                mismatches.append("matrix.package.immediate_predecessor")
            if len(archived) != 1:
                mismatches.append("matrix.package.archived_v31")
    except (OSError, UnicodeError, SyntaxError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "FAIL",
            "reason": "VERSION_IDENTITY_READ_ERROR",
            "error": str(error),
            "mismatches": sorted(set(mismatches)),
        }

    unique = sorted(set(mismatches))
    return {"status": "PASS" if not unique else "FAIL", "mismatches": unique}


def _manual_root_check(root: Path) -> dict[str, object]:
    path = root / "docs" / "manual" / "README.md"
    if not path.is_file():
        return {"status": "FAIL", "reason": "MISSING_MANUAL_ROOT"}
    return {"status": "PASS", "path": "docs/manual/README.md"}


def _safe_repo_file(root: Path, raw: object, *, role: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"unsafe {role}: {raw}")
    path = PurePosixPath(raw)
    canonical = path.as_posix()
    if (
        path.is_absolute()
        or canonical != raw
        or ".." in path.parts
        or not path.parts
        or ":" in path.parts[0]
    ):
        raise ValueError(f"unsafe {role}: {raw}")
    resolved = root / Path(canonical)
    if not resolved.is_file():
        raise ValueError(f"{role} missing: {raw}")
    return resolved


def _load_coverage_manifest(root: Path) -> dict[str, Any]:
    path = root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("coverage manifest must be a JSON object")
    return value


def _coverage_manifest_check(root: Path) -> dict[str, object]:
    path = root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json"
    if not path.is_file():
        return {"status": "FAIL", "reason": "MISSING_COVERAGE_MANIFEST"}
    try:
        manifest = _load_coverage_manifest(root)
        if manifest.get("schema") != _COVERAGE_SCHEMA:
            raise ValueError("coverage manifest schema mismatch")
        for name, expected in sorted(_EXPECTED_COVERAGE_IDENTITIES.items()):
            if manifest.get(name) != expected:
                raise ValueError(f"coverage identity mismatch: {name}")
        phase = manifest.get("phase")
        if not isinstance(phase, str) or not phase:
            raise ValueError("coverage manifest phase must be non-empty text")

        domains = manifest.get("domains")
        if not isinstance(domains, dict):
            raise ValueError("coverage manifest domains missing")
        observed_domains = set(domains)
        missing = sorted(_REQUIRED_COVERAGE_DOMAINS - observed_domains)
        if missing:
            raise ValueError("missing coverage domains: " + ",".join(missing))
        extra = sorted(observed_domains - _REQUIRED_COVERAGE_DOMAINS)
        if extra:
            raise ValueError("unexpected coverage domains: " + ",".join(extra))

        entry_count = 0
        for domain in sorted(_REQUIRED_COVERAGE_DOMAINS):
            rows = domains[domain]
            if not isinstance(rows, list):
                raise ValueError(f"coverage domain must be a list: {domain}")
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"coverage entry must be an object: {domain}")
                identifier = row.get("id")
                status = row.get("status")
                if not isinstance(identifier, str) or not identifier:
                    raise ValueError(f"coverage entry id missing: {domain}")
                if identifier in seen:
                    raise ValueError(f"duplicate coverage id: {domain}:{identifier}")
                seen.add(identifier)
                if not isinstance(status, str) or not status:
                    raise ValueError(f"coverage entry status missing: {domain}:{identifier}")
                _safe_repo_file(root, row.get("page"), role="coverage page")
                _safe_repo_file(root, row.get("authority"), role="coverage authority")
                entry_count += 1
        return {"status": "PASS", "entry_count": entry_count}
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "FAIL",
            "reason": "INVALID_COVERAGE_MANIFEST",
            "error": str(error),
        }


def _normalized_bound_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    return normalized[:-1] if normalized.endswith("\n") else normalized


def _bound_source_path(root: Path, raw: str) -> Path:
    try:
        resolved = _safe_repo_file(root, raw, role="bound source")
    except ValueError as error:
        message = str(error)
        if message.startswith("unsafe bound source"):
            raise ValueError(message.replace("unsafe bound source", "unsafe bound source path", 1)) from error
        raise
    path = PurePosixPath(raw)
    if not path.as_posix().startswith("examples/docs/v31/") or path.suffix != ".tevs":
        raise ValueError(f"bound source outside canonical v31 examples: {raw}")
    return resolved


def _skip_fence(lines: list[str], opening_index: int) -> int:
    for index in range(opening_index + 1, len(lines)):
        if lines[index].strip() == "```":
            return index + 1
    raise ValueError("unterminated markdown fence")


def _validate_source_bindings_page(root: Path, page: Path) -> int:
    text = page.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    count = 0
    index = 0
    relative_page = page.relative_to(root).as_posix()
    while index < len(lines):
        line = lines[index]
        source_match = _TEVDOC_SOURCE_RE.fullmatch(line)
        if source_match is not None:
            raw_source = source_match.group(1)
            next_index = index + 1
            if next_index < len(lines) and _TEVDOC_SOURCE_RE.fullmatch(lines[next_index]):
                raise ValueError(f"multiple source directives before one fence: {relative_page}")
            if next_index < len(lines) and _TEVDOC_EXPECT_RE.fullmatch(lines[next_index]):
                next_index += 1
            if next_index >= len(lines):
                raise ValueError(f"source directive without tevs fence: {relative_page}")
            fence_match = _FENCE_OPEN_RE.fullmatch(lines[next_index])
            if fence_match is None or fence_match.group(1).strip() not in {"tevs", "tevscript"}:
                raise ValueError(f"source directive not immediately followed by tevs fence: {relative_page}")
            end_index = _skip_fence(lines, next_index)
            fence_text = "\n".join(lines[next_index + 1 : end_index - 1])
            source_path = _bound_source_path(root, raw_source)
            source_text = source_path.read_text(encoding="utf-8")
            if _normalized_bound_text(fence_text) != _normalized_bound_text(source_text):
                raise ValueError(f"source fence drift: {relative_page}:{raw_source}")
            count += 1
            index = end_index
            continue
        if _TEVDOC_EXPECT_RE.fullmatch(line) is not None:
            raise ValueError(f"orphan diagnostic expectation: {relative_page}")
        fence_match = _FENCE_OPEN_RE.fullmatch(line)
        if fence_match is not None:
            language = fence_match.group(1).strip()
            if language in {"tevs", "tevscript"}:
                raise ValueError(f"unbound tevs fence: {relative_page}")
            index = _skip_fence(lines, index)
            continue
        index += 1
    return count


def _source_bindings_check(root: Path) -> dict[str, object]:
    manual_root = root / "docs" / "manual"
    if not manual_root.is_dir():
        return {"status": "FAIL", "reason": "MISSING_MANUAL_ROOT"}
    try:
        count = sum(
            _validate_source_bindings_page(root, page)
            for page in sorted(manual_root.rglob("*.md"), key=lambda value: value.as_posix())
        )
        return {"status": "PASS", "binding_count": count}
    except (OSError, UnicodeError, ValueError) as error:
        return {"status": "FAIL", "reason": "INVALID_SOURCE_BINDINGS", "error": str(error)}


def _case_path(case_dir: Path, raw: object, *, role: str) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ValueError(f"unsafe case path for {role}: {raw}")
    path = PurePosixPath(raw)
    canonical = path.as_posix()
    if path.is_absolute() or canonical != raw or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"unsafe case path for {role}: {raw}")
    resolved = case_dir / Path(canonical)
    if not resolved.is_file():
        raise ValueError(f"case path missing for {role}: {raw}")
    return resolved


def _case_bindings(case_dir: Path, raw: object, *, role: str) -> dict[str, Path]:
    if not isinstance(raw, dict):
        raise ValueError(f"case {role} must be an object")
    result: dict[str, Path] = {}
    for name in sorted(raw):
        if not isinstance(name, str) or _CASE_BINDING_NAME_RE.fullmatch(name) is None:
            raise ValueError(f"invalid case binding name for {role}: {name}")
        result[name] = _case_path(case_dir, raw[name], role=f"{role}:{name}")
    return result


def _case_proofs(case_dir: Path, raw: object) -> list[Path]:
    if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
        raise ValueError("case proof_admissions must be a list of paths")
    return [_case_path(case_dir, item, role="proof_admission") for item in raw]


def _invoke_current_cli(argv: list[str]) -> tuple[int, str, str]:
    from tev_script import cli as current_cli

    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        try:
            returncode = current_cli.main(argv)
        except SystemExit as error:
            returncode = int(error.code)
    return int(returncode), stdout.getvalue(), stderr.getvalue()


def _json_output(raw: str, *, stream: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"case {stream} is not one JSON value") from error
    if not isinstance(value, dict):
        raise ValueError(f"case {stream} JSON must be an object")
    return value


def _execute_case(case_dir: Path, case: dict[str, Any]) -> None:
    if set(case) != _CASE_FIELDS:
        missing = sorted(_CASE_FIELDS - set(case))
        extra = sorted(set(case) - _CASE_FIELDS)
        raise ValueError(f"case field set mismatch missing={missing} extra={extra}")
    if case.get("schema") != _CASE_SCHEMA:
        raise ValueError("case schema mismatch")
    operation = case.get("operation")
    if operation not in _CASE_OPERATIONS:
        raise ValueError(f"unsupported case operation: {operation}")
    if case.get("source") != "main.tevs":
        raw_source = case.get("source")
        if isinstance(raw_source, str) and ".." in PurePosixPath(raw_source).parts:
            raise ValueError(f"unsafe case path for source: {raw_source}")
        raise ValueError("case source must be main.tevs")

    source = _case_path(case_dir, case["source"], role="source")
    units = _case_bindings(case_dir, case["units"], role="units")
    effects = _case_bindings(case_dir, case["effect_inputs"], role="effect_inputs")
    proofs = _case_proofs(case_dir, case["proof_admissions"])

    epochs = case.get("epochs")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or not 1 <= epochs <= _MAX_DOCUMENTATION_EPOCHS:
        raise ValueError(f"case epochs must be in 1..{_MAX_DOCUMENTATION_EPOCHS}")
    expected_returncode = case.get("expected_returncode")
    if isinstance(expected_returncode, bool) or not isinstance(expected_returncode, int):
        raise ValueError("case expected_returncode must be an integer")
    expected_status = case.get("expected_status")
    if not isinstance(expected_status, str) or not expected_status:
        raise ValueError("case expected_status must be non-empty text")
    expected_diagnostic = case.get("expected_diagnostic_code")
    if expected_diagnostic is not None and (
        not isinstance(expected_diagnostic, str)
        or re.fullmatch(r"[A-Z0-9_]+", expected_diagnostic) is None
    ):
        raise ValueError("case expected_diagnostic_code must be null or a diagnostic code")

    def project_argv(command: str) -> list[str]:
        argv = [command, str(source)]
        for name, path in units.items():
            argv.extend(("--unit", f"{name}={path}"))
        for name, path in effects.items():
            argv.extend(("--effect-input", f"{name}={path}"))
        for path in proofs:
            argv.extend(("--proof-admission", str(path)))
        return argv

    with tempfile.TemporaryDirectory(prefix="tevdoc-v31-") as temporary:
        temp_root = Path(temporary)
        if operation == "check":
            returncode, stdout, stderr = _invoke_current_cli(project_argv("check"))
        elif operation == "compile":
            artifact = temp_root / "program.json"
            returncode, stdout, stderr = _invoke_current_cli(
                project_argv("compile") + ["--output", str(artifact)]
            )
        else:
            artifact = temp_root / "program.json"
            compile_code, _compile_stdout, compile_stderr = _invoke_current_cli(
                project_argv("compile") + ["--output", str(artifact)]
            )
            if compile_code != 0:
                raise ValueError(f"run case precompile failed: {compile_stderr.strip()}")
            returncode, stdout, stderr = _invoke_current_cli(
                ["run", str(artifact), "--epochs", str(epochs)]
            )

    if returncode != expected_returncode:
        raise ValueError(f"case returncode mismatch expected={expected_returncode} observed={returncode}")
    selected = stderr if returncode != 0 else stdout
    payload = _json_output(selected, stream="stderr" if returncode != 0 else "stdout")
    if payload.get("status") != expected_status:
        raise ValueError(f"case status mismatch expected={expected_status} observed={payload.get('status')}")
    observed_diagnostic = None
    diagnostic = payload.get("diagnostic")
    if isinstance(diagnostic, dict):
        observed_diagnostic = diagnostic.get("code")
    if observed_diagnostic != expected_diagnostic:
        raise ValueError(f"diagnostic mismatch expected={expected_diagnostic} observed={observed_diagnostic}")


def _example_cases_check(root: Path) -> dict[str, object]:
    examples_root = root / "examples" / "docs" / "v31"
    if not examples_root.exists():
        return {"status": "PASS", "case_count": 0}
    if not examples_root.is_dir():
        return {"status": "FAIL", "reason": "INVALID_EXAMPLE_CASES", "error": "examples/docs/v31 is not a directory"}
    try:
        main_dirs = {path.parent for path in examples_root.rglob("main.tevs") if path.is_file()}
        case_dirs = {path.parent for path in examples_root.rglob("case.json") if path.is_file()}
        for case_dir in sorted(main_dirs - case_dirs, key=lambda value: value.as_posix()):
            raise ValueError("case.json missing: " + case_dir.relative_to(root).as_posix())
        directories = sorted(main_dirs | case_dirs, key=lambda value: value.as_posix())
        for case_dir in directories:
            case_path = case_dir / "case.json"
            if not case_path.is_file():
                raise ValueError("case.json missing: " + case_dir.relative_to(root).as_posix())
            value = json.loads(case_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("case.json must be an object: " + case_path.relative_to(root).as_posix())
            _execute_case(case_dir, value)
        return {"status": "PASS", "case_count": len(directories)}
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return {"status": "FAIL", "reason": "INVALID_EXAMPLE_CASES", "error": str(error)}


def _coverage_ids(root: Path, domain: str) -> set[str]:
    manifest = _load_coverage_manifest(root)
    domains = manifest.get("domains")
    if not isinstance(domains, dict):
        raise ValueError("coverage manifest domains missing")
    rows = domains.get(domain)
    if not isinstance(rows, list):
        raise ValueError(f"coverage domain missing: {domain}")
    result: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            raise ValueError(f"invalid coverage row: {domain}")
        result.add(str(row["id"]))
    return result


def _current_v31_diagnostics(root: Path) -> set[str]:
    package_root = root / "tev_script"
    if not package_root.is_dir():
        raise ValueError("tev_script package root missing")
    result: set[str] = set()
    for path in sorted(package_root.rglob("*.py"), key=lambda value: value.as_posix()):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith("TEVS_V31_")
            ):
                result.add(node.value)
    return result


def _diagnostic_coverage_check(root: Path) -> dict[str, object]:
    try:
        required = _current_v31_diagnostics(root)
        documented = _coverage_ids(root, "diagnostics")
        missing = sorted(required - documented)
        extra = sorted(documented - required)
        return {
            "status": "PASS" if not missing and not extra else "FAIL",
            "diagnostic_count": len(required),
            "missing_diagnostics": missing,
            "extra_diagnostics": extra,
        }
    except (OSError, UnicodeError, SyntaxError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "FAIL",
            "reason": "DIAGNOSTIC_INVENTORY_ERROR",
            "error": str(error),
            "diagnostic_count": 0,
            "missing_diagnostics": [],
            "extra_diagnostics": [],
        }


def _current_cli_surface(root: Path) -> set[str]:
    path = root / "tev_script" / "cli.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    result: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr == "add_parser" and node.args:
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                result.add(f"command:{value.value}")
        elif node.func.attr == "add_argument":
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and argument.value.startswith("-"):
                    result.add(f"option:{argument.value}")
    return result


def _current_python_api(root: Path) -> set[str]:
    raw = _literal_assignment(root / "tev_script" / "__init__.py", "__all__")
    if not isinstance(raw, (list, tuple)) or any(not isinstance(item, str) for item in raw):
        raise ValueError("tev_script.__all__ must be a literal string sequence")
    if len(set(raw)) != len(raw):
        raise ValueError("tev_script.__all__ contains duplicate public symbols")
    return {f"symbol:{item}" for item in raw}


def _public_surface_coverage_check(root: Path) -> dict[str, object]:
    try:
        required_cli = _current_cli_surface(root)
        required_python = _current_python_api(root)
        documented_cli = _coverage_ids(root, "cli_surface")
        documented_python = _coverage_ids(root, "python_api")
        missing_cli = sorted(required_cli - documented_cli)
        extra_cli = sorted(documented_cli - required_cli)
        missing_python = sorted(required_python - documented_python)
        extra_python = sorted(documented_python - required_python)
        status = "PASS" if not (missing_cli or extra_cli or missing_python or extra_python) else "FAIL"
        return {
            "status": status,
            "cli_surface_count": len(required_cli),
            "python_api_count": len(required_python),
            "missing_cli_surface": missing_cli,
            "extra_cli_surface": extra_cli,
            "missing_python_api": missing_python,
            "extra_python_api": extra_python,
        }
    except (OSError, UnicodeError, SyntaxError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "FAIL",
            "reason": "PUBLIC_SURFACE_INVENTORY_ERROR",
            "error": str(error),
            "missing_cli_surface": [],
            "extra_cli_surface": [],
            "missing_python_api": [],
            "extra_python_api": [],
        }


def _closed_later(reason: str) -> dict[str, object]:
    return {"status": "FAIL", "reason": reason}


def validate_documentation(root: Path) -> dict[str, object]:
    root = Path(root)
    checks: dict[str, dict[str, object]] = {
        "VERSION_IDENTITY": _version_identity_check(root),
        "MANUAL_ROOT": _manual_root_check(root),
        "COVERAGE_MANIFEST": _coverage_manifest_check(root),
        "INTERNAL_PATHS": _closed_later("INTERNAL_PATH_VALIDATION_NOT_CLOSED"),
        "SOURCE_BINDINGS": _source_bindings_check(root),
        "EXAMPLE_CASES": _example_cases_check(root),
        "DIAGNOSTIC_COVERAGE": _diagnostic_coverage_check(root),
        "PUBLIC_SURFACE_COVERAGE": _public_surface_coverage_check(root),
        "HISTORICAL_CLASSIFICATION": _closed_later("HISTORICAL_CLASSIFICATION_NOT_CLOSED"),
    }
    ordered = {name: checks[name] for name in CHECK_ORDER}
    failed = [name for name in CHECK_ORDER if ordered[name].get("status") != "PASS"]
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS" if not failed else "FAIL",
        "package_version": "3.1.2",
        "language_version": "3.1.0",
        "profile": "total_core",
        "failed_checks": failed,
        "checks": ordered,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="validate_documentation_v31.py")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    receipt = validate_documentation(arguments.root)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
