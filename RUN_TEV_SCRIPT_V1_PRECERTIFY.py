from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V0_2_ORACLE = "6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5"


def run(arguments: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        check=False,
        capture_output=capture,
        text=True,
        encoding="utf-8",
    )


def require_success(label: str, completed: subprocess.CompletedProcess[str]) -> str:
    if completed.returncode != 0:
        print(label + "=FAIL")
        if completed.stdout:
            print(label + "_STDOUT=" + completed.stdout[-10000:].replace("\n", "\\n"))
        if completed.stderr:
            print(label + "_STDERR=" + completed.stderr[-10000:].replace("\n", "\\n"))
        raise SystemExit(1)
    print(label + "=PASS")
    return completed.stdout


def git_text(*arguments: str) -> str:
    completed = run(["git", *arguments])
    require_success("GIT_" + arguments[0].upper().replace("-", "_"), completed)
    return completed.stdout.strip()


def tree_manifest_sha() -> str:
    completed = run(["git", "ls-files", "-s"])
    require_success("GIT_LS_FILES", completed)
    lines = sorted(line.rstrip("\n") for line in completed.stdout.splitlines())
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require_clean(stage: str) -> None:
    completed = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    require_success("GIT_STATUS_" + stage, completed)
    if completed.stdout:
        print("GIT_CLEAN_" + stage + "=FAIL")
        print("GIT_DIRTY_ENTRIES=" + completed.stdout.replace("\n", "\\n"))
        raise SystemExit(1)
    print("GIT_CLEAN_" + stage + "=PASS")


def require_witnesses(label: str, stdout: str, witnesses: tuple[str, ...]) -> None:
    for witness in witnesses:
        if witness not in stdout:
            print(label + "=FAIL missing=" + witness)
            raise SystemExit(1)
    if "SKIPPED_" in stdout:
        print(label + "=FAIL unexpected_skip")
        raise SystemExit(1)
    print(label + "=PASS")


def main() -> int:
    for tool in ("git", "node", "dotnet"):
        if shutil.which(tool) is None:
            print(f"V1_PRECERTIFY_TOOL_{tool.upper()}=MISSING")
            print("V1_PRECERTIFY=FAIL")
            print("CERTIFY_FULL=NO")
            return 1

    require_clean("BEFORE")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD")
    ancestry = run(["git", "merge-base", "--is-ancestor", V0_2_ORACLE, "HEAD"])
    if ancestry.returncode != 0:
        print("V0_2_ORACLE_ANCESTRY=FAIL")
        return 1
    print("V0_2_ORACLE_ANCESTRY=PASS")

    closure = run([sys.executable, str(ROOT / "RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py")])
    closure_stdout = require_success("TEV_SCRIPT_V1_FRONTEND_CLOSURE_GATE", closure)
    require_witnesses(
        "TEV_SCRIPT_V1_FRONTEND_CLOSURE_WITNESSES",
        closure_stdout,
        (
            "TEV_SCRIPT_V1_PYTHON_COMPILE=PASS",
            "TEV_SCRIPT_V1_TESTS=PASS",
            "TEV_SCRIPT_IR_V3_TESTS=PASS",
            "TEV_SCRIPT_V0_2_PYTHON_REGRESSION=PASS",
            "TEV_SCRIPT_V1_PYTHON_CLOSURE=PASS_CANDIDATE",
        ),
    )
    if "skipped=" in closure_stdout.lower():
        print("TEV_SCRIPT_V1_FRONTEND_CLOSURE_SKIPS=FAIL")
        return 1

    csharp_surface = run(
        [sys.executable, str(ROOT / "tools" / "validate_ir_v3_csharp_portable_surface.py")]
    )
    csharp_surface_stdout = require_success(
        "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE_GATE",
        csharp_surface,
    )
    require_witnesses(
        "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE_WITNESSES",
        csharp_surface_stdout,
        (
            "TEV_SCRIPT_IR_V3_CSHARP_CORE_TFM=NETSTANDARD2_1_PASS",
            "TEV_SCRIPT_IR_V3_CSHARP_REFLECTION_FREE=PASS",
            "TEV_SCRIPT_IR_V3_CSHARP_MODERN_API_GUARD=PASS",
            "TEV_SCRIPT_IR_V3_CSHARP_CHECKPOINT_BOUNDARY=PASS",
            "TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE=PASS",
        ),
    )

    cross = run([sys.executable, str(ROOT / "tools" / "validate_ir_v3_cross_runtime_parity.py")])
    cross_stdout = require_success("TEV_SCRIPT_IR_V3_CROSS_RUNTIME_GATE", cross)
    require_witnesses(
        "TEV_SCRIPT_IR_V3_CROSS_RUNTIME_WITNESSES",
        cross_stdout,
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
    )

    checkpoint = run(
        [sys.executable, str(ROOT / "tools" / "validate_ir_v3_checkpoint_cross_runtime.py")]
    )
    checkpoint_stdout = require_success(
        "TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME_GATE",
        checkpoint,
    )
    require_witnesses(
        "TEV_SCRIPT_IR_V3_CHECKPOINT_CROSS_RUNTIME_WITNESSES",
        checkpoint_stdout,
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
    )

    portable = run([sys.executable, str(ROOT / "RUN_PORTABLE_CONFORMANCE.py")])
    portable_stdout = require_success("TEV_SCRIPT_V0_2_PORTABLE_CONFORMANCE", portable)
    if "=FAIL" in portable_stdout or "command_failed:" in portable_stdout:
        print("TEV_SCRIPT_V0_2_PORTABLE_CONFORMANCE_WITNESSES=FAIL")
        return 1
    if not any("PASS" in line and ("WASM" in line.upper() or "BROWSER" in line.upper()) for line in portable_stdout.splitlines()):
        print("TEV_SCRIPT_V0_2_BROWSER_WASM_WITNESS=FAIL")
        return 1
    if not any("PASS" in line and "WASI" in line.upper() for line in portable_stdout.splitlines()):
        print("TEV_SCRIPT_V0_2_WASI_WITNESS=FAIL")
        return 1
    print("TEV_SCRIPT_V0_2_BROWSER_WASM_WITNESS=PASS")
    print("TEV_SCRIPT_V0_2_WASI_WITNESS=PASS")

    require_clean("AFTER")
    head_after = git_text("rev-parse", "HEAD")
    tree_after = git_text("rev-parse", "HEAD^{tree}")
    if head_after != head or tree_after != tree:
        print("GIT_IDENTITY_STABLE_DURING_VALIDATION=FAIL")
        return 1
    print("GIT_IDENTITY_STABLE_DURING_VALIDATION=PASS")

    evidence = {
        "schema": "TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V2",
        "branch": branch,
        "commit": head,
        "tree": tree,
        "v0_2_oracle": V0_2_ORACLE,
        "tracked_index_manifest_sha256": tree_manifest_sha(),
        "v1_python_gate": "PASS",
        "ir_v3_csharp_portable_surface": "PASS",
        "ir_v3_python_js_csharp_parity": "PASS",
        "checkpoint_v2_cross_host": "PASS",
        "v0_2_portable_regression": "PASS",
        "browser_wasm_v3": "PENDING",
        "wasi_v3": "PENDING",
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
