from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
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
    return {
        "status": "PASS" if not unique else "FAIL",
        "mismatches": unique,
    }


def _manual_root_check(root: Path) -> dict[str, object]:
    path = root / "docs" / "manual" / "README.md"
    if not path.is_file():
        return {"status": "FAIL", "reason": "MISSING_MANUAL_ROOT"}
    return {"status": "PASS", "path": "docs/manual/README.md"}


def _coverage_manifest_check(root: Path) -> dict[str, object]:
    path = root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json"
    if not path.is_file():
        return {"status": "FAIL", "reason": "MISSING_COVERAGE_MANIFEST"}
    return {"status": "FAIL", "reason": "COVERAGE_VALIDATION_NOT_CLOSED"}


def _closed_later(reason: str) -> dict[str, object]:
    return {"status": "FAIL", "reason": reason}


def validate_documentation(root: Path) -> dict[str, object]:
    root = Path(root)
    checks: dict[str, dict[str, object]] = {
        "VERSION_IDENTITY": _version_identity_check(root),
        "MANUAL_ROOT": _manual_root_check(root),
        "COVERAGE_MANIFEST": _coverage_manifest_check(root),
        "INTERNAL_PATHS": _closed_later("INTERNAL_PATH_VALIDATION_NOT_CLOSED"),
        "SOURCE_BINDINGS": _closed_later("SOURCE_BINDING_VALIDATION_NOT_CLOSED"),
        "EXAMPLE_CASES": _closed_later("EXAMPLE_CASE_VALIDATION_NOT_CLOSED"),
        "DIAGNOSTIC_COVERAGE": _closed_later("DIAGNOSTIC_COVERAGE_NOT_CLOSED"),
        "PUBLIC_SURFACE_COVERAGE": _closed_later("PUBLIC_SURFACE_COVERAGE_NOT_CLOSED"),
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
    print(
        json.dumps(
            receipt,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    )
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
