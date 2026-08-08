from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script.canonical import canonical_json  # noqa: E402
from tev_script.ir_v3_conformance import run_ir_v3_conformance  # noqa: E402
from tev_script.json_io import load_strict_json  # noqa: E402

CASES_PATH = ROOT / "conformance" / "ir-v3-validator-cases.json"
SCENARIO_PATH = ROOT / "conformance" / "ir-v3-portable.scenario.json"
CSHARP_PROJECT = ROOT / "runtimes" / "csharp" / "TevScript.V3ConformanceGate" / "TevScript.V3ConformanceGate.csproj"
CSHARP_DLL = ROOT / "runtimes" / "csharp" / "TevScript.V3ConformanceGate" / "bin" / "Release" / "net8.0" / "TevScript.V3ConformanceGate.dll"


def _run(arguments: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _fail_process(label: str, completed: subprocess.CompletedProcess[str]) -> int:
    print(label + "=FAIL")
    if completed.stdout:
        print(label + "_STDOUT=" + completed.stdout[-6000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-6000:].replace("\n", "\\n"))
    return 1


def main() -> int:
    node = shutil.which("node")
    dotnet = shutil.which("dotnet")
    if node is None:
        print("TEV_SCRIPT_IR_V3_CROSS_RUNTIME_PARITY=SKIPPED_NODE_UNAVAILABLE")
        return 0
    if dotnet is None:
        print("TEV_SCRIPT_IR_V3_CROSS_RUNTIME_PARITY=SKIPPED_DOTNET_UNAVAILABLE")
        return 0

    cases = load_strict_json(CASES_PATH)
    scenario = load_strict_json(SCENARIO_PATH)
    program = cases["valid_program"]
    python_bundle = run_ir_v3_conformance(program, scenario)

    node_tests = _run(
        [
            node,
            "--test",
            str(ROOT / "javascript" / "test" / "runtime-v3.test.mjs"),
            str(ROOT / "javascript" / "test" / "ir-v3-conformance.test.mjs"),
        ]
    )
    if node_tests.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_NODE_TESTS", node_tests)
    print("TEV_SCRIPT_IR_V3_NODE_TESTS=PASS")

    build = _run(
        [
            dotnet,
            "build",
            str(CSHARP_PROJECT),
            "--configuration",
            "Release",
            "--nologo",
            "--verbosity",
            "quiet",
        ]
    )
    if build.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_CSHARP_BUILD", build)
    if not CSHARP_DLL.exists():
        print("TEV_SCRIPT_IR_V3_CSHARP_BUILD=FAIL_DLL_MISSING")
        return 1
    print("TEV_SCRIPT_IR_V3_CSHARP_BUILD=PASS")

    csharp_self_test = _run(
        [dotnet, str(CSHARP_DLL), "--self-test", str(CASES_PATH), str(SCENARIO_PATH)]
    )
    if csharp_self_test.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_CSHARP_SELF_TEST", csharp_self_test)
    if "CSHARP_IR_V3_NEGATIVE_CORPUS=PASS" not in csharp_self_test.stdout:
        print("TEV_SCRIPT_IR_V3_CSHARP_SELF_TEST=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_CSHARP_SELF_TEST=PASS")

    with tempfile.TemporaryDirectory(prefix="tev_script_ir_v3_cross_runtime_") as temp:
        temp_root = Path(temp)
        program_path = temp_root / "program.irv3.json"
        scenario_path = temp_root / "scenario.json"
        program_path.write_text(canonical_json(program), encoding="utf-8", newline="")
        scenario_path.write_text(canonical_json(scenario), encoding="utf-8", newline="")

        node_receipt_process = _run(
            [
                node,
                str(ROOT / "javascript" / "src" / "run-ir-v3-conformance.mjs"),
                str(program_path),
                str(scenario_path),
            ]
        )
        if node_receipt_process.returncode != 0:
            return _fail_process("TEV_SCRIPT_IR_V3_NODE_RECEIPT", node_receipt_process)

        csharp_receipt_process = _run(
            [dotnet, str(CSHARP_DLL), str(program_path), str(scenario_path)]
        )
        if csharp_receipt_process.returncode != 0:
            return _fail_process("TEV_SCRIPT_IR_V3_CSHARP_RECEIPT", csharp_receipt_process)

    python_receipt = python_bundle.canonical_json
    node_receipt = node_receipt_process.stdout
    csharp_receipt = csharp_receipt_process.stdout

    if node_receipt != python_receipt:
        print("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=FAIL_BYTE_MISMATCH")
        _print_hashes(python_bundle.receipt_hash, node_receipt, csharp_receipt)
        return 1
    print("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=PASS")

    if csharp_receipt != python_receipt:
        print("TEV_SCRIPT_IR_V3_PYTHON_CSHARP_PARITY=FAIL_BYTE_MISMATCH")
        _print_hashes(python_bundle.receipt_hash, node_receipt, csharp_receipt)
        return 1
    print("TEV_SCRIPT_IR_V3_PYTHON_CSHARP_PARITY=PASS")

    if csharp_receipt != node_receipt:
        print("TEV_SCRIPT_IR_V3_JS_CSHARP_PARITY=FAIL_BYTE_MISMATCH")
        return 1
    print("TEV_SCRIPT_IR_V3_JS_CSHARP_PARITY=PASS")
    print("TEV_SCRIPT_IR_V3_CROSS_RUNTIME_RECEIPT_HASH=" + python_bundle.receipt_hash)
    print("TEV_SCRIPT_IR_V3_CROSS_RUNTIME_CANONICAL_BYTES=PASS")
    print("TEV_SCRIPT_IR_V3_CROSS_RUNTIME_PARITY=PASS")
    return 0


def _print_hashes(python_hash: str, node_receipt: str, csharp_receipt: str) -> None:
    print("PYTHON_RECEIPT_HASH=" + python_hash)
    for label, receipt in (("NODE", node_receipt), ("CSHARP", csharp_receipt)):
        try:
            parsed = json.loads(receipt)
            print(label + "_RECEIPT_HASH=" + str(parsed.get("receipt_hash", "MISSING")))
        except json.JSONDecodeError:
            print(label + "_RECEIPT_HASH=INVALID_JSON")


if __name__ == "__main__":
    raise SystemExit(main())
