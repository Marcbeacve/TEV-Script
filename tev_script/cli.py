from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .compiler import (
    IR_SCHEMA,
    LANGUAGE_VERSION,
    MAX_ENTITIES,
    MAX_EVENT_CHAIN,
    MAX_HANDLERS_PER_ENTITY,
    MAX_INSTRUCTIONS_PER_HANDLER,
    MAX_SOURCE_BYTES,
    MAX_STATES_PER_ENTITY,
    compile_path,
)
from .diagnostics import TevScriptError
from .canonical import canonical_json
from .conformance import run_conformance
from .json_io import load_strict_json
from .capability_catalog import load_capability_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tev-script")
    commands = parser.add_subparsers(dest="command", required=True)

    descriptor = commands.add_parser("descriptor")
    descriptor.set_defaults(handler=_descriptor)

    check = commands.add_parser("check")
    check.add_argument("source", type=Path)
    check.add_argument("--capability-catalog", type=Path)
    check.set_defaults(handler=_check)

    compile_command = commands.add_parser("compile")
    compile_command.add_argument("source", type=Path)
    compile_command.add_argument("--output", type=Path, required=True)
    compile_command.add_argument("--capability-catalog", type=Path)
    compile_command.set_defaults(handler=_compile)

    conformance = commands.add_parser("conformance")
    conformance.add_argument("source", type=Path)
    conformance.add_argument("scenario", type=Path)
    conformance.add_argument("--output", type=Path)
    conformance.add_argument("--capability-catalog", type=Path)
    conformance.set_defaults(handler=_conformance)
    return parser


def _descriptor(_arguments: argparse.Namespace) -> int:
    payload = {
        "schema": "TEV_SCRIPT_DESCRIPTOR_V2",
        "language_version": LANGUAGE_VERSION,
        "ir_schema": IR_SCHEMA,
        "source_extension": ".tevs",
        "budgets": {
            "source_bytes": MAX_SOURCE_BYTES,
            "entities": MAX_ENTITIES,
            "states_per_entity": MAX_STATES_PER_ENTITY,
            "handlers_per_entity": MAX_HANDLERS_PER_ENTITY,
            "instructions_per_handler": MAX_INSTRUCTIONS_PER_HANDLER,
            "event_chain": MAX_EVENT_CHAIN,
        },
        "boundaries": {
            "dynamic_code": False,
            "reflection": False,
            "unbounded_loops": False,
            "runtime_source_compilation": False,
            "implicit_physical_effects": False,
        },
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0


def _catalog(arguments: argparse.Namespace):
    selected = getattr(arguments, "capability_catalog", None)
    return None if selected is None else load_capability_catalog(selected)


def _check(arguments: argparse.Namespace) -> int:
    bundle = compile_path(arguments.source, capability_catalog=_catalog(arguments))
    print(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_CHECK_RESULT_V1",
                "status": "PASS",
                "semantic_hash": bundle.ir["semantic_hash"],
                "source": arguments.source.as_posix(),
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _compile(arguments: argparse.Namespace) -> int:
    bundle = compile_path(arguments.source, capability_catalog=_catalog(arguments))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes((bundle.canonical_json + "\n").encode("utf-8"))
    print(
        json.dumps(
            {
                "schema": "TEV_SCRIPT_COMPILE_RESULT_V1",
                "status": "PASS",
                "output": arguments.output.as_posix(),
                "semantic_hash": bundle.ir["semantic_hash"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _conformance(arguments: argparse.Namespace) -> int:
    bundle = compile_path(arguments.source, capability_catalog=_catalog(arguments))
    scenario = load_strict_json(arguments.scenario)
    receipt = run_conformance(bundle.ir, scenario)
    output = canonical_json(receipt) + "\n"
    if arguments.output is None:
        print(output, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(output.encode("utf-8"))
        print(
            json.dumps(
                {
                    "schema": "TEV_SCRIPT_CONFORMANCE_RESULT_V1",
                    "status": "PASS",
                    "output": arguments.output.as_posix(),
                    "receipt_hash": receipt["receipt_hash"],
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        return int(arguments.handler(arguments))
    except TevScriptError as error:
        print(
            json.dumps(
                {
                    "schema": "TEV_SCRIPT_DIAGNOSTIC_V1",
                    "status": "HOLD",
                    "diagnostic": error.diagnostic.to_dict(),
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "schema": "TEV_SCRIPT_DIAGNOSTIC_V1",
                    "status": "HOLD",
                    "diagnostic": {
                        "code": "TEVS_CLI_FAILURE",
                        "message": str(error),
                        "span": None,
                        "hint": "",
                    },
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
