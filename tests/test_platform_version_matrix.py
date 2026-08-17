from __future__ import annotations

import json
from pathlib import Path

import pytest

from tev_script.platform_compatibility import (
    resolve_runtime_route,
    validate_version_matrix,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_authority(root: Path, relative: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("synthetic authority\n", encoding="utf-8")


def _write_matrix(root: Path, *, duplicate: bool = False) -> None:
    spec = root / "spec"
    spec.mkdir(parents=True)
    authorities = {
        "spec/platform.md",
        "spec/total.md",
        "spec/linked.md",
        "tev_script/version.py",
    }
    for authority in authorities:
        _write_authority(root, authority)
    package_rows = [
        {
            "version": "3.1.1",
            "status": "current",
            "authority": "tev_script/version.py",
            "entrypoint": "tev_script",
        }
    ]
    if duplicate:
        package_rows.append(dict(package_rows[0]))
    matrix = {
        "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
        "current_language": "3.1.0",
        "domains": {
            "language": [
                {
                    "version": "3.1.0",
                    "status": "current",
                    "authority": "spec/platform.md",
                }
            ],
            "source_profile": [
                {
                    "version": "3.1.0",
                    "profile": "total_core",
                    "status": "current",
                    "authority": "spec/total.md",
                    "entrypoint": "tev_script.source_total_core_v31:compile_total_core_v31",
                }
            ],
            "linked_program": [
                {
                    "version": "1",
                    "profile": "v1",
                    "status": "compatible",
                    "authority": "spec/linked.md",
                }
            ],
            "program_ir": [
                {
                    "version": "5",
                    "profile": "total_core",
                    "status": "current",
                    "authority": "spec/total.md",
                    "entrypoint": "tev_script.runtime_v5_total:run_total_core_quantum",
                }
            ],
            "runtime_abi": [
                {
                    "version": "v5-total-v1",
                    "profile": "total_core",
                    "status": "current",
                    "authority": "spec/total.md",
                    "entrypoint": "tev_script.runtime_v5_total:run_total_core_quantum",
                }
            ],
            "checkpoint": [
                {
                    "version": "v5-total-checkpoint-v1",
                    "profile": "total_core",
                    "status": "current",
                    "authority": "spec/total.md",
                    "entrypoint": "tev_script.runtime_v5_total:TotalCoreCheckpointV1",
                }
            ],
            "package": package_rows,
        },
    }
    (spec / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(matrix),
        encoding="utf-8",
    )


def test_repository_version_matrix_is_explicit_and_current() -> None:
    receipt = validate_version_matrix(ROOT)
    assert receipt["status"] == "PASS"
    assert receipt["current_language"] == "3.1.0"
    assert receipt["current_package"] == "3.1.1"
    assert "total_core" in receipt["current_profiles"]
    assert receipt["row_count"] >= 10
    assert receipt["authority_count"] >= 1
    assert receipt["entrypoint_count"] >= 1


def test_total_core_runtime_route_is_exact() -> None:
    row = resolve_runtime_route(ROOT, "program_ir", "5", "total_core")
    assert row["status"] == "current"
    assert row["entrypoint"] == "tev_script.runtime_v5_total:run_total_core_quantum"


def test_duplicate_version_route_fails_closed(tmp_path: Path) -> None:
    _write_matrix(tmp_path, duplicate=True)
    receipt = validate_version_matrix(tmp_path)
    assert receipt["status"] == "FAIL"
    assert "duplicate version row" in receipt["error"]


def test_missing_authority_file_fails_closed(tmp_path: Path) -> None:
    _write_matrix(tmp_path)
    path = tmp_path / "spec" / "platform.md"
    path.unlink()
    receipt = validate_version_matrix(tmp_path)
    assert receipt["status"] == "FAIL"
    assert "authority path missing" in receipt["error"]


def test_unresolvable_entrypoint_fails_closed(tmp_path: Path) -> None:
    _write_matrix(tmp_path)
    path = tmp_path / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    matrix["domains"]["program_ir"][0]["entrypoint"] = "tev_script.missing:nope"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    receipt = validate_version_matrix(tmp_path)
    assert receipt["status"] == "FAIL"
    assert "entrypoint unavailable" in receipt["error"]


def test_current_package_must_match_package_authority(tmp_path: Path) -> None:
    _write_matrix(tmp_path)
    path = tmp_path / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json"
    matrix = json.loads(path.read_text(encoding="utf-8"))
    matrix["domains"]["package"][0]["version"] = "9.9.9"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    receipt = validate_version_matrix(tmp_path)
    assert receipt["status"] == "FAIL"
    assert "current package mismatch" in receipt["error"]


def test_unknown_route_is_not_inferred(tmp_path: Path) -> None:
    _write_matrix(tmp_path)
    with pytest.raises(ValueError, match="unresolved version route"):
        resolve_runtime_route(tmp_path, "program_ir", "5", "semantic_process")
