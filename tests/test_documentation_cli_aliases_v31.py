from __future__ import annotations

from pathlib import Path

from tools.validate_documentation_v31 import _cli_surface


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
