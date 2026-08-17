from __future__ import annotations

import json
from pathlib import Path

import pytest

from tev_script import cli, lsp
from tev_script.lsp_v1 import main as lsp_v1_main
from tev_script.lsp_v31 import main as lsp_v31_main
from tev_script.platform_tooling import (
    describe_current_platform,
    platform_check,
    validate_tooling_surface,
)
from tev_script.version import PACKAGE_VERSION

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = "a" * 64

PROCESS = f'''
process GenericCli version "3.1.0";
authority {AUTHORITY};
quantum_steps 4;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.total.result End;
label End = halt;
entry Start;
'''
UNIT = 'script Calc version "2.0.0"; fn add1(x:Int)->Int=x+1; entry main:Int=add1(4);'


def test_current_platform_description_binds_current_package_language_310() -> None:
    value = describe_current_platform()
    assert value["package_version"] == PACKAGE_VERSION
    assert value["language_version"] == "3.1.0"
    assert value["profile"] == "total_core"
    assert value["runtime_source_compilation"] is False
    assert value["implicit_physical_effects"] is False
    assert value["generic_lsp_current_semantics"] == "SUPPORTED"


def test_repository_tooling_surface_is_current() -> None:
    receipt = validate_tooling_surface(ROOT)
    assert receipt["status"] == "PASS"
    assert receipt["mismatches"] == []


def test_current_platform_check_passes_foundational_tooling_gates() -> None:
    receipt = platform_check(ROOT)
    assert receipt["status"] == "PASS"
    assert set(receipt["gates"]) == {
        "VERSION_IDENTITY",
        "NORMATIVE_SPEC",
        "VERSION_MATRIX",
        "TOOLING_3X",
    }


def test_lsp_v1_dispatch_is_explicit() -> None:
    assert lsp.select_lsp_main("1.0.0") is lsp_v1_main


def test_current_lsp_dispatches_to_total_core_semantics() -> None:
    assert lsp.select_lsp_main("3.1.0") is lsp_v31_main


def test_unknown_lsp_version_is_not_inferred() -> None:
    with pytest.raises(RuntimeError, match="unsupported"):
        lsp.select_lsp_main("9.9.9")


def test_generic_cli_describe_reports_current_platform(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["describe"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_version"] == PACKAGE_VERSION
    assert payload["language_version"] == "3.1.0"
    assert payload["profile"] == "total_core"


def test_generic_cli_check_compile_run_are_current_total_core(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    process = tmp_path / "program.tevs"
    unit = tmp_path / "calc.tevs"
    artifact = tmp_path / "program.json"
    process.write_text(PROCESS, encoding="utf-8")
    unit.write_text(UNIT, encoding="utf-8")

    assert cli.main(["check", str(process), "--unit", f"Calc={unit}"]) == 0
    checked = json.loads(capsys.readouterr().out)
    assert checked["status"] == "PASS"
    assert checked["language_version"] == "3.1.0"
    assert checked["profile"] == "total_core"
    assert not artifact.exists()

    assert cli.main([
        "compile",
        str(process),
        "--unit", f"Calc={unit}",
        "--output", str(artifact),
    ]) == 0
    compiled = json.loads(capsys.readouterr().out)
    assert compiled["schema"] == "TEV_SCRIPT_V31_COMPILE_TOTAL_RESULT_V1"
    assert artifact.is_file()

    assert cli.main(["run", str(artifact)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema"] == "TEV_SCRIPT_V31_RUN_TOTAL_RESULT_V1"
    assert result["status"] == "HALTED"


def test_generic_cli_platform_check_is_fail_closed(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["platform-check", "--root", str(ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
