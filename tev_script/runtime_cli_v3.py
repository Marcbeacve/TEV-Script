from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .artifact_write_v1 import write_text_artifact_v1
from .canonical import canonical_json
from .diagnostics import TevScriptError
from .ir_v3_conformance import run_ir_v3_conformance
from .ir_v3_validation import validate_program_ir_v3
from .json_io import load_strict_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tev_script.runtime_cli_v3",
        description=(
            "Read-only TEV Script IR V3 validation/conformance tooling. "
            "This CLI never supplies arbitrary host capabilities and "
            "does not act as a generic production execution host."
        ),
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    describe = subcommands.add_parser(
        "describe",
        help="validate IR V3 and print a compact canonical program summary",
    )
    describe.add_argument("ir")

    validate = subcommands.add_parser(
        "validate",
        help="strictly parse and validate TEV_SCRIPT_PROGRAM_IR_V3",
    )
    validate.add_argument("ir")
    validate.add_argument(
        "--source-hash",
        help="optional expected linked/source semantic hash",
    )

    conformance = subcommands.add_parser(
        "conformance",
        help="run a scripted TEV_SCRIPT_IR_V3_SCENARIO_V1 and emit its receipt",
    )
    conformance.add_argument("ir")
    conformance.add_argument("scenario")
    conformance.add_argument("--output", "-o")
    conformance.add_argument(
        "--print-receipt",
        action="store_true",
        help="print canonical receipt JSON after the compact result",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        program = _load_object(arguments.ir, "IR")

        if arguments.command == "describe":
            table = validate_program_ir_v3(program)
            capabilities: set[str] = set()
            handler_count = 0
            state_count = 0
            for entity in program["entities"]:
                state_count += len(entity["states"])
                handler_count += len(entity["handlers"])
                capabilities.update(
                    item["capability_id"] for item in entity["capabilities"]
                )
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_IR_V3_DESCRIPTION_V1",
                        "status": "PASS_CANDIDATE",
                        "program_id": program["program_id"],
                        "semantic_hash": program["semantic_hash"],
                        "source_schema": program["source_schema"],
                        "source_semantic_hash": program["source_semantic_hash"],
                        "type_count": len(table.descriptors),
                        "entity_count": len(program["entities"]),
                        "state_count": state_count,
                        "handler_count": handler_count,
                        "capability_ids": sorted(capabilities),
                        "maximum_value_nesting": table.maximum_value_nesting,
                        "host_object_references": False,
                    }
                )
            )
            return 0

        if arguments.command == "validate":
            validate_program_ir_v3(
                program,
                expected_source_semantic_hash=arguments.source_hash,
            )
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_IR_V3_VALIDATION_RESULT_V1",
                        "status": "PASS_CANDIDATE",
                        "program_id": program["program_id"],
                        "semantic_hash": program["semantic_hash"],
                        "source_semantic_hash": program["source_semantic_hash"],
                    }
                )
            )
            return 0

        if arguments.command == "conformance":
            scenario = _load_object(arguments.scenario, "scenario")
            bundle = run_ir_v3_conformance(program, scenario)
            output_path: str | None = None
            if arguments.output:
                write_text_artifact_v1(arguments.output, bundle.canonical_json)
                output_path = Path(arguments.output).as_posix()
            print(
                canonical_json(
                    {
                        "schema": "TEV_SCRIPT_IR_V3_CONFORMANCE_RUN_RESULT_V1",
                        "status": "PASS_CANDIDATE",
                        "program_semantic_hash": program["semantic_hash"],
                        "scenario_id": scenario["scenario_id"],
                        "receipt_hash": bundle.receipt_hash,
                        "output": output_path,
                    }
                )
            )
            if arguments.print_receipt:
                print(bundle.canonical_json)
            return 0

        raise AssertionError(arguments.command)
    except TevScriptError as exc:
        print(
            canonical_json(
                {
                    "schema": "TEV_SCRIPT_IR_V3_TOOL_DIAGNOSTIC_V1",
                    "status": "FAIL",
                    "diagnostic": exc.diagnostic.to_dict(),
                }
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(
            canonical_json(
                {
                    "schema": "TEV_SCRIPT_IR_V3_TOOL_HOST_ERROR_V1",
                    "status": "FAIL",
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
            ),
            file=sys.stderr,
        )
        return 2


def _load_object(path: str, label: str) -> dict[str, object]:
    value = load_strict_json(Path(path))
    if not isinstance(value, dict):
        raise TevScriptError(
            "TEVS_IR_V3_TOOL_JSON_ROOT",
            f"{label} JSON root must be an object",
        )
    return value


if __name__ == "__main__":
    raise SystemExit(main())
