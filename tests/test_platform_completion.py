from __future__ import annotations

from pathlib import Path

from tev_script.platform_completion import GATE_ORDER, EXPECTED_GATES, validate_platform_completion


SOURCE_COMMIT = "a" * 40
SOURCE_TREE = "b" * 40


def _gate_receipt(name: str, status: str) -> dict[str, object]:
    receipt: dict[str, object] = {"status": status, "gate": name}
    if name in {"REPRODUCIBLE_RELEASE", "FULL_REGRESSION"} and status == "PASS":
        receipt["source_commit"] = SOURCE_COMMIT
        receipt["source_tree"] = SOURCE_TREE
    if name == "FULL_REGRESSION" and status == "PASS":
        receipt["receipt_sha256"] = "c" * 64
        receipt["test_count"] = 17
    return receipt


def _gates(status: str = "PASS"):
    return {
        name: (lambda root, _name=name: _gate_receipt(_name, status))
        for name in EXPECTED_GATES
    }


def test_all_nine_gates_are_required_for_completion(tmp_path: Path) -> None:
    receipt = validate_platform_completion(tmp_path, gate_functions=_gates())
    assert receipt["status"] == "PASS"
    assert receipt["platform_completion"] == "PASS"
    assert set(receipt["gates"]) == EXPECTED_GATES
    assert len(EXPECTED_GATES) == 9
    assert GATE_ORDER[-1] == "FULL_REGRESSION"
    assert receipt["source_commit"] == SOURCE_COMMIT
    assert receipt["source_tree"] == SOURCE_TREE
    assert receipt["full_regression_test_count"] == 17


def test_one_failure_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["NORMATIVE_SPEC"] = lambda root: {"status": "FAIL"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["platform_completion"] == "FAIL"
    assert receipt["failed_gates"] == ["NORMATIVE_SPEC"]


def test_full_regression_failure_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["FULL_REGRESSION"] = lambda root: {"status": "FAIL"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["failed_gates"] == ["FULL_REGRESSION"]


def test_release_and_regression_identity_mismatch_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["FULL_REGRESSION"] = lambda root: {
        "status": "PASS",
        "source_commit": "c" * 40,
        "source_tree": "d" * 40,
        "receipt_sha256": "e" * 64,
        "test_count": 17,
    }
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["failed_gates"] == ["FULL_REGRESSION"]
    assert (
        receipt["gates"]["FULL_REGRESSION"]["reason"]
        == "SOURCE_IDENTITY_MISMATCH_WITH_RELEASE"
    )


def test_missing_source_identity_on_pass_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    gates["REPRODUCIBLE_RELEASE"] = lambda root: {"status": "PASS"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["failed_gates"] == ["REPRODUCIBLE_RELEASE"]
    assert (
        receipt["gates"]["REPRODUCIBLE_RELEASE"]["reason"]
        == "SOURCE_IDENTITY_MISSING"
    )


def test_hold_never_promotes_to_pass(tmp_path: Path) -> None:
    gates = _gates()
    gates["DIFFERENTIAL_FUZZ"] = lambda root: {"status": "HOLD"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "HOLD"
    assert receipt["platform_completion"] == "HOLD"
    assert receipt["hold_gates"] == ["DIFFERENTIAL_FUZZ"]


def test_missing_gate_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    gates.pop("FULL_REGRESSION")
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["missing_gates"] == ["FULL_REGRESSION"]
