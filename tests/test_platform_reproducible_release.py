from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tev_script.platform_release import (
    build_provenance,
    build_sbom,
    compare_artifacts,
    validate_platform_release,
)


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _platform_fixture(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True)
    (root / "tev_script" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tev_script" / "x.py").write_text("X=1\n", encoding="utf-8")
    (root / "tev_script" / "release_metadata_v31.py").write_text(
        'LANGUAGE_VERSION = "3.1.0"\n', encoding="utf-8"
    )
    (root / "packaging" / "v31").mkdir(parents=True)
    root_project = (
        "[project]\n"
        'name = "tev-script-portable-reference"\n'
        'version = "3.1.0"\n'
        "dependencies = []\n"
    )
    (root / "pyproject.toml").write_text(root_project, encoding="utf-8")
    (root / "packaging" / "v31" / "pyproject.toml").write_text(
        root_project, encoding="utf-8"
    )
    (root / "spec").mkdir()
    data = b"normative\n"
    (root / "spec" / "X.md").write_bytes(data)
    (root / "spec" / "TEV_SCRIPT_3_1_NORMATIVE_INDEX.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_3_1_NORMATIVE_INDEX_V1",
                "language_version": "3.1.0",
                "hash_algorithm": "SHA-256",
                "entries": [
                    {
                        "path": "spec/X.md",
                        "role": "synthetic",
                        "git_blob_sha1": _git_blob_sha1(data),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_sbom_is_deterministic_and_dependency_explicit(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    assert build_sbom(tmp_path) == build_sbom(tmp_path)
    sbom = build_sbom(tmp_path)
    assert sbom["package_version"] == "3.1.0"
    assert sbom["dependencies"] == []
    assert len(sbom["sbom_sha256"]) == 64


def test_equal_and_different_artifacts_are_distinguished(tmp_path: Path) -> None:
    a = tmp_path / "a.whl"
    b = tmp_path / "b.whl"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    assert compare_artifacts(a, b)["status"] == "PASS"
    b.write_bytes(b"different")
    assert compare_artifacts(a, b)["status"] == "FAIL"


def test_provenance_has_no_timestamp_identity(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    receipt = build_provenance(
        tmp_path,
        source_commit="a" * 40,
        source_tree="b" * 40,
        normative_set_sha256="c" * 64,
        version_identity_sha256="d" * 64,
    )
    assert "timestamp" not in receipt
    assert len(receipt["provenance_sha256"]) == 64


def test_full_release_evidence_requires_byte_reproducibility(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)

    def builder(root: Path, destination: Path) -> Path:
        del root
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / "synthetic.whl"
        target.write_bytes(b"deterministic-wheel")
        return target

    receipt = validate_platform_release(
        tmp_path,
        builder=builder,
        identity_resolver=lambda root: ("a" * 40, "b" * 40),
    )
    assert receipt["status"] == "PASS"
    assert receipt["runtime_dependency_count"] == 0
    assert receipt["source_commit"] == "a" * 40
    assert receipt["source_tree"] == "b" * 40
    assert len(receipt["provenance_sha256"]) == 64
