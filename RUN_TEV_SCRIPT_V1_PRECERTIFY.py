from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V0_2_ORACLE = "6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5"
RECEIPT_SCHEMA = "TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V5"


@dataclass(frozen=True, slots=True)
class Gate:
    label: str
    command: tuple[str, ...]
    witnesses: tuple[str, ...]
    reject_skip: bool = True


def run(arguments: list[str] | tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fail(label: str, message: str, completed: subprocess.CompletedProcess[str] | None = None) -> None:
    print(label + "=FAIL " + message)
    if completed is not None:
        if completed.stdout:
            print(label + "_STDOUT=" + completed.stdout[-16000:].replace("\n", "\\n"))
        if completed.stderr:
            print(label + "_STDERR=" + completed.stderr[-16000:].replace("\n", "\\n"))
    print("V1_PRECERTIFY=FAIL")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    raise SystemExit(1)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        fail("V1_PRECERTIFY_TOOL_" + name.upper(), "MISSING")
    print("V1_PRECERTIFY_TOOL_" + name.upper() + "=PASS")


def git_text(*arguments: str) -> str:
    completed = run(("git", *arguments))
    if completed.returncode != 0:
        fail("GIT_" + arguments[0].upper().replace("-", "_"), "COMMAND_FAILED", completed)
    return completed.stdout.strip()


def require_clean(stage: str) -> None:
    completed = run(("git", "status", "--porcelain=v1", "--untracked-files=all"))
    if completed.returncode != 0:
        fail("GIT_STATUS_" + stage, "COMMAND_FAILED", completed)
    if completed.stdout:
        fail("GIT_CLEAN_" + stage, "DIRTY=" + completed.stdout.replace("\n", "\\n"))
    print("GIT_CLEAN_" + stage + "=PASS")


def tree_manifest_sha() -> str:
    completed = run(("git", "ls-files", "-s"))
    if completed.returncode != 0:
        fail("GIT_LS_FILES", "COMMAND_FAILED", completed)
    lines = sorted(line.rstrip("\n") for line in completed.stdout.splitlines())
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def python_command(relative: str) -> tuple[str, ...]:
    return (sys.executable, str(ROOT / relative))


def require_gate(gate: Gate) -> str:
    completed = run(gate.command)
    if completed.returncode != 0:
        fail(gate.label, "COMMAND_FAILED", completed)
    stdout = completed.stdout
    if gate.reject_skip and "SKIPPED_" in stdout:
        fail(gate.label, "UNEXPECTED_SKIP", completed)
    for witness in gate.witnesses:
        if witness not in stdout:
            fail(gate.label, "MISSING_WITNESS=" + witness, completed)
    print(gate.label + "=PASS")
    return stdout


def mandatory_gates() -> tuple[Gate, ...]:
    return (
        Gate(
            "TEV_SCRIPT_V1_GOVERNANCE_GATE",
            python_command("tools/validate_v1_governance.py"),
            (
                "TEV_SCRIPT_V1_GOVERNANCE_CANON_MATRIX=PASS",
                "TEV_SCRIPT_V1_GOVERNANCE_AUTHORITY_FILES=PASS",
                "TEV_SCRIPT_V1_GOVERNANCE_GATE_BINDINGS=PASS",
                "TEV_SCRIPT_V1_GOVERNANCE_PRECERTIFY_CERTIFY_PROTOCOL=PASS",
                "TEV_SCRIPT_V1_GOVERNANCE_NO_TRANSITIVE_CERTIFICATION=PASS",
                "TEV_SCRIPT_V1_GOVERNANCE=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_V1_FRONTEND_CLOSURE_GATE",
            python_command("RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py"),
            (
                "TEV_SCRIPT_V1_PYTHON_COMPILE=PASS",
                "TEV_SCRIPT_V1_TESTS=PASS",
                "TEV_SCRIPT_IR_V3_TESTS=PASS",
                "TEV_SCRIPT_V0_2_PYTHON_REGRESSION=PASS",
                "TEV_SCRIPT_V1_PYTHON_CLOSURE=PASS_CANDIDATE",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE_GATE",
            python_command("tools/validate_ir_v3_csharp_portable_surface.py"),
            (
                "TEV_SCRIPT_IR_V3_CSHARP_CORE_TFM=NETSTANDARD2_1_PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_V0_2_ASSEMBLY_ISOLATION=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_V3_ASSEMBLY=NET8_DEPENDENCY_FREE_PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_REFLECTION_FREE=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_AOT_JSON=REFLECTION_FREE_PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SHA256=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_CHECKPOINT_BOUNDARY=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_TRANSACTIONAL_SWAP=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE_CONSUMERS=3_PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_RUNTIME_CRYPTO_DECOUPLED=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_CROSS_RUNTIME_GATE",
            python_command("tools/validate_ir_v3_cross_runtime_parity.py"),
            (
                "TEV_SCRIPT_IR_V3_NODE_TESTS=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_CSHARP_SELF_TEST=PASS",
                "TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_PYTHON_CSHARP_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_JS_CSHARP_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_CROSS_RUNTIME_CANONICAL_BYTES=PASS",
                "TEV_SCRIPT_IR_V3_CROSS_RUNTIME_PARITY=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME_GATE",
            python_command("tools/validate_ir_v3_checkpoint_cross_runtime.py"),
            (
                "TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_CAPTURE=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_RESTORE=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_NODE_TEST=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_JS_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_CSHARP_SELF_TEST=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_PYTHON_CSHARP_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_JS_CSHARP_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_CANONICAL_BYTES=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_RESTART_CONTINUATION=PASS",
                "TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_BROWSER_WASM_DYNAMIC_GATE",
            python_command("tools/validate_ir_v3_browser_wasm.py"),
            (
                "TEV_SCRIPT_IR_V3_BROWSER_HOST_ORACLES=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_WASM_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_WASM_MAGIC=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_WASM_AOT_REQUESTED=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_HTTP_WITNESS=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_RECEIPT_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_CHECKPOINT_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_WASM_GATE=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_WASI_DYNAMIC_GATE",
            python_command("tools/validate_ir_v3_wasi.py"),
            (
                "TEV_SCRIPT_IR_V3_WASI_SDK_RESOLVED=PASS",
                "TEV_SCRIPT_IR_V3_WASI_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_WASI_WASM_MAGIC=PASS",
                "TEV_SCRIPT_IR_V3_WASI_FRESH=PASS",
                "TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_CANONICAL_BYTES=PASS",
                "TEV_SCRIPT_IR_V3_WASI_RESTORE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_RECEIPT_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_WASI_CHECKPOINT_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_WASI_RESTART_CONTINUATION=PASS",
                "TEV_SCRIPT_IR_V3_WASI_GATE=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_HOST_GATE",
            python_command("tools/validate_ir_v3_signed_update.py"),
            (
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_CSHARP_SURFACE=PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_PROGRAM_GENERATION=PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_FIXTURE_SIGN=PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_DYNAMIC=PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_TEMP_FIXTURES=EPHEMERAL_PASS",
                "TEV_SCRIPT_IR_V3_SIGNED_UPDATE_GATE=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_DYNAMIC_GATE",
            python_command("tools/validate_ir_v3_browser_signed_update.py"),
            (
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_SURFACE=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PROGRAMS=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_FIXTURE_SIGN=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_HOST_ORACLE=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_WASM_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_WASM_MAGIC=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_AOT_REQUESTED=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_HTTP_WITNESS=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_PACKAGE_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_TARGET_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_BROWSER_SIGNED_UPDATE_GATE=PASS",
            ),
        ),
        Gate(
            "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_DYNAMIC_GATE",
            python_command("tools/validate_ir_v3_wasi_signed_update.py"),
            (
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SDK_RESOLVED=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_SURFACE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PROGRAMS=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FIXTURE_SIGN=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_HOST_ORACLE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_BUILD=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_WASM_MAGIC=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_FRESH=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_INSTALLED_BYTES=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PYTHON_CHECKPOINT=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTORE=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_PACKAGE_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_TARGET_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_CHECKPOINT_PARITY=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_RESTART_CONTINUATION=PASS",
                "TEV_SCRIPT_IR_V3_WASI_SIGNED_UPDATE_GATE=PASS",
            ),
        ),
    )


def main() -> int:
    for tool in ("git", "node", "dotnet", "wasmtime"):
        require_tool(tool)

    require_clean("BEFORE")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD")

    ancestry = run(("git", "merge-base", "--is-ancestor", V0_2_ORACLE, "HEAD"))
    if ancestry.returncode != 0:
        fail("V0_2_ORACLE_ANCESTRY", "FAIL", ancestry)
    print("V0_2_ORACLE_ANCESTRY=PASS")

    for gate in mandatory_gates():
        stdout = require_gate(gate)
        if gate.label == "TEV_SCRIPT_V1_FRONTEND_CLOSURE_GATE" and "skipped=" in stdout.lower():
            fail(gate.label, "TEST_SKIP_DETECTED")

    portable = require_gate(
        Gate(
            "TEV_SCRIPT_V0_2_PORTABLE_CONFORMANCE",
            python_command("RUN_PORTABLE_CONFORMANCE.py"),
            (),
            reject_skip=False,
        )
    )
    if "=FAIL" in portable or "command_failed:" in portable:
        fail("TEV_SCRIPT_V0_2_PORTABLE_CONFORMANCE", "FAIL_WITNESS")
    if not any("PASS" in line and ("WASM" in line.upper() or "BROWSER" in line.upper()) for line in portable.splitlines()):
        fail("TEV_SCRIPT_V0_2_BROWSER_WASM_WITNESS", "MISSING")
    if not any("PASS" in line and "WASI" in line.upper() for line in portable.splitlines()):
        fail("TEV_SCRIPT_V0_2_WASI_WITNESS", "MISSING")
    print("TEV_SCRIPT_V0_2_BROWSER_WASM_WITNESS=PASS")
    print("TEV_SCRIPT_V0_2_WASI_WITNESS=PASS")

    require_clean("AFTER")
    head_after = git_text("rev-parse", "HEAD")
    tree_after = git_text("rev-parse", "HEAD^{tree}")
    if head_after != head or tree_after != tree:
        fail("GIT_IDENTITY_STABLE_DURING_VALIDATION", "HEAD_OR_TREE_CHANGED")
    print("GIT_IDENTITY_STABLE_DURING_VALIDATION=PASS")

    evidence = {
        "schema": RECEIPT_SCHEMA,
        "branch": branch,
        "commit": head,
        "tree": tree,
        "v0_2_oracle": V0_2_ORACLE,
        "tracked_index_manifest_sha256": tree_manifest_sha(),
        "v1_governance": "PASS",
        "v1_python_gate": "PASS",
        "ir_v3_csharp_v0_2_assembly_isolation": "PASS",
        "ir_v3_csharp_runtime_assembly": "PASS_NET8_DEPENDENCY_FREE",
        "ir_v3_csharp_aot_json": "PASS_REFLECTION_FREE",
        "ir_v3_python_js_csharp_parity": "PASS",
        "checkpoint_v2_cross_host": "PASS",
        "browser_wasm_v3": "PASS",
        "wasi_v3": "PASS_FRESH_RESTORE",
        "signed_update_v3_host": "PASS",
        "signed_update_v3_browser_wasm": "PASS",
        "signed_update_v3_wasi": "PASS_FRESH_RESTORE",
        "v0_2_portable_regression": "PASS",
        "certify_full": False,
        "language_stable": False,
    }
    evidence_json = json.dumps(
        evidence,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    print("V1_PRECERTIFY_RECEIPT=" + evidence_json)
    print("V1_PRECERTIFY_RECEIPT_SHA256=" + hashlib.sha256(evidence_json.encode("utf-8")).hexdigest())
    print("V1_PRECERTIFY=PASS")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
