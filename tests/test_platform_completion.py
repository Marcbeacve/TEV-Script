from __future__ import annotations

from pathlib import Path

from tev_script.platform_completion import EXPECTED_GATES, validate_platform_completion


def _gates(status: str = "PASS"):
    return {
        name: (lambda root, _name=name: {"status": status, "gate": _name})
        for name in EXPECTED_GATES
    }


def test_all_eight_gates_are_required_for_completion(tmp_path: Path) -> None:
    receipt = validate_platform_completion(tmp_path, gate_functions=_gates())
    assert receipt["status"] == "PASS"
    assert receipt["platform_completion"] == "PASS"
    assert set(receipt["gates"]) == EXPECTED_GATES


def test_one_failure_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["NORMATIVE_SPEC"] = lambda root: {"status": "FAIL"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["platform_completion"] == "FAIL"
    assert receipt["failed_gates"] == ["NORMATIVE_SPEC"]


def test_hold_never_promotes_to_pass(tmp_path: Path) -> None:
    gates = _gates()
    gates["DIFFERENTIAL_FUZZ"] = lambda root: {"status": "HOLD"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "HOLD"
    assert receipt["platform_completion"] == "HOLD"
    assert receipt["hold_gates"] == ["DIFFERENTIAL_FUZZ"]


def test_missing_gate_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    gates.pop("REPRODUCIBLE_RELEASE")
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["missing_gates"] == ["REPRODUCIBLE_RELEASE"]
