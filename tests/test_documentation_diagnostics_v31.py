from __future__ import annotations

import json
from pathlib import Path

from tools.validate_documentation_v31 import validate_documentation


DOMAINS = (
    "language_constructs",
    "cli_surface",
    "python_api",
    "source_profiles",
    "ir_runtime_profiles",
    "diagnostics",
    "integrations",
    "version_domains",
)


def _write_foundation(root: Path) -> None:
    package = root / "tev_script"
    package.mkdir(parents=True, exist_ok=True)
    spec = root / "spec"
    spec.mkdir(parents=True, exist_ok=True)
    manual = root / "docs" / "manual"
    manual.mkdir(parents=True, exist_ok=True)
    (manual / "diagnostics.md").write_text("# Diagnostics\n", encoding="utf-8")
    (package / "version.py").write_text(
        'PACKAGE_VERSION = "3.1.2"\n'
        'CURRENT_LANGUAGE_VERSION = "3.1.0"\n'
        'CURRENT_PROFILE = "total_core"\n'
        'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"\n'
        'ARCHIVED_V31_PACKAGE_VERSION = "3.1.0"\n',
        encoding="utf-8",
    )
    (spec / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        "package_version = 3.1.2\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n"
        "published_predecessor_package = 3.1.1\n",
        encoding="utf-8",
    )
    (spec / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
                "current_language": "3.1.0",
                "domains": {
                    "package": [
                        {"version": "3.1.2", "status": "current"},
                        {"version": "3.1.1", "status": "compatible", "note": "published immutable immediate predecessor v3.1.1"},
                        {"version": "3.1.0", "status": "compatible", "note": "published immutable predecessor v3.1.0"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (manual / "README.md").write_text("# Manual\n", encoding="utf-8")
    (package / "cli.py").write_text("__all__ = []\n", encoding="utf-8")
    (package / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
    (package / "current.py").write_text(
        "def one():\n"
        "    raise RuntimeError('TEVS_V31_ONE')\n\n"
        "def two():\n"
        "    code = 'TEVS_V31_TWO'\n"
        "    return code\n\n"
        "OLD = 'TEVS_V3_OLD'\n",
        encoding="utf-8",
    )


def _manifest(codes: list[str]) -> dict[str, object]:
    domains: dict[str, list[dict[str, str]]] = {name: [] for name in DOMAINS}
    domains["diagnostics"] = [
        {
            "id": code,
            "status": "DOCUMENTED",
            "page": "docs/manual/diagnostics.md",
            "authority": "tev_script/current.py",
        }
        for code in codes
    ]
    return {
        "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
        "package_version": "3.1.2",
        "language_version": "3.1.0",
        "profile": "total_core",
        "phase": "TEST",
        "domains": domains,
    }


def _write_manifest(root: Path, codes: list[str]) -> None:
    (root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json").write_text(
        json.dumps(_manifest(codes), sort_keys=True),
        encoding="utf-8",
    )


def test_all_v31_diagnostic_literals_are_covered(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _write_manifest(tmp_path, ["TEVS_V31_ONE", "TEVS_V31_TWO"])
    check = validate_documentation(tmp_path)["checks"]["DIAGNOSTIC_COVERAGE"]
    assert check == {
        "status": "PASS",
        "diagnostic_count": 2,
        "missing_diagnostics": [],
        "extra_diagnostics": [],
    }


def test_missing_v31_diagnostic_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _write_manifest(tmp_path, ["TEVS_V31_ONE"])
    check = validate_documentation(tmp_path)["checks"]["DIAGNOSTIC_COVERAGE"]
    assert check["status"] == "FAIL"
    assert check["missing_diagnostics"] == ["TEVS_V31_TWO"]


def test_documented_nonexistent_v31_diagnostic_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _write_manifest(tmp_path, ["TEVS_V31_ONE", "TEVS_V31_TWO", "TEVS_V31_GHOST"])
    check = validate_documentation(tmp_path)["checks"]["DIAGNOSTIC_COVERAGE"]
    assert check["status"] == "FAIL"
    assert check["extra_diagnostics"] == ["TEVS_V31_GHOST"]


def test_non_v31_compatibility_code_is_not_in_current_inventory(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _write_manifest(tmp_path, ["TEVS_V31_ONE", "TEVS_V31_TWO"])
    check = validate_documentation(tmp_path)["checks"]["DIAGNOSTIC_COVERAGE"]
    assert "TEVS_V3_OLD" not in check.get("missing_diagnostics", [])
