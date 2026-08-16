from __future__ import annotations

import hmac
import json
from typing import Any, Callable, Mapping

from tev_script.canonical import canonical_hash
from tev_script.omega_semantic_basis_v1 import (
    apply_field_transformation,
    field_fact,
    field_transformation,
    semantic_field,
)

REPORT_SCHEMA = "TEV_SCRIPT_MAX_V3_PRIMITIVE_BASIS_REPORT_V1"
LANGUAGE_VERSION = "3.0.0"
_EFFECT_SET_HASH = "1" * 64
_RESOURCE_VECTOR_HASH = "2" * 64


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _partition(rows: list[dict[str, str]], key: Callable[[dict[str, str]], str]) -> list[list[str]]:
    groups: dict[str, list[str]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row["case_id"])
    return sorted((sorted(members) for members in groups.values()), key=lambda members: tuple(members))


def _partition_by_outcome(rows: list[dict[str, str]]) -> list[list[str]]:
    return _partition(rows, lambda row: row["outcome_hash"])


def _analyze(
    rows: list[dict[str, str]],
    key: Callable[[dict[str, str]], str],
    operational: list[list[str]],
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)

    counterexample: dict[str, str] | None = None
    sufficient = True
    for members in groups.values():
        outcomes = {item["outcome_hash"] for item in members}
        if len(outcomes) > 1:
            sufficient = False
            left = members[0]
            right = next(item for item in members[1:] if item["outcome_hash"] != left["outcome_hash"])
            counterexample = {
                "left_case_id": left["case_id"],
                "right_case_id": right["case_id"],
                "left_outcome_hash": left["outcome_hash"],
                "right_outcome_hash": right["outcome_hash"],
            }
            break

    partition = sorted((sorted(item["case_id"] for item in members) for members in groups.values()), key=lambda members: tuple(members))
    minimal = sufficient and partition == operational
    overrefined = sufficient and len(partition) > len(operational)
    return {
        "sufficient": sufficient,
        "minimal": minimal,
        "overrefined": overrefined,
        "class_count": len(partition),
        "classes": partition,
        "counterexample": counterexample,
    }


def _witness_rows() -> list[dict[str, str]]:
    closed = field_fact("door.state", ("closed",))
    opened = field_fact("door.state", ("open",))
    before = semantic_field((closed,), profile="actual")
    open_tx = field_transformation(
        transformation_id="door.open",
        required_before_hash=before.field_hash,
        remove_fact_hashes=(closed.fact_hash,),
        add_facts=(opened,),
        effect_set_hash=_EFFECT_SET_HASH,
        resource_vector_hash=_RESOURCE_VECTOR_HASH,
    )
    noop_tx = field_transformation(
        transformation_id="door.noop",
        required_before_hash=before.field_hash,
        effect_set_hash=_EFFECT_SET_HASH,
        resource_vector_hash=_RESOURCE_VECTOR_HASH,
    )
    opened_field, _ = apply_field_transformation(before, open_tx)
    closed_field, _ = apply_field_transformation(before, noop_tx)

    rows: list[dict[str, str]] = []
    for policy in ("policy_a", "policy_b"):
        rows.append(
            {
                "case_id": f"open_{policy}",
                "field_hash": before.field_hash,
                "transformation_hash": open_tx.transformation_hash,
                "policy_tag": policy,
                "outcome_hash": opened_field.field_hash,
            }
        )
        rows.append(
            {
                "case_id": f"noop_{policy}",
                "field_hash": before.field_hash,
                "transformation_hash": noop_tx.transformation_hash,
                "policy_tag": policy,
                "outcome_hash": closed_field.field_hash,
            }
        )
    return sorted(rows, key=lambda row: row["case_id"])


def evaluate_basis() -> dict[str, Any]:
    rows = _witness_rows()
    operational = _partition_by_outcome(rows)
    minimal = _analyze(
        rows,
        lambda row: canonical_hash([row["field_hash"], row["transformation_hash"]]),
        operational,
    )
    overrefined = _analyze(
        rows,
        lambda row: canonical_hash([row["field_hash"], row["transformation_hash"], row["policy_tag"]]),
        operational,
    )
    insufficient = _analyze(rows, lambda row: row["field_hash"], operational)

    passed = bool(
        minimal["sufficient"]
        and minimal["minimal"]
        and not minimal["overrefined"]
        and overrefined["sufficient"]
        and not overrefined["minimal"]
        and overrefined["overrefined"]
        and not insufficient["sufficient"]
        and isinstance(insufficient["counterexample"], dict)
    )
    body: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "status": "PASS" if passed else "HOLD",
        "witness_case_count": len(rows),
        "witness_hash": canonical_hash(rows),
        "operational_quotient": {
            "class_count": len(operational),
            "classes": operational,
        },
        "minimal": minimal,
        "overrefined": overrefined,
        "insufficient": insufficient,
        "kernel_tcb_expanded_bool": False,
        "promotion_authority_bool": False,
        "language_stable_bool": False,
    }
    return {**body, "report_hash": canonical_hash(body)}


def verify_basis_report(report: Mapping[str, Any]) -> bool:
    try:
        observed = dict(report)
        embedded = observed.get("report_hash")
        if not isinstance(embedded, str):
            return False
        body = {key: value for key, value in observed.items() if key != "report_hash"}
        if not hmac.compare_digest(embedded, canonical_hash(body)):
            return False
        expected = evaluate_basis()
        return hmac.compare_digest(_canonical(observed), _canonical(expected))
    except (TypeError, ValueError, OverflowError):
        return False


__all__ = ["REPORT_SCHEMA", "evaluate_basis", "verify_basis_report"]
