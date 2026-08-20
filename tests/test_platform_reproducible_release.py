from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from tev_script.platform_release import (
    build_provenance,
    build_sbom,
    compare_artifacts,
    validate_platform_release,
)
from tev_script.platform_release_receipt import verify_platform_release_receipt
from tev_script.version import PACKAGE_VERSION, PUBLISHED_PREDECESSOR_PACKAGE_VERSION


def _git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _platform_fixture(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True)
    (root / "packaging" / "v31").mkdir(parents=True)
    (root / "spec").mkdir(parents=True)
    (root / "tev_script" / "x.py").write_text("X=1\n", encoding="utf-8")
    (root / "tev_script" / "__init__.py").write_text(
        "from .version import PACKAGE_VERSION as __version__\n",
        encoding="utf-8",
    )
    (root / "tev_script" / "cli.py").write_text(
        "from .version import PACKAGE_VERSION\n"
        "# action=\"version\", version=PACKAGE_VERSION\n",
        encoding="utf-8",
    )
    (root / "tev_script" / "descriptor_v31.py").write_text(
        'BODY={"language_version":"3.1.0"}\n', encoding="utf-8"
    )
    (root / "tev_script" / "release_metadata_v31.py").write_text(
        'LANGUAGE_VERSION = "3.1.0"\n', encoding="utf-8"
    )
    (root / "pyproject.toml").write_text(
        "[build-system]\nrequires=[]\nbuild-backend='tev_script_build_backend'\nbackend-path=['tools']\n"
        "[project]\n"
        'name = "tev-script-portable-reference"\n'
        f'version = "{PACKAGE_VERSION}"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    (root / "packaging" / "v31" / "pyproject.toml").write_text(
        "[project]\n"
        'name = "tev-script-portable-reference"\n'
        'version = "3.1.0"\n'
        "dependencies = []\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        f"package_version = {PACKAGE_VERSION}\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n"
        f"published_predecessor_package = {PUBLISHED_PREDECESSOR_PACKAGE_VERSION}\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(
            {
                "current_language": "3.1.0",
                "domains": {
                    "package": [
                        {
                            "version": PACKAGE_VERSION,
                            "status": "current",
                            "authority": "tev_script/version.py",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        f"## {PACKAGE_VERSION} - platform completion candidate\n"
        "P_PYTHON_CERTIFY_FULL_RECEIPT_SHA256="
        "271d3fbdf6d1e9284b8fede03823fbff1c98ba3fab81a0e2dd1602420a5437c8\n"
        "Technical certificate file SHA-256: "
        "`1f0c60f8f50322a5dfde69073cbc84e419aebdcf0f46bb99613167a13d8efc46`\n",
        encoding="utf-8",
    )
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


def _conformance(_root: Path) -> dict[str, object]:
    return {"status": "PASS", "receipt_sha256": "c" * 64}


def _environment(_root: Path) -> dict[str, object]:
    return {
        "schema": "TEV_SCRIPT_BUILD_ENVIRONMENT_V1",
        "python_implementation": "CPython",
        "python_version": "3.11.0",
        "source_date_epoch": "1786380000",
    }


def _builder(root: Path, destination: Path) -> Path:
    del root
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "synthetic.whl"
    target.write_bytes(b"deterministic-wheel")
    return target


def _release(root: Path, **overrides):
    arguments = {
        "builder": _builder,
        "identity_resolver": lambda root: ("a" * 40, "b" * 40),
        "worktree_clean_resolver": lambda root: True,
        "conformance_runner": _conformance,
        "environment_resolver": _environment,
    }
    arguments.update(overrides)
    return validate_platform_release(root, **arguments)


def test_sbom_is_deterministic_and_dependency_explicit(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    assert build_sbom(tmp_path) == build_sbom(tmp_path)
    sbom = build_sbom(tmp_path)
    assert sbom["package_version"] == PACKAGE_VERSION
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
        conformance_sha256="e" * 64,
        build_environment_descriptor_sha256="f" * 64,
    )
    assert receipt["package_version"] == PACKAGE_VERSION
    assert receipt["conformance_sha256"] == "e" * 64
    assert receipt["build_environment_descriptor_sha256"] == "f" * 64
    assert "timestamp" not in receipt
    assert len(receipt["provenance_sha256"]) == 64


def test_full_release_evidence_requires_byte_reproducibility(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    receipt = _release(tmp_path)
    assert receipt["status"] == "PASS"
    assert receipt["package_version"] == PACKAGE_VERSION
    assert receipt["runtime_dependency_count"] == 0
    assert receipt["source_commit"] == "a" * 40
    assert receipt["source_tree"] == "b" * 40
    assert receipt["conformance_sha256"] == "c" * 64
    assert len(receipt["build_environment_descriptor_sha256"]) == 64
    assert len(receipt["provenance_sha256"]) == 64
    assert verify_platform_release_receipt(receipt)


def test_release_receipt_tamper_is_rejected(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    receipt = _release(tmp_path)
    tampered = copy.deepcopy(receipt)
    tampered["wheel_sha256"] = "0" * 64
    assert not verify_platform_release_receipt(tampered)
    tampered = copy.deepcopy(receipt)
    tampered["source_commit"] = "c" * 40
    assert not verify_platform_release_receipt(tampered)


def test_dirty_worktree_blocks_release_evidence(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    receipt = _release(
        tmp_path,
        worktree_clean_resolver=lambda root: False,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["error"] == "git working tree is not clean"
    assert verify_platform_release_receipt(receipt)


def test_nonpassing_conformance_blocks_release_evidence(tmp_path: Path) -> None:
    _platform_fixture(tmp_path)
    receipt = _release(
        tmp_path,
        conformance_runner=lambda root: {
            "status": "HOLD",
            "receipt_sha256": "d" * 64,
        },
    )
    assert receipt["status"] == "HOLD"
    assert receipt["error"] == "conformance not PASS"
    assert verify_platform_release_receipt(receipt)
