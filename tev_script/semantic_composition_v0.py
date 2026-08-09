from __future__ import annotations
from typing import Iterable
from .semantic_kernel_v0 import SemanticFieldV0
from .semantic_apply_v0 import RuleOpV0, rule_field, parse_rule, outcome_after_field, outcome_expected_field

_BARRIERS = {"UNKNOWN_COMMIT", "PARTIAL", "LAW_VIOLATION"}

def compose_rules(rule_id: str, rules: Iterable[SemanticFieldV0]) -> SemanticFieldV0:
    all_ops: list[RuleOpV0] = []
    all_effects = []
    for rule in rules:
        _, _, ops, effects = parse_rule(rule)
        offset = len(all_effects)
        for op in ops:
            if op.opcode == "effect":
                payload = dict(op.payload)
                payload["effect_index"] = int(payload["effect_index"]) + offset
                all_ops.append(RuleOpV0("effect", payload))
            else:
                all_ops.append(op)
        all_effects.extend(effects)
    return rule_field(rule_id, tuple(all_ops), tuple(all_effects))

def outcome_status(outcome: SemanticFieldV0) -> str:
    roots = outcome.facts_for("tev.outcome")
    if len(roots) != 1:
        raise ValueError("invalid outcome")
    return str(roots[0].arguments[0])

def composition_barrier(outcome: SemanticFieldV0) -> bool:
    return outcome_status(outcome) in _BARRIERS

def reconcile_unknown(outcome: SemanticFieldV0, observed_actual: SemanticFieldV0) -> tuple[str, SemanticFieldV0]:
    if outcome_status(outcome) != "UNKNOWN_COMMIT":
        raise ValueError("reconcile requires unknown commit")
    expected = outcome_expected_field(outcome)
    return ("COMMITTED" if expected.field_hash == observed_actual.field_hash else "DIVERGED", observed_actual)

__all__ = ["compose_rules", "outcome_status", "composition_barrier", "reconcile_unknown"]
