from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .canonical import canonical_json
from .diagnostics import TevScriptError
from .lowering_receipt_v1 import build_ir_v2_lowering_receipt
from .lowering_receipt_v2 import build_ir_v3_lowering_receipt
from .pipeline_v1 import (
    analyze_v1_paths,
    compile_v1_paths_auto,
    compile_v1_paths_to_ir_v2,
    compile_v1_paths_to_ir_v3,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tev_script.cli_v1",
        description=(
            "TEV Script V1 candidate frontend/linker/compiler. "
            "The canonical linked program is the source-semantic authority. "
            "Target 'auto' uses certified IR V2 when the V1 runtime surface is "
            "provably erasable and IR V3 otherwise."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    check = subcommands.add_parser(
        "check",
        help="parse, link, type-check and report canonical V1 semantic identity",
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

    compile_command = subcommands.add_parser(
        "compile",
        help="compile V1 source set to auto-selected, IR V2, or IR V3 target",
    )
    _add_sources(compile_command)
    compile_command.add_argument(
        "--target",
        choices=("auto", "irv2", "irv3"),
        default="auto",
        help=(
            "auto selects IR V2 only when the linked program is losslessly "
            "erasable to that profile; otherwise it selects IR V3"
        ),
    )
    compile_command.add_argument("--output", "-o", required=True)
    compile_command.add_argument(
        "--receipt",
        help="optional path for canonical TEV Script lowering receipt",
    )

    lower_v2 = subcommands.add_parser(
        "lower-irv2",
        help="lower the linked V1 program to the certified IR V2 profile",
    )
    _add_sources(lower_v2)
    lower_v2.add_argument("--output", "-o", required=True)
    lower_v2.add_argument("--receipt")

    lower_v3 = subcommands.add_parser(
        "lower-irv3",
        help="lower the complete linked V1 program to TEV_SCRIPT_PROGRAM_IR_V3",
    )
    _add_sources(lower_v3)
    lower_v3.add_argument("--output", "-o", required=True)
    lower_v3.add_argument("--receipt")

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
                        "schema": "TEV_SCRIPT_V1_CHECK_RESULT_V2",
                        "status": "PASS_CANDIDATE",
                        "program_id": analysis.plan.program_id,
                        "linked_semantic_hash": analysis.linked_program.semantic_hash,
                        "static_semantic_hash": analysis.semantics.semantic_hash,
                        "ir_v2_lowerable": analysis.ir_v2_boundary.lowerable,
                        "ir_v2_blocker_count": len(analysis.ir_v2_boundary.blockers),
                        "default_target_ir": (
                            "TEV_SCRIPT_PROGRAM_IR_V2"
                            if analysis.ir_v2_boundary.lowerable
                            else "TEV_SCRIPT_PROGRAM_IR_V3"
                        ),
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

        if arguments.command == "compile":
            return _compile_command(
                arguments.sources,
                arguments.target,
                arguments.output,
                arguments.receipt,
            )

        if arguments.command == "lower-irv2":
            compilation = compile_v1_paths_to_ir_v2(arguments.sources)
            receipt = _emit_receipt(
                compilation.analysis.linked_program,
                compilation.target,
                arguments.receipt,
            )
            return _write_compilation_result(
                compilation.analysis.plan.program_id,
                compilation.analysis.linked_program.semantic_hash,
                compilation.target.ir,
                compilation.target.canonical_json,
                arguments.output,
                "TEV_SCRIPT_V1_IRV2_LOWER_RESULT_V2",
                receipt,
            )

        if arguments.command == "lower-irv3":
            compilation = compile_v1_paths_to_ir_v3(arguments.sources)
            receipt = _emit_receipt(
                compilation.analysis.linked_program,
                compilation.target,
                arguments.receipt,
            )
            return _write_compilation_result(
                compilation.analysis.plan.program_id,
                compilation.analysis.linked_program.semantic_hash,
                compilation.target.ir,
                compilation.target.canonical_json,
                arguments.output,
                "TEV_SCRIPT_V1_IRV3_LOWER_RESULT_V2",
                receipt,
            )

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


def _compile_command(
    sources: list[str],
    target: str,
    output: str,
    receipt_path: str | None,
) -> int:
    if target == "irv2":
        compilation = compile_v1_paths_to_ir_v2(sources)
    elif target == "irv3":
        compilation = compile_v1_paths_to_ir_v3(sources)
    elif target == "auto":
        compilation = compile_v1_paths_auto(sources)
    else:
        raise AssertionError(target)

    selected = compilation.target
    linked = compilation.analysis.linked_program
    receipt = _emit_receipt(linked, selected, receipt_path)
    _write_text(output, selected.canonical_json)

    print(
        canonical_json(
            {
                "schema": "TEV_SCRIPT_V1_COMPILE_RESULT_V2",
                "status": "PASS_CANDIDATE",
                "program_id": compilation.analysis.plan.program_id,
                "requested_target": target,
                "target_ir_schema": selected.ir["schema"],
                "linked_semantic_hash": linked.semantic_hash,
                "target_ir_semantic_hash": selected.ir["semantic_hash"],
                "output": Path(output).as_posix(),
                "lowering_receipt": receipt,
                "stable_release": False,
            }
        )
    )
    return 0


def _emit_receipt(linked, target, receipt_path: str | None) -> dict[str, object] | None:
    if receipt_path is None:
        return None
    schema = str(target.ir["schema"])
    if schema == "TEV_SCRIPT_PROGRAM_IR_V2":
        bundle = build_ir_v2_lowering_receipt(linked, target)
    elif schema == "TEV_SCRIPT_PROGRAM_IR_V3":
        bundle = build_ir_v3_lowering_receipt(linked, target)
    else:
        raise TevScriptError(
            "TEVS_V1_CLI_RECEIPT_TARGET",
            f"unsupported lowering receipt target schema {schema!r}",
        )
    _write_text(receipt_path, bundle.canonical_json)
    return {
        "schema": bundle.receipt["schema"],
        "profile": bundle.receipt["profile"],
        "receipt_hash": bundle.receipt_hash,
        "output": Path(receipt_path).as_posix(),
    }


def _write_compilation_result(
    program_id: str,
    linked_hash: str,
    ir: dict[str, object],
    ir_json: str,
    output: str,
    result_schema: str,
    receipt: dict[str, object] | None,
) -> int:
    _write_text(output, ir_json)
    print(
        canonical_json(
            {
                "schema": result_schema,
                "status": "PASS_CANDIDATE",
                "program_id": program_id,
                "linked_semantic_hash": linked_hash,
                "target_ir_schema": ir["schema"],
                "target_ir_semantic_hash": ir["semantic_hash"],
                "output": Path(output).as_posix(),
                "lowering_receipt": receipt,
            }
        )
    )
    return 0


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
