from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tev_script.platform_conformance import run_platform_conformance

ROOT = Path(__file__).resolve().parents[1]


def _git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _write_fixture(root: Path) -> None:
    (root / "conformance").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    data = b"def test_ok():\n    assert True\n"
    (root / "tests" / "test_ok.py").write_bytes(data)
    manifest = {
        "schema": "TEV_SCRIPT_PLATFORM_CONFORMANCE_MANIFEST_V1",
        "language_version": "3.1.0",
        "cases": [
            {
                "case_id": "ok",
                "kind": "pytest",
                "target": "tests/test_ok.py",
                "required_tools": ["python"],
                "git_blob_sha1": _git_blob_sha1(data),
            }
        ],
    }
    (root / "conformance" / "v31-platform-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_repository_manifest_binds_expected_campaign() -> None:
    manifest = json.loads(
        (ROOT / "conformance" / "v31-platform-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["language_version"] == "3.1.0"
    assert {case["case_id"] for case in manifest["cases"]} >= {
        "program-ir-v5-total",
        "runtime-v5-total",
        "source-total-core-v31",
        "runtime-v5-total-js-parity",
        "bounded-step-limit-v2",
        "checkpoint-replay-v2",
        "v31-authority-boundaries",
    }


def test_all_zero_cases_pass(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    receipt = run_platform_conformance(
        tmp_path,
        executor=lambda command, cwd: 0,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "PASS"
    assert receipt["failed_cases"] == []
    assert receipt["hold_cases"] == []


def test_case_failure_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    receipt = run_platform_conformance(
        tmp_path,
        executor=lambda command, cwd: 1,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "FAIL"
    assert receipt["failed_cases"] == ["ok"]


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
    assert receipt["hold_cases"] == ["ok"]
