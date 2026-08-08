from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script.json_io import load_strict_json  # noqa: E402
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2  # noqa: E402
from tev_script.runtime_v3 import ScriptRuntimeV3  # noqa: E402

CASES_PATH = ROOT / "conformance" / "ir-v3-validator-cases.json"
NODE_CLI = ROOT / "javascript" / "src" / "run-ir-v3-checkpoint.mjs"
NODE_TEST = ROOT / "javascript" / "test" / "runtime-checkpoint-v2.test.mjs"
CSHARP_PROJECT = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3CheckpointGate"
    / "TevScript.V3CheckpointGate.csproj"
)
CSHARP_DLL = (
    ROOT
    / "runtimes"
    / "csharp"
    / "TevScript.V3CheckpointGate"
    / "bin"
    / "Release"
    / "net8.0"
    / "TevScript.V3CheckpointGate.dll"
)


def _run(
    arguments: list[str],
    *,
    dotnet_roll_forward: bool = False,
) -> subprocess.CompletedProcess[str]:
    environment = None
    if dotnet_roll_forward:
        environment = os.environ.copy()
        environment.setdefault("DOTNET_ROLL_FORWARD", "Major")
    return subprocess.run(
        arguments,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
    )


def _fail_process(label: str, completed: subprocess.CompletedProcess[str]) -> int:
    print(label + "=FAIL")
    if completed.stdout:
        print(label + "_STDOUT=" + completed.stdout[-6000:].replace("\n", "\\n"))
    if completed.stderr:
        print(label + "_STDERR=" + completed.stderr[-6000:].replace("\n", "\\n"))
    return 1


def main() -> int:
    cases = load_strict_json(CASES_PATH)
    program = cases["valid_program"]

    python_runtime = ScriptRuntimeV3(program)
    python_runtime.invoke("E", "start")
    python_checkpoint = RuntimeCheckpointV2.capture(python_runtime)
    python_bytes = python_checkpoint.to_canonical_json()
    python_hash = python_checkpoint.checkpoint_hash
    parsed_python = RuntimeCheckpointV2.parse(python_bytes)
    restored_python = parsed_python.restore_exact(program)
    if restored_python.canonical_state("E") != python_runtime.canonical_state("E"):
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_RESTORE=FAIL_STATE_MISMATCH")
        return 1
    continuation = restored_python.invoke("E", "update")
    if len(continuation) != 1 or continuation[0].event_id != "changed":
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_RESTORE=FAIL_CONTINUATION")
        return 1
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_CAPTURE=PASS")
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_RESTORE=PASS")

    node = shutil.which("node")
    if node is None:
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME=SKIPPED_NODE_UNAVAILABLE")
        return 0
    dotnet = shutil.which("dotnet")
    if dotnet is None:
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME=SKIPPED_DOTNET_UNAVAILABLE")
        return 0

    node_test = _run([node, "--test", str(NODE_TEST)])
    if node_test.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_CHECKPOINT_NODE_TEST", node_test)
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_NODE_TEST=PASS")

    node_capture = _run([node, str(NODE_CLI), str(CASES_PATH)])
    if node_capture.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_CHECKPOINT_NODE_CAPTURE", node_capture)
    node_bytes = node_capture.stdout
    try:
        node_checkpoint = RuntimeCheckpointV2.parse(node_bytes)
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_NODE_CAPTURE=FAIL_INVALID_CHECKPOINT")
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_NODE_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    if node_bytes != python_bytes:
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_JS_PARITY=FAIL_BYTE_MISMATCH")
        print("PYTHON_CHECKPOINT_HASH=" + python_hash)
        print("NODE_CHECKPOINT_HASH=" + node_checkpoint.checkpoint_hash)
        return 1
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_JS_PARITY=PASS")

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
        return _fail_process("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_BUILD", build)
    if not CSHARP_DLL.exists():
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_BUILD=FAIL_DLL_MISSING")
        return 1
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_BUILD=PASS")

    csharp_test = _run(
        [dotnet, str(CSHARP_DLL), "--self-test", str(CASES_PATH)],
        dotnet_roll_forward=True,
    )
    if csharp_test.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_SELF_TEST", csharp_test)
    required_witnesses = (
        "CSHARP_IR_V3_CHECKPOINT_CAPTURE=PASS",
        "CSHARP_IR_V3_CHECKPOINT_CANONICAL_ROUNDTRIP=PASS",
        "CSHARP_IR_V3_CHECKPOINT_RESTORE_CONTINUATION=PASS",
        "CSHARP_IR_V3_CHECKPOINT_TAMPER=PASS",
    )
    if any(witness not in csharp_test.stdout for witness in required_witnesses):
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_SELF_TEST=FAIL_MISSING_WITNESS")
        return 1
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_SELF_TEST=PASS")

    csharp_capture = _run(
        [dotnet, str(CSHARP_DLL), "--capture", str(CASES_PATH)],
        dotnet_roll_forward=True,
    )
    if csharp_capture.returncode != 0:
        return _fail_process("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_CAPTURE", csharp_capture)
    csharp_bytes = csharp_capture.stdout
    try:
        csharp_checkpoint = RuntimeCheckpointV2.parse(csharp_bytes)
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_CAPTURE=FAIL_INVALID_CHECKPOINT")
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    if csharp_bytes != python_bytes:
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_CSHARP_PARITY=FAIL_BYTE_MISMATCH")
        print("PYTHON_CHECKPOINT_HASH=" + python_hash)
        print("CSHARP_CHECKPOINT_HASH=" + csharp_checkpoint.checkpoint_hash)
        return 1
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_CSHARP_PARITY=PASS")

    if csharp_bytes != node_bytes:
        print("TEV_SCRIPT_IR_V3_CHECKPOINT_JS_CSHARP_PARITY=FAIL_BYTE_MISMATCH")
        return 1
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_JS_CSHARP_PARITY=PASS")
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_HASH=" + python_hash)
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_CANONICAL_BYTES=PASS")
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_RESTART_CONTINUATION=PASS")
    print("TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
