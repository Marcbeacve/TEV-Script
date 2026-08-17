from __future__ import annotations

import ast
from pathlib import Path
import tomllib

from .platform_compatibility import validate_version_matrix
from .platform_spec import validate_normative_index
from .platform_versioning import validate_current_version_identity
from .version import CURRENT_LANGUAGE_VERSION, CURRENT_PROFILE, PACKAGE_VERSION

REQUIRED_CURRENT_SCRIPTS = {
    "tev-script": "tev_script.cli:main",
    "tev-script-lsp": "tev_script.lsp:main",
    "tev-script-v1-lsp": "tev_script.lsp_v1:main",
    "tev-script-v3": "tev_script.cli_v3:main",
    "tev-script-v31": "tev_script.cli_v31:main",
}


def describe_current_platform() -> dict[str, object]:
    return {
        "schema": "TEV_SCRIPT_PLATFORM_DESCRIPTION_V1",
        "package_version": PACKAGE_VERSION,
        "language_version": CURRENT_LANGUAGE_VERSION,
        "profile": CURRENT_PROFILE,
        "runtime_source_compilation": False,
        "implicit_physical_effects": False,
        "generic_lsp_current_semantics": "SUPPORTED",
    }


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())


def _has_import_alias(
    tree: ast.Module,
    *,
    module: str,
    imported: str,
    alias: str,
) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == module
        and any(
            row.name == imported and row.asname == alias
            for row in node.names
        )
        for node in ast.walk(tree)
    )


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    if len(matches) != 1:
        raise ValueError(f"tooling function missing or ambiguous: {name}")
    return matches[0]


def _function_has_name_and_literal(
    tree: ast.Module,
    function_name: str,
    *,
    name: str,
    literal: str,
) -> bool:
    function = _function(tree, function_name)
    names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
    }
    literals = {
        node.value
        for node in ast.walk(function)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    return name in names and literal in literals


def _cli_route_errors(root: Path) -> list[str]:
    path = root / "tev_script" / "cli.py"
    tree = _tree(path)
    errors: list[str] = []
    if not _has_import_alias(
        tree,
        module="cli_v31",
        imported="main",
        alias="v31_main",
    ):
        errors.append("CURRENT_CLI_V31_IMPORT")
    for function_name, command in (
        ("_check_current", "check-total"),
        ("_compile_current", "compile-total"),
        ("_run_current", "run-total"),
    ):
        if not _function_has_name_and_literal(
            tree,
            function_name,
            name="v31_main",
            literal=command,
        ):
            errors.append(f"CURRENT_CLI_ROUTE:{function_name}:{command}")
    return errors


def _lsp_route_errors(root: Path) -> list[str]:
    path = root / "tev_script" / "lsp.py"
    tree = _tree(path)
    function = _function(tree, "select_lsp_main")
    errors: list[str] = []
    if not _has_import_alias(
        ast.Module(body=list(function.body), type_ignores=[]),
        module="lsp_v31",
        imported="main",
        alias="v31_main",
    ):
        errors.append("CURRENT_LSP_V31_IMPORT")
    names = {
        node.id
        for node in ast.walk(function)
        if isinstance(node, ast.Name)
    }
    if "CURRENT_LANGUAGE_VERSION" not in names or "v31_main" not in names:
        errors.append("CURRENT_LSP_V31_ROUTE")
    if not any(
        isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Name)
        and node.exc.func.id == "RuntimeError"
        for node in ast.walk(function)
    ):
        errors.append("CURRENT_LSP_UNKNOWN_VERSION_FAIL_CLOSED")
    return errors


def validate_tooling_surface(root: Path) -> dict[str, object]:
    try:
        root = Path(root)
        with (root / "pyproject.toml").open("rb") as stream:
            document = tomllib.load(stream)
        project = document.get("project")
        if not isinstance(project, dict):
            raise ValueError("missing [project] table")
        scripts = project.get("scripts")
        if not isinstance(scripts, dict):
            raise ValueError("missing [project.scripts] table")
        mismatches: list[dict[str, object]] = [
            {
                "surface": name,
                "expected": target,
                "observed": scripts.get(name),
            }
            for name, target in sorted(REQUIRED_CURRENT_SCRIPTS.items())
            if scripts.get(name) != target
        ]
        for relative in (
            "tev_script/cli.py",
            "tev_script/cli_v31.py",
            "tev_script/lsp.py",
            "tev_script/lsp_v31.py",
        ):
            if not (root / relative).is_file():
                mismatches.append(
                    {
                        "surface": relative,
                        "expected": "present",
                        "observed": None,
                    }
                )
        if not mismatches:
            for error in _cli_route_errors(root):
                mismatches.append(
                    {
                        "surface": "tev-script",
                        "expected": "current Total-Core V31 delegation",
                        "observed": error,
                    }
                )
            for error in _lsp_route_errors(root):
                mismatches.append(
                    {
                        "surface": "tev-script-lsp",
                        "expected": "current Total-Core V31 dispatch",
                        "observed": error,
                    }
                )
        return {
            "schema": "TEV_SCRIPT_PLATFORM_TOOLING_VALIDATION_V3",
            "status": "PASS" if not mismatches else "FAIL",
            "current_cli_semantics": "SUPPORTED" if not mismatches else "INVALID",
            "current_lsp_semantics": "SUPPORTED" if not mismatches else "INVALID",
            "mismatches": mismatches,
        }
    except (
        OSError,
        UnicodeError,
        ValueError,
        SyntaxError,
        tomllib.TOMLDecodeError,
    ) as error:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_TOOLING_VALIDATION_V3",
            "status": "FAIL",
            "current_cli_semantics": "INVALID",
            "current_lsp_semantics": "INVALID",
            "mismatches": [],
            "error": str(error),
        }


def platform_check(root: Path) -> dict[str, object]:
    root = Path(root)
    gates = {
        "VERSION_IDENTITY": validate_current_version_identity(root),
        "NORMATIVE_SPEC": validate_normative_index(root),
        "VERSION_MATRIX": validate_version_matrix(root),
        "TOOLING_3X": validate_tooling_surface(root),
    }
    status = (
        "PASS"
        if all(gate.get("status") == "PASS" for gate in gates.values())
        else "FAIL"
    )
    return {
        "schema": "TEV_SCRIPT_PLATFORM_CHECK_V1",
        "status": status,
        "package_version": PACKAGE_VERSION,
        "language_version": CURRENT_LANGUAGE_VERSION,
        "profile": CURRENT_PROFILE,
        "gates": gates,
    }


__all__ = [
    "REQUIRED_CURRENT_SCRIPTS",
    "describe_current_platform",
    "platform_check",
    "validate_tooling_surface",
]
