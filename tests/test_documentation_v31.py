from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _validator_module() -> ModuleType:
    spec = importlib.util.find_spec("tools.validate_documentation_v31")
    assert spec is not None, "documentation validator module must exist"
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_current_identity(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
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
                        {
                            "version": "3.1.1",
                            "status": "compatible",
                            "note": "published immutable immediate predecessor v3.1.1",
                        },
                        {
                            "version": "3.1.0",
                            "status": "compatible",
                            "note": "published immutable predecessor v3.1.0",
                        },
                    ]
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_validator_module_is_present() -> None:
    _validator_module()


def test_missing_manual_root_fails_closed(tmp_path: Path) -> None:
    validator = _validator_module()
    _write_current_identity(tmp_path)
    receipt = validator.validate_documentation(tmp_path)
    assert receipt["schema"] == "TEV_SCRIPT_DOCUMENTATION_VALIDATION_RECEIPT_V1"
    assert receipt["status"] == "FAIL"
    assert receipt["checks"]["VERSION_IDENTITY"]["status"] == "PASS"
    assert receipt["checks"]["MANUAL_ROOT"] == {
        "status": "FAIL",
        "reason": "MISSING_MANUAL_ROOT",
    }


def test_required_check_order_is_stable_and_complete(tmp_path: Path) -> None:
    validator = _validator_module()
    _write_current_identity(tmp_path)
    receipt = validator.validate_documentation(tmp_path)
    assert list(receipt["checks"]) == list(validator.CHECK_ORDER)
    assert validator.CHECK_ORDER == (
        "VERSION_IDENTITY",
        "MANUAL_ROOT",
        "COVERAGE_MANIFEST",
        "INTERNAL_PATHS",
        "SOURCE_BINDINGS",
        "EXAMPLE_CASES",
        "DIAGNOSTIC_COVERAGE",
        "PUBLIC_SURFACE_COVERAGE",
        "HISTORICAL_CLASSIFICATION",
    )


def test_wrong_version_identity_fails_before_documentation_claim(tmp_path: Path) -> None:
    validator = _validator_module()
    _write_current_identity(tmp_path)
    path = tmp_path / "tev_script" / "version.py"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.1"',
            'PUBLISHED_PREDECESSOR_PACKAGE_VERSION = "3.1.0"',
        ),
        encoding="utf-8",
    )
    receipt = validator.validate_documentation(tmp_path)
    assert receipt["status"] == "FAIL"
    check = receipt["checks"]["VERSION_IDENTITY"]
    assert check["status"] == "FAIL"
    assert "PUBLISHED_PREDECESSOR_PACKAGE_VERSION" in check["mismatches"]


def test_validator_result_is_deterministic(tmp_path: Path) -> None:
    validator = _validator_module()
    _write_current_identity(tmp_path)
    first = validator.validate_documentation(tmp_path)
    second = validator.validate_documentation(tmp_path)
    assert first == second
