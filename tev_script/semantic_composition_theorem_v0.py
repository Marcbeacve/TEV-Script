from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations

from .canonical import canonical_hash
from .semantic_apply_v0 import (
    apply_rule,
    outcome_after_field,
    parse_rule,
)
from .semantic_effects_v0 import effects_commute


def composition_law_hash(laws) -> str:
    rows = []
    for key, law in sorted(laws.items()):
        rows.append(
            {
                "key": key,
                "domain": law.domain,
                "complete": law.complete,
                "snapshot_reads_commute": (
                    law.snapshot_reads_commute
                ),
                "stable_reads_commute": (
                    law.stable_reads_commute
                ),
                "explicit_commuting_modes": [
                    list(pair)
                    for pair in sorted(
                        law.explicit_commuting_modes
                    )
                ],
            }
        )
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_COMPOSITION_LAW_CONTEXT_V0",
            "laws": rows,
        }
    )


@dataclass(frozen=True, slots=True)
class CompositionJudgmentV0:
    status: str
    reason: str
    left_then_right_hash: str = ""
    right_then_left_hash: str = ""
    context_hash: str = ""
    law_hash: str = ""
    left_rule_hash: str = ""
    right_rule_hash: str = ""


def _accesses(rule):
    _, rule_hash, operations, effects = parse_rule(rule)
    reads = []
    writes = []
    has_observation = False

    for operation in operations:
        payload = dict(operation.payload)
        if operation.opcode == "require":
            reads.append(
                (
                    str(payload["relation"]),
                    tuple(payload.get("arguments", [])),
                )
            )
        elif operation.opcode == "put":
            writes.append(
                (
                    str(payload["relation"]),
                    tuple(payload.get("arguments", [])),
                    "put",
                )
            )
        elif operation.opcode == "remove":
            writes.append(
                (
                    str(payload["relation"]),
                    (
                        tuple(payload["arguments"])
                        if "arguments" in payload
                        else None
                    ),
                    "remove",
                )
            )
        elif operation.opcode == "observe":
            has_observation = True
            target = payload.get("target_relation")
            if target:
                writes.append(
                    (
                        str(target),
                        None,
                        "observe",
                    )
                )

    return (
        rule_hash,
        tuple(reads),
        tuple(writes),
        tuple(effects),
        has_observation,
    )


def _overlap(left, right) -> bool:
    return (
        left[0] == right[0]
        and (
            left[1] is None
            or right[1] is None
            or left[1] == right[1]
        )
    )


def _outcome_status(outcome) -> str:
    roots = outcome.facts_for("tev.outcome")
    if len(roots) != 1:
        return "INVALID"
    return str(roots[0].arguments[0])


def prove_semantic_diamond(
    before,
    left,
    right,
    *,
    laws,
    context_hash: str,
    law_hash: str,
) -> CompositionJudgmentV0:
    expected_law_hash = composition_law_hash(laws)
    (
        left_rule_hash,
        left_reads,
        left_writes,
        left_effects,
        left_observation,
    ) = _accesses(left)
    (
        right_rule_hash,
        right_reads,
        right_writes,
        right_effects,
        right_observation,
    ) = _accesses(right)

    common = {
        "context_hash": context_hash,
        "law_hash": law_hash,
        "left_rule_hash": left_rule_hash,
        "right_rule_hash": right_rule_hash,
    }

    if law_hash != expected_law_hash:
        return CompositionJudgmentV0(
            "REJECT",
            "law_context_hash_mismatch",
            **common,
        )

    if left_observation or right_observation:
        return CompositionJudgmentV0(
            "PROOF_REQUIRED",
            "observation_requires_realization_witness",
            **common,
        )

    if any(
        _overlap(read, write)
        for read in left_reads
        for write in right_writes
    ) or any(
        _overlap(read, write)
        for read in right_reads
        for write in left_writes
    ):
        return CompositionJudgmentV0(
            "REJECT",
            "read_write_conflict",
            **common,
        )

    for left_write in left_writes:
        for right_write in right_writes:
            if not _overlap(left_write, right_write):
                continue
            identical_idempotent = (
                left_write[2] == right_write[2]
                and left_write[2] in {"put", "remove"}
                and left_write[1] is not None
                and left_write[1] == right_write[1]
            )
            if not identical_idempotent:
                return CompositionJudgmentV0(
                    "REJECT",
                    "write_write_conflict",
                    **common,
                )

    effects_ok, reasons = effects_commute(
        left_effects,
        right_effects,
        laws,
    )
    if not effects_ok:
        return CompositionJudgmentV0(
            "REJECT",
            ",".join(reasons),
            **common,
        )

    def apply_completed(field, rule):
        outcome = apply_rule(
            field,
            rule,
            mode="evaluate",
            context_hash=context_hash,
            law_hash=law_hash,
        )
        return (
            _outcome_status(outcome),
            outcome_after_field(outcome),
        )

    left_status, left_after = apply_completed(
        before,
        left,
    )
    right_status, right_after = apply_completed(
        before,
        right,
    )
    if (
        left_status != "COMPLETED"
        or right_status != "COMPLETED"
    ):
        return CompositionJudgmentV0(
            "REJECT",
            "component_not_applicable",
            **common,
        )

    lr_status, left_then_right = apply_completed(
        left_after,
        right,
    )
    rl_status, right_then_left = apply_completed(
        right_after,
        left,
    )
    if (
        lr_status != "COMPLETED"
        or rl_status != "COMPLETED"
    ):
        return CompositionJudgmentV0(
            "REJECT",
            "second_component_not_applicable",
            **common,
        )

    if (
        left_then_right.field_hash
        != right_then_left.field_hash
    ):
        return CompositionJudgmentV0(
            "LAW_VIOLATION",
            "dynamic_diamond_failed",
            left_then_right.field_hash,
            right_then_left.field_hash,
            **common,
        )

    return CompositionJudgmentV0(
        "PASS",
        "semantic_diamond_closed",
        left_then_right.field_hash,
        right_then_left.field_hash,
        **common,
    )


def commit_scope_hash(
    diamond: CompositionJudgmentV0,
) -> str:
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_COMMIT_COMPOSITION_SCOPE_V0",
            "left_after": diamond.left_then_right_hash,
            "right_after": diamond.right_then_left_hash,
            "context_hash": diamond.context_hash,
            "law_hash": diamond.law_hash,
            "left_rule_hash": diamond.left_rule_hash,
            "right_rule_hash": diamond.right_rule_hash,
        }
    )


def physical_commit_composition(
    diamond: CompositionJudgmentV0,
    *,
    proof_witness=None,
    trust_policy=None,
) -> CompositionJudgmentV0:
    if diamond.status != "PASS":
        return diamond

    scope_hash = commit_scope_hash(diamond)
    if not (
        proof_witness is not None
        and trust_policy is not None
        and trust_policy.accepts(
            proof_witness,
            scope_hash,
        )
    ):
        return CompositionJudgmentV0(
            "PROOF_REQUIRED",
            "external_commit_serializability",
            context_hash=diamond.context_hash,
            law_hash=diamond.law_hash,
            left_rule_hash=diamond.left_rule_hash,
            right_rule_hash=diamond.right_rule_hash,
        )

    return CompositionJudgmentV0(
        "PASS",
        (
            "semantic_plus_trusted_external_serializability:"
            + proof_witness.witness_hash
        ),
        diamond.left_then_right_hash,
        diamond.right_then_left_hash,
        diamond.context_hash,
        diamond.law_hash,
        diamond.left_rule_hash,
        diamond.right_rule_hash,
    )


def family_scope_hash(
    before,
    rules,
    context_hash: str,
    law_hash: str,
) -> str:
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_FAMILY_COMPOSITION_SCOPE_V0",
            "field_hash": before.field_hash,
            "rule_hashes": [
                parse_rule(rule)[1]
                for rule in rules
            ],
            "context_hash": context_hash,
            "law_hash": law_hash,
        }
    )


def prove_finite_family_serializable(
    before,
    rules,
    *,
    laws,
    context_hash: str,
    law_hash: str,
    max_exact_rules: int = 6,
    proof_witness=None,
    trust_policy=None,
) -> CompositionJudgmentV0:
    rules = tuple(rules)
    if law_hash != composition_law_hash(laws):
        return CompositionJudgmentV0(
            "REJECT",
            "law_context_hash_mismatch",
            context_hash=context_hash,
            law_hash=law_hash,
        )

    scope_hash = family_scope_hash(
        before,
        rules,
        context_hash,
        law_hash,
    )
    if len(rules) > max_exact_rules:
        if (
            proof_witness is not None
            and trust_policy is not None
            and trust_policy.accepts(
                proof_witness,
                scope_hash,
            )
        ):
            return CompositionJudgmentV0(
                "PASS",
                (
                    "trusted_family_serializability:"
                    + proof_witness.witness_hash
                ),
                context_hash=context_hash,
                law_hash=law_hash,
            )
        return CompositionJudgmentV0(
            "PROOF_REQUIRED",
            "family_exact_bound",
            context_hash=context_hash,
            law_hash=law_hash,
        )

    for left, right in combinations(rules, 2):
        pair = prove_semantic_diamond(
            before,
            left,
            right,
            laws=laws,
            context_hash=context_hash,
            law_hash=law_hash,
        )
        if pair.status != "PASS":
            return pair

    final_hashes: set[str] = set()
    for order in permutations(rules):
        current = before
        for rule in order:
            outcome = apply_rule(
                current,
                rule,
                mode="evaluate",
                context_hash=context_hash,
                law_hash=law_hash,
            )
            if _outcome_status(outcome) != "COMPLETED":
                return CompositionJudgmentV0(
                    "REJECT",
                    "family_component_not_applicable",
                    context_hash=context_hash,
                    law_hash=law_hash,
                )
            current = outcome_after_field(outcome)

        final_hashes.add(current.field_hash)
        if len(final_hashes) > 1:
            return CompositionJudgmentV0(
                "LAW_VIOLATION",
                "family_permutation_divergence",
                context_hash=context_hash,
                law_hash=law_hash,
            )

    final_hash = next(
        iter(final_hashes),
        before.field_hash,
    )
    return CompositionJudgmentV0(
        "PASS",
        "finite_family_exhaustive",
        final_hash,
        final_hash,
        context_hash,
        law_hash,
    )


__all__ = [
    "CompositionJudgmentV0",
    "composition_law_hash",
    "prove_semantic_diamond",
    "commit_scope_hash",
    "physical_commit_composition",
    "family_scope_hash",
    "prove_finite_family_serializable",
]
