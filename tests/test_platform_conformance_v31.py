from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tev_script.platform_conformance import (
    REQUIRED_SEMANTIC_AREAS,
    run_platform_conformance,
)

ROOT = Path(__file__).resolve().parents[1]


def _git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _write_fixture(root: Path) -> None:
    (root / "conformance").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    data = b"def test_ok():\n    assert True\n"
    (root / "tests" / "test_ok.py").write_bytes(data)
    cases = [
        {
            "case_id": f"area-{index}",
            "semantic_area": area,
            "expected_status": "PASS",
            "kind": "pytest",
            "target": "tests/test_ok.py",
            "required_tools": ["python"],
            "git_blob_sha1": _git_blob_sha1(data),
        }
        for index, area in enumerate(sorted(REQUIRED_SEMANTIC_AREAS))
    ]
    manifest = {
        "schema": "TEV_SCRIPT_PLATFORM_CONFORMANCE_MANIFEST_V2",
        "language_version": "3.1.0",
        "profile": "total_core",
        "cases": cases,
    }
    (root / "conformance" / "v31-platform-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_repository_manifest_covers_every_required_semantic_area() -> None:
    manifest = json.loads(
        (ROOT / "conformance" / "v31-platform-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["language_version"] == "3.1.0"
    assert manifest["profile"] == "total_core"
    assert {case["semantic_area"] for case in manifest["cases"]} >= REQUIRED_SEMANTIC_AREAS
    assert all(case["expected_status"] == "PASS" for case in manifest["cases"])


def test_all_required_areas_pass(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    receipt = run_platform_conformance(
        tmp_path,
        executor=lambda command, cwd: 0,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "PASS"
    assert receipt["failed_cases"] == []
    assert receipt["hold_cases"] == []
    assert set(receipt["covered_semantic_areas"]) == REQUIRED_SEMANTIC_AREAS
    assert receipt["missing_semantic_areas"] == []


def test_missing_semantic_area_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    path = tmp_path / "conformance" / "v31-platform-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED_SEMANTIC_AREAS)[0]
    manifest["cases"] = [
        row for row in manifest["cases"] if row["semantic_area"] != missing
    ]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    receipt = run_platform_conformance(
        tmp_path,
        executor=lambda command, cwd: 0,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "FAIL"
    assert receipt["missing_semantic_areas"] == [missing]


def test_case_failure_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    receipt = run_platform_conformance(
        tmp_path,
        executor=lambda command, cwd: 1,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "FAIL"
    assert len(receipt["failed_cases"]) == len(REQUIRED_SEMANTIC_AREAS)


def test_missing_required_node_is_hold_not_pass(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    manifest_path = tmp_path / "conformance" / "v31-platform-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cases"][0]["required_tools"] = ["python", "node"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    receipt = run_platform_conformance(
        tmp_path,
        executor=lambda command, cwd: 0,
        tool_resolver=lambda tool: None if tool == "node" else "/available",
    )
    assert receipt["status"] == "HOLD"
    assert len(receipt["hold_cases"]) == 1
