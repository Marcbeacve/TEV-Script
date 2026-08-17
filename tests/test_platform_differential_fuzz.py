from __future__ import annotations

from pathlib import Path

from tev_script.platform_fuzz import generate_cases, run_differential_fuzz

ROOT = Path(__file__).resolve().parents[1]


def test_generator_is_seed_replayable() -> None:
    assert generate_cases(310, 32) == generate_cases(310, 32)
    assert generate_cases(310, 32) != generate_cases(311, 32)


def test_generated_cases_are_bounded_total_core_sources() -> None:
    cases = generate_cases(310, 8)
    assert len(cases) == 8
    assert all('version "3.1.0"' in case["source"] for case in cases)
    assert all(1 <= case["quantum_steps"] <= 8 for case in cases)
    assert all(1 <= case["epochs"] <= 3 for case in cases)


def test_campaign_passes_only_if_every_case_agrees(tmp_path: Path) -> None:
    receipt = run_differential_fuzz(
        tmp_path,
        seed=310,
        count=8,
        tool_resolver=lambda tool: "/node",
        case_executor=lambda root, case, node: {"status": "PASS"},
    )
    assert receipt["status"] == "PASS"
    assert receipt["first_divergence"] is None
    assert len(receipt["corpus_sha256"]) == 64


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
        count=5,
        tool_resolver=lambda tool: "/node",
        case_executor=executor,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["first_divergence"]["case_id"] == "fuzz-0002"


def test_missing_node_is_hold_not_pass(tmp_path: Path) -> None:
    receipt = run_differential_fuzz(
        tmp_path,
        seed=310,
        count=1,
        tool_resolver=lambda tool: None,
        case_executor=lambda root, case, node: {"status": "PASS"},
    )
    assert receipt["status"] == "HOLD"


def test_real_total_core_differential_smoke_when_node_is_available() -> None:
    receipt = run_differential_fuzz(ROOT, seed=31031, count=4)
    if receipt["status"] == "HOLD":
        assert receipt["reason"] == "NODE_UNAVAILABLE"
    else:
        assert receipt["status"] == "PASS", receipt.get("first_divergence")
