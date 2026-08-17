from __future__ import annotations

from pathlib import Path

from tev_script.platform_fuzz import (
    REQUIRED_CASE_KINDS,
    generate_cases,
    run_differential_fuzz,
)

ROOT = Path(__file__).resolve().parents[1]


def test_generator_is_seed_replayable() -> None:
    assert generate_cases(310, 32) == generate_cases(310, 32)
    assert generate_cases(310, 32) != generate_cases(311, 32)


def test_generated_cases_are_bounded_total_core_inputs() -> None:
    cases = generate_cases(310, 12)
    assert len(cases) == 12
    assert all('version "3.1.0"' in case["source"] for case in cases)
    assert all(1 <= case["quantum_steps"] <= 8 for case in cases)
    assert all(1 <= case["epochs"] <= 3 for case in cases)
    assert {case["case_kind"] for case in cases} == REQUIRED_CASE_KINDS


def test_required_fuzz_families_cover_total_core_semantic_surface() -> None:
    assert REQUIRED_CASE_KINDS == {
        "control_flow",
        "branch_apply",
        "invoke_pure",
        "invoke_recursive",
        "invoke_effects",
        "proof_apply",
    }


def test_external_semantic_inputs_are_bound_into_generated_cases() -> None:
    by_kind = {case["case_kind"]: case for case in generate_cases(311, 6)}
    assert by_kind["invoke_pure"]["unit_sources"]
    assert by_kind["invoke_recursive"]["unit_sources"]
    assert by_kind["invoke_effects"]["unit_sources"]
    assert isinstance(by_kind["invoke_effects"]["effect_return"], int)
    assert len(by_kind["proof_apply"]["proof_requirement_hash"]) == 64
    assert len(by_kind["proof_apply"]["verification_receipt_hash"]) == 64
    assert len(by_kind["proof_apply"]["verifier_identity_hash"]) == 64


def test_campaign_passes_only_if_every_case_agrees(tmp_path: Path) -> None:
    receipt = run_differential_fuzz(
        tmp_path,
        seed=310,
        count=12,
        tool_resolver=lambda tool: "/node",
        case_executor=lambda root, case, node: {"status": "PASS"},
    )
    assert receipt["status"] == "PASS"
    assert receipt["first_divergence"] is None
    assert len(receipt["corpus_sha256"]) == 64
    assert set(receipt["case_kind_counts"]) == REQUIRED_CASE_KINDS
    assert all(receipt["case_kind_counts"][kind] >= 1 for kind in REQUIRED_CASE_KINDS)


def test_campaign_rejects_incomplete_required_coverage(tmp_path: Path) -> None:
    receipt = run_differential_fuzz(
        tmp_path,
        seed=310,
        count=5,
        tool_resolver=lambda tool: "/node",
        case_executor=lambda root, case, node: {"status": "PASS"},
    )
    assert receipt["status"] == "HOLD"
    assert receipt["reason"] == "INSUFFICIENT_CASE_KIND_COVERAGE"
    assert receipt["missing_case_kinds"]


def test_campaign_records_first_divergence(tmp_path: Path) -> None:
    def executor(root: Path, case: dict[str, object], node: str) -> dict[str, object]:
        del root, node
        return {
            "status": "FAIL" if case["case_id"] == "fuzz-0002" else "PASS",
            "reason": "DIFF",
        }

    receipt = run_differential_fuzz(
        tmp_path,
        seed=310,
        count=12,
        tool_resolver=lambda tool: "/node",
        case_executor=executor,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["first_divergence"]["case_id"] == "fuzz-0002"
    assert receipt["first_divergence"]["case_kind"] in REQUIRED_CASE_KINDS


def test_missing_node_is_hold_not_pass(tmp_path: Path) -> None:
    receipt = run_differential_fuzz(
        tmp_path,
        seed=310,
        count=6,
        tool_resolver=lambda tool: None,
        case_executor=lambda root, case, node: {"status": "PASS"},
    )
    assert receipt["status"] == "HOLD"
    assert receipt["reason"] == "NODE_UNAVAILABLE"


def test_real_total_core_differential_smoke_when_node_is_available() -> None:
    receipt = run_differential_fuzz(ROOT, seed=31031, count=6)
    if receipt["status"] == "HOLD":
        assert receipt["reason"] == "NODE_UNAVAILABLE"
    else:
        assert receipt["status"] == "PASS", receipt.get("first_divergence")
        assert set(receipt["case_kind_counts"]) == REQUIRED_CASE_KINDS
