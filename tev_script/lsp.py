from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable

from .version import CURRENT_LANGUAGE_VERSION

V1_LANGUAGE_VERSION = "1.0.0"


def select_lsp_main(language_version: str) -> Callable[[list[str] | None], int]:
    if language_version == V1_LANGUAGE_VERSION:
        from .lsp_v1 import main as v1_main

        return v1_main
    if language_version == CURRENT_LANGUAGE_VERSION:
        from .lsp_v31 import main as v31_main

        return v31_main
    raise RuntimeError(
        f"TEVS_LSP_VERSION_UNSUPPORTED: unsupported language version {language_version}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tev-script-lsp")
    parser.add_argument("--language-version", default=CURRENT_LANGUAGE_VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments, rest = build_parser().parse_known_args(argv)
    try:
        handler = select_lsp_main(arguments.language_version)
    except RuntimeError as error:
        print(
            json.dumps(
                {
                    "schema": "TEV_SCRIPT_LSP_DISPATCH_V1",
                    "status": "HOLD",
                    "language_version": arguments.language_version,
                    "error": str(error),
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ),
            file=sys.stderr,
        )
        return 2
    return int(handler(rest))


__all__ = ["V1_LANGUAGE_VERSION", "build_parser", "main", "select_lsp_main"]
