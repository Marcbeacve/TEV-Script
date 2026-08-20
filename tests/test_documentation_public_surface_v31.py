from __future__ import annotations

import json
from pathlib import Path

from tools.validate_documentation_v31 import validate_documentation


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


def _write_foundation(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "manual").mkdir(parents=True, exist_ok=True)
    (root / "tev_script" / "version.py").write_text(
        'PACKAGE_VERSION = "3.1.2"\n'
        'CURRENT_LANGUAGE_VERSION = "3.1.0"\n'
        'CURRENT_PROFILE = "total_core"\n'
        'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"\n'
        'ARCHIVED_V31_PACKAGE_VERSION = "3.1.0"\n',
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        "package_version = 3.1.2\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n"
        "published_predecessor_package = 3.1.1\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
                "current_language": "3.1.0",
                "domains": {
                    "package": [
                        {"version": "3.1.2", "status": "current"},
                        {
                            "version": "3.1.1",
                            "status": "compatible",
                            "note": "published immutable immediate predecessor v3.1.1",
                        },
                        {
                            "version": "3.1.0",
                            "status": "compatible",
                            "note": "published immutable predecessor v3.1.0",
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "manual" / "README.md").write_text("# Manual\n", encoding="utf-8")
    (root / "docs" / "manual" / "public.md").write_text("# Public\n", encoding="utf-8")
    (root / "tev_script" / "cli.py").write_text(
        "import argparse\n"
        "def build_parser():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--version')\n"
        "    commands = parser.add_subparsers()\n"
        "    check = commands.add_parser('check')\n"
        "    check.add_argument('--unit', action='append')\n"
        "    run = commands.add_parser('run')\n"
        "    run.add_argument('--epochs')\n"
        "    return parser\n",
        encoding="utf-8",
    )
    (root / "tev_script" / "__init__.py").write_text(
        "__all__ = ['compile_total_core_v31', 'run_total_core_quantum']\n",
        encoding="utf-8",
    )


def _row(identifier: str, authority: str) -> dict[str, str]:
    return {
        "id": identifier,
        "status": "DOCUMENTED",
        "page": "docs/manual/public.md",
        "authority": authority,
    }


def _manifest() -> dict[str, object]:
    domains: dict[str, list[dict[str, str]]] = {domain: [] for domain in REQUIRED_DOMAINS}
    domains["cli_surface"] = [
        _row("command:check", "tev_script/cli.py"),
        _row("command:run", "tev_script/cli.py"),
        _row("option:--epochs", "tev_script/cli.py"),
        _row("option:--unit", "tev_script/cli.py"),
        _row("option:--version", "tev_script/cli.py"),
    ]
    domains["python_api"] = [
        _row("symbol:compile_total_core_v31", "tev_script/__init__.py"),
        _row("symbol:run_total_core_quantum", "tev_script/__init__.py"),
    ]
    return {
        "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
        "package_version": "3.1.2",
        "language_version": "3.1.0",
        "profile": "total_core",
        "phase": "TEST",
        "domains": domains,
    }


def _write_manifest(root: Path, value: dict[str, object]) -> None:
    (root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json").write_text(
        json.dumps(value, sort_keys=True),
        encoding="utf-8",
    )


def test_public_cli_and_python_surface_closes_exactly(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _write_manifest(tmp_path, _manifest())
    check = validate_documentation(tmp_path)["checks"]["PUBLIC_SURFACE_COVERAGE"]
    assert check["status"] == "PASS"
    assert check["cli_surface_count"] == 5
    assert check["python_api_count"] == 2


def test_missing_cli_option_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    manifest = _manifest()
    manifest["domains"]["cli_surface"] = [
        row for row in manifest["domains"]["cli_surface"] if row["id"] != "option:--unit"
    ]
    _write_manifest(tmp_path, manifest)
    check = validate_documentation(tmp_path)["checks"]["PUBLIC_SURFACE_COVERAGE"]
    assert check["status"] == "FAIL"
    assert check["missing_cli_surface"] == ["option:--unit"]


def test_documented_nonexistent_cli_surface_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    manifest = _manifest()
    manifest["domains"]["cli_surface"].append(_row("command:ghost", "tev_script/cli.py"))
    _write_manifest(tmp_path, manifest)
    check = validate_documentation(tmp_path)["checks"]["PUBLIC_SURFACE_COVERAGE"]
    assert check["status"] == "FAIL"
    assert check["extra_cli_surface"] == ["command:ghost"]


def test_missing_exported_python_symbol_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    manifest = _manifest()
    manifest["domains"]["python_api"] = [
        row
        for row in manifest["domains"]["python_api"]
        if row["id"] != "symbol:run_total_core_quantum"
    ]
    _write_manifest(tmp_path, manifest)
    check = validate_documentation(tmp_path)["checks"]["PUBLIC_SURFACE_COVERAGE"]
    assert check["status"] == "FAIL"
    assert check["missing_python_api"] == ["symbol:run_total_core_quantum"]
