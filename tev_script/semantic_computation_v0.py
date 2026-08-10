from __future__ import annotations
from typing import Callable, Iterable, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class QuantumOutcomeV0(Generic[T]):
    status: str
    value: T
    steps: int

def run_quantum(
    value: T,
    *,
    step: Callable[[T], T],
    done: Callable[[T], bool],
    fuel: int,
) -> QuantumOutcomeV0[T]:
    if fuel < 0:
        raise ValueError("fuel")
    current = value
    used = 0
    while used < fuel and not done(current):
        current = step(current)
        used += 1
    return QuantumOutcomeV0("COMPLETED" if done(current) else "SUSPENDED", current, used)

def run_to_completion_by_quanta(
    value: T,
    *,
    step: Callable[[T], T],
    done: Callable[[T], bool],
    quantum: int,
    max_quanta: int,
) -> QuantumOutcomeV0[T]:
    if quantum <= 0 or max_quanta <= 0:
        raise ValueError("bounds")
    current = value
    total = 0
    for _ in range(max_quanta):
        out = run_quantum(current, step=step, done=done, fuel=quantum)
        total += out.steps
        current = out.value
        if out.status == "COMPLETED":
            return QuantumOutcomeV0("COMPLETED", current, total)
    return QuantumOutcomeV0("BUDGET_EXCEEDED", current, total)

def strictly_decreasing_measure(values: Iterable[int]) -> bool:
    vals = tuple(values)
    return bool(vals) and all(b < a for a, b in zip(vals, vals[1:]))

def bounded_capacity_append(values: tuple[T, ...], item: T, maximum: int) -> tuple[str, tuple[T, ...]]:
    if maximum < 0:
        raise ValueError("maximum")
    if len(values) >= maximum:
        return "CAPACITY_EXCEEDED", values
    return "PASS", values + (item,)

__all__ = [
    "QuantumOutcomeV0", "run_quantum", "run_to_completion_by_quanta",
    "strictly_decreasing_measure", "bounded_capacity_append",
]
