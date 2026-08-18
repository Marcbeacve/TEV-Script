from __future__ import annotations

import argparse
import json
import time
from unittest.mock import patch

import tev_script.runtime_v5_total_optimized as optimized_runtime
from tools.benchmark_v31_total_core_performance import _mixed_program


def _timed_wrapper(name, fn, totals):
    def wrapped(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return fn(*args, **kwargs)
        finally:
            totals[name] += time.perf_counter_ns() - start
    return wrapped


def profile_boundary_share(*, warmup: int, iterations: int) -> dict[str, object]:
    program = _mixed_program()
    checkpoint = optimized_runtime.validate_total_core_checkpoint(
        program,
        __import__(
            "tev_script.runtime_v5_total",
            fromlist=["initial_total_core_checkpoint"],
        ).initial_total_core_checkpoint(program),
    )
    plan = optimized_runtime.prepare_total_core_execution_plan(program)

    # Prove instrumentation is observing a semantically valid prepared path.
    baseline = optimized_runtime.run_prepared_total_core_quantum(plan, checkpoint)

    originals = {
        "entry_checkpoint_validation": optimized_runtime.validate_total_core_checkpoint,
        "next_checkpoint_construction": optimized_runtime.total_core_checkpoint,
        "quantum_result_construction": optimized_runtime._build_quantum_result,
    }
    totals = {name: 0 for name in originals}

    patches = [
        patch.object(
            optimized_runtime,
            attr,
            _timed_wrapper(attr, original, totals),
        )
        for attr, original in originals.items()
    ]

    for manager in patches:
        manager.start()
    try:
        for _ in range(warmup):
            optimized_runtime.run_prepared_total_core_quantum(plan, checkpoint)
        for name in totals:
            totals[name] = 0

        start = time.perf_counter_ns()
        last = None
        for _ in range(iterations):
            last = optimized_runtime.run_prepared_total_core_quantum(plan, checkpoint)
        total_ns = time.perf_counter_ns() - start
    finally:
        for manager in reversed(patches):
            manager.stop()

    if last != baseline:
        raise AssertionError("profiling instrumentation changed canonical result")

    boundary_evidence_ns = sum(totals.values())
    share = boundary_evidence_ns / total_ns
    return {
        "schema": "TEV_SCRIPT_V31_TOTAL_CORE_BOUNDARY_PROFILE_V1",
        "iterations": iterations,
        "total_ns": total_ns,
        "components_ns": totals,
        "boundary_evidence_ns": boundary_evidence_ns,
        "boundary_evidence_share": share,
        "phase_b_required": share >= 0.20,
        "semantic_identity_under_instrumentation": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = profile_boundary_share(
        warmup=args.warmup,
        iterations=args.iterations,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
