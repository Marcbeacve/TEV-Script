from __future__ import annotations

import ast
from pathlib import Path
import tomllib
from typing import Any

from .version import CURRENT_LANGUAGE_VERSION, CURRENT_PROFILE, PACKAGE_VERSION


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
        "root.pyproject": str(root_project.get("version", "")),
        "packaging.v31.pyproject": str(v31_project.get("version", "")),
        "release_metadata_v31": release_version,
    }


def validate_current_version_identity(root: Path) -> dict[str, object]:
    expected = PACKAGE_VERSION
    facts = collect_current_version_facts(Path(root))
    mismatches = [
        {"source": source, "expected": expected, "observed": observed}
        for source, observed in sorted(facts.items())
        if observed != expected
    ]
    return {
        "schema": "TEV_SCRIPT_PLATFORM_VERSION_IDENTITY_V1",
        "status": "PASS" if not mismatches else "FAIL",
        "version": expected,
        "language_version": CURRENT_LANGUAGE_VERSION,
        "profile": CURRENT_PROFILE,
        "facts": facts,
        "mismatches": mismatches,
    }


__all__ = [
    "collect_current_version_facts",
    "validate_current_version_identity",
]
