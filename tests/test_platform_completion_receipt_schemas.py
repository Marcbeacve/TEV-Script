from __future__ import annotations

import json
from pathlib import Path

from tev_script.platform_completion import EXPECTED_GATES

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def test_full_regression_schema_requires_zero_skip_pass_contract() -> None:
    schema = _load("tev-script-platform-full-regression-v2.schema.json")
    assert schema["properties"]["schema"]["const"] == "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2"
    pass_contract = schema["allOf"][0]["then"]["properties"]
    assert pass_contract["returncode"]["const"] == 0
    assert pass_contract["test_count"]["minimum"] == 1
    assert pass_contract["failure_count"]["const"] == 0
    assert pass_contract["error_count"]["const"] == 0
    assert pass_contract["skipped_count"]["const"] == 0
    assert pass_contract["identity_stable"]["const"] is True
    assert pass_contract["worktree_clean_before"]["const"] is True
    assert pass_contract["worktree_clean_after"]["const"] is True


def test_completion_schema_requires_all_nine_gates_only_for_pass() -> None:
    schema = _load("tev-script-platform-completion-receipt-v2.schema.json")
    assert schema["properties"]["schema"]["const"] == "TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V2"
    gate_properties = set(schema["properties"]["gates"]["properties"])
    assert gate_properties == EXPECTED_GATES
    assert "required" not in schema["properties"]["gates"]
    pass_gate_requirements = set(
        schema["allOf"][0]["then"]["properties"]["gates"]["required"]
    )
    assert pass_gate_requirements == EXPECTED_GATES
    assert "FULL_REGRESSION" in pass_gate_requirements


def test_completion_pass_schema_requires_exact_source_and_regression_binding() -> None:
    schema = _load("tev-script-platform-completion-receipt-v2.schema.json")
    required = set(schema["allOf"][0]["then"]["required"])
    assert required == {
        "source_commit",
        "source_tree",
        "full_regression_receipt_sha256",
        "full_regression_test_count",
    }
