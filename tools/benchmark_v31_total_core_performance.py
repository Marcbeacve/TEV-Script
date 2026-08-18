from __future__ import annotations

import argparse
import json
import math
from statistics import median
import time
from typing import Callable

from tev_script.canonical import canonical_hash
from tev_script.omega_semantic_basis_v1 import field_fact, field_transformation, semantic_field
from tev_script.program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    VerifiedProofAdmissionV1,
)
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
from tev_script.runtime_v5_total_optimized import (
    _fact_hash_index,
    prepare_total_core_execution_plan,
    run_prepared_total_core_quantum,
)
from tests.test_runtime_v5_total import RuntimeV5TotalCoreTests, _base_program
from tests.test_runtime_v5_total_optimized import (
    _branch_program,
    _plain_apply_program,
    _proof_apply_program,
)


AUTHORITY = canonical_hash({"authority": "tev.v31.performance"})
SOURCE = canonical_hash({"source": "tev.v31.performance"})


def _p95(values: list[int]) -> int:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return ordered[index]


def _samples(fn: Callable[[], object], *, warmup: int, iterations: int) -> list[int]:
    for _ in range(warmup):
        fn()
    values: list[int] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        values.append(time.perf_counter_ns() - start)
    return values


def _jump_program_10k() -> TotalCoreProgramV1:
    return TotalCoreProgramV1.build(
        program_id="PerfJump10k",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((), profile="actual"),
        transformations=(),
        v4_units=(),
        proof_admissions=(),
        instructions=(TotalCoreInstructionV1.jump(0),),
        entry_pc=0,
        quantum_step_limit=10_000,
        authority_hash=AUTHORITY,
    )


def _mixed_program() -> TotalCoreProgramV1:
    initial = field_fact("tev.perf.initial", ({"value": 1},))
    plain_added = field_fact("tev.perf.plain", ({"value": 2},))
    proof_added = field_fact("tev.perf.proof", ({"value": 3},))

    plain = field_transformation(
        transformation_id="tev.perf.plain.apply",
        add_facts=(plain_added,),
        effect_set_hash=canonical_hash({"effect": "plain"}),
        resource_vector_hash=canonical_hash({"resource": "plain"}),
        proof_requirement_hashes=(),
    )

    requirement = canonical_hash({"requirement": "mixed"})
    proof = field_transformation(
        transformation_id="tev.perf.proof.apply",
        add_facts=(proof_added,),
        effect_set_hash=canonical_hash({"effect": "proof"}),
        resource_vector_hash=canonical_hash({"resource": "proof"}),
        proof_requirement_hashes=(requirement,),
    )
    admission = VerifiedProofAdmissionV1.build(
        requirement_hash=requirement,
        verification_receipt_hash=canonical_hash({"receipt": "mixed"}),
        verifier_identity_hash=canonical_hash({"verifier": "mixed"}),
        authority_hash=AUTHORITY,
    )

    unit = RuntimeV5TotalCoreTests().pure_unit()
    return TotalCoreProgramV1.build(
        program_id="PerfMixed",
        source_semantic_hash=SOURCE,
        initial_field=semantic_field((initial,), profile="actual"),
        transformations=(plain, proof),
        v4_units=(unit,),
        proof_admissions=(admission,),
        instructions=(
            TotalCoreInstructionV1.branch_fact(
                initial.fact_hash,
                present_pc=1,
                absent_pc=5,
            ),
            TotalCoreInstructionV1.apply(plain.transformation_hash, next_pc=2),
            TotalCoreInstructionV1.apply(proof.transformation_hash, next_pc=3),
            TotalCoreInstructionV1.invoke_v4(
                unit_hash=unit.unit_hash,
                result_relation="tev.perf.v4",
                next_pc=4,
            ),
            TotalCoreInstructionV1.halt(),
            TotalCoreInstructionV1.halt(),
        ),
        entry_pc=0,
        quantum_step_limit=8,
        authority_hash=AUTHORITY,
    )


def _case_programs() -> dict[str, TotalCoreProgramV1]:
    fixtures = RuntimeV5TotalCoreTests()
    return {
        "jump_10k": _jump_program_10k(),
        "branch_fact_10": _branch_program(fact_count=10, present=True),
        "branch_fact_100": _branch_program(fact_count=100, present=True),
        "branch_fact_1k": _branch_program(fact_count=1_000, present=True),
        "branch_fact_10k": _branch_program(fact_count=10_000, present=True),
        "apply_plain": _plain_apply_program(),
        "apply_proof_admitted": _proof_apply_program(),
        "invoke_v4_pure": _base_program(fixtures.pure_unit()),
        "invoke_v4_recursive": _base_program(fixtures.recursive_unit()),
        "invoke_v4_effects": _base_program(fixtures.effects_unit()),
        "mixed_total_core": _mixed_program(),
    }


def benchmark_quantum_case(
    name: str,
    program: TotalCoreProgramV1,
    *,
    warmup: int,
    iterations: int,
    prepare_iterations: int,
) -> dict[str, object]:
    checkpoint = initial_total_core_checkpoint(program)
    plan = prepare_total_core_execution_plan(program)

    reference_identity = run_total_core_quantum(program, checkpoint)
    prepared_identity = run_prepared_total_core_quantum(plan, checkpoint)
    identity_pass = reference_identity == prepared_identity
    if not identity_pass:
        raise AssertionError(f"semantic identity failed before benchmark: {name}")

    reference_samples = _samples(
        lambda: run_total_core_quantum(program, checkpoint),
        warmup=warmup,
        iterations=iterations,
    )
    prepared_samples = _samples(
        lambda: run_prepared_total_core_quantum(plan, checkpoint),
        warmup=warmup,
        iterations=iterations,
    )
    prepare_samples = _samples(
        lambda: prepare_total_core_execution_plan(program),
        warmup=min(2, warmup),
        iterations=prepare_iterations,
    )

    reference_median = int(median(reference_samples))
    prepared_median = int(median(prepared_samples))
    reference_p95 = _p95(reference_samples)
    prepared_p95 = _p95(prepared_samples)

    return {
        "case": name,
        "iterations": iterations,
        "warmup_iterations": warmup,
        "reference_median_ns": reference_median,
        "prepared_median_ns": prepared_median,
        "speedup": reference_median / prepared_median,
        "reference_p95_ns": reference_p95,
        "prepared_p95_ns": prepared_p95,
        "p95_ratio": prepared_p95 / reference_p95,
        "plan_prepare_median_ns": int(median(prepare_samples)),
        "semantic_identity_pass": identity_pass,
    }


def benchmark_branch_algorithmic(*, iterations: int) -> dict[str, object]:
    cardinalities = (10, 100, 1_000, 10_000)
    cases: dict[str, dict[str, float | int]] = {}

    for cardinality in cardinalities:
        facts = tuple(
            field_fact("tev.perf.lookup", ({"index": index},))
            for index in range(cardinality)
        )
        field = semantic_field(facts, profile="actual")
        needle = facts[-1].fact_hash
        fact_hashes = _fact_hash_index(field)

        def reference_lookup() -> bool:
            return any(fact.fact_hash == needle for fact in field.facts)

        def prepared_lookup() -> bool:
            return needle in fact_hashes

        if reference_lookup() != prepared_lookup():
            raise AssertionError("branch lookup identity mismatch")

        reference_samples = _samples(reference_lookup, warmup=50, iterations=iterations)
        prepared_samples = _samples(prepared_lookup, warmup=50, iterations=iterations)
        reference_median = int(median(reference_samples))
        prepared_median = int(median(prepared_samples))
        cases[str(cardinality)] = {
            "reference_median_ns": reference_median,
            "prepared_median_ns": prepared_median,
            "speedup": reference_median / prepared_median,
        }

    c10 = cases["10"]
    c10k = cases["10000"]
    metrics = {
        "cases": cases,
        "lookup_10k_speedup": c10k["speedup"],
        "prepared_scaling_10k_over_10": (
            c10k["prepared_median_ns"] / c10["prepared_median_ns"]
        ),
        "reference_scaling_10k_over_10": (
            c10k["reference_median_ns"] / c10["reference_median_ns"]
        ),
    }
    metrics["pass"] = bool(
        metrics["lookup_10k_speedup"] >= 10.0
        and metrics["prepared_scaling_10k_over_10"] <= 2.0
        and metrics["reference_scaling_10k_over_10"] >= 20.0
    )
    return metrics


def _geomean(values: list[float]) -> float:
    return math.exp(sum(math.log(value) for value in values) / len(values))


def evaluate_phase_a_gates(results: list[dict[str, object]]) -> dict[str, object]:
    by_name = {str(item["case"]): item for item in results}
    identity = all(bool(item["semantic_identity_pass"]) for item in results)
    geomean = _geomean([float(item["speedup"]) for item in results])

    gates = {
        "semantic_identity_all_cases": identity,
        "jump_10k": float(by_name["jump_10k"]["speedup"]) >= 1.02,
        "apply_plain": float(by_name["apply_plain"]["speedup"]) >= 1.02,
        "apply_proof_admitted": float(by_name["apply_proof_admitted"]["speedup"]) >= 1.05,
        "mixed_total_core": float(by_name["mixed_total_core"]["speedup"]) >= 1.05,
        "branch_fact_10_p95": float(by_name["branch_fact_10"]["p95_ratio"]) <= 1.05,
        "branch_fact_100_p95": float(by_name["branch_fact_100"]["p95_ratio"]) <= 1.05,
        "branch_fact_1k_p95": float(by_name["branch_fact_1k"]["p95_ratio"]) <= 1.05,
        "branch_fact_10k_p95": float(by_name["branch_fact_10k"]["p95_ratio"]) <= 1.05,
        "invoke_v4_pure_p95": float(by_name["invoke_v4_pure"]["p95_ratio"]) <= 1.05,
        "invoke_v4_recursive_p95": float(by_name["invoke_v4_recursive"]["p95_ratio"]) <= 1.05,
        "invoke_v4_effects_p95": float(by_name["invoke_v4_effects"]["p95_ratio"]) <= 1.05,
        "geomean_phase_a_e2e": geomean >= 1.05,
    }
    return {
        "gates": gates,
        "geomean_phase_a_e2e_speedup": geomean,
        "pass": all(gates.values()),
    }


def run_benchmark(
    *,
    warmup: int,
    iterations: int,
    prepare_iterations: int,
    lookup_iterations: int,
) -> dict[str, object]:
    results = [
        benchmark_quantum_case(
            name,
            program,
            warmup=warmup,
            iterations=iterations,
            prepare_iterations=prepare_iterations,
        )
        for name, program in _case_programs().items()
    ]
    algorithmic = benchmark_branch_algorithmic(iterations=lookup_iterations)
    phase_a = evaluate_phase_a_gates(results)
    return {
        "schema": "TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE_EXPERIMENT_V1",
        "algorithmic_hot_path": algorithmic,
        "phase_a_end_to_end": phase_a,
        "cases": results,
        "performance_pass": bool(algorithmic["pass"] and phase_a["pass"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--prepare-iterations", type=int, default=5)
    parser.add_argument("--lookup-iterations", type=int, default=2_000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = run_benchmark(
        warmup=args.warmup,
        iterations=args.iterations,
        prepare_iterations=args.prepare_iterations,
        lookup_iterations=args.lookup_iterations,
    )
    if args.json:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["performance_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
