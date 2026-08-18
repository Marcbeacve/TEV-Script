from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parent


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


def _run(name: str, command: Sequence[str]) -> dict[str, object]:
    completed = subprocess.run(
        tuple(command),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "command": list(command),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_performance() -> dict[str, object]:
    command = (
        sys.executable,
        str(ROOT / "RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE.py"),
        "--json",
    )
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    raw = completed.stdout.strip()
    try:
        payload = json.loads(raw.splitlines()[-1]) if raw else None
    except json.JSONDecodeError:
        payload = None

    if not isinstance(payload, dict):
        return {
            "name": "PERFORMANCE",
            "status": "FAIL",
            "returncode": completed.returncode,
            "command": list(command),
            "stdout": completed.stdout,
            "stderr": completed.stderr,
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
        "returncode": completed.returncode,
        "command": list(command),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "phase_a_performance_pass": phase_a_pass,
        "phase_b_required": phase_b_required,
        "final_10_10_ready": final_ready,
        "performance_receipt": payload,
    }


def certify() -> dict[str, object]:
    commands = (
        (
            "STATIC_COMPILE",
            (
                sys.executable,
                "-m",
                "py_compile",
                "tev_script/runtime_v5_total_optimized.py",
                "tests/test_runtime_v5_total_optimized.py",
                "tests/test_runtime_v5_total_optimized_js_parity.py",
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

    gates = {name: _run(name, command) for name, command in commands}
    gates["PERFORMANCE"] = _run_performance()
    gates["PLATFORM_COMPLETION"] = _run(
        "PLATFORM_COMPLETION",
        (sys.executable, "RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py"),
    )

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
        "final_10_10": "PASS" if status == "PASS" else "HOLD" if status == "HOLD" else "FAIL",
        "failed_gates": failures,
        "hold_gates": holds,
        "phase_b_required": bool(performance.get("phase_b_required")),
        "gates": gates,
        "source_commit": _git("rev-parse", "HEAD"),
        "source_tree": _git("rev-parse", "HEAD^{tree}"),
        "worktree_clean": _git("status", "--porcelain=v1", "--untracked-files=all") == "",
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
        args.receipt.write_text(_canonical_json(receipt) + "\n", encoding="utf-8")

    if args.json:
        print(_canonical_json(receipt))
    else:
        for name, gate in receipt["gates"].items():
            print(f"{name}={gate['status']}")
        print(f"PHASE_B_REQUIRED={'YES' if receipt['phase_b_required'] else 'NO'}")
        print(f"FINAL_10_10={receipt['final_10_10']}")
        print(f"SOURCE_COMMIT={receipt['source_commit']}")
        print(f"SOURCE_TREE={receipt['source_tree']}")
        print(f"WORKTREE_CLEAN={'PASS' if receipt['worktree_clean'] else 'FAIL'}")
        print(f"RECEIPT_SHA256={receipt['receipt_sha256']}")

    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
