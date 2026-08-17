from __future__ import annotations

from pathlib import Path

from tev_script.platform_tooling import validate_tooling_surface


def _fixture(root: Path) -> None:
    package = root / "tev_script"
    package.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name="tev-script-portable-reference"\n'
        'version="3.1.1"\n'
        "[project.scripts]\n"
        'tev-script="tev_script.cli:main"\n'
        'tev-script-lsp="tev_script.lsp:main"\n'
        'tev-script-v1-lsp="tev_script.lsp_v1:main"\n'
        'tev-script-v3="tev_script.cli_v3:main"\n'
        'tev-script-v31="tev_script.cli_v31:main"\n',
        encoding="utf-8",
    )
    (package / "cli_v31.py").write_text("def main(argv=None): return 0\n", encoding="utf-8")
    (package / "lsp_v31.py").write_text("def main(argv=None): return 0\n", encoding="utf-8")
    (package / "cli.py").write_text(
        "from .cli_v31 import main as v31_main\n"
        "def _project_argv(arguments, command): return [command]\n"
        "def _check_current(arguments): return v31_main(_project_argv(arguments, 'check-total'))\n"
        "def _compile_current(arguments): return v31_main(_project_argv(arguments, 'compile-total'))\n"
        "def _run_current(arguments): return v31_main(['run-total'])\n",
        encoding="utf-8",
    )
    (package / "lsp.py").write_text(
        "CURRENT_LANGUAGE_VERSION='3.1.0'\n"
        "V1_LANGUAGE_VERSION='1.0.0'\n"
        "def select_lsp_main(language_version):\n"
        "    if language_version == CURRENT_LANGUAGE_VERSION:\n"
        "        from .lsp_v31 import main as v31_main\n"
        "        return v31_main\n"
        "    raise RuntimeError('unsupported')\n",
        encoding="utf-8",
    )


def test_synthetic_current_tooling_routes_pass(tmp_path: Path) -> None:
    _fixture(tmp_path)
    receipt = validate_tooling_surface(tmp_path)
    assert receipt["status"] == "PASS", receipt
    assert receipt["current_cli_semantics"] == "SUPPORTED"
    assert receipt["current_lsp_semantics"] == "SUPPORTED"


def test_cli_route_cannot_be_borrowed_from_ambient_checkout(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "tev_script" / "cli.py").write_text(
        "def _check_current(arguments): return 0\n"
        "def _compile_current(arguments): return 0\n"
        "def _run_current(arguments): return 0\n",
        encoding="utf-8",
    )
    receipt = validate_tooling_surface(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(
        row["observed"] == "CURRENT_CLI_V31_IMPORT"
        for row in receipt["mismatches"]
    )


def test_lsp_route_cannot_be_borrowed_from_ambient_checkout(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "tev_script" / "lsp.py").write_text(
        "def select_lsp_main(language_version):\n"
        "    raise RuntimeError('unsupported')\n",
        encoding="utf-8",
    )
    receipt = validate_tooling_surface(tmp_path)
    assert receipt["status"] == "FAIL"
    assert any(
        str(row["observed"]).startswith("CURRENT_LSP_")
        for row in receipt["mismatches"]
    )
