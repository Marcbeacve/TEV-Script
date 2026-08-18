from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tev_script.canonical import canonical_hash
from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import (
    field_fact,
    field_transformation,
    semantic_field,
)
from tev_script.program_ir_v5_total import (
    TotalCoreInstructionV1,
    TotalCoreProgramV1,
    VerifiedProofAdmissionV1,
)
from tev_script.runtime_v5_total import (
    initial_total_core_checkpoint,
    run_total_core_quantum,
)
from tev_script.runtime_v5_total_optimized import (
    prepare_total_core_execution_plan,
    run_prepared_total_core_quantum,
)
from tests.test_runtime_v5_total import RuntimeV5TotalCoreTests, _base_program


SEED_COUNT = 1_000
AUTHORITY = canonical_hash({"authority": "tev.v31.optimized.fuzz"})
EXPECTED_INSTRUCTION_KINDS = frozenset(
    {"apply", "branch_fact", "jump", "halt", "invoke_v4"}
)
EXPECTED_V4_PROFILES = frozenset({"pure", "recursive", "effects"})


def _hash(kind: str, seed: int, index: int) -> str:
    return canonical_hash({"kind": kind, "seed": seed, "index": index})


def _default_workers() -> int:
    return max(1, min(8, os.cpu_count() or 1))


def _partition_seed_ranges(
    *,
    seed_count: int,
    shard_count: int,
) -> tuple[tuple[int, int], ...]:
    if (
        isinstance(seed_count, bool)
        or not isinstance(seed_count, int)
        or seed_count <= 0
    ):
        raise ValueError("seed_count must be an integer > 0")
    if (
        isinstance(shard_count, bool)
        or not isinstance(shard_count, int)
        or shard_count <= 0
    ):
        raise ValueError("shard_count must be an integer > 0")

    actual_shards = min(seed_count, shard_count)
    base, extra = divmod(seed_count, actual_shards)
    ranges: list[tuple[int, int]] = []
    start = 0
    for index in range(actual_shards):
        size = base + (1 if index < extra else 0)
        stop = start + size
        ranges.append((start, stop))
        start = stop
    return tuple(ranges)


def build_fuzz_program(seed: int) -> TotalCoreProgramV1:
    rng = random.Random(seed)
    instruction_count = rng.randint(1, 128)
    fact_count = rng.randint(0, 512)

    initial_facts = tuple(
        field_fact("tev.fuzz.initial", ({"seed": seed, "index": index},))
        for index in range(fact_count)
    )
    initial_field = semantic_field(initial_facts, profile="actual")

    transformations = []
    admissions = []
    instructions = []

    for pc in range(instruction_count - 1):
        kind = rng.randrange(4)

        if kind == 0:
            instructions.append(TotalCoreInstructionV1.jump(pc + 1))
            continue

        if kind == 1:
            choose_present = bool(initial_facts) and rng.choice((True, False))
            if choose_present:
                needle = rng.choice(initial_facts)
            else:
                needle = field_fact(
                    "tev.fuzz.missing",
                    ({"seed": seed, "pc": pc},),
                )
            present_pc = min(pc + 1, instruction_count - 1)
            absent_pc = min(pc + 2, instruction_count - 1)
            instructions.append(
                TotalCoreInstructionV1.branch_fact(
                    needle.fact_hash,
                    present_pc=present_pc,
                    absent_pc=absent_pc,
                )
            )
            continue

        added = field_fact(
            "tev.fuzz.added",
            ({"seed": seed, "pc": pc},),
        )
        proof_requirements = ()
        if kind == 3:
            requirement = _hash("requirement", seed, pc)
            admission = VerifiedProofAdmissionV1.build(
                requirement_hash=requirement,
                verification_receipt_hash=_hash("verification_receipt", seed, pc),
                verifier_identity_hash=_hash("verifier", seed, pc),
                authority_hash=AUTHORITY,
            )
            admissions.append(admission)
            proof_requirements = (requirement,)

        transformation = field_transformation(
            transformation_id=f"tev.fuzz.tx.{seed}.{pc}",
            add_facts=(added,),
            effect_set_hash=_hash("effect", seed, pc),
            resource_vector_hash=_hash("resource", seed, pc),
            proof_requirement_hashes=proof_requirements,
        )
        transformations.append(transformation)
        instructions.append(
            TotalCoreInstructionV1.apply(
                transformation.transformation_hash,
                next_pc=pc + 1,
            )
        )

    instructions.append(TotalCoreInstructionV1.halt())

    return TotalCoreProgramV1.build(
        program_id=f"Fuzz{seed}",
        source_semantic_hash=_hash("source", seed, 0),
        initial_field=initial_field,
        transformations=tuple(transformations),
        v4_units=(),
        proof_admissions=tuple(admissions),
        instructions=tuple(instructions),
        entry_pc=0,
        quantum_step_limit=rng.randint(1, min(16, instruction_count)),
        authority_hash=AUTHORITY,
    )


def assert_program_differential_identity(program: TotalCoreProgramV1) -> int:
    plan = prepare_total_core_execution_plan(program)
    reference_checkpoint = initial_total_core_checkpoint(program)
    prepared_checkpoint = reference_checkpoint
    quantum_count = 0

    # The generated control flow is forward-only. This bound is deliberately
    # larger than the maximum number of instructions, even when quantum limit=1.
    for _ in range(len(program.instructions) + 2):
        reference = run_total_core_quantum(program, reference_checkpoint)
        prepared = run_prepared_total_core_quantum(plan, prepared_checkpoint)
        if reference != prepared:
            raise AssertionError(
                "prepared/reference mismatch",
                program.program_hash,
                quantum_count,
                reference,
                prepared,
            )
        quantum_count += 1
        if reference.status == "HALTED":
            break
        reference_checkpoint = reference.next_checkpoint
        prepared_checkpoint = prepared.next_checkpoint
    else:
        raise AssertionError(
            "generated forward-only program did not halt",
            program.program_hash,
        )

    # A derived plan is sealed after preparation. Rewriting any dataclass field
    # must fail before a forged plan can reach the executor.
    try:
        replace(plan, program_hash="f" * 64)
    except TypeError:
        pass
    else:
        raise AssertionError("sealed execution plan could be rewritten")

    return quantum_count


def _run_seed_shard(seed_range: tuple[int, int]) -> dict[str, object]:
    start, stop = seed_range
    total_quanta = 0
    maximum_instruction_count = 0
    maximum_fact_count = 0
    minimum_instruction_count = 129
    minimum_fact_count = 513
    proof_programs = 0
    instruction_kinds: set[str] = set()

    for seed in range(start, stop):
        program = build_fuzz_program(seed)
        instruction_count = len(program.instructions)
        fact_count = len(program.initial_field.facts)
        minimum_instruction_count = min(minimum_instruction_count, instruction_count)
        maximum_instruction_count = max(maximum_instruction_count, instruction_count)
        minimum_fact_count = min(minimum_fact_count, fact_count)
        maximum_fact_count = max(maximum_fact_count, fact_count)
        instruction_kinds.update(
            instruction.kind for instruction in program.instructions
        )
        if program.proof_admissions:
            proof_programs += 1
        total_quanta += assert_program_differential_identity(program)

    return {
        "start": start,
        "stop": stop,
        "seed_count": stop - start,
        "total_quanta": total_quanta,
        "minimum_instruction_count": minimum_instruction_count,
        "maximum_instruction_count": maximum_instruction_count,
        "minimum_fact_count": minimum_fact_count,
        "maximum_fact_count": maximum_fact_count,
        "proof_programs": proof_programs,
        "instruction_kinds": tuple(sorted(instruction_kinds)),
    }


def _run_parallel_seed_campaign(
    *,
    seed_count: int,
    workers: int,
    shard_count: int,
    progress_every: int,
) -> dict[str, object]:
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ValueError("workers must be an integer > 0")
    if (
        isinstance(progress_every, bool)
        or not isinstance(progress_every, int)
        or progress_every <= 0
    ):
        raise ValueError("progress_every must be an integer > 0")

    ranges = _partition_seed_ranges(
        seed_count=seed_count,
        shard_count=shard_count,
    )
    actual_workers = min(workers, len(ranges))
    completed_seeds = 0
    next_progress = progress_every
    results: list[dict[str, object]] = []

    print(
        f"[FUZZ] starting {seed_count} seeds across "
        f"{actual_workers} workers / {len(ranges)} shards",
        file=sys.stderr,
        flush=True,
    )

    with ProcessPoolExecutor(max_workers=actual_workers) as executor:
        future_to_range = {
            executor.submit(_run_seed_shard, seed_range): seed_range
            for seed_range in ranges
        }
        for future in as_completed(future_to_range):
            shard = future.result()
            results.append(shard)
            completed_seeds += int(shard["seed_count"])
            if completed_seeds >= next_progress or completed_seeds == seed_count:
                print(
                    f"[FUZZ] {completed_seeds}/{seed_count} seeds complete",
                    file=sys.stderr,
                    flush=True,
                )
                while next_progress <= completed_seeds:
                    next_progress += progress_every

    ordered = sorted(results, key=lambda item: int(item["start"]))
    covered = [
        seed
        for shard in ordered
        for seed in range(int(shard["start"]), int(shard["stop"]))
    ]
    if covered != list(range(seed_count)):
        raise AssertionError("parallel fuzz shard coverage is incomplete or overlapping")

    instruction_kinds: set[str] = set()
    for shard in ordered:
        instruction_kinds.update(str(value) for value in shard["instruction_kinds"])

    return {
        "workers": actual_workers,
        "shards": len(ranges),
        "total_quanta": sum(int(item["total_quanta"]) for item in ordered),
        "minimum_instruction_count": min(
            int(item["minimum_instruction_count"]) for item in ordered
        ),
        "maximum_instruction_count": max(
            int(item["maximum_instruction_count"]) for item in ordered
        ),
        "minimum_fact_count": min(
            int(item["minimum_fact_count"]) for item in ordered
        ),
        "maximum_fact_count": max(
            int(item["maximum_fact_count"]) for item in ordered
        ),
        "proof_programs": sum(int(item["proof_programs"]) for item in ordered),
        "instruction_kinds": instruction_kinds,
    }


def assert_checkpoint_mismatch_negative() -> None:
    left = build_fuzz_program(17)
    right = build_fuzz_program(23)
    right_plan = prepare_total_core_execution_plan(right)
    left_checkpoint = initial_total_core_checkpoint(left)

    try:
        run_prepared_total_core_quantum(right_plan, left_checkpoint)
    except TevScriptError:
        return
    raise AssertionError("checkpoint from another program was accepted")


def assert_v4_profile_identity() -> tuple[int, set[str], set[str]]:
    fixtures = RuntimeV5TotalCoreTests()
    units = (
        fixtures.pure_unit(),
        fixtures.recursive_unit(),
        fixtures.effects_unit(),
    )
    total = 0
    profiles: set[str] = set()
    instruction_kinds: set[str] = set()
    for unit in units:
        program = _base_program(unit)
        total += assert_program_differential_identity(program)
        profiles.add(unit.profile)
        instruction_kinds.update(
            instruction.kind for instruction in program.instructions
        )
    return total, profiles, instruction_kinds


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="run_v31_total_core_optimized_differential_fuzz.py"
    )
    parser.add_argument("--seeds", type=int, default=SEED_COUNT)
    parser.add_argument("--workers", type=int, default=_default_workers())
    parser.add_argument("--shards", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args()

    shard_count = args.shards if args.shards > 0 else args.workers * 4
    campaign = _run_parallel_seed_campaign(
        seed_count=args.seeds,
        workers=args.workers,
        shard_count=shard_count,
        progress_every=args.progress_every,
    )

    total_quanta = int(campaign["total_quanta"])
    instruction_kinds = set(campaign["instruction_kinds"])
    proof_programs = int(campaign["proof_programs"])

    v4_quanta, v4_profiles, v4_instruction_kinds = assert_v4_profile_identity()
    total_quanta += v4_quanta
    instruction_kinds.update(v4_instruction_kinds)
    assert_checkpoint_mismatch_negative()

    missing_instruction_kinds = sorted(
        EXPECTED_INSTRUCTION_KINDS - instruction_kinds
    )
    missing_v4_profiles = sorted(EXPECTED_V4_PROFILES - v4_profiles)
    if missing_instruction_kinds:
        raise AssertionError(
            "differential fuzz missed required instruction kinds",
            missing_instruction_kinds,
        )
    if missing_v4_profiles:
        raise AssertionError(
            "differential fuzz missed required V4 profiles",
            missing_v4_profiles,
        )
    if proof_programs == 0:
        raise AssertionError(
            "differential fuzz produced no proof-admitted program"
        )
    if args.seeds != SEED_COUNT:
        raise AssertionError(
            f"certification requires exactly {SEED_COUNT} seeds; got {args.seeds}"
        )

    print("TEVScript 3.1 IR5 prepared-runtime differential fuzz")
    print(f"SEEDS={args.seeds}")
    print(f"WORKERS={campaign['workers']}")
    print(f"SHARDS={campaign['shards']}")
    print(f"TOTAL_QUANTA={total_quanta}")
    print(f"MIN_INSTRUCTIONS={campaign['minimum_instruction_count']}")
    print(f"MAX_INSTRUCTIONS={campaign['maximum_instruction_count']}")
    print(f"MIN_INITIAL_FACTS={campaign['minimum_fact_count']}")
    print(f"MAX_INITIAL_FACTS={campaign['maximum_fact_count']}")
    print(f"PROOF_PROGRAMS={proof_programs}")
    print("INSTRUCTION_KINDS=" + ",".join(sorted(instruction_kinds)))
    print("V4_PROFILES=" + ",".join(sorted(v4_profiles)))
    print("REFERENCE_PREPARED_EXACT_IDENTITY=PASS")
    print("PARALLEL_SEED_COVERAGE=PASS")
    print("INSTRUCTION_COVERAGE=PASS")
    print("V4_PROFILE_COVERAGE=PASS")
    print("PROOF_APPLY_COVERAGE=PASS")
    print("SEALED_PLAN_NEGATIVE=PASS")
    print("CHECKPOINT_PROGRAM_MISMATCH_NEGATIVE=PASS")
    print("DIFFERENTIAL_FUZZ_1000=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
