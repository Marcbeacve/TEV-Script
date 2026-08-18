from __future__ import annotations

import json
from pathlib import Path

from tools.validate_documentation_v31 import validate_documentation


AUTHORITY = "a" * 64
PROCESS = f'''
process Demo version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.total.result End;
label End = halt;
entry Start;
'''
UNIT = 'script Calc version "2.0.0"; fn add1(x:Int)->Int=x+1; entry main:Int=add1(4);'


def _write_foundation(root: Path) -> None:
    (root / "tev_script").mkdir(parents=True, exist_ok=True)
    (root / "spec").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "manual").mkdir(parents=True, exist_ok=True)
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
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "manual" / "README.md").write_text("# Manual\n", encoding="utf-8")
    (root / "docs" / "manual" / "DOCUMENTATION_COVERAGE_V1.json").write_text(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_DOCUMENTATION_COVERAGE_V1",
                "package_version": "3.1.2",
                "language_version": "3.1.0",
                "profile": "total_core",
                "phase": "TEST",
                "domains": {
                    "language_constructs": [],
                    "cli_surface": [],
                    "python_api": [],
                    "source_profiles": [],
                    "ir_runtime_profiles": [],
                    "diagnostics": [],
                    "integrations": [],
                    "version_domains": [],
                },
            }
        ),
        encoding="utf-8",
    )


def _case_dir(root: Path) -> Path:
    path = root / "examples" / "docs" / "v31" / "getting_started" / "01_first"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _case(*, expected_code: str | None = None) -> dict[str, object]:
    return {
        "schema": "TEV_SCRIPT_DOCUMENTATION_CASE_V1",
        "operation": "check",
        "source": "main.tevs",
        "units": {"Calc": "calc.tevs"},
        "effect_inputs": {},
        "proof_admissions": [],
        "epochs": 1,
        "expected_returncode": 2 if expected_code is not None else 0,
        "expected_status": "FAIL" if expected_code is not None else "PASS",
        "expected_diagnostic_code": expected_code,
    }


def _write_case(root: Path, *, source: str = PROCESS, expected_code: str | None = None) -> Path:
    case_dir = _case_dir(root)
    (case_dir / "main.tevs").write_text(source, encoding="utf-8")
    (case_dir / "calc.tevs").write_text(UNIT, encoding="utf-8")
    (case_dir / "case.json").write_text(
        json.dumps(_case(expected_code=expected_code), sort_keys=True),
        encoding="utf-8",
    )
    return case_dir


def test_valid_check_case_executes_current_public_cli(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    _write_case(tmp_path)
    assert validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"] == {
        "status": "PASS",
        "case_count": 1,
    }


def test_main_source_without_case_json_fails_closed(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    case_dir = _case_dir(tmp_path)
    (case_dir / "main.tevs").write_text(PROCESS, encoding="utf-8")
    check = validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"]
    assert check["status"] == "FAIL"
    assert "case.json missing" in check["error"]


def test_case_rejects_unknown_fields(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    case_dir = _write_case(tmp_path)
    value = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    value["typo"] = True
    (case_dir / "case.json").write_text(json.dumps(value), encoding="utf-8")
    check = validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"]
    assert check["status"] == "FAIL"
    assert "case field set mismatch" in check["error"]


def test_case_rejects_parent_path_escape(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    case_dir = _write_case(tmp_path)
    value = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    value["source"] = "../main.tevs"
    (case_dir / "case.json").write_text(json.dumps(value), encoding="utf-8")
    check = validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"]
    assert check["status"] == "FAIL"
    assert "unsafe case path" in check["error"]


def test_expected_diagnostic_is_asserted_exactly(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    wrong = PROCESS.replace('version "3.1.0"', 'version "3.0.0"')
    _write_case(tmp_path, source=wrong, expected_code="TEVS_V31_SOURCE_VERSION")
    assert validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"] == {
        "status": "PASS",
        "case_count": 1,
    }


def test_unexpected_diagnostic_fails_documentation(tmp_path: Path) -> None:
    _write_foundation(tmp_path)
    wrong = PROCESS.replace('version "3.1.0"', 'version "3.0.0"')
    _write_case(tmp_path, source=wrong, expected_code="TEVS_V31_SOURCE_UNIT_SET")
    check = validate_documentation(tmp_path)["checks"]["EXAMPLE_CASES"]
    assert check["status"] == "FAIL"
    assert "diagnostic mismatch" in check["error"]
