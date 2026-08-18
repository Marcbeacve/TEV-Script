from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
BENCHMARK = ROOT / "tools" / "benchmark_v31_total_core_performance.py"
PROFILER = ROOT / "tools" / "profile_v31_total_core_boundary_share.py"


def _progress(message: str) -> None:
    print(f"[PERFORMANCE] {message}", file=sys.stderr, flush=True)


def _run_json(command: list[str]) -> tuple[dict[str, object], int, str]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    stdout = completed.stdout.strip()
    if not stdout:
        raise RuntimeError(
            f"command produced no JSON: {' '.join(command)}\n{completed.stderr}"
        )
    try:
        payload = json.loads(stdout.splitlines()[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"command produced invalid JSON: {' '.join(command)}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        ) from exc
    return payload, completed.returncode, completed.stderr


def _geomean(values: list[float]) -> float:
    return math.exp(sum(math.log(value) for value in values) / len(values))


def _median_case_metrics(
    runs: list[dict[str, object]],
) -> dict[str, dict[str, float]]:
    names = [str(item["case"]) for item in runs[0]["cases"]]
    result: dict[str, dict[str, float]] = {}
    for name in names:
        run_cases = [
            next(item for item in run["cases"] if item["case"] == name)
            for run in runs
        ]
        result[name] = {
            "speedup": float(
                median(float(item["speedup"]) for item in run_cases)
            ),
            "p95_ratio": float(
                median(float(item["p95_ratio"]) for item in run_cases)
            ),
            "reference_median_ns": float(
                median(
                    float(item["reference_median_ns"]) for item in run_cases
                )
            ),
            "prepared_median_ns": float(
                median(
                    float(item["prepared_median_ns"]) for item in run_cases
                )
            ),
        }
    return result


def _aggregate_algorithmic(runs: list[dict[str, object]]) -> dict[str, object]:
    hot = [run["algorithmic_hot_path"] for run in runs]
    lookup_speedup = float(
        median(float(item["lookup_10k_speedup"]) for item in hot)
    )
    prepared_scaling = float(
        median(float(item["prepared_scaling_10k_over_10"]) for item in hot)
    )
    reference_scaling = float(
        median(float(item["reference_scaling_10k_over_10"]) for item in hot)
    )
    passed = (
        lookup_speedup >= 10.0
        and prepared_scaling <= 2.0
        and reference_scaling >= 20.0
    )
    return {
        "lookup_10k_speedup": lookup_speedup,
        "prepared_scaling_10k_over_10": prepared_scaling,
        "reference_scaling_10k_over_10": reference_scaling,
        "pass": passed,
    }


def _aggregate_phase_a(
    benchmark_runs: list[dict[str, object]],
    case_metrics: dict[str, dict[str, float]],
) -> dict[str, object]:
    identity = all(
        all(bool(case["semantic_identity_pass"]) for case in run["cases"])
        for run in benchmark_runs
    )
    geomean = _geomean(
        [metrics["speedup"] for metrics in case_metrics.values()]
    )
    gates = {
        "semantic_identity_all_runs": identity,
        "jump_10k": case_metrics["jump_10k"]["speedup"] >= 1.02,
        "apply_plain": case_metrics["apply_plain"]["speedup"] >= 1.02,
        "apply_proof_admitted": (
            case_metrics["apply_proof_admitted"]["speedup"] >= 1.05
        ),
        "mixed_total_core": (
            case_metrics["mixed_total_core"]["speedup"] >= 1.05
        ),
        "branch_fact_10_p95": (
            case_metrics["branch_fact_10"]["p95_ratio"] <= 1.05
        ),
        "branch_fact_100_p95": (
            case_metrics["branch_fact_100"]["p95_ratio"] <= 1.05
        ),
        "branch_fact_1k_p95": (
            case_metrics["branch_fact_1k"]["p95_ratio"] <= 1.05
        ),
        "branch_fact_10k_p95": (
            case_metrics["branch_fact_10k"]["p95_ratio"] <= 1.05
        ),
        "invoke_v4_pure_p95": (
            case_metrics["invoke_v4_pure"]["p95_ratio"] <= 1.05
        ),
        "invoke_v4_recursive_p95": (
            case_metrics["invoke_v4_recursive"]["p95_ratio"] <= 1.05
        ),
        "invoke_v4_effects_p95": (
            case_metrics["invoke_v4_effects"]["p95_ratio"] <= 1.05
        ),
        "geomean_phase_a_e2e": geomean >= 1.05,
    }
    return {
        "gates": gates,
        "geomean_phase_a_e2e_speedup": geomean,
        "pass": all(gates.values()),
    }


def run_gate(
    *,
    runs: int,
    warmup: int,
    iterations: int,
    lookup_iterations: int,
    profile_iterations: int,
) -> dict[str, object]:
    benchmark_runs: list[dict[str, object]] = []
    benchmark_returncodes: list[int] = []
    profile_runs: list[dict[str, object]] = []

    for run_index in range(1, runs + 1):
        _progress(f"fresh run {run_index}/{runs} benchmark")
        benchmark, returncode, benchmark_stderr = _run_json(
            [
                sys.executable,
                str(BENCHMARK),
                "--warmup",
                str(warmup),
                "--iterations",
                str(iterations),
                "--lookup-iterations",
                str(lookup_iterations),
                "--json",
            ]
        )
        if benchmark_stderr.strip():
            _progress(
                f"fresh run {run_index}/{runs} benchmark stderr: "
                f"{benchmark_stderr.strip()}"
            )
        benchmark_runs.append(benchmark)
        benchmark_returncodes.append(returncode)

        _progress(f"fresh run {run_index}/{runs} boundary profiler")
        profile, profile_returncode, profile_stderr = _run_json(
            [
                sys.executable,
                str(PROFILER),
                "--warmup",
                str(warmup),
                "--iterations",
                str(profile_iterations),
                "--json",
            ]
        )
        if profile_returncode != 0:
            raise RuntimeError(
                f"boundary profiler failed: {profile_stderr}"
            )
        if profile_stderr.strip():
            _progress(
                f"fresh run {run_index}/{runs} profiler stderr: "
                f"{profile_stderr.strip()}"
            )
        profile_runs.append(profile)

    _progress("aggregating three-process medians")
    case_metrics = _median_case_metrics(benchmark_runs)
    algorithmic = _aggregate_algorithmic(benchmark_runs)
    phase_a = _aggregate_phase_a(benchmark_runs, case_metrics)
    boundary_share = float(
        median(
            float(item["boundary_evidence_share"])
            for item in profile_runs
        )
    )
    profile_identity = all(
        bool(item["semantic_identity_under_instrumentation"])
        for item in profile_runs
    )
    phase_b_required = boundary_share >= 0.20

    final_ready = bool(
        algorithmic["pass"]
        and phase_a["pass"]
        and profile_identity
        and not phase_b_required
    )

    return {
        "schema": "TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE_GATE_V1",
        "fresh_process_runs": runs,
        "benchmark_returncodes": benchmark_returncodes,
        "algorithmic_hot_path": algorithmic,
        "phase_a_end_to_end": phase_a,
        "median_case_metrics": case_metrics,
        "boundary_profile": {
            "median_boundary_evidence_share": boundary_share,
            "semantic_identity_all_runs": profile_identity,
            "phase_b_required": phase_b_required,
        },
        "phase_a_performance_pass": bool(
            algorithmic["pass"] and phase_a["pass"]
        ),
        "final_10_10_ready": final_ready,
        "benchmark_runs": benchmark_runs,
        "profile_runs": profile_runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--lookup-iterations", type=int, default=2_000)
    parser.add_argument("--profile-iterations", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.runs < 3:
        raise SystemExit("at least three fresh-process runs are required")

    payload = run_gate(
        runs=args.runs,
        warmup=args.warmup,
        iterations=args.iterations,
        lookup_iterations=args.lookup_iterations,
        profile_iterations=args.profile_iterations,
    )

    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            "PHASE_A_PERFORMANCE="
            + (
                "PASS"
                if payload["phase_a_performance_pass"]
                else "FAIL"
            )
        )
        print(
            "PHASE_B_REQUIRED="
            + (
                "YES"
                if payload["boundary_profile"]["phase_b_required"]
                else "NO"
            )
        )
        print(
            "FINAL_10_10="
            + ("READY" if payload["final_10_10_ready"] else "HOLD")
        )

    return 0 if payload["final_10_10_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
