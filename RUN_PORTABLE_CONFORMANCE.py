from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tev_script.json_io import load_strict_json

ROOT = Path(__file__).resolve().parent
VECTORS = (
    ("player", "Player.tevs"),
    ("matrix", "ConformanceMatrix.tevs"),
    ("player-idle", "Player.tevs"),
    ("event-chain", "EventChain.tevs"),
)


def emit_text(text: str, *, stream: object = sys.stdout) -> None:
    if not text:
        return
    encoding = getattr(stream, "encoding", None) or "utf-8"
    safe = text.encode(encoding, errors="backslashreplace").decode(encoding)
    stream.write(safe)
    stream.flush()


def run(arguments: list[str], *, cwd: Path = ROOT) -> str:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "command_failed:" + " ".join(arguments) + "\n"
            + completed.stdout[-4000:] + "\n" + completed.stderr[-4000:]
        )
    emit_text(completed.stdout)
    emit_text(completed.stderr, stream=sys.stderr)
    return completed.stdout


def validate_schemas() -> None:
    try:
        import jsonschema
    except ImportError:
        print("JSON_SCHEMA_VALIDATION=SKIPPED_DEPENDENCY_UNAVAILABLE")
        return

    program_schema = load_strict_json(
        ROOT / "schemas" / "tev_script_program_ir_v2.schema.json"
    )
    scenario_schema = load_strict_json(
        ROOT / "schemas" / "tev_script_conformance_scenario_v1.schema.json"
    )
    receipt_schema = load_strict_json(
        ROOT / "schemas" / "tev_script_conformance_receipt_v1.schema.json"
    )
    program_validator = jsonschema.Draft202012Validator(program_schema)
    scenario_validator = jsonschema.Draft202012Validator(scenario_schema)
    receipt_validator = jsonschema.Draft202012Validator(receipt_schema)

    for vector_id, source_name in VECTORS:
        ir_name = source_name + ".ir.json"
        program = load_strict_json(ROOT / "examples" / ir_name)
        scenario = load_strict_json(
            ROOT / "conformance" / f"{vector_id}.scenario.json"
        )
        receipt = load_strict_json(
            ROOT / "conformance" / f"{vector_id}.expected.json"
        )
        program_validator.validate(program)
        scenario_validator.validate(scenario)
        receipt_validator.validate(receipt)
    print("STRICT_JSON_INPUT_BOUNDARY=PASS")
    print("JSON_SCHEMA_VALIDATION=PASS")


def csharp_brace_balance(text: str) -> int:
    balance = 0
    index = 0
    state = "code"
    escaped = False
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if current == '"':
                state = "string"
            elif current == "'":
                state = "character"
            elif current == "/" and following == "/":
                state = "line_comment"
                index += 1
            elif current == "/" and following == "*":
                state = "block_comment"
                index += 1
            elif current == "{":
                balance += 1
            elif current == "}":
                balance -= 1
        elif state in {"string", "character"}:
            closing = '"' if state == "string" else "'"
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == closing:
                state = "code"
        elif state == "line_comment":
            if current == "\n":
                state = "code"
        elif state == "block_comment":
            if current == "*" and following == "/":
                state = "code"
                index += 1
        index += 1
    if state not in {"code", "line_comment"}:
        raise RuntimeError("csharp_lexical_state_unclosed:" + state)
    return balance


def validate_csharp_source() -> None:
    source_root = ROOT / "runtimes" / "csharp" / "TevScript.Core"
    files = sorted(source_root.glob("*.cs"))
    if len(files) < 4:
        raise RuntimeError("csharp_source_file_set_incomplete")
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    forbidden = (
        "UnityEngine",
        "Marcbeacve.TevLnu.Core",
        "System.Reflection.Emit",
        "Microsoft.CSharp",
    )
    for marker in forbidden:
        if marker in combined:
            raise RuntimeError("csharp_forbidden_dependency:" + marker)
    required = (
        "TEV_SCRIPT_PROGRAM_IR_V2",
        "public sealed class TevScriptRuntime",
        "public interface ITevScriptCapability",
        "System.Numerics",
        "TevJson.Hash",
        "TevRational",
        "public sealed class TevContractException",
    )
    for marker in required:
        if marker not in combined:
            raise RuntimeError("csharp_marker_missing:" + marker)
    for path in files:
        text = path.read_text(encoding="utf-8")
        if csharp_brace_balance(text) != 0:
            raise RuntimeError("csharp_brace_mismatch:" + path.name)
    project = source_root / "TevScript.Core.csproj"
    if not project.is_file():
        raise RuntimeError("csharp_project_missing")
    print("CSHARP_PORTABLE_STATIC_BOUNDARY=PASS")
    print("CSHARP_COMPILATION=NOT_PROBED_BY_PORTABLE_RUNNER")


def validate_receipt_parity() -> dict[str, dict[str, str]]:
    hashes: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory(prefix="tev-script-conformance-") as temporary:
        temporary_root = Path(temporary)
        for vector_id, source_name in VECTORS:
            python_receipt = temporary_root / f"{vector_id}.python.receipt.json"
            js_receipt = temporary_root / f"{vector_id}.javascript.receipt.json"
            scenario_path = f"conformance/{vector_id}.scenario.json"
            run([
                sys.executable,
                "-m",
                "tev_script.cli",
                "conformance",
                f"examples/{source_name}",
                scenario_path,
                "--output",
                str(python_receipt),
            ])
            js_receipt.write_bytes(
                run([
                    "node",
                    "javascript/src/run-conformance.mjs",
                    scenario_path,
                ]).encode("utf-8")
            )
            if python_receipt.read_bytes() != js_receipt.read_bytes():
                raise RuntimeError(
                    f"python_javascript_receipt_mismatch:{vector_id}"
                )
            expected = ROOT / "conformance" / f"{vector_id}.expected.json"
            if python_receipt.read_bytes() != expected.read_bytes():
                raise RuntimeError(
                    f"receipt_does_not_match_authoritative_vector:{vector_id}"
                )
            receipt = load_strict_json(expected)
            hashes[vector_id] = {
                "program_hash": receipt["program_hash"],
                "receipt_hash": receipt["receipt_hash"],
            }
    print("CONFORMANCE_SCENARIOS=" + str(len(VECTORS)))
    print("PYTHON_JAVASCRIPT_BYTE_PARITY=PASS")
    return hashes


def main() -> int:
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    if shutil.which("node") is None:
        raise RuntimeError("node_runtime_required_for_portable_conformance")
    run(["node", "--test", "javascript/test/runtime.test.mjs"])

    hashes = validate_receipt_parity()
    validate_schemas()
    validate_csharp_source()

    for vector_id in sorted(hashes):
        prefix = vector_id.upper()
        print(prefix + "_PROGRAM_HASH=" + hashes[vector_id]["program_hash"])
        print(prefix + "_RECEIPT_HASH=" + hashes[vector_id]["receipt_hash"])
    print("PROGRAM_HASH=" + hashes["player"]["program_hash"])
    print("RECEIPT_HASH=" + hashes["player"]["receipt_hash"])
    print("TEV_SCRIPT_PORTABLE_V0_2=PASS_PYTHON_JAVASCRIPT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
