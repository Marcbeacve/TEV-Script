from __future__ import annotations

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
        "generic_lsp_current_semantics": "FAIL_CLOSED_UNTIL_IMPLEMENTED",
    }


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
        mismatches = [
            {
                "script": name,
                "expected": target,
                "observed": scripts.get(name),
            }
            for name, target in sorted(REQUIRED_CURRENT_SCRIPTS.items())
            if scripts.get(name) != target
        ]
        if not (root / "tev_script" / "lsp.py").is_file():
            mismatches.append(
                {
                    "script": "tev-script-lsp",
                    "expected": "tev_script/lsp.py",
                    "observed": None,
                }
            )
        return {
            "schema": "TEV_SCRIPT_PLATFORM_TOOLING_VALIDATION_V1",
            "status": "PASS" if not mismatches else "FAIL",
            "mismatches": mismatches,
        }
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_TOOLING_VALIDATION_V1",
            "status": "FAIL",
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
