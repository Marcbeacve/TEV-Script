from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tools.validate_hot_update_batch_5c_5e import validate_core_mirror


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(root: Path) -> tuple[Path, Path]:
    core = root / "runtimes" / "csharp" / "TevScript.Core"
    unity = root / "unity" / "Package" / "Runtime" / "Core"
    core.mkdir(parents=True)
    unity.mkdir(parents=True)

    rows = []
    for name, data in (("TevScriptA.cs", b"A\n"), ("TevScriptB.cs", b"B\n")):
        (core / name).write_bytes(data)
        (unity / name).write_bytes(data)
        rows.append(
            {
                "canonical": f"runtimes/csharp/TevScript.Core/{name}",
                "package": f"unity/Package/Runtime/Core/{name}",
                "sha256": _sha256(data),
            }
        )

    # C#-host compatibility support is deliberately outside the portable
    # Unity mirror authority.
    (core / "CompilerCompatibility.V3.cs").write_text(
        "// host-only compatibility shim\n",
        encoding="utf-8",
    )

    identity = root / "unity" / "CORE_SOURCE_IDENTITY.json"
    identity.write_text(
        json.dumps(
            {
                "certified_parent_commit": "a" * 40,
                "files": rows,
                "schema": "TEV_SCRIPT_UNITY_CORE_SOURCE_IDENTITY_V1",
            }
        ),
        encoding="utf-8",
    )
    return core, unity


def test_identity_drives_portable_mirror_and_allows_known_host_only_support(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path)
    assert validate_core_mirror(tmp_path) == 2


def test_unknown_csharp_core_file_cannot_escape_classification(tmp_path: Path) -> None:
    core, _ = _fixture(tmp_path)
    (core / "TevScriptUnclassified.cs").write_text(
        "// semantic surface must be classified\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="core_unclassified"):
        validate_core_mirror(tmp_path)


def test_unity_core_cannot_add_file_outside_identity(tmp_path: Path) -> None:
    _, unity = _fixture(tmp_path)
    (unity / "TevScriptUnexpected.cs").write_text(
        "// ungoverned mirror file\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unity_identity_set"):
        validate_core_mirror(tmp_path)


def test_identity_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    _fixture(tmp_path)
    identity_path = tmp_path / "unity" / "CORE_SOURCE_IDENTITY.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["files"][0]["sha256"] = "0" * 64
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    with pytest.raises(RuntimeError, match="core_identity_hash"):
        validate_core_mirror(tmp_path)


def test_identity_path_escape_fails_closed(tmp_path: Path) -> None:
    _fixture(tmp_path)
    identity_path = tmp_path / "unity" / "CORE_SOURCE_IDENTITY.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["files"][0]["canonical"] = "../outside.cs"
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    with pytest.raises(RuntimeError, match="canonical_path"):
        validate_core_mirror(tmp_path)
