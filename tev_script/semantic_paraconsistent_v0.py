from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping

from .canonical import canonical_hash


@dataclass(frozen=True, slots=True)
class FourValueV0:
    support: bool
    refute: bool

    @property
    def name(self) -> str:
        if self.support and self.refute:
            return "BOTH"
        if self.support:
            return "TRUE_ONLY"
        if self.refute:
            return "FALSE_ONLY"
        return "NEITHER"

    @classmethod
    def from_name(cls, name: str) -> "FourValueV0":
        if name not in {"NEITHER", "TRUE_ONLY", "FALSE_ONLY", "BOTH"}:
            raise ValueError("four_value")
        return cls(
            name in {"TRUE_ONLY", "BOTH"},
            name in {"FALSE_ONLY", "BOTH"},
        )

    def negate(self) -> "FourValueV0":
        return FourValueV0(self.refute, self.support)

    def conjunction(self, other: "FourValueV0") -> "FourValueV0":
        return FourValueV0(
            self.support and other.support,
            self.refute or other.refute,
        )

    def disjunction(self, other: "FourValueV0") -> "FourValueV0":
        return FourValueV0(
            self.support or other.support,
            self.refute and other.refute,
        )


@dataclass(frozen=True, slots=True)
class RevisionPolicyV0:
    policy_id: str
    source_priority: tuple[str, ...] = ()
    prefer_newer_knowledge: bool = True

    def __post_init__(self) -> None:
        if len(set(self.source_priority)) != len(self.source_priority):
            raise ValueError("duplicate_source_priority")

    @property
    def policy_hash(self) -> str:
        return canonical_hash(
            {
                "schema": "TEV_SCRIPT_REVISION_POLICY_V0",
                "policy_id": self.policy_id,
                "source_priority": list(self.source_priority),
                "prefer_newer_knowledge": self.prefer_newer_knowledge,
            }
        )

    def priority(self, source: str) -> int:
        try:
            return len(self.source_priority) - self.source_priority.index(source)
        except ValueError:
            return 0


@dataclass(frozen=True, slots=True)
class InferenceJudgmentV0:
    status: str
    reason: str
    countermodel: tuple[tuple[str, str], ...] = ()


def four_value_of(field, proposition: str) -> FourValueV0:
    invalid = {
        str(f.arguments[0])
        for f in field.facts_for("tev.evidence.invalidated")
    }
    support = False
    refute = False
    for fact in field.facts_for("tev.evidence"):
        eid, prop, polarity, _, _, _, _, status = fact.arguments
        if (
            str(prop) != proposition
            or str(status) != "active"
            or str(eid) in invalid
        ):
            continue
        support |= str(polarity) == "support"
        refute |= str(polarity) == "refute"
    return FourValueV0(support, refute)


def revised_four_value(
    field,
    proposition: str,
    policy: RevisionPolicyV0,
) -> FourValueV0:
    invalid = {
        str(f.arguments[0])
        for f in field.facts_for("tev.evidence.invalidated")
    }
    rows: list[tuple[int, int, str]] = []
    for fact in field.facts_for("tev.evidence"):
        (
            eid,
            prop,
            polarity,
            source,
            _event_time,
            knowledge_time,
            _support_id,
            status,
        ) = fact.arguments
        if (
            str(prop) == proposition
            and str(status) == "active"
            and str(eid) not in invalid
        ):
            rows.append(
                (
                    policy.priority(str(source)),
                    int(knowledge_time),
                    str(polarity),
                )
            )
    if not rows:
        return FourValueV0(False, False)

    best_priority = max(row[0] for row in rows)
    rows = [row for row in rows if row[0] == best_priority]

    if policy.prefer_newer_knowledge:
        newest = max(row[1] for row in rows)
        rows = [row for row in rows if row[1] == newest]

    return FourValueV0(
        any(row[2] == "support" for row in rows),
        any(row[2] == "refute" for row in rows),
    )


def evaluate_formula(
    formula,
    valuation: Mapping[str, FourValueV0],
) -> FourValueV0:
    if isinstance(formula, str):
        return valuation.get(formula, FourValueV0(False, False))

    if not isinstance(formula, tuple) or not formula:
        raise ValueError("formula")

    op = formula[0]
    if op == "not" and len(formula) == 2:
        return evaluate_formula(formula[1], valuation).negate()

    if op in {"and", "or"} and len(formula) == 3:
        left = evaluate_formula(formula[1], valuation)
        right = evaluate_formula(formula[2], valuation)
        return (
            left.conjunction(right)
            if op == "and"
            else left.disjunction(right)
        )

    raise ValueError("formula")


def finite_entails(
    premises,
    conclusion,
    atoms,
    *,
    max_atoms: int = 7,
) -> InferenceJudgmentV0:
    atoms = tuple(sorted(set(atoms)))
    if len(atoms) > max_atoms:
        return InferenceJudgmentV0(
            "PROOF_REQUIRED",
            "valuation_space_bound",
        )

    values = (
        FourValueV0(False, False),
        FourValueV0(True, False),
        FourValueV0(False, True),
        FourValueV0(True, True),
    )
    for selected in product(values, repeat=len(atoms)):
        valuation = dict(zip(atoms, selected))
        premises_supported = all(
            evaluate_formula(formula, valuation).support
            for formula in premises
        )
        conclusion_supported = evaluate_formula(
            conclusion,
            valuation,
        ).support
        if premises_supported and not conclusion_supported:
            return InferenceJudgmentV0(
                "REJECT",
                "countermodel",
                tuple(
                    (atom, valuation[atom].name)
                    for atom in atoms
                ),
            )

    return InferenceJudgmentV0(
        "PASS",
        "exhaustive_four_valued_entailment",
    )


__all__ = [
    "FourValueV0",
    "RevisionPolicyV0",
    "InferenceJudgmentV0",
    "four_value_of",
    "revised_four_value",
    "evaluate_formula",
    "finite_entails",
]
