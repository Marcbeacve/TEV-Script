from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from .descriptor_v3 import v3_descriptor
from .diagnostics import TevScriptError
from .json_io import load_strict_json
from .program_ir_v5_semantic import (
    PROGRAM_SCHEMA,
    checkpoint_to_object,
    initial_process_checkpoint,
    program_to_object,
    validate_process_checkpoint,
    validate_semantic_process_program,
)
from .runtime_v5_semantic import run_semantic_quantum
from .source_semantic_process_v3 import compile_semantic_process_v3, parse_semantic_process_v3

ARTIFACT_COMMIT_POLICY_V3 = "ATOMIC_SINGLE_PATH_REPLACE_V1"
MAX_CLI_EPOCHS = 1_000_000


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _atomic_write(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tev-script-v3", description="TEVScript MAX 3.0 candidate compiler/runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    describe = commands.add_parser("describe", help="report V3 candidate language/runtime surface")
    describe.set_defaults(handler=_describe)
    check = commands.add_parser("check", help="parse/check native V3 semantic-process source")
    check.add_argument("source", type=Path)
    check.set_defaults(handler=_check)
    compile_cmd = commands.add_parser("compile", help="compile native V3 source to canonical Program IR V5")
    compile_cmd.add_argument("source", type=Path)
    compile_cmd.add_argument("--output", "-o", type=Path, required=True)
    compile_cmd.set_defaults(handler=_compile)
    run = commands.add_parser("run", help="execute a bounded number of V3 semantic-process epochs")
    run.add_argument("program_ir", type=Path)
    run.add_argument("--checkpoint", type=Path)
    run.add_argument("--checkpoint-output", type=Path)
    run.add_argument("--epochs", type=int, default=1)
    run.set_defaults(handler=_run)
    v2 = commands.add_parser("v2", help="explicit passthrough to unchanged TEV Script V2 CLI")
    v2.add_argument("v2_args", nargs=argparse.REMAINDER)
    v2.set_defaults(handler=_v2)
    return parser


def _describe(_arguments: argparse.Namespace) -> int:
    print(_canonical_json(v3_descriptor()))
    return 0


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TevScriptError("TEVS_V3_SOURCE_UTF8", "source must be valid UTF-8") from error


def _check(arguments: argparse.Namespace) -> int:
    source = _read_source(arguments.source)
    parsed = parse_semantic_process_v3(source)
    program = compile_semantic_process_v3(source)
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V3_CHECK_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "language_version": "3.0.0",
        "profile": "semantic_process",
        "program_id": parsed.program_id,
        "source_semantic_hash": parsed.source_semantic_hash,
        "program_ir_schema": program.schema,
        "program_ir_hash": program.program_hash,
        "stable": False,
    }))
    return 0


def _compile(arguments: argparse.Namespace) -> int:
    source_text = _read_source(arguments.source)
    program = compile_semantic_process_v3(source_text)
    from .translation_validation_v3 import validate_source_to_ir_v3
    validation = validate_source_to_ir_v3(source_text, program)
    if validation.status != "PASS":
        raise TevScriptError("TEVS_V3_CLI_TRANSLATION_VALIDATION", "independent Source-to-IR validation rejected compiler output")
    payload = program_to_object(program)
    _atomic_write(arguments.output, (_canonical_json(payload) + "\n").encode("utf-8"))
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V3_COMPILE_RESULT_V1",
        "status": "PASS_CANDIDATE",
        "language_version": "3.0.0",
        "profile": "semantic_process",
        "program_ir_schema": program.schema,
        "program_ir_hash": program.program_hash,
        "source_semantic_hash": program.source_semantic_hash,
        "output": arguments.output.as_posix(),
        "artifact_commit": ARTIFACT_COMMIT_POLICY_V3,
        "translation_validation_status": validation.status,
        "translation_validation_receipt_hash": validation.receipt_hash,
        "stable": False,
    }))
    return 0


def _run(arguments: argparse.Namespace) -> int:
    if isinstance(arguments.epochs, bool) or not isinstance(arguments.epochs, int) or not 1 <= arguments.epochs <= MAX_CLI_EPOCHS:
        raise TevScriptError("TEVS_V3_CLI_EPOCHS", f"epochs must be in 1..{MAX_CLI_EPOCHS}")
    raw = load_strict_json(arguments.program_ir)
    if not isinstance(raw, dict) or raw.get("schema") != PROGRAM_SCHEMA:
        raise TevScriptError("TEVS_V3_CLI_PROGRAM_IR", "run requires V3 semantic-process Program IR V5")
    program = validate_semantic_process_program(raw)
    if arguments.checkpoint is None:
        checkpoint = initial_process_checkpoint(program)
    else:
        checkpoint = validate_process_checkpoint(program, load_strict_json(arguments.checkpoint))
    last = None
    executed = 0
    for _ in range(arguments.epochs):
        last = run_semantic_quantum(program, checkpoint)
        checkpoint = last.next_checkpoint
        executed += 1
        if last.status == "HALTED":
            break
    assert last is not None
    if arguments.checkpoint_output is not None:
        _atomic_write(
            arguments.checkpoint_output,
            (_canonical_json(checkpoint_to_object(checkpoint, program)) + "\n").encode("utf-8"),
        )
    print(_canonical_json({
        "schema": "TEV_SCRIPT_V3_RUN_RESULT_V1",
        "status": last.status,
        "program_ir_hash": program.program_hash,
        "source_semantic_hash": program.source_semantic_hash,
        "epochs_executed": executed,
        "last_epoch_index": last.continuation.epoch_index,
        "continuation_hash": last.continuation.continuation_hash,
        "field_hash": last.field.field_hash,
        "checkpoint_hash": checkpoint.checkpoint_hash,
        "checkpoint_output": None if arguments.checkpoint_output is None else arguments.checkpoint_output.as_posix(),
        "stable": False,
    }))
    return 0


def _v2(arguments: argparse.Namespace) -> int:
    from . import cli_v2
    if not arguments.v2_args:
        raise TevScriptError("TEVS_V3_CLI_V2_ARGS", "v2 passthrough requires V2 command arguments")
    return int(cli_v2.main(list(arguments.v2_args)))


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = build_parser().parse_args(argv)
        return int(arguments.handler(arguments))
    except TevScriptError as error:
        print(_canonical_json({
            "schema": "TEV_SCRIPT_V3_DIAGNOSTIC_V1",
            "status": "FAIL",
            "diagnostic": error.diagnostic.to_dict(),
        }), file=sys.stderr)
        return 2
    except (OSError, UnicodeError, ValueError) as error:
        print(_canonical_json({
            "schema": "TEV_SCRIPT_V3_HOST_IO_ERROR_V1",
            "status": "FAIL",
            "error": type(error).__name__,
            "message": str(error),
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
