from __future__ import annotations

import hashlib
from pathlib import Path

from tev_script.platform_invariants import (
    DEFAULT_WITNESSES,
    EXPECTED_INVARIANTS,
    validate_platform_invariants,
)

ROOT = Path(__file__).resolve().parents[1]


def _blob(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _synthetic_witnesses(root: Path) -> dict[str, dict[str, object]]:
    (root / "tests").mkdir(parents=True, exist_ok=True)
    data = b"def test_x():\n    assert True\n"
    (root / "tests" / "test_x.py").write_bytes(data)
    return {
        name: {
            "kind": "pytest",
            "target": "tests/test_x.py",
            "git_blob_sha1": _blob(data),
            "required_tools": ["python"],
        }
        for name in EXPECTED_INVARIANTS
    }


def test_default_witness_set_is_exact() -> None:
    assert set(DEFAULT_WITNESSES) == EXPECTED_INVARIANTS


def test_all_constitutional_witnesses_are_explicit(tmp_path: Path) -> None:
    receipt = validate_platform_invariants(
        tmp_path,
        witnesses=_synthetic_witnesses(tmp_path),
        executor=lambda command, cwd: 0,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "PASS"
    assert set(receipt["witnesses"]) == EXPECTED_INVARIANTS


def test_missing_witness_fails_closed(tmp_path: Path) -> None:
    witnesses = _synthetic_witnesses(tmp_path)
    witnesses.pop("UPGRADE_NO_FORK")
    receipt = validate_platform_invariants(
        tmp_path,
        witnesses=witnesses,
        executor=lambda command, cwd: 0,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "FAIL"
    assert receipt["missing_witnesses"] == ["UPGRADE_NO_FORK"]


def test_failed_witness_fails_aggregate(tmp_path: Path) -> None:
    receipt = validate_platform_invariants(
        tmp_path,
        witnesses=_synthetic_witnesses(tmp_path),
        executor=lambda command, cwd: 1,
        tool_resolver=lambda tool: "/available",
    )
    assert receipt["status"] == "FAIL"
    assert set(receipt["failed_witnesses"]) == EXPECTED_INVARIANTS


def test_repository_witness_targets_have_frozen_identities() -> None:
    for name, witness in DEFAULT_WITNESSES.items():
        target = str(witness["target"]).split("::", 1)[0]
        data = (ROOT / target).read_bytes()
        assert _blob(data) == witness["git_blob_sha1"], name
