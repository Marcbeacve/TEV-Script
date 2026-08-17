from __future__ import annotations

from pathlib import Path

from tev_script.platform_versioning import validate_current_version_identity
from tev_script.version import CURRENT_LANGUAGE_VERSION, CURRENT_PROFILE, PACKAGE_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _write_fixture(
    root: Path,
    *,
    root_version: str = "3.1.0",
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


def test_current_version_constants_are_310() -> None:
    assert PACKAGE_VERSION == "3.1.0"
    assert CURRENT_LANGUAGE_VERSION == "3.1.0"
    assert CURRENT_PROFILE == "total_core"


def test_repository_current_metadata_has_one_identity() -> None:
    receipt = validate_current_version_identity(ROOT)
    assert receipt["status"] == "PASS"
    assert receipt["version"] == "3.1.0"
    assert receipt["mismatches"] == []


def test_stale_root_version_fails_closed(tmp_path: Path) -> None:
    _write_fixture(tmp_path, root_version="1.0.0")
    receipt = validate_current_version_identity(tmp_path)
    assert receipt["status"] == "FAIL"
    assert receipt["mismatches"] == [
        {
            "source": "root.pyproject",
            "expected": "3.1.0",
            "observed": "1.0.0",
        }
    ]
