from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

from .descriptor_v31 import v31_descriptor
from .diagnostics import TevScriptError
from .json_io import load_strict_json
from .omega_kernel_v1 import omega_wire, validate_continuation_receipt
from .omega_semantic_basis_v1 import validate_semantic_field
from .program_ir_v5_total import (
    canonical_total_core_program_bytes,
    validate_total_core_program,
    validate_verified_proof_admission,
)
from .runtime_v5_total import (
    TotalCoreCheckpointV1,
    initial_total_core_checkpoint,
    run_total_core_quantum,
    validate_total_core_checkpoint,
)
from .source_total_core_v31 import compile_total_core_v31

ARTIFACT_COMMIT_POLICY_V31 = "ATOMIC_SINGLE_PATH_REPLACE_V1"
MAX_CLI_EPOCHS_V31 = 1_000_000


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _atomic_write(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
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


def _read_source(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TevScriptError(
            "TEVS_V31_SOURCE_UTF8",
            "source must be valid UTF-8",
        ) from error


def _named_paths(values: list[str], *, code: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for raw in values:
        if "=" not in raw:
            raise TevScriptError(code, "binding must be NAME=PATH")
        name, path_text = raw.split("=", 1)
        if not name or not path_text:
            raise TevScriptError(code, "binding must contain non-empty NAME and PATH")
        if name in result:
            raise TevScriptError(code, f"duplicate binding for {name}")
        result[name] = Path(path_text)
    return result


def _checkpoint_to_mapping(value: TotalCoreCheckpointV1) -> dict[str, Any]:
    return {
        "schema": value.schema,
        "program_hash": value.program_hash,
        "field": {
            "schema": value.field.schema,
            "profile": value.field.profile,
            "facts": [
                {
                    "relation": fact.relation,
                    "arguments": list(fact.arguments),
                    "fact_hash": fact.fact_hash,
                }
                for fact in value.field.facts
            ],
            "field_hash": value.field.field_hash,
        },
        "pc": value.pc,
        "next_epoch_index": value.next_epoch_index,
        "previous_continuation": (
            None
            if value.previous_continuation is None
            else omega_wire(value.previous_continuation)
        ),
        "halted": value.halted,
        "checkpoint_hash": value.checkpoint_hash,
    }


def _load_checkpoint(program: Any, path: Path) -> TotalCoreCheckpointV1:
    raw = load_strict_json(path)
    if not isinstance(raw, Mapping):
        raise TevScriptError(
            "TEVS_V31_CLI_CHECKPOINT",
            "checkpoint must be a JSON object",
        )
    required = {
        "schema",
        "program_hash",
        "field",
        "pc",
        "next_epoch_index",
        "previous_continuation",
        "halted",
        "checkpoint_hash",
    }
    if set(raw) != required:
        raise TevScriptError(
            "TEVS_V31_CLI_CHECKPOINT",
            "checkpoint field set mismatch",
        )
    previous_raw = raw["previous_continuation"]
    previous = (
        None
        if previous_raw is None
        else validate_continuation_receipt(previous_raw)
    )
    candidate = TotalCoreCheckpointV1(
        raw["schema"],
        raw["program_hash"],
        validate_semantic_field(raw["field"]),
        raw["pc"],
        raw["next_epoch_index"],
        previous,
        raw["halted"],
        raw["checkpoint_hash"],
    )
    return validate_total_core_checkpoint(program, candidate)


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
        prog="tev-script-v31",
        description="TEVScript MAX 3.1 Total-Core compiler/runtime",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    descriptor = commands.add_parser(
        "descriptor",
        help="report the TEVScript MAX 3.1 Total-Core descriptor",
    )
    descriptor.set_defaults(handler=_descriptor)

    check = commands.add_parser(
        "check-total",
        help="check one TEVScript 3.1 Total-Core project without writing an artifact",
    )
    _add_project_arguments(check, output=False)
    check.set_defaults(handler=_check_total)

    compile_cmd = commands.add_parser(
        "compile-total",
        help="compile one TEVScript 3.1 Total-Core project",
    )
    _add_project_arguments(compile_cmd, output=True)
    compile_cmd.set_defaults(handler=_compile_total)

    validate = commands.add_parser(
        "validate-total",
        help="validate canonical Total-Core Program IR V5",
    )
    validate.add_argument("program_ir", type=Path)
    validate.set_defaults(handler=_validate_total)

    run = commands.add_parser(
        "run-total",
        help="run Total-Core from its initial checkpoint",
    )
    run.add_argument("program_ir", type=Path)
    run.add_argument("--checkpoint-output", type=Path)
    run.add_argument("--epochs", type=int, default=1)
    run.set_defaults(handler=_run_total)

    resume = commands.add_parser(
        "resume-total",
        help="resume Total-Core from a canonical checkpoint",
    )
    resume.add_argument("program_ir", type=Path)
    resume.add_argument("--checkpoint", type=Path, required=True)
    resume.add_argument("--checkpoint-output", type=Path)
    resume.add_argument("--epochs", type=int, default=1)
    resume.set_defaults(handler=_resume_total)

    return parser


def _descriptor(_arguments: argparse.Namespace) -> int:
    print(_canonical_json(v31_descriptor()))
    return 0


def _compile_program_from_arguments(arguments: argparse.Namespace):
    unit_paths = _named_paths(
        list(arguments.unit),
        code="TEVS_V31_CLI_UNIT_BINDING",
    )
    effect_paths = _named_paths(
        list(arguments.effect_input),
        code="TEVS_V31_CLI_EFFECT_BINDING",
    )
    unit_sources = {name: _read_source(path) for name, path in unit_paths.items()}
    effect_inputs: dict[str, dict[str, Any]] = {}
    for name, path in effect_paths.items():
        raw = load_strict_json(path)
        if not isinstance(raw, dict):
            raise TevScriptError(
                "TEVS_V31_CLI_EFFECT_INPUT",
                f"effect input for {name} must be a JSON object",
            )
        effect_inputs[name] = raw

    proofs = []
    for path in arguments.proof_admission:
        raw = load_strict_json(path)
        if not isinstance(raw, dict):
            raise TevScriptError(
                "TEVS_V31_CLI_PROOF_ADMISSION",
                "proof admission must be a JSON object",
            )
        proofs.append(validate_verified_proof_admission(raw))

    return compile_total_core_v31(
        _read_source(arguments.source),
        unit_sources=unit_sources,
        effect_inputs=effect_inputs or None,
        proof_admissions=tuple(proofs),
    )


def _check_total(arguments: argparse.Namespace) -> int:
    program = _compile_program_from_arguments(arguments)
    print(
        _canonical_json(
            {
                "schema": "TEV_SCRIPT_V31_CHECK_TOTAL_RESULT_V1",
                "status": "PASS",
                "language_version": "3.1.0",
                "profile": "total_core",
                "program_ir_schema": program.schema,
                "program_ir_hash": program.program_hash,
                "source_semantic_hash": program.source_semantic_hash,
            }
        )
    )
    return 0


def _compile_total(arguments: argparse.Namespace) -> int:
    program = _compile_program_from_arguments(arguments)
    _atomic_write(
        arguments.output,
        canonical_total_core_program_bytes(program) + b"\n",
    )
    print(
        _canonical_json(
            {
                "schema": "TEV_SCRIPT_V31_COMPILE_TOTAL_RESULT_V1",
                "status": "PASS",
                "language_version": "3.1.0",
                "profile": "total_core",
                "program_ir_schema": program.schema,
                "program_ir_hash": program.program_hash,
                "source_semantic_hash": program.source_semantic_hash,
                "output": arguments.output.as_posix(),
                "artifact_commit": ARTIFACT_COMMIT_POLICY_V31,
                "stable": False,
            }
        )
    )
    return 0


def _load_program(path: Path):
    raw = load_strict_json(path)
    if not isinstance(raw, dict):
        raise TevScriptError(
            "TEVS_V31_CLI_PROGRAM_IR",
            "Program IR must be a JSON object",
        )
    return validate_total_core_program(raw)


def _validate_total(arguments: argparse.Namespace) -> int:
    program = _load_program(arguments.program_ir)
    print(
        _canonical_json(
            {
                "schema": "TEV_SCRIPT_V31_VALIDATE_TOTAL_RESULT_V1",
                "status": "PASS",
                "language_version": "3.1.0",
                "profile": "total_core",
                "program_ir_hash": program.program_hash,
                "source_semantic_hash": program.source_semantic_hash,
            }
        )
    )
    return 0


def _run_epochs(
    program: Any,
    checkpoint: TotalCoreCheckpointV1,
    *,
    epochs: int,
    checkpoint_output: Path | None,
) -> int:
    if (
        isinstance(epochs, bool)
        or not isinstance(epochs, int)
        or not 1 <= epochs <= MAX_CLI_EPOCHS_V31
    ):
        raise TevScriptError(
            "TEVS_V31_CLI_EPOCHS",
            f"epochs must be in 1..{MAX_CLI_EPOCHS_V31}",
        )

    last = None
    executed = 0
    current = checkpoint
    for _ in range(epochs):
        last = run_total_core_quantum(program, current)
        current = last.next_checkpoint
        executed += 1
        if last.status == "HALTED":
            break
    assert last is not None

    if checkpoint_output is not None:
        _atomic_write(
            checkpoint_output,
            (_canonical_json(_checkpoint_to_mapping(current)) + "\n").encode("utf-8"),
        )

    print(
        _canonical_json(
            {
                "schema": "TEV_SCRIPT_V31_RUN_TOTAL_RESULT_V1",
                "status": last.status,
                "program_ir_hash": program.program_hash,
                "source_semantic_hash": program.source_semantic_hash,
                "epochs_executed": executed,
                "last_epoch_index": last.continuation.epoch_index,
                "continuation_hash": last.continuation.continuation_hash,
                "field_hash": last.field.field_hash,
                "checkpoint_hash": current.checkpoint_hash,
                "checkpoint_output": (
                    None
                    if checkpoint_output is None
                    else checkpoint_output.as_posix()
                ),
            }
        )
    )
    return 0


def _run_total(arguments: argparse.Namespace) -> int:
    program = _load_program(arguments.program_ir)
    return _run_epochs(
        program,
        initial_total_core_checkpoint(program),
        epochs=arguments.epochs,
        checkpoint_output=arguments.checkpoint_output,
    )


def _resume_total(arguments: argparse.Namespace) -> int:
    program = _load_program(arguments.program_ir)
    checkpoint = _load_checkpoint(program, arguments.checkpoint)
    return _run_epochs(
        program,
        checkpoint,
        epochs=arguments.epochs,
        checkpoint_output=arguments.checkpoint_output,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        try:
            arguments = build_parser().parse_args(argv)
        except SystemExit as error:
            return int(error.code)
        return int(arguments.handler(arguments))
    except TevScriptError as error:
        print(
            _canonical_json(
                {
                    "schema": "TEV_SCRIPT_V31_DIAGNOSTIC_V1",
                    "status": "FAIL",
                    "diagnostic": error.diagnostic.to_dict(),
                }
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        print(
            _canonical_json(
                {
                    "schema": "TEV_SCRIPT_V31_HOST_IO_ERROR_V1",
                    "status": "FAIL",
                    "error": type(error).__name__,
                    "message": str(error),
                }
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
