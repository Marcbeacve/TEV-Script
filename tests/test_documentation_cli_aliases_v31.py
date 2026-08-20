from __future__ import annotations

from pathlib import Path

from tools.validate_documentation_v31 import _cli_surface


ROOT = Path(__file__).resolve().parents[1]


def test_cli_surface_includes_all_option_aliases(tmp_path: Path) -> None:
    cli = tmp_path / "cli.py"
    cli.write_text(
        "import argparse\n"
        "def build_parser():\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--output', '-o')\n"
        "    parser.add_argument('--version')\n"
        "    return parser\n",
        encoding="utf-8",
    )
    assert _cli_surface(cli) == {
        "option:--output",
        "option:-o",
        "option:--version",
    }


def test_cli_reference_marks_json_operands_as_file_paths() -> None:
    check = (ROOT / "docs" / "manual" / "cli-reference" / "check.md").read_text(encoding="utf-8")
    compile_page = (ROOT / "docs" / "manual" / "cli-reference" / "compile.md").read_text(encoding="utf-8")

    assert "`JSON` representa una **ruta a un archivo JSON**" in check
    assert "--effect-input Sensors=effects.json" in check
    assert "--proof-admission proof-a.json" in check
    assert "mismo contrato de rutas que en [`check.md`](check.md)" in compile_page
