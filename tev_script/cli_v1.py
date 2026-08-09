from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .artifact_write_v1 import write_compilation_artifacts_v1, write_text_artifact_v1
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
from .project_v1 import load_v1_project, verify_v1_project_inputs

ARTIFACT_COMMIT_POLICY_V1 = "EVIDENCE_SAFE_RECEIPT_LAST_V1"


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

    project_check = subcommands.add_parser(
        "project-check",
        help="validate an explicit TEV_SCRIPT_PROJECT_V1 and its complete source set",
    )
    project_check.add_argument("project")

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
        help="compile an explicit V1 source set to auto-selected, IR V2, or IR V3 target",
    )
    _add_sources(compile_command)
    _add_target(compile_command, default="auto")
    compile_command.add_argument("--output", "-o", required=True)
    compile_command.add_argument(
        "--receipt",
        help="optional path for canonical TEV Script lowering receipt",
    )

    build = subcommands.add_parser(
        "build",
        help="compile a TEV_SCRIPT_PROJECT_V1 using its finite source manifest",
    )
    build.add_argument("project")
    _add_target(build, default=None)
    build.add_argument("--output", "-o", required=True)
    build.add_argument("--receipt")

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
            print(canonical_json(_check_result(analysis)))
            return 0

        if arguments.command == "project-check":
            project = load_v1_project(arguments.project)
            analysis = analyze_v1_paths(project.source_paths)
            verify_v1_project_inputs(project)
            result = _check_result(analysis)
            result.update(
                {
                    "schema": "TEV_SCRIPT_V1_PROJECT_CHECK_RESULT_V1",
                    "project_manifest_hash": project.manifest_hash,
                    "project_input_hash": project.project_input_hash,
                    "manifest_default_target": project.default_target,
                    "source_count": len(project.sources),
                    "sources": list(project.relative_sources),
                }
            )
            print(canonical_json(result))
            return 0

        if arguments.command == "link":
            analysis = analyze_v1_paths(arguments.sources)
            write_text_artifact_v1(arguments.output, analysis.linked_program.canonical_json)
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_V1_LINK_RESULT_V2",
                        "status": "PASS_CANDIDATE",
                        "program_id": analysis.plan.program_id,
                        "linked_semantic_hash": analysis.linked_program.semantic_hash,
                        "output": Path(arguments.output).as_posix(),
                        "artifact_commit": "ATOMIC_SINGLE_PATH_REPLACE_V1",
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

        if arguments.command == "build":
            project = load_v1_project(arguments.project)
            target = arguments.target or project.default_target
            compilation = _select_compilation(list(project.source_paths), target)
            # Build metadata is not semantic authority, but the exact finite
            # input set must remain stable across one governed build operation.
            verify_v1_project_inputs(project)
            selected = compilation.target
            receipt_summary, receipt_content = _build_receipt(
                compilation.analysis.linked_program,
                selected,
                arguments.receipt,
            )
            write_compilation_artifacts_v1(
                arguments.output,
                selected.canonical_json,
                receipt_path=arguments.receipt,
                receipt_content=receipt_content,
            )
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_V1_PROJECT_BUILD_RESULT_V2",
                        "status": "PASS_CANDIDATE",
                        "program_id": compilation.analysis.plan.program_id,
                        "project_manifest_hash": project.manifest_hash,
                        "project_input_hash": project.project_input_hash,
                        "manifest_default_target": project.default_target,
                        "requested_target_override": arguments.target,
                        "effective_target": target,
                        "target_ir_schema": selected.ir["schema"],
                        "linked_semantic_hash": compilation.analysis.linked_program.semantic_hash,
                        "target_ir_semantic_hash": selected.ir["semantic_hash"],
                        "source_count": len(project.sources),
                        "output": Path(arguments.output).as_posix(),
                        "lowering_receipt": receipt_summary,
                        "artifact_commit": ARTIFACT_COMMIT_POLICY_V1,
                        "stable_release": False,
                    }
                )
            )
            return 0

        if arguments.command == "lower-irv2":
            compilation = compile_v1_paths_to_ir_v2(arguments.sources)
            return _write_compilation_result(
                compilation,
                arguments.output,
                arguments.receipt,
                "TEV_SCRIPT_V1_IRV2_LOWER_RESULT_V3",
            )

        if arguments.command == "lower-irv3":
            compilation = compile_v1_paths_to_ir_v3(arguments.sources)
            return _write_compilation_result(
                compilation,
                arguments.output,
                arguments.receipt,
                "TEV_SCRIPT_V1_IRV3_LOWER_RESULT_V3",
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


def _check_result(analysis) -> dict[str, object]:
    return {
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


def _select_compilation(sources, target: str):
    if target == "irv2":
        return compile_v1_paths_to_ir_v2(sources)
    if target == "irv3":
        return compile_v1_paths_to_ir_v3(sources)
    if target == "auto":
        return compile_v1_paths_auto(sources)
    raise TevScriptError(
        "TEVS_V1_CLI_TARGET",
        f"unsupported V1 compilation target {target!r}",
    )


def _compile_command(
    sources: list[str],
    target: str,
    output: str,
    receipt_path: str | None,
) -> int:
    compilation = _select_compilation(sources, target)
    selected = compilation.target
    linked = compilation.analysis.linked_program
    receipt_summary, receipt_content = _build_receipt(linked, selected, receipt_path)
    write_compilation_artifacts_v1(
        output,
        selected.canonical_json,
        receipt_path=receipt_path,
        receipt_content=receipt_content,
    )

    print(
        canonical_json(
            {
                "schema": "TEV_SCRIPT_V1_COMPILE_RESULT_V3",
                "status": "PASS_CANDIDATE",
                "program_id": compilation.analysis.plan.program_id,
                "requested_target": target,
                "target_ir_schema": selected.ir["schema"],
                "linked_semantic_hash": linked.semantic_hash,
                "target_ir_semantic_hash": selected.ir["semantic_hash"],
                "output": Path(output).as_posix(),
                "lowering_receipt": receipt_summary,
                "artifact_commit": ARTIFACT_COMMIT_POLICY_V1,
                "stable_release": False,
            }
        )
    )
    return 0


def _build_receipt(linked, target, receipt_path: str | None):
    if receipt_path is None:
        return None, None
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
    return (
        {
            "schema": bundle.receipt["schema"],
            "profile": bundle.receipt["profile"],
            "receipt_hash": bundle.receipt_hash,
            "output": Path(receipt_path).as_posix(),
        },
        bundle.canonical_json,
    )


def _write_compilation_result(
    compilation,
    output: str,
    receipt_path: str | None,
    result_schema: str,
) -> int:
    selected = compilation.target
    linked = compilation.analysis.linked_program
    receipt_summary, receipt_content = _build_receipt(linked, selected, receipt_path)
    write_compilation_artifacts_v1(
        output,
        selected.canonical_json,
        receipt_path=receipt_path,
        receipt_content=receipt_content,
    )
    print(
        canonical_json(
            {
                "schema": result_schema,
                "status": "PASS_CANDIDATE",
                "program_id": compilation.analysis.plan.program_id,
                "linked_semantic_hash": linked.semantic_hash,
                "target_ir_schema": selected.ir["schema"],
                "target_ir_semantic_hash": selected.ir["semantic_hash"],
                "output": Path(output).as_posix(),
                "lowering_receipt": receipt_summary,
                "artifact_commit": ARTIFACT_COMMIT_POLICY_V1,
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


def _add_target(parser: argparse.ArgumentParser, *, default: str | None) -> None:
    parser.add_argument(
        "--target",
        choices=("auto", "irv2", "irv3"),
        default=default,
        help=(
            "auto selects IR V2 only when the linked program is losslessly "
            "erasable to that profile; otherwise it selects IR V3"
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
