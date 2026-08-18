from __future__ import annotations

import ast
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _string_assignments(path: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    result: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = ast.literal_eval(node.value)
        if isinstance(value, str):
            result[target.id] = value
    return result


def _spec_identity(name: str) -> str:
    text = (ROOT / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").read_text(encoding="utf-8")
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*([^\s]+)\s*$", text)
    assert match is not None, f"missing platform identity {name}"
    return match.group(1)


def _package_rows() -> list[dict[str, object]]:
    matrix = json.loads(
        (ROOT / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").read_text(encoding="utf-8")
    )
    return matrix["domains"]["package"]


def test_current_package_predecessor_and_archived_v31_are_distinct_domains() -> None:
    version = _string_assignments(ROOT / "tev_script" / "version.py")
    assert version["PACKAGE_VERSION"] == "3.1.2"
    assert version["CURRENT_LANGUAGE_VERSION"] == "3.1.0"
    assert version["CURRENT_PROFILE"] == "total_core"
    assert version["PUBLISHED_PREDECESSOR_PACKAGE_VERSION"] == "3.1.1"
    assert version["ARCHIVED_V31_PACKAGE_VERSION"] == "3.1.0"


def test_platform_spec_names_the_immediate_published_predecessor() -> None:
    assert _spec_identity("published_predecessor_package") == "3.1.1"


def test_version_matrix_preserves_both_package_identities() -> None:
    rows = _package_rows()
    immediate = [
        row
        for row in rows
        if row.get("version") == "3.1.1"
        and "immediate predecessor" in str(row.get("note", ""))
    ]
    archived = [
        row
        for row in rows
        if row.get("version") == "3.1.0"
        and "predecessor" in str(row.get("note", ""))
    ]
    assert len(immediate) == 1
    assert len(archived) == 1


def test_version_validator_does_not_alias_archived_v31_to_immediate_predecessor() -> None:
    text = (ROOT / "tev_script" / "platform_versioning.py").read_text(encoding="utf-8")
    assert "ARCHIVED_V31_PACKAGE_VERSION" in text
    assert (
        '"published_v31.pyproject.package": ARCHIVED_V31_PACKAGE_VERSION'
        in text
    )
