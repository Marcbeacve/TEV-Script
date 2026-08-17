from __future__ import annotations

import ast
from pathlib import Path
import tomllib
from typing import Any

from .version import (
    CURRENT_LANGUAGE_VERSION,
    CURRENT_PROFILE,
    PACKAGE_VERSION,
    PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
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


def collect_current_version_facts(root: Path) -> dict[str, str]:
    root = Path(root)
    root_project = _toml_project(root / "pyproject.toml")
    v31_project = _toml_project(root / "packaging" / "v31" / "pyproject.toml")
    release_version = _literal_assignment(
        root / "tev_script" / "release_metadata_v31.py",
        "LANGUAGE_VERSION",
    )
    return {
        "source.package": PACKAGE_VERSION,
        "source.language": CURRENT_LANGUAGE_VERSION,
        "root.pyproject.package": str(root_project.get("version", "")),
        "published_v31.pyproject.package": str(v31_project.get("version", "")),
        "release_metadata_v31.language": release_version,
    }


def validate_current_version_identity(root: Path) -> dict[str, object]:
    facts = collect_current_version_facts(Path(root))
    expectations = {
        "source.package": PACKAGE_VERSION,
        "source.language": CURRENT_LANGUAGE_VERSION,
        "root.pyproject.package": PACKAGE_VERSION,
        "published_v31.pyproject.package": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
        "release_metadata_v31.language": CURRENT_LANGUAGE_VERSION,
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
    return {
        "schema": "TEV_SCRIPT_PLATFORM_VERSION_IDENTITY_V2",
        "status": "PASS" if not mismatches else "FAIL",
        "package_version": PACKAGE_VERSION,
        "language_version": CURRENT_LANGUAGE_VERSION,
        "published_predecessor_package_version": PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
        "profile": CURRENT_PROFILE,
        "facts": facts,
        "mismatches": mismatches,
    }


__all__ = [
    "collect_current_version_facts",
    "validate_current_version_identity",
]
