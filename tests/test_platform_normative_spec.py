from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tev_script.platform_spec import validate_normative_index

ROOT = Path(__file__).resolve().parents[1]


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _write_fixture(root: Path, *, corrupt: bool = False) -> None:
    spec = root / "spec"
    spec.mkdir(parents=True)
    one = b"alpha\n"
    two = b"beta\n"
    (spec / "ONE.md").write_bytes(one)
    (spec / "TWO.md").write_bytes(two)
    index = {
        "schema": "TEV_SCRIPT_3_1_NORMATIVE_INDEX_V1",
        "language_version": "3.1.0",
        "hash_algorithm": "SHA-256",
        "entries": [
            {
                "path": "spec/ONE.md",
                "role": "one",
                "git_blob_sha1": _git_blob_sha1(one),
            },
            {
                "path": "spec/TWO.md",
                "role": "two",
                "git_blob_sha1": "0" * 40 if corrupt else _git_blob_sha1(two),
            },
        ],
    }
    (spec / "TEV_SCRIPT_3_1_NORMATIVE_INDEX.json").write_text(
        json.dumps(index),
        encoding="utf-8",
    )


def test_repository_normative_index_is_current() -> None:
    receipt = validate_normative_index(ROOT)
    assert receipt["status"] == "PASS"
    assert receipt["language_version"] == "3.1.0"
    assert receipt["mismatched"] == []
    assert len(receipt["files"]) >= 10
    assert len(receipt["normative_set_sha256"]) == 64


def test_normative_validation_emits_sha256_for_each_file(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    receipt = validate_normative_index(tmp_path)
    assert receipt["status"] == "PASS"
    assert all(len(item["sha256"]) == 64 for item in receipt["files"])


def test_stale_normative_blob_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, corrupt=True)
    receipt = validate_normative_index(tmp_path)
    assert receipt["status"] == "FAIL"
    assert [item["path"] for item in receipt["mismatched"]] == ["spec/TWO.md"]
