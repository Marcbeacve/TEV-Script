from __future__ import annotations

from dataclasses import replace
import random

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


def _hash(kind: str, seed: int, index: int) -> str:
    return canonical_hash({"kind": kind, "seed": seed, "index": index})


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
        raise AssertionError("generated forward-only program did not halt", program.program_hash)

    # A derived plan is sealed after preparation. Rewriting any dataclass field
    # must fail before a forged plan can reach the executor.
    try:
        replace(plan, program_hash="f" * 64)
    except TypeError:
        pass
    else:
        raise AssertionError("sealed execution plan could be rewritten")

    return quantum_count


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


def assert_v4_profile_identity() -> int:
    fixtures = RuntimeV5TotalCoreTests()
    units = (
        fixtures.pure_unit(),
        fixtures.recursive_unit(),
        fixtures.effects_unit(),
    )
    total = 0
    for unit in units:
        total += assert_program_differential_identity(_base_program(unit))
    return total


def main() -> int:
    total_quanta = 0
    maximum_instruction_count = 0
    maximum_fact_count = 0
    minimum_instruction_count = 129
    proof_programs = 0

    for seed in range(SEED_COUNT):
        program = build_fuzz_program(seed)
        instruction_count = len(program.instructions)
        minimum_instruction_count = min(minimum_instruction_count, instruction_count)
        maximum_instruction_count = max(maximum_instruction_count, instruction_count)
        maximum_fact_count = max(maximum_fact_count, len(program.initial_field.facts))
        if program.proof_admissions:
            proof_programs += 1
        total_quanta += assert_program_differential_identity(program)

    total_quanta += assert_v4_profile_identity()
    assert_checkpoint_mismatch_negative()

    print("TEVScript 3.1 IR5 prepared-runtime differential fuzz")
    print(f"SEEDS={SEED_COUNT}")
    print(f"TOTAL_QUANTA={total_quanta}")
    print(f"MIN_INSTRUCTIONS={minimum_instruction_count}")
    print(f"MAX_INSTRUCTIONS={maximum_instruction_count}")
    print(f"MAX_INITIAL_FACTS={maximum_fact_count}")
    print(f"PROOF_PROGRAMS={proof_programs}")
    print("V4_PROFILES=pure,recursive,effects")
    print("REFERENCE_PREPARED_EXACT_IDENTITY=PASS")
    print("SEALED_PLAN_NEGATIVE=PASS")
    print("CHECKPOINT_PROGRAM_MISMATCH_NEGATIVE=PASS")
    print("DIFFERENTIAL_FUZZ_1000=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
