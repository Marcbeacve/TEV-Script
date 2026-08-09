from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .canonical import canonical_hash


@dataclass(frozen=True, slots=True)
class BooleanEquationV0:
    variable: str
    parents: tuple[str, ...]
    table: tuple[tuple[tuple[bool, ...], bool], ...]

    def __post_init__(self) -> None:
        expected = set(
            product((False, True), repeat=len(self.parents))
        )
        observed = {
            tuple(key)
            for key, _ in self.table
        }
        if observed != expected or len(observed) != len(self.table):
            raise ValueError(
                "equation truth table must be complete and deterministic"
            )

    def evaluate(self, values) -> bool:
        key = tuple(
            bool(values[parent])
            for parent in self.parents
        )
        for row, result in self.table:
            if tuple(row) == key:
                return bool(result)
        raise AssertionError("complete truth table")

    def to_object(self) -> dict:
        return {
            "variable": self.variable,
            "parents": list(self.parents),
            "table": [
                [list(key), bool(result)]
                for key, result in self.table
            ],
        }


@dataclass(frozen=True, slots=True)
class FiniteBooleanSCMV0:
    exogenous: tuple[str, ...]
    equations: tuple[BooleanEquationV0, ...]

    def __post_init__(self) -> None:
        known = set(self.exogenous)
        if len(known) != len(self.exogenous):
            raise ValueError("duplicate_exogenous")

        for equation in self.equations:
            if equation.variable in known:
                raise ValueError("duplicate_variable")
            if any(
                parent not in known
                for parent in equation.parents
            ):
                raise ValueError("topological_equations")
            known.add(equation.variable)

    @property
    def endogenous(self) -> tuple[str, ...]:
        return tuple(
            equation.variable
            for equation in self.equations
        )

    @property
    def model_hash(self) -> str:
        return canonical_hash(
            {
                "schema": "TEV_SCRIPT_FINITE_BOOLEAN_SCM_V0",
                "exogenous": list(self.exogenous),
                "equations": [
                    equation.to_object()
                    for equation in self.equations
                ],
            }
        )

    def evaluate(
        self,
        context,
        intervention=None,
    ) -> dict[str, bool]:
        if set(context) != set(self.exogenous):
            raise ValueError("context")

        intervention = dict(intervention or {})
        if not set(intervention) <= set(self.endogenous):
            raise ValueError("intervention")

        values = {
            key: bool(value)
            for key, value in context.items()
        }
        for equation in self.equations:
            if equation.variable in intervention:
                values[equation.variable] = bool(
                    intervention[equation.variable]
                )
            else:
                values[equation.variable] = equation.evaluate(values)
        return values


@dataclass(frozen=True, slots=True)
class CausalJudgmentV0:
    status: str
    criterion: str
    model_hash: str
    context_hash: str
    scope_hash: str
    cause: tuple
    outcome: tuple
    counterfactual: tuple = ()
    reason: str = ""


def causal_scope_hash(
    model,
    context,
    cause,
    outcome_variable,
    outcome_value,
    criterion,
) -> str:
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_CAUSAL_SCOPE_V0",
            "criterion": criterion,
            "model_hash": (
                model.model_hash
                if model is not None
                else "unspecified"
            ),
            "context": dict(
                sorted((context or {}).items())
            ),
            "cause": dict(
                sorted((cause or {}).items())
            ),
            "outcome": [
                outcome_variable,
                bool(outcome_value),
            ],
        }
    )


def but_for_actual_cause(
    model: FiniteBooleanSCMV0,
    context,
    cause,
    outcome_variable: str,
    outcome_value: bool,
) -> CausalJudgmentV0:
    criterion = "TEV_BUT_FOR_MINIMAL_V0"
    scope_hash = causal_scope_hash(
        model,
        context,
        cause,
        outcome_variable,
        outcome_value,
        criterion,
    )
    actual = model.evaluate(context)
    cause_tuple = tuple(
        sorted(
            (str(key), bool(value))
            for key, value in cause.items()
        )
    )
    context_hash = canonical_hash(
        dict(sorted(context.items()))
    )
    outcome = (
        outcome_variable,
        bool(outcome_value),
    )

    if not cause_tuple:
        return CausalJudgmentV0(
            "REJECT",
            criterion,
            model.model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            outcome,
            reason="empty_cause",
        )

    endogenous = set(model.endogenous)
    if any(
        variable not in endogenous
        for variable, _ in cause_tuple
    ):
        return CausalJudgmentV0(
            "REJECT",
            criterion,
            model.model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            outcome,
            reason="cause_not_endogenous",
        )

    if outcome_variable not in endogenous:
        return CausalJudgmentV0(
            "REJECT",
            criterion,
            model.model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            outcome,
            reason="outcome_not_endogenous",
        )

    if outcome_variable in dict(cause_tuple):
        return CausalJudgmentV0(
            "REJECT",
            criterion,
            model.model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            outcome,
            reason="self_causation_disallowed",
        )

    if (
        any(
            actual[variable] != value
            for variable, value in cause_tuple
        )
        or actual[outcome_variable] != bool(outcome_value)
    ):
        return CausalJudgmentV0(
            "REJECT",
            criterion,
            model.model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            outcome,
            reason="not_actual",
        )

    cause_values = dict(cause_tuple)
    names = [variable for variable, _ in cause_tuple]
    counterfactual = {
        variable: not cause_values[variable]
        for variable in names
    }

    if (
        model.evaluate(
            context,
            counterfactual,
        )[outcome_variable]
        == bool(outcome_value)
    ):
        return CausalJudgmentV0(
            "REJECT",
            criterion,
            model.model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            outcome,
            tuple(sorted(counterfactual.items())),
            "but_for_failed",
        )

    for mask in range(1, (1 << len(names)) - 1):
        subset_intervention = {
            names[index]: not cause_values[names[index]]
            for index in range(len(names))
            if mask & (1 << index)
        }
        if (
            model.evaluate(
                context,
                subset_intervention,
            )[outcome_variable]
            != bool(outcome_value)
        ):
            return CausalJudgmentV0(
                "REJECT",
                criterion,
                model.model_hash,
                context_hash,
                scope_hash,
                cause_tuple,
                outcome,
                tuple(sorted(subset_intervention.items())),
                "cause_not_minimal",
            )

    return CausalJudgmentV0(
        "PASS",
        criterion,
        model.model_hash,
        context_hash,
        scope_hash,
        cause_tuple,
        outcome,
        tuple(sorted(counterfactual.items())),
        "finite_exhaustive_but_for",
    )


def causal_judgment(
    *,
    criterion: str,
    model=None,
    context=None,
    cause=None,
    outcome_variable: str = "",
    outcome_value: bool = True,
    proof_witness=None,
    trust_policy=None,
) -> CausalJudgmentV0:
    if (
        criterion == "TEV_BUT_FOR_MINIMAL_V0"
        and model is not None
        and context is not None
        and cause is not None
    ):
        return but_for_actual_cause(
            model,
            context,
            cause,
            outcome_variable,
            outcome_value,
        )

    scope_hash = causal_scope_hash(
        model,
        context,
        cause,
        outcome_variable,
        outcome_value,
        criterion,
    )
    model_hash = (
        model.model_hash
        if model is not None
        else "unspecified"
    )
    context_hash = canonical_hash(
        dict(context or {})
    )
    cause_tuple = tuple(
        sorted((cause or {}).items())
    )

    if (
        proof_witness is not None
        and trust_policy is not None
        and trust_policy.accepts(
            proof_witness,
            scope_hash,
        )
    ):
        return CausalJudgmentV0(
            "PASS",
            criterion,
            model_hash,
            context_hash,
            scope_hash,
            cause_tuple,
            (outcome_variable, bool(outcome_value)),
            reason=(
                "trusted_external_proof:"
                + proof_witness.witness_hash
            ),
        )

    return CausalJudgmentV0(
        "PROOF_REQUIRED",
        criterion,
        model_hash,
        context_hash,
        scope_hash,
        cause_tuple,
        (outcome_variable, bool(outcome_value)),
        reason="unsupported_or_general_actual_causality",
    )


__all__ = [
    "BooleanEquationV0",
    "FiniteBooleanSCMV0",
    "CausalJudgmentV0",
    "causal_scope_hash",
    "but_for_actual_cause",
    "causal_judgment",
]
