from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from tools.v1_optimizer_oracle_contract import OptimizerOracleContractError, parse_optimizer_oracle_output

ROOT = Path(__file__).resolve().parent

EXPERIMENT_LIMITS = {
    "counter": {"min_speedup": 2.0, "max_vs_direct": 20.0},
    "branch_true": {"min_speedup": 1.10, "max_vs_direct": 30.0},
    "algebraic_start": {"min_speedup": 1.20, "max_vs_direct": 15.0},
    "capability_int": {"min_speedup": 1.00, "max_vs_direct": 30.0},
}
EXPERIMENT_HOST_LIMITS = {
    "host_counter": {"min_speedup": 1.50, "max_vs_direct": 25.0},
    "host_capability_int": {"min_speedup": 1.00, "max_vs_direct": 30.0},
}

# Actual usefulness targets before the optimized runtime/host may replace the
# reference implementation in production-facing surfaces. Cold startup is
# reported but not required to beat the reference: plan compilation has a real
# first-use cost. Warm startup, however, must not be slower once the exact
# canonical artifact has a sealed template in the bounded cache.
PROMOTION_LIMITS = {
    "counter": {"min_speedup": 5.0, "max_vs_direct": 5.0},
    "branch_true": {"min_speedup": 2.0, "max_vs_direct": 5.0},
    "algebraic_start": {"min_speedup": 2.0, "max_vs_direct": 3.0},
    "capability_int": {"min_speedup": 1.25, "max_vs_direct": 5.0},
}
PROMOTION_HOST_LIMITS = {
    "host_counter": {
        "min_speedup": 4.0,
        "max_vs_direct": 5.0,
        "max_warm_startup_vs_reference": 1.0,
    },
    "host_capability_int": {
        "min_speedup": 1.25,
        "max_vs_direct": 5.0,
        "max_warm_startup_vs_reference": 1.0,
    },
}


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _fail(
    label: str,
    detail: str,
    completed: subprocess.CompletedProcess[str] | None = None,
) -> int:
    print(f"{label}=FAIL {detail}")
    if completed is not None and completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    print("TEV_SCRIPT_V1_PERFORMANCE_POLISH=HOLD")
    print("RUNTIME_PROMOTION=NO")
    return 1


def _parse_json_result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any] | None:
    if completed.returncode != 0:
        return None
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _runtime_benchmark(
    *,
    events: int,
    rich_events: int,
    capability_events: int,
    rounds: int,
    warmup: int,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    completed = _run(
        [
            sys.executable,
            str(ROOT / "tools" / "benchmark_v1_runtime_performance.py"),
            "--events",
            str(events),
            "--rich-events",
            str(rich_events),
            "--capability-events",
            str(capability_events),
            "--rounds",
            str(rounds),
            "--warmup",
            str(warmup),
        ]
    )
    return completed, _parse_json_result(completed)


def _host_benchmark(
    *,
    events: int,
    capability_events: int,
    rounds: int,
    warmup: int,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any] | None]:
    completed = _run(
        [
            sys.executable,
            str(ROOT / "tools" / "benchmark_v1_python_host_performance.py"),
            "--events",
            str(events),
            "--capability-events",
            str(capability_events),
            "--rounds",
            str(rounds),
            "--warmup",
            str(warmup),
        ]
    )
    return completed, _parse_json_result(completed)


def _assess(
    benchmark: dict[str, Any],
    limits: dict[str, dict[str, float]],
) -> tuple[bool, list[dict[str, Any]]]:
    workloads = benchmark.get("workloads")
    if not isinstance(workloads, list):
        return False, [{"reason": "workloads_missing"}]
    by_name = {
        row.get("name"): row
        for row in workloads
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    decisions: list[dict[str, Any]] = []
    passed = benchmark.get("same_final_state") is True
    for name, limit in limits.items():
        row = by_name.get(name)
        if not isinstance(row, dict):
            decisions.append({"name": name, "pass": False, "reason": "workload_missing"})
            passed = False
            continue
        speedup = float(row.get("optimized_speedup_vs_reference", 0.0))
        vs_direct = float(row.get("optimized_vs_direct", float("inf")))
        warm_ratio_raw = row.get("optimized_warm_startup_vs_reference")
        warm_ratio = (
            float(warm_ratio_raw)
            if isinstance(warm_ratio_raw, (int, float))
            else None
        )
        speed_pass = speedup >= limit["min_speedup"]
        direct_pass = vs_direct <= limit["max_vs_direct"]
        startup_limit = limit.get("max_warm_startup_vs_reference")
        startup_pass = (
            True
            if startup_limit is None
            else warm_ratio is not None and warm_ratio <= startup_limit
        )
        row_pass = speed_pass and direct_pass and startup_pass
        decision: dict[str, Any] = {
            "name": name,
            "pass": row_pass,
            "optimized_speedup_vs_reference": speedup,
            "optimized_vs_direct": vs_direct,
            "min_speedup_required": limit["min_speedup"],
            "max_vs_direct_allowed": limit["max_vs_direct"],
        }
        if startup_limit is not None:
            decision["optimized_warm_startup_vs_reference"] = warm_ratio
            decision["max_warm_startup_vs_reference_allowed"] = startup_limit
        decisions.append(decision)
        passed = passed and row_pass
    return passed, decisions


def _optimizer_oracle(requested: str):
    provider = (
        Path(requested).expanduser()
        if requested
        else ROOT / "tools" / "v1_optimizer_oracle_local.py"
    )
    if not provider.is_absolute():
        provider = ROOT / provider
    provider = provider.resolve()
    if not provider.is_file():
        return (
            subprocess.CompletedProcess(
                [str(provider)],
                2,
                stdout="optimizer oracle provider missing\n",
            ),
            None,
        )
    command = (
        [sys.executable, str(provider)]
        if provider.suffix.lower() == ".py"
        else [str(provider)]
    )
    completed = _run(command)
    if completed.returncode != 0:
        return completed, None
    try:
        receipt = parse_optimizer_oracle_output(completed.stdout)
    except OptimizerOracleContractError:
        return completed, None
    return completed, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEV Script V1 performance-polish admission")
    parser.add_argument("--profile", choices=("experiment", "promotion"), default="experiment")
    parser.add_argument("--optimizer-oracle", default="")
    parser.add_argument("--events", type=int, default=200_000)
    parser.add_argument("--rich-events", type=int, default=50_000)
    parser.add_argument("--capability-events", type=int, default=100_000)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=5_000)
    args = parser.parse_args(argv)

    print("TEV_SCRIPT_V1_PERFORMANCE_POLISH_SCHEMA=V4")
    print("PERFORMANCE_PROFILE=" + args.profile)
    print("REFERENCE_RUNTIME_REPLACED=NO")
    print("REFERENCE_PYTHON_HOST_REPLACED=NO")

    core_tests = _run(
        [sys.executable, "-m", "unittest", "tests.test_runtime_v3_optimized", "-v"]
    )
    if core_tests.returncode != 0:
        return _fail("OPTIMIZED_RUNTIME_EQUIVALENCE", "TEST_FAILURE", core_tests)
    print("OPTIMIZED_RUNTIME_EQUIVALENCE=PASS")

    host_tests = _run(
        [sys.executable, "-m", "unittest", "tests.test_v1_python_host_optimized", "-v"]
    )
    if host_tests.returncode != 0:
        return _fail("OPTIMIZED_PYTHON_HOST_EQUIVALENCE", "TEST_FAILURE", host_tests)
    print("OPTIMIZED_PYTHON_HOST_EQUIVALENCE=PASS")

    oracle_completed, oracle_receipt = _optimizer_oracle(args.optimizer_oracle)
    if oracle_receipt is None:
        return _fail("OPTIMIZER_ORACLE", "ORACLE_FAILURE", oracle_completed)
    print("OPTIMIZER_ORACLE=PASS")
    print("OPTIMIZER_ORACLE_PROVIDER=" + str(oracle_receipt["provider_id"]))
    print("OPTIMIZER_ORACLE_KIND=" + str(oracle_receipt["provider_kind"]))
    print("EXTERNAL_SEMANTIC_AUTHORITY_REQUIRED=NO")

    runtime_completed, runtime_benchmark = _runtime_benchmark(
        events=args.events,
        rich_events=args.rich_events,
        capability_events=args.capability_events,
        rounds=args.rounds,
        warmup=args.warmup,
    )
    if runtime_benchmark is None:
        return _fail("RUNTIME_PERFORMANCE_BENCHMARK", "INVALID_OR_FAILED", runtime_completed)
    if runtime_benchmark.get("schema") != "TEV_SCRIPT_V1_RUNTIME_PERFORMANCE_V2":
        return _fail("RUNTIME_PERFORMANCE_BENCHMARK", "SCHEMA_MISMATCH", runtime_completed)
    print("RUNTIME_PERFORMANCE_BENCHMARK=PASS")

    host_completed, host_benchmark = _host_benchmark(
        events=args.events,
        capability_events=args.capability_events,
        rounds=args.rounds,
        warmup=args.warmup,
    )
    if host_benchmark is None:
        return _fail("PYTHON_HOST_PERFORMANCE_BENCHMARK", "INVALID_OR_FAILED", host_completed)
    if host_benchmark.get("schema") != "TEV_SCRIPT_V1_PYTHON_HOST_PERFORMANCE_V2":
        return _fail("PYTHON_HOST_PERFORMANCE_BENCHMARK", "SCHEMA_MISMATCH", host_completed)
    print("PYTHON_HOST_PERFORMANCE_BENCHMARK=PASS")

    runtime_limits = PROMOTION_LIMITS if args.profile == "promotion" else EXPERIMENT_LIMITS
    host_limits = PROMOTION_HOST_LIMITS if args.profile == "promotion" else EXPERIMENT_HOST_LIMITS
    runtime_admitted, runtime_decisions = _assess(runtime_benchmark, runtime_limits)
    host_admitted, host_decisions = _assess(host_benchmark, host_limits)
    admitted = runtime_admitted and host_admitted

    receipt = {
        "schema": "TEV_SCRIPT_V1_PERFORMANCE_POLISH_RECEIPT_V4",
        "profile": args.profile,
        "semantic_equivalence_tests": True,
        "python_host_equivalence_tests": True,
        "optimizer_oracle": oracle_receipt,
        "optimizer_oracle_provider": oracle_receipt["provider_id"],
        "external_semantic_authority_required": False,
        "standalone_semantic_authority": True,
        "runtime_benchmark": runtime_benchmark,
        "python_host_benchmark": host_benchmark,
        "runtime_decisions": runtime_decisions,
        "python_host_decisions": host_decisions,
        "admitted": admitted,
        "reference_runtime_replaced": False,
        "reference_python_host_replaced": False,
        "language_semantics_changed": False,
    }
    print(
        "TEV_SCRIPT_V1_PERFORMANCE_POLISH_RECEIPT="
        + json.dumps(receipt, sort_keys=True, separators=(",", ":"))
    )

    if not admitted:
        print("TEV_SCRIPT_V1_PERFORMANCE_POLISH=HOLD")
        print("RUNTIME_PROMOTION=NO")
        return 2

    print("TEV_SCRIPT_V1_PERFORMANCE_POLISH=PASS")
    print(
        "RUNTIME_PROMOTION="
        + ("ELIGIBLE_FOR_REVIEW" if args.profile == "promotion" else "NO_EXPERIMENT_ONLY")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
