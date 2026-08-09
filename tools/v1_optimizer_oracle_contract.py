from __future__ import annotations

import json
from typing import Any

OPTIMIZER_ORACLE_SCHEMA_V1 = "TEV_SCRIPT_V1_OPTIMIZER_ORACLE_RECEIPT_V1"
OPTIMIZER_ORACLE_PASS_MARKER = "TEV_SCRIPT_V1_OPTIMIZER_ORACLE=PASS"
OPTIMIZER_ORACLE_RECEIPT_PREFIX = "TEV_SCRIPT_V1_OPTIMIZER_ORACLE_RECEIPT="


class OptimizerOracleContractError(ValueError):
    pass


def validate_optimizer_oracle_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    if receipt.get("schema") != OPTIMIZER_ORACLE_SCHEMA_V1:
        raise OptimizerOracleContractError("schema")
    if not isinstance(receipt.get("provider_id"), str) or not receipt["provider_id"]:
        raise OptimizerOracleContractError("provider_id")
    if receipt.get("provider_kind") not in {"local", "external"}:
        raise OptimizerOracleContractError("provider_kind")
    if receipt.get("evidence_scope") != "finite_selected_carriers":
        raise OptimizerOracleContractError("evidence_scope")
    families = receipt.get("transformation_families")
    if not isinstance(families, list) or not families or any(not isinstance(x, str) or not x for x in families):
        raise OptimizerOracleContractError("transformation_families")
    moduli = receipt.get("moduli")
    if not isinstance(moduli, list) or not moduli or len(moduli) != len(set(moduli)):
        raise OptimizerOracleContractError("moduli")
    if any(not isinstance(x, int) or isinstance(x, bool) or x <= 5 for x in moduli):
        raise OptimizerOracleContractError("moduli")
    points = receipt.get("finite_program_points_verified")
    if not isinstance(points, int) or isinstance(points, bool) or points <= 0:
        raise OptimizerOracleContractError("finite_program_points_verified")
    if receipt.get("all_agree") is not True:
        raise OptimizerOracleContractError("all_agree")
    if receipt.get("negative_controls_detected") is not True:
        raise OptimizerOracleContractError("negative_controls_detected")
    for name in (
        "runtime_implementation_equivalence_proved",
        "universal_integer_equivalence_proved",
        "write_authority",
        "promotion_authority",
    ):
        if receipt.get(name) is not False:
            raise OptimizerOracleContractError(name)
    return receipt


def optimizer_oracle_receipt_line(receipt: dict[str, Any]) -> str:
    value = validate_optimizer_oracle_receipt(dict(receipt))
    return OPTIMIZER_ORACLE_RECEIPT_PREFIX + json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_optimizer_oracle_output(stdout: str) -> dict[str, Any]:
    lines = stdout.splitlines()
    if OPTIMIZER_ORACLE_PASS_MARKER not in lines:
        raise OptimizerOracleContractError("pass marker")
    matches = [line for line in lines if line.startswith(OPTIMIZER_ORACLE_RECEIPT_PREFIX)]
    if len(matches) != 1:
        raise OptimizerOracleContractError("receipt marker")
    try:
        receipt = json.loads(matches[0][len(OPTIMIZER_ORACLE_RECEIPT_PREFIX):])
    except json.JSONDecodeError as exc:
        raise OptimizerOracleContractError("receipt json") from exc
    if not isinstance(receipt, dict):
        raise OptimizerOracleContractError("receipt type")
    return validate_optimizer_oracle_receipt(receipt)


__all__ = [
    "OPTIMIZER_ORACLE_SCHEMA_V1",
    "OPTIMIZER_ORACLE_PASS_MARKER",
    "OPTIMIZER_ORACLE_RECEIPT_PREFIX",
    "OptimizerOracleContractError",
    "validate_optimizer_oracle_receipt",
    "optimizer_oracle_receipt_line",
    "parse_optimizer_oracle_output",
]
