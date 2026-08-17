from __future__ import annotations

import json
from pathlib import Path

import pytest

from tev_script import cli, lsp
from tev_script.lsp_v1 import main as lsp_v1_main
from tev_script.platform_tooling import (
    describe_current_platform,
    platform_check,
    validate_tooling_surface,
)

ROOT = Path(__file__).resolve().parents[1]


def test_current_platform_description_binds_package_311_language_310() -> None:
    value = describe_current_platform()
    assert value["package_version"] == "3.1.1"
    assert value["language_version"] == "3.1.0"
    assert value["profile"] == "total_core"
    assert value["runtime_source_compilation"] is False
    assert value["implicit_physical_effects"] is False


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


def test_current_lsp_fails_closed_instead_of_using_v1() -> None:
    with pytest.raises(RuntimeError, match="3.1.0"):
        lsp.select_lsp_main("3.1.0")


def test_unknown_lsp_version_is_not_inferred() -> None:
    with pytest.raises(RuntimeError, match="unsupported"):
        lsp.select_lsp_main("9.9.9")


def test_generic_cli_describe_reports_current_platform(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["describe"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package_version"] == "3.1.1"
    assert payload["language_version"] == "3.1.0"
    assert payload["profile"] == "total_core"


def test_generic_cli_platform_check_is_fail_closed(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["platform-check", "--root", str(ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "PASS"
