from __future__ import annotations

from itertools import product
from pathlib import Path

from tools.validate_axiomatic_semantics_v0 import validate

ROOT = Path(__file__).resolve().parents[1]


def _compose(g, f, carrier):
    return frozenset(
        (x, z)
        for x in carrier
        for z in carrier
        if any((x, y) in f and (y, z) in g for y in carrier)
    )


def test_axiomatic_static_correspondence() -> None:
    assert validate(ROOT) == ()


def test_relational_composition_associative_exhaustive_carrier_2() -> None:
    carrier = (0, 1)
    pairs = tuple(product(carrier, carrier))
    relations = tuple(
        frozenset(
            pairs[index]
            for index in range(len(pairs))
            if mask & (1 << index)
        )
        for mask in range(1 << len(pairs))
    )
    for f in relations:
        for g in relations:
            for h in relations:
                assert _compose(h, _compose(g, f, carrier), carrier) == _compose(
                    _compose(h, g, carrier), f, carrier
                )


def test_four_value_algebra_exhaustive() -> None:
    values = tuple(product((False, True), repeat=2))

    def neg(value):
        return value[1], value[0]

    def conj(left, right):
        return left[0] and right[0], left[1] or right[1]

    def disj(left, right):
        return left[0] or right[0], left[1] and right[1]

    for value in values:
        assert neg(neg(value)) == value
    for left in values:
        for right in values:
            assert conj(left, right) == conj(right, left)
            assert disj(left, right) == disj(right, left)
            assert neg(conj(left, right)) == disj(neg(left), neg(right))
            assert neg(disj(left, right)) == conj(neg(left), neg(right))
            for third in values:
                assert conj(conj(left, right), third) == conj(
                    left, conj(right, third)
                )
                assert disj(disj(left, right), third) == disj(
                    left, disj(right, third)
                )


def test_selection_fail_closed_truth_table() -> None:
    for selected, admitted, proof_required, rejected in product(
        (False, True), repeat=4
    ):
        axioms_hold = (
            (not selected or admitted)
            and (not selected or not proof_required)
            and (not selected or not rejected)
        )
        if selected and axioms_hold:
            assert admitted
            assert not proof_required
            assert not rejected


def test_metadata_noncollapse_model() -> None:
    a = {"semantic": 0, "backend": 0, "cost": 0}
    b = {"semantic": 0, "backend": 1, "cost": 1}
    c = {"semantic": 1, "backend": 0, "cost": 0}
    sem_eq = lambda left, right: left["semantic"] == right["semantic"]

    assert sem_eq(a, b)
    assert a["backend"] != b["backend"]
    assert a["cost"] != b["cost"]

    assert not sem_eq(a, c)
    assert a["backend"] == c["backend"]
    assert a["cost"] == c["cost"]
