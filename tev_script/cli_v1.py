from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .canonical import canonical_json
from .diagnostics import TevScriptError
from .pipeline_v1 import analyze_v1_paths, compile_v1_paths_to_ir_v2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tev_script.cli_v1",
        description=(
            "TEV Script V1 candidate frontend/linker. "
            "The linked program is the semantic authority; IR V2 lowering "
            "is available only for the proven erasable runtime profile."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    check = subcommands.add_parser(
        "check",
        help="parse, link, type-check and emit the canonical linked V1 program",
    )
    _add_sources(check)

    link = subcommands.add_parser(
        "link",
        help="write TEV_SCRIPT_LINKED_PROGRAM_V1 canonical JSON",
    )
    _add_sources(link)
    link.add_argument("--output", "-o", required=True)

    boundary = subcommands.add_parser(
        "boundary",
        help="report whether the linked program can lower losslessly to IR V2",
    )
    _add_sources(boundary)

    lower = subcommands.add_parser(
        "lower-irv2",
        help="lower the linked V1 program to the certified IR V2 profile",
    )
    _add_sources(lower)
    lower.add_argument("--output", "-o", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "check":
            analysis = analyze_v1_paths(arguments.sources)
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_V1_CHECK_RESULT_V1",
                        "status": "PASS_CANDIDATE",
                        "program_id": analysis.plan.program_id,
                        "linked_semantic_hash": analysis.linked_program.semantic_hash,
                        "static_semantic_hash": analysis.semantics.semantic_hash,
                        "ir_v2_lowerable": analysis.ir_v2_boundary.lowerable,
                        "ir_v2_blocker_count": len(analysis.ir_v2_boundary.blockers),
                        "stable_release": False,
                    }
                )
            )
            return 0

        if arguments.command == "link":
            analysis = analyze_v1_paths(arguments.sources)
            _write_text(arguments.output, analysis.linked_program.canonical_json)
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_V1_LINK_RESULT_V1",
                        "status": "PASS_CANDIDATE",
                        "program_id": analysis.plan.program_id,
                        "linked_semantic_hash": analysis.linked_program.semantic_hash,
                        "output": Path(arguments.output).as_posix(),
                    }
                )
            )
            return 0

        if arguments.command == "boundary":
            analysis = analyze_v1_paths(arguments.sources)
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_V1_IRV2_BOUNDARY_RESULT_V1",
                        "program_id": analysis.plan.program_id,
                        **analysis.ir_v2_boundary.semantic_surface(),
                    }
                )
            )
            return 0 if analysis.ir_v2_boundary.lowerable else 3

        if arguments.command == "lower-irv2":
            compilation = compile_v1_paths_to_ir_v2(arguments.sources)
            _write_text(arguments.output, compilation.target.canonical_json)
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_V1_IRV2_LOWER_RESULT_V1",
                        "status": "PASS_CANDIDATE",
                        "program_id": compilation.analysis.plan.program_id,
                        "linked_semantic_hash": compilation.analysis.linked_program.semantic_hash,
                        "ir_v2_semantic_hash": compilation.target.ir["semantic_hash"],
                        "output": Path(arguments.output).as_posix(),
                    }
                )
            )
            return 0

        raise AssertionError(arguments.command)
    except TevScriptError as exc:
        print(
            canonical_json(
                {
                    "schema": "TEV_SCRIPT_V1_DIAGNOSTIC_V1",
                    "status": "FAIL",
                    "diagnostic": exc.diagnostic.to_dict(),
                }
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, UnicodeError) as exc:
        print(
            canonical_json(
                {
                    "schema": "TEV_SCRIPT_V1_HOST_IO_ERROR_V1",
                    "status": "FAIL",
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
            ),
            file=sys.stderr,
        )
        return 2


def _add_sources(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "sources",
        nargs="+",
        help="explicit finite V1 source set: one script root plus reachable modules",
    )


def _write_text(path: str, content: str) -> None:
    selected = Path(path)
    selected.write_text(content + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
