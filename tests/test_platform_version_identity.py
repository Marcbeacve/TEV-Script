from __future__ import annotations

from pathlib import Path

from tev_script.platform_versioning import validate_current_version_identity
from tev_script.version import (
    CURRENT_LANGUAGE_VERSION,
    CURRENT_PROFILE,
    PACKAGE_VERSION,
    PUBLISHED_PREDECESSOR_PACKAGE_VERSION,
)

ROOT = Path(__file__).resolve().parents[1]


def _write_fixture(
    root: Path,
    *,
    root_version: str = "3.1.1",
    v31_version: str = "3.1.0",
    release_version: str = "3.1.0",
) -> None:
    (root / "packaging" / "v31").mkdir(parents=True)
    (root / "tev_script").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "tev-script-portable-reference"\n'
        f'version = "{root_version}"\n',
        encoding="utf-8",
    )
    (root / "packaging" / "v31" / "pyproject.toml").write_text(
        "[project]\n"
        'name = "tev-script-portable-reference"\n'
        f'version = "{v31_version}"\n',
        encoding="utf-8",
    )
    (root / "tev_script" / "release_metadata_v31.py").write_text(
        f'LANGUAGE_VERSION = "{release_version}"\n',
        encoding="utf-8",
    )


def test_current_version_domains_are_explicit() -> None:
    assert PACKAGE_VERSION == "3.1.1"
    assert CURRENT_LANGUAGE_VERSION == "3.1.0"
    assert PUBLISHED_PREDECESSOR_PACKAGE_VERSION == "3.1.0"
    assert CURRENT_PROFILE == "total_core"


def test_repository_current_metadata_respects_domain_identity() -> None:
    receipt = validate_current_version_identity(ROOT)
    assert receipt["status"] == "PASS"
    assert receipt["package_version"] == "3.1.1"
    assert receipt["language_version"] == "3.1.0"
    assert receipt["published_predecessor_package_version"] == "3.1.0"
    assert receipt["mismatches"] == []


def test_stale_current_package_version_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, root_version="3.1.0")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert receipt["mismatches"] == [
        {
            "source": "root.pyproject.package",
            "expected": "3.1.1",
            "observed": "3.1.0",
        }
    ]


def test_published_predecessor_rewrite_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, v31_version="3.1.1")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert receipt["mismatches"] == [
        {
            "source": "published_v31.pyproject.package",
            "expected": "3.1.0",
            "observed": "3.1.1",
        }
    ]


def test_language_rewrite_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, release_version="3.1.1")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert receipt["mismatches"] == [
        {
            "source": "release_metadata_v31.language",
            "expected": "3.1.0",
            "observed": "3.1.1",
        }
    ]
