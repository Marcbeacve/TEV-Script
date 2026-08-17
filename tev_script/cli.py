from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .capability_catalog import load_capability_catalog
from .canonical import canonical_json
from .cli_v31 import main as v31_main
from .compiler import compile_path
from .conformance import run_conformance
from .descriptor_v31 import v31_descriptor
from .json_io import load_strict_json
from .platform_conformance import run_platform_conformance
from .platform_tooling import describe_current_platform, platform_check
from .version import PACKAGE_VERSION


def _add_project_arguments(parser: argparse.ArgumentParser, *, output: bool) -> None:
    parser.add_argument("source", type=Path)
    parser.add_argument("--unit", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument(
        "--effect-input",
        action="append",
        default=[],
        metavar="NAME=JSON",
    )
    parser.add_argument(
        "--proof-admission",
        action="append",
        default=[],
        type=Path,
        metavar="JSON",
    )
    if output:
        parser.add_argument("--output", "-o", type=Path, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tev-script",
        description="Current TEVScript 3.1 Total-Core platform entry point",
    )
    parser.add_argument("--version", action="version", version=PACKAGE_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    describe = commands.add_parser(
        "describe",
        help="report current package/language/profile identity and boundaries",
    )
    describe.set_defaults(handler=_describe_current)

    descriptor = commands.add_parser(
        "descriptor",
        help="report the current TEVScript 3.1 Total-Core descriptor",
    )
    descriptor.set_defaults(handler=_descriptor_current)

    check = commands.add_parser(
        "check",
        help="check a TEVScript 3.1 Total-Core project without writing IR",
    )
    _add_project_arguments(check, output=False)
    check.set_defaults(handler=_check_current)

    compile_command = commands.add_parser(
        "compile",
        help="compile a TEVScript 3.1 Total-Core project to canonical Program IR V5",
    )
    _add_project_arguments(compile_command, output=True)
    compile_command.set_defaults(handler=_compile_current)

    run = commands.add_parser(
        "run",
        help="run canonical Total-Core Program IR V5",
    )
    run.add_argument("program_ir", type=Path)
    run.add_argument("--checkpoint-output", type=Path)
    run.add_argument("--epochs", type=int, default=1)
    run.set_defaults(handler=_run_current)

    conformance = commands.add_parser(
        "conformance",
        help="run the content-addressed TEVScript 3.1 platform conformance manifest",
    )
    conformance.add_argument("--root", type=Path, default=Path.cwd())
    conformance.set_defaults(handler=_conformance_current)

    platform = commands.add_parser(
        "platform-check",
        help="validate current platform identity/spec/version/tooling gates",
    )
    platform.add_argument("--root", type=Path, default=Path.cwd())
    platform.set_defaults(handler=_platform_check)
    return parser


def _canonical_print(value: object) -> None:
    print(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )


def _project_argv(arguments: argparse.Namespace, command: str) -> list[str]:
    result = [command, str(arguments.source)]
    for value in arguments.unit:
        result.extend(("--unit", value))
    for value in arguments.effect_input:
        result.extend(("--effect-input", value))
    for path in arguments.proof_admission:
        result.extend(("--proof-admission", str(path)))
    if hasattr(arguments, "output"):
        result.extend(("--output", str(arguments.output)))
    return result


def _describe_current(_arguments: argparse.Namespace) -> int:
    _canonical_print(describe_current_platform())
    return 0


def _descriptor_current(_arguments: argparse.Namespace) -> int:
    _canonical_print(v31_descriptor())
    return 0


def _check_current(arguments: argparse.Namespace) -> int:
    return v31_main(_project_argv(arguments, "check-total"))


def _compile_current(arguments: argparse.Namespace) -> int:
    return v31_main(_project_argv(arguments, "compile-total"))


def _run_current(arguments: argparse.Namespace) -> int:
    argv = ["run-total", str(arguments.program_ir), "--epochs", str(arguments.epochs)]
    if arguments.checkpoint_output is not None:
        argv.extend(("--checkpoint-output", str(arguments.checkpoint_output)))
    return v31_main(argv)


def _conformance_current(arguments: argparse.Namespace) -> int:
    receipt = run_platform_conformance(arguments.root)
    _canonical_print(receipt)
    if receipt.get("status") == "PASS":
        return 0
    if receipt.get("status") == "HOLD":
        return 2
    return 1


def _platform_check(arguments: argparse.Namespace) -> int:
    receipt = platform_check(arguments.root)
    _canonical_print(receipt)
    return 0 if receipt["status"] == "PASS" else 1


# Internal compatibility helpers retained for historical portable tests and
# embedders that imported these private functions before the generic `tev-script`
# command was rebound to the current 3.1 Total-Core platform. They are
# deliberately NOT registered in build_parser(); the public generic CLI remains
# exclusively the current platform surface above.
def _legacy_catalog(arguments: argparse.Namespace):
    selected = getattr(arguments, "capability_catalog", None)
    return None if selected is None else load_capability_catalog(selected)


def _compile(arguments: argparse.Namespace) -> int:
    bundle = compile_path(
        arguments.source,
        capability_catalog=_legacy_catalog(arguments),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes((bundle.canonical_json + "\n").encode("utf-8"))
    _canonical_print(
        {
            "schema": "TEV_SCRIPT_COMPILE_RESULT_V1",
            "status": "PASS",
            "output": arguments.output.as_posix(),
            "semantic_hash": bundle.ir["semantic_hash"],
        }
    )
    return 0


def _conformance(arguments: argparse.Namespace) -> int:
    bundle = compile_path(
        arguments.source,
        capability_catalog=_legacy_catalog(arguments),
    )
    scenario = load_strict_json(arguments.scenario)
    receipt = run_conformance(bundle.ir, scenario)
    output = canonical_json(receipt) + "\n"
    if arguments.output is None:
        print(output, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(output.encode("utf-8"))
        _canonical_print(
            {
                "schema": "TEV_SCRIPT_CONFORMANCE_RESULT_V1",
                "status": "PASS",
                "output": arguments.output.as_posix(),
                "receipt_hash": receipt["receipt_hash"],
            }
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        return int(arguments.handler(arguments))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as error:
        _canonical_print(
            {
                "schema": "TEV_SCRIPT_CURRENT_CLI_ERROR_V1",
                "status": "FAIL",
                "error": type(error).__name__,
                "message": str(error),
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
