from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
from typing import Sequence


ROOT = Path(__file__).resolve().parent
BASE_COMMIT = "a0c3951a03403f871ff4a192f75f2c29437f5fdb"
EXPECTED_BRANCH = "agent/tevscript-v31-ir5-execution-plan-v1"
REMOTE_BRANCH = f"origin/{EXPECTED_BRANCH}"
TOTAL_PROGRESS_GATES = 10


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _receipt(body: dict[str, object]) -> dict[str, object]:
    digest = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return {**body, "receipt_sha256": digest}


def _git(*arguments: str) -> str | None:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _is_git_sha(value: object) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _source_identity_gate() -> dict[str, object]:
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    branch = _git("branch", "--show-current")
    local_main = _git("rev-parse", "main")
    remote_main = _git("rev-parse", "origin/main")
    remote_candidate = _git("rev-parse", REMOTE_BRANCH)
    merge_base = _git("merge-base", "HEAD", "main")
    status_porcelain = _git(
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )

    checks = {
        "head_is_git_sha": _is_git_sha(head),
        "tree_is_git_sha": _is_git_sha(tree),
        "expected_branch": branch == EXPECTED_BRANCH,
        "local_main_is_certified_base": local_main == BASE_COMMIT,
        "origin_main_is_certified_base": remote_main == BASE_COMMIT,
        "merge_base_is_certified_base": merge_base == BASE_COMMIT,
        "remote_candidate_matches_head": remote_candidate == head,
        "worktree_clean": status_porcelain == "",
    }
    return {
        "name": "SOURCE_IDENTITY",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "source_commit": head,
        "source_tree": tree,
        "branch": branch,
        "local_main": local_main,
        "remote_main": remote_main,
        "remote_candidate": remote_candidate,
        "merge_base": merge_base,
        "expected_base": BASE_COMMIT,
        "worktree_clean": status_porcelain == "",
    }


def _pump_pipe(
    pipe,
    chunks: list[str],
    *,
    name: str,
    echo: bool,
) -> None:
    try:
        for line in iter(pipe.readline, ""):
            chunks.append(line)
            if echo:
                print(
                    f"[{name}] {line.rstrip()}",
                    file=sys.stderr,
                    flush=True,
                )
    finally:
        pipe.close()


def _execute_streamed(
    name: str,
    command: Sequence[str],
    *,
    index: int,
    total: int,
    echo_stdout: bool,
    echo_stderr: bool = True,
) -> tuple[int, str, str]:
    print(
        f"[{index}/{total}] {name}...",
        file=sys.stderr,
        flush=True,
    )
    process = subprocess.Popen(
        tuple(command),
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise RuntimeError(f"cannot capture child streams for {name}")

    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_thread = threading.Thread(
        target=_pump_pipe,
        args=(process.stdout, stdout_chunks),
        kwargs={"name": name, "echo": echo_stdout},
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_pump_pipe,
        args=(process.stderr, stderr_chunks),
        kwargs={"name": name, "echo": echo_stderr},
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    returncode = process.wait()
    stdout_thread.join()
    stderr_thread.join()

    status = "PASS" if returncode == 0 else "FAIL"
    print(
        f"[{index}/{total}] {name}={status}",
        file=sys.stderr,
        flush=True,
    )
    return returncode, "".join(stdout_chunks), "".join(stderr_chunks)


def _run(
    name: str,
    command: Sequence[str],
    *,
    index: int,
    total: int,
) -> dict[str, object]:
    returncode, stdout, stderr = _execute_streamed(
        name,
        command,
        index=index,
        total=total,
        echo_stdout=True,
    )
    return {
        "name": name,
        "status": "PASS" if returncode == 0 else "FAIL",
        "returncode": returncode,
        "command": list(command),
        "stdout": stdout,
        "stderr": stderr,
    }


def _run_performance(*, index: int, total: int) -> dict[str, object]:
    command = (
        sys.executable,
        str(ROOT / "RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE.py"),
        "--json",
    )
    returncode, stdout, stderr = _execute_streamed(
        "PERFORMANCE",
        command,
        index=index,
        total=total,
        echo_stdout=False,
    )
    raw = stdout.strip()
    try:
        payload = json.loads(raw.splitlines()[-1]) if raw else None
    except json.JSONDecodeError:
        payload = None

    if not isinstance(payload, dict):
        return {
            "name": "PERFORMANCE",
            "status": "FAIL",
            "returncode": returncode,
            "command": list(command),
            "stdout": stdout,
            "stderr": stderr,
            "reason": "INVALID_PERFORMANCE_RECEIPT",
        }

    phase_a_pass = bool(payload.get("phase_a_performance_pass"))
    boundary = payload.get("boundary_profile")
    phase_b_required = bool(
        isinstance(boundary, dict) and boundary.get("phase_b_required")
    )
    final_ready = bool(payload.get("final_10_10_ready"))

    if final_ready:
        status = "PASS"
    elif phase_a_pass and phase_b_required:
        status = "HOLD"
    else:
        status = "FAIL"

    return {
        "name": "PERFORMANCE",
        "status": status,
        "returncode": returncode,
        "command": list(command),
        "stdout": stdout,
        "stderr": stderr,
        "phase_a_performance_pass": phase_a_pass,
        "phase_b_required": phase_b_required,
        "final_10_10_ready": final_ready,
        "performance_receipt": payload,
    }


def certify() -> dict[str, object]:
    print(
        f"[1/{TOTAL_PROGRESS_GATES}] SOURCE_IDENTITY...",
        file=sys.stderr,
        flush=True,
    )
    source_gate = _source_identity_gate()
    print(
        f"[1/{TOTAL_PROGRESS_GATES}] SOURCE_IDENTITY={source_gate['status']}",
        file=sys.stderr,
        flush=True,
    )
    if source_gate["status"] != "PASS":
        gates = {"SOURCE_IDENTITY": source_gate}
        body = {
            "schema": "TEV_SCRIPT_V31_IR5_OPTIMIZATION_CERTIFY_RECEIPT_V1",
            "status": "FAIL",
            "final_10_10": "FAIL",
            "failed_gates": ["SOURCE_IDENTITY"],
            "hold_gates": [],
            "phase_b_required": False,
            "gates": gates,
            "source_commit": source_gate.get("source_commit"),
            "source_tree": source_gate.get("source_tree"),
            "worktree_clean": source_gate.get("worktree_clean") is True,
        }
        return _receipt(body)

    commands = (
        (
            "STATIC_COMPILE",
            (
                sys.executable,
                "-m",
                "py_compile",
                "tev_script/runtime_v5_total_optimized.py",
                "tests/test_runtime_v5_total_optimized.py",
                "tests/test_runtime_v5_total_optimized_fuzz_harness.py",
                "tests/test_runtime_v5_total_optimized_js_parity.py",
                "tests/test_ir5_optimization_certifier_progress.py",
                "tools/run_v31_total_core_optimized_differential_fuzz.py",
                "tools/benchmark_v31_total_core_performance.py",
                "tools/profile_v31_total_core_boundary_share.py",
                "RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE.py",
                "RUN_TEV_SCRIPT_V31_IR5_OPTIMIZATION_CERTIFY.py",
            ),
        ),
        (
            "FOCAL_DIFFERENTIAL",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_runtime_v5_total_optimized.py",
                "tests/test_runtime_v5_total_optimized_fuzz_harness.py",
                "tests/test_ir5_optimization_certifier_progress.py",
                "-q",
            ),
        ),
        (
            "DIFFERENTIAL_FUZZ_1000",
            (
                sys.executable,
                "tools/run_v31_total_core_optimized_differential_fuzz.py",
            ),
        ),
        (
            "OPTIMIZED_JS_PARITY",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_runtime_v5_total_optimized_js_parity.py",
                "-q",
            ),
        ),
        (
            "CERTIFIED_JS_WITNESS_NONREGRESSION",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_runtime_v5_total_js_parity.py",
                "-q",
            ),
        ),
        (
            "REFERENCE_IR5_NONREGRESSION",
            (
                sys.executable,
                "-m",
                "pytest",
                "tests/test_program_ir_v5_total.py",
                "tests/test_runtime_v5_total.py",
                "tests/test_runtime_v5_total_proof.py",
                "-q",
            ),
        ),
    )

    gates = {"SOURCE_IDENTITY": source_gate}
    for offset, (name, command) in enumerate(commands, start=2):
        gates[name] = _run(
            name,
            command,
            index=offset,
            total=TOTAL_PROGRESS_GATES,
        )

    gates["PERFORMANCE"] = _run_performance(
        index=8,
        total=TOTAL_PROGRESS_GATES,
    )
    gates["PLATFORM_COMPLETION"] = _run(
        "PLATFORM_COMPLETION",
        (sys.executable, "RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py"),
        index=9,
        total=TOTAL_PROGRESS_GATES,
    )

    print(
        f"[10/{TOTAL_PROGRESS_GATES}] SOURCE_IDENTITY_AFTER...",
        file=sys.stderr,
        flush=True,
    )
    source_after = _source_identity_gate()
    print(
        f"[10/{TOTAL_PROGRESS_GATES}] SOURCE_IDENTITY_AFTER={source_after['status']}",
        file=sys.stderr,
        flush=True,
    )
    gates["SOURCE_IDENTITY_AFTER"] = source_after

    failures = sorted(
        name for name, gate in gates.items() if gate.get("status") == "FAIL"
    )
    holds = sorted(
        name for name, gate in gates.items() if gate.get("status") == "HOLD"
    )
    status = "FAIL" if failures else ("HOLD" if holds else "PASS")
    performance = gates["PERFORMANCE"]

    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_V31_IR5_OPTIMIZATION_CERTIFY_RECEIPT_V1",
        "status": status,
        "final_10_10": (
            "PASS"
            if status == "PASS"
            else "HOLD"
            if status == "HOLD"
            else "FAIL"
        ),
        "failed_gates": failures,
        "hold_gates": holds,
        "phase_b_required": bool(performance.get("phase_b_required")),
        "gates": gates,
        "source_commit": source_after.get("source_commit"),
        "source_tree": source_after.get("source_tree"),
        "worktree_clean": source_after.get("worktree_clean") is True,
    }
    return _receipt(body)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="RUN_TEV_SCRIPT_V31_IR5_OPTIMIZATION_CERTIFY.py"
    )
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    receipt = certify()
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            _canonical_json(receipt) + "\n",
            encoding="utf-8",
        )

    if args.json:
        print(_canonical_json(receipt))
    else:
        for name, gate in receipt["gates"].items():
            print(f"{name}={gate['status']}")
        print(
            f"PHASE_B_REQUIRED={'YES' if receipt['phase_b_required'] else 'NO'}"
        )
        print(f"FINAL_10_10={receipt['final_10_10']}")
        print(f"SOURCE_COMMIT={receipt['source_commit']}")
        print(f"SOURCE_TREE={receipt['source_tree']}")
        print(
            f"WORKTREE_CLEAN={'PASS' if receipt['worktree_clean'] else 'FAIL'}"
        )
        print(f"RECEIPT_SHA256={receipt['receipt_sha256']}")

    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
