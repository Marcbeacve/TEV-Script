from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import tomllib
from typing import Any

from .version import (
    ARCHIVED_V31_PACKAGE_VERSION,
    CURRENT_LANGUAGE_VERSION,
    CURRENT_PROFILE,
    PACKAGE_VERSION,
    PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
)

_PLATFORM_SPEC = Path("spec/TEV_SCRIPT_3_1_PLATFORM.md")
_VERSION_MATRIX = Path("spec/TEV_SCRIPT_VERSION_MATRIX.json")
_V1_CERTIFICATE_MARKER = (
    "P_PYTHON_CERTIFY_FULL_RECEIPT_SHA256="
    "271d3fbdf6d1e9284b8fede03823fbff1c98ba3fab81a0e2dd1602420a5437c8"
)
_V31_TECHNICAL_MARKER = (
    "Technical certificate file SHA-256: "
    "`1f0c60f8f50322a5dfde69073cbc84e419aebdcf0f46bb99613167a13d8efc46`"
)


def _toml_project(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    project = value.get("project")
    if not isinstance(project, dict):
        raise ValueError(f"missing [project] table: {path.as_posix()}")
    return project


def _literal_assignment(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            value = ast.literal_eval(node.value)
            if isinstance(value, str):
                return value
    raise ValueError(f"missing literal {name}: {path.as_posix()}")


def _spec_assignment(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\s]+)\s*$",
        text,
    )
    if match is None:
        raise ValueError(f"missing spec identity {name}: {path.as_posix()}")
    return match.group(1)


def _descriptor_language(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'"language_version"\s*:\s*"([0-9.]+)"', text)
    if match is None:
        raise ValueError("descriptor_v31 language identity missing")
    return match.group(1)


def _matrix_facts(path: Path) -> tuple[str, str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("version matrix must be an object")
    language = value.get("current_language")
    domains = value.get("domains")
    if not isinstance(language, str) or not isinstance(domains, dict):
        raise ValueError("version matrix current identities missing")
    package_rows = domains.get("package")
    if not isinstance(package_rows, list):
        raise ValueError("version matrix package rows missing")
    current = [
        row
        for row in package_rows
        if isinstance(row, dict) and row.get("status") == "current"
    ]
    if len(current) != 1 or not isinstance(current[0].get("version"), str):
        raise ValueError("version matrix current package is not unique")
    return language, str(current[0]["version"])


def collect_current_version_facts(root: Path) -> dict[str, str]:
    root = Path(root)
    root_project = _toml_project(root / "pyproject.toml")
    v31_project = _toml_project(root / "packaging" / "v31" / "pyproject.toml")
    release_version = _literal_assignment(
        root / "tev_script" / "release_metadata_v31.py",
        "LANGUAGE_VERSION",
    )
    matrix_language, matrix_package = _matrix_facts(root / _VERSION_MATRIX)
    return {
        "source.package": PACKAGE_VERSION,
        "source.language": CURRENT_LANGUAGE_VERSION,
        "source.profile": CURRENT_PROFILE,
        "source.published_predecessor_package": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
        "source.archived_v31_package": ARCHIVED_V31_PACKAGE_VERSION,
        "root.pyproject.package": str(root_project.get("version", "")),
        "published_v31.pyproject.package": str(v31_project.get("version", "")),
        "release_metadata_v31.language": release_version,
        "descriptor_v31.language": _descriptor_language(
            root / "tev_script" / "descriptor_v31.py"
        ),
        "platform_spec.package": _spec_assignment(root / _PLATFORM_SPEC, "package_version"),
        "platform_spec.language": _spec_assignment(root / _PLATFORM_SPEC, "language_version"),
        "platform_spec.profile": _spec_assignment(root / _PLATFORM_SPEC, "current_profile"),
        "platform_spec.published_predecessor_package": _spec_assignment(
            root / _PLATFORM_SPEC,
            "published_predecessor_package",
        ),
        "version_matrix.language": matrix_language,
        "version_matrix.package": matrix_package,
    }


def _binding_errors(root: Path) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    init_text = (root / "tev_script" / "__init__.py").read_text(encoding="utf-8")
    if "from .version import PACKAGE_VERSION as __version__" not in init_text:
        errors.append("PUBLIC_VERSION_BINDING")

    cli_text = (root / "tev_script" / "cli.py").read_text(encoding="utf-8")
    if "from .version import PACKAGE_VERSION" not in cli_text or not re.search(
        r"action\s*=\s*[\"']version[\"']\s*,\s*version\s*=\s*PACKAGE_VERSION",
        cli_text,
    ):
        errors.append("CLI_VERSION_BINDING")

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## {PACKAGE_VERSION} - platform completion candidate" not in changelog:
        errors.append("CHANGELOG_CURRENT_PACKAGE")
    if _V1_CERTIFICATE_MARKER not in changelog:
        errors.append("CHANGELOG_V1_PREDECESSOR_IDENTITY")
    if _V31_TECHNICAL_MARKER not in changelog:
        errors.append("CHANGELOG_V31_PREDECESSOR_IDENTITY")
    return errors


def validate_current_version_identity(root: Path) -> dict[str, object]:
    try:
        facts = collect_current_version_facts(Path(root))
        expectations = {
            "source.package": PACKAGE_VERSION,
            "source.language": CURRENT_LANGUAGE_VERSION,
            "source.profile": CURRENT_PROFILE,
            "source.published_predecessor_package": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
            "source.archived_v31_package": ARCHIVED_V31_PACKAGE_VERSION,
            "root.pyproject.package": PACKAGE_VERSION,
            "published_v31.pyproject.package": ARCHIVED_V31_PACKAGE_VERSION,
            "release_metadata_v31.language": CURRENT_LANGUAGE_VERSION,
            "descriptor_v31.language": CURRENT_LANGUAGE_VERSION,
            "platform_spec.package": PACKAGE_VERSION,
            "platform_spec.language": CURRENT_LANGUAGE_VERSION,
            "platform_spec.profile": CURRENT_PROFILE,
            "platform_spec.published_predecessor_package": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
            "version_matrix.language": CURRENT_LANGUAGE_VERSION,
            "version_matrix.package": PACKAGE_VERSION,
        }
        mismatches = [
            {
                "source": source,
                "expected": expectations[source],
                "observed": facts[source],
            }
            for source in sorted(expectations)
            if facts[source] != expectations[source]
        ]
        binding_errors = _binding_errors(Path(root))
        status = "PASS" if not mismatches and not binding_errors else "FAIL"
        return {
            "schema": "TEV_SCRIPT_PLATFORM_VERSION_IDENTITY_V3",
            "status": status,
            "package_version": PACKAGE_VERSION,
            "language_version": CURRENT_LANGUAGE_VERSION,
            "published_predecessor_package_version": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
            "archived_v31_package_version": ARCHIVED_V31_PACKAGE_VERSION,
            "profile": CURRENT_PROFILE,
            "facts": facts,
            "mismatches": mismatches,
            "binding_errors": binding_errors,
        }
    except (
        OSError,
        UnicodeError,
        ValueError,
        SyntaxError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as error:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_VERSION_IDENTITY_V3",
            "status": "FAIL",
            "package_version": PACKAGE_VERSION,
            "language_version": CURRENT_LANGUAGE_VERSION,
            "published_predecessor_package_version": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
            "archived_v31_package_version": ARCHIVED_V31_PACKAGE_VERSION,
            "profile": CURRENT_PROFILE,
            "facts": {},
            "mismatches": [],
            "binding_errors": [],
            "error": str(error),
        }


__all__ = [
    "collect_current_version_facts",
    "validate_current_version_identity",
]
