from __future__ import annotations

import json
from pathlib import Path

from tools.validate_documentation_v31 import validate_documentation


REQUIRED_DOMAINS = (
    "language_constructs",
    "cli_surface",
    "python_api",
    "source_profiles",
    "ir_runtime_profiles",
    "diagnostics",
    "integrations",
    "version_domains",
)


def _write_identity(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "manual" / "versions").mkdir(parents=True, exist_ok=True)
    (root / "tev_script" / "version.py").write_text(
        'PACKAGE_VERSION = "3.1.2"\n'
        'CURRENT_LANGUAGE_VERSION = "3.1.0"\n'
        'CURRENT_PROFILE = "total_core"\n'
        'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"\n'
        'ARCHIVED_V31_PACKAGE_VERSION = "3.1.0"\n',
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_3_1_PLATFORM.md").write_text(
        "package_version = 3.1.2\n"
        "language_version = 3.1.0\n"
        "current_profile = total_core\n"
        "published_predecessor_package = 3.1.1\n",
        encoding="utf-8",
    )
    (root / "spec" / "TEV_SCRIPT_VERSION_MATRIX.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_VERSION_MATRIX_V1",
                "current_language": "3.1.0",
                "domains": {
                    "package": [
                        {"version": "3.1.2", "status": "current"},
                        {"version": "3.1.1", "status": "compatible", "note": "published immutable immediate predecessor v3.1.1"},
                        {"version": "3.1.0", "status": "compatible", "note": "published immutable predecessor v3.1.0"}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "manual" / "README.md").write_text("# Manual\n", encoding="utf-8")
    (root / "docs" / "manual" / "versions" / "version-domains.md").write_text(
        "# Version domains\n",
        encoding="utf-8",
    )
    (root / "spec" / "AUTHORITY.md").write_text("authority\n", encoding="utf-8")


def _manifest() -> dict[str, object]:
    return {
        "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
        "package_version": "3.1.2",
        "language_version": "3.1.0",
        "profile": "total_core",
        "phase": "TEST",
        "domains": {domain: [] for domain in REQUIRED_DOMAINS},
    }


def _write_manifest(root: Path, manifest: dict[str, object]) -> None:
    path = root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json"
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def test_complete_empty_domain_shape_is_structurally_valid(tmp_path: Path) -> None:
    _write_identity(tmp_path)
    _write_manifest(tmp_path, _manifest())
    receipt = validate_documentation(tmp_path)
    assert receipt["checks"]["COVERAGE_MANIFEST"] == {
        "status": "PASS",
        "entry_count": 0,
    }


def test_missing_required_coverage_domain_fails_closed(tmp_path: Path) -> None:
    _write_identity(tmp_path)
    manifest = _manifest()
    del manifest["domains"]["diagnostics"]
    _write_manifest(tmp_path, manifest)
    check = validate_documentation(tmp_path)["checks"]["COVERAGE_MANIFEST"]
    assert check["status"] == "FAIL"
    assert check["reason"] == "INVALID_COVERAGE_MANIFEST"
    assert "missing coverage domains: diagnostics" in check["error"]


def test_duplicate_coverage_id_in_one_domain_fails_closed(tmp_path: Path) -> None:
    _write_identity(tmp_path)
    manifest = _manifest()
    row = {
        "id": "package",
        "status": "DOCUMENTED",
        "page": "docs/manual/versions/version-domains.md",
        "authority": "spec/AUTHORITY.md",
    }
    manifest["domains"]["version_domains"] = [row, dict(row)]
    _write_manifest(tmp_path, manifest)
    check = validate_documentation(tmp_path)["checks"]["COVERAGE_MANIFEST"]
    assert check["status"] == "FAIL"
    assert "duplicate coverage id: version_domains:package" in check["error"]


def test_coverage_entry_requires_existing_page_and_authority(tmp_path: Path) -> None:
    _write_identity(tmp_path)
    manifest = _manifest()
    manifest["domains"]["version_domains"] = [
        {
            "id": "package",
            "status": "DOCUMENTED",
            "page": "docs/manual/versions/missing.md",
            "authority": "spec/AUTHORITY.md",
        }
    ]
    _write_manifest(tmp_path, manifest)
    check = validate_documentation(tmp_path)["checks"]["COVERAGE_MANIFEST"]
    assert check["status"] == "FAIL"
    assert "coverage page missing" in check["error"]
