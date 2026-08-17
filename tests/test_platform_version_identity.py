from __future__ import annotations

from pathlib import Path

from tev_script import __version__
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
    spec_package: str = "3.1.1",
    matrix_package: str = "3.1.1",
) -> None:
    (root / "packaging" / "v31").mkdir(parents=True)
    (root / "tev_script").mkdir(parents=True)
    (root / "spec").mkdir(parents=True)
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
    (root / "tev_script" / "__init__.py").write_text(
        "from .version import PACKAGE_VERSION as __version__\n",
        encoding="utf-8",
    )
    (root / "tev_script" / "cli.py").write_text(
        "from .version import PACKAGE_VERSION\n"
        "# parser.add_argument('--version', action='version', version=PACKAGE_VERSION)\n",
        encoding="utf-8",
    )
    (root / "tev_script" / "descriptor_v31.py").write_text(
        'BODY = {"language_version": "3.1.0", "profiles": ["total_core"]}\n',
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        f"package_version = {spec_package}\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        "{\n"
        '  "current_language": "3.1.0",\n'
        '  "domains": {"package": [{"version": "'
        + matrix_package
        + '", "status": "current", "authority": "tev_script/version.py"}]}\n'
        "}\n",
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 3.1.1 - platform completion candidate\n",
        encoding="utf-8",
    )


def test_current_version_domains_are_explicit() -> None:
    assert PACKAGE_VERSION == "3.1.1"
    assert __version__ == PACKAGE_VERSION
    assert CURRENT_LANGUAGE_VERSION == "3.1.0"
    assert PUBLISHED_PREDECESSOR_PACKAGE_VERSION == "3.1.0"
    assert CURRENT_PROFILE == "total_core"


def test_repository_current_metadata_respects_domain_identity() -> None:
    receipt = validate_current_version_identity(ROOT)
    assert receipt["status"] == "PASS"
    assert receipt["package_version"] == "3.1.1"
    assert receipt["language_version"] == "3.1.0"
    assert receipt["published_predecessor_package_version"] == "3.1.0"
    assert receipt["profile"] == "total_core"
    assert receipt["mismatches"] == []
    assert receipt["binding_errors"] == []


def test_stale_current_package_version_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, root_version="3.1.0")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(row["source"] == "root.pyproject.package" for row in receipt["mismatches"])


def test_published_predecessor_rewrite_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, v31_version="3.1.1")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(
        row["source"] == "published_v31.pyproject.package"
        for row in receipt["mismatches"]
    )


def test_language_rewrite_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, release_version="3.1.1")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(
        row["source"] == "release_metadata_v31.language"
        for row in receipt["mismatches"]
    )


def test_platform_spec_package_drift_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, spec_package="3.1.0")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(row["source"] == "platform_spec.package" for row in receipt["mismatches"])


def test_version_matrix_package_drift_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, matrix_package="3.1.0")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(row["source"] == "version_matrix.package" for row in receipt["mismatches"])


def test_missing_public_version_binding_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    (tmp_path / "tev_script" / "__init__.py").write_text("", encoding="utf-8")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert "PUBLIC_VERSION_BINDING" in receipt["binding_errors"]
