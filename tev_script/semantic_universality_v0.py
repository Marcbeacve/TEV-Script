from __future__ import annotations

from dataclasses import dataclass

from .canonical import canonical_hash
from .semantic_apply_v0 import (
    RuleOpV0,
    apply_rule,
    outcome_after_field,
    rule_field,
)
from .semantic_kernel_v0 import FactV0, SemanticFieldV0

_COUNTER_DECLS = (
    ("machine.pc", 1),
    ("machine.c0", 1),
    ("machine.c1", 1),
    ("machine.halted", 1),
)

THEOREM_SCOPE = canonical_hash(
    {
        "schema": "TEV_SCRIPT_TWO_COUNTER_UNIVERSALITY_THEOREM_SCOPE_V0",
        "source_model": "deterministic_two_counter_machine",
    }
)


@dataclass(frozen=True, slots=True)
class CounterInstructionV0:
    op: str
    counter: int = 0
    next_pc: int = 0
    zero_pc: int = 0
    nonzero_pc: int = 0

    def __post_init__(self) -> None:
        if self.op not in {"INC", "DECJZ", "HALT"}:
            raise ValueError("instruction")
        if self.counter not in {0, 1}:
            raise ValueError("counter")


@dataclass(frozen=True, slots=True)
class CounterMachineStateV0:
    pc: int
    c0: int
    c1: int
    halted: bool = False

    def __post_init__(self) -> None:
        if min(self.pc, self.c0, self.c1) < 0:
            raise ValueError("state")


@dataclass(frozen=True, slots=True)
class UniversalityWitnessV0:
    status: str
    source_model: str
    step_embedding: str
    operational_quantum: str
    unbounded_trace: str
    theorem_boundary: str
    proof_witness_hash: str = ""


def validate_program(
    program: tuple[CounterInstructionV0, ...],
) -> None:
    if not program:
        raise ValueError("empty_program")

    size = len(program)
    for instruction in program:
        if instruction.op == "HALT":
            targets = ()
        elif instruction.op == "INC":
            targets = (instruction.next_pc,)
        else:
            targets = (
                instruction.zero_pc,
                instruction.nonzero_pc,
            )
        if any(
            target < 0 or target >= size
            for target in targets
        ):
            raise ValueError("jump_target")


def counter_step(
    program: tuple[CounterInstructionV0, ...],
    state: CounterMachineStateV0,
) -> CounterMachineStateV0:
    validate_program(program)

    if state.halted:
        return state
    if state.pc >= len(program):
        raise ValueError("pc")

    instruction = program[state.pc]
    if instruction.op == "HALT":
        return CounterMachineStateV0(
            state.pc,
            state.c0,
            state.c1,
            True,
        )

    counters = [state.c0, state.c1]
    if instruction.op == "INC":
        counters[instruction.counter] += 1
        return CounterMachineStateV0(
            instruction.next_pc,
            counters[0],
            counters[1],
        )

    if counters[instruction.counter] == 0:
        return CounterMachineStateV0(
            instruction.zero_pc,
            counters[0],
            counters[1],
        )

    counters[instruction.counter] -= 1
    return CounterMachineStateV0(
        instruction.nonzero_pc,
        counters[0],
        counters[1],
    )


def counter_state_field(
    state: CounterMachineStateV0,
) -> SemanticFieldV0:
    return SemanticFieldV0.build(
        _COUNTER_DECLS,
        (
            FactV0("machine.pc", (state.pc,)),
            FactV0("machine.c0", (state.c0,)),
            FactV0("machine.c1", (state.c1,)),
            FactV0("machine.halted", (state.halted,)),
        ),
    )


def counter_state_from_field(
    field: SemanticFieldV0,
) -> CounterMachineStateV0:
    def one(relation: str):
        facts = field.facts_for(relation)
        if len(facts) != 1:
            raise ValueError("counter_state_field")
        return facts[0].arguments[0]

    return CounterMachineStateV0(
        int(one("machine.pc")),
        int(one("machine.c0")),
        int(one("machine.c1")),
        bool(one("machine.halted")),
    )


def counter_step_rule(
    program: tuple[CounterInstructionV0, ...],
    state: CounterMachineStateV0,
):
    target = counter_step(program, state)
    operations: list[RuleOpV0] = []

    for relation, value in (
        ("machine.pc", target.pc),
        ("machine.c0", target.c0),
        ("machine.c1", target.c1),
        ("machine.halted", target.halted),
    ):
        operations.append(
            RuleOpV0(
                "remove",
                {"relation": relation},
            )
        )
        operations.append(
            RuleOpV0(
                "put",
                {
                    "relation": relation,
                    "arguments": [value],
                },
            )
        )

    return rule_field(
        f"counter.step.{state.pc}",
        tuple(operations),
    )


def embedded_counter_step(
    program: tuple[CounterInstructionV0, ...],
    state: CounterMachineStateV0,
) -> CounterMachineStateV0:
    before = counter_state_field(state)
    outcome = apply_rule(
        before,
        counter_step_rule(program, state),
        mode="evaluate",
    )
    return counter_state_from_field(
        outcome_after_field(outcome)
    )


def run_counter_quantum(
    program: tuple[CounterInstructionV0, ...],
    state: CounterMachineStateV0,
    fuel: int,
):
    if fuel < 0:
        raise ValueError("fuel")

    used = 0
    current = state
    while used < fuel and not current.halted:
        current = embedded_counter_step(
            program,
            current,
        )
        used += 1

    return (
        "COMPLETED" if current.halted else "SUSPENDED",
        current,
        used,
    )


def verify_step_embedding(
    program,
    samples,
) -> bool:
    return all(
        embedded_counter_step(program, state)
        == counter_step(program, state)
        for state in samples
    )


def trace_universality_witness(
    step_embedding_valid: bool,
    *,
    proof_witness=None,
    trust_policy=None,
) -> UniversalityWitnessV0:
    if not step_embedding_valid:
        return UniversalityWitnessV0(
            "REJECT",
            "two_counter_machine",
            "failed",
            "bounded_total",
            "required",
            "embedding_failed",
        )

    if not (
        proof_witness is not None
        and trust_policy is not None
        and trust_policy.accepts(
            proof_witness,
            THEOREM_SCOPE,
        )
    ):
        return UniversalityWitnessV0(
            "PROOF_REQUIRED",
            "two_counter_machine",
            "exact_Field+Apply_one_step",
            "bounded_total",
            "unbounded_continuations",
            "source_universality_theorem",
        )

    return UniversalityWitnessV0(
        "PASS_RELATIVE",
        "two_counter_machine",
        "exact_Field+Apply_one_step",
        "bounded_total",
        "unbounded_continuations",
        "trusted_source_universality_theorem",
        proof_witness.witness_hash,
    )


__all__ = [
    "CounterInstructionV0",
    "CounterMachineStateV0",
    "UniversalityWitnessV0",
    "THEOREM_SCOPE",
    "validate_program",
    "counter_step",
    "counter_state_field",
    "counter_state_from_field",
    "counter_step_rule",
    "embedded_counter_step",
    "run_counter_quantum",
    "verify_step_embedding",
    "trace_universality_witness",
]
