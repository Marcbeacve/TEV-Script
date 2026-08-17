from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from tev_script.platform_completion import (
    GATE_ORDER,
    EXPECTED_GATES,
    validate_platform_completion,
    verify_platform_completion_receipt,
)


SOURCE_COMMIT = "a" * 40
SOURCE_TREE = "b" * 40
NORMATIVE_SET_SHA256 = "1" * 64
CONFORMANCE_SHA256 = "2" * 64


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash_object(value: object) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _full_regression_receipt(
    *,
    source_commit: str = SOURCE_COMMIT,
    source_tree: str = SOURCE_TREE,
) -> dict[str, object]:
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2",
        "status": "PASS",
        "reason": "",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "identity_stable": True,
        "worktree_clean_before": True,
        "worktree_clean_after": True,
        "returncode": 0,
        "test_count": 17,
        "failure_count": 0,
        "error_count": 0,
        "skipped_count": 0,
        "junit_sha256": "d" * 64,
    }
    return {**body, "receipt_sha256": _hash_object(body)}


def _release_receipt(
    version_receipt: dict[str, object],
    *,
    source_commit: str = SOURCE_COMMIT,
    source_tree: str = SOURCE_TREE,
    version_identity_sha256: str | None = None,
    normative_set_sha256: str = NORMATIVE_SET_SHA256,
    conformance_sha256: str = CONFORMANCE_SHA256,
) -> dict[str, object]:
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V2",
        "status": "PASS",
        "package_version": "3.1.1",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "wheel_sha256": "3" * 64,
        "sbom_sha256": "4" * 64,
        "normative_set_sha256": normative_set_sha256,
        "version_identity_sha256": (
            _hash_object(version_receipt)
            if version_identity_sha256 is None
            else version_identity_sha256
        ),
        "conformance_sha256": conformance_sha256,
        "build_environment_descriptor_sha256": "5" * 64,
        "provenance_sha256": "6" * 64,
        "runtime_dependency_count": 0,
    }
    return {**body, "receipt_sha256": _hash_object(body)}


def _pass_receipts() -> dict[str, dict[str, object]]:
    receipts: dict[str, dict[str, object]] = {
        name: {"status": "PASS", "gate": name}
        for name in EXPECTED_GATES
    }
    receipts["NORMATIVE_SPEC"] = {
        "status": "PASS",
        "normative_set_sha256": NORMATIVE_SET_SHA256,
    }
    receipts["CONFORMANCE"] = {
        "status": "PASS",
        "receipt_sha256": CONFORMANCE_SHA256,
    }
    receipts["FULL_REGRESSION"] = _full_regression_receipt()
    receipts["REPRODUCIBLE_RELEASE"] = _release_receipt(
        receipts["VERSION_IDENTITY"]
    )
    return receipts


def _gates():
    receipts = _pass_receipts()
    return {
        name: (lambda root, _name=name: copy.deepcopy(receipts[_name]))
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
    assert verify_platform_completion_receipt(receipt)


def test_aggregate_receipt_tamper_is_rejected(tmp_path: Path) -> None:
    receipt = validate_platform_completion(tmp_path, gate_functions=_gates())
    tampered = copy.deepcopy(receipt)
    tampered["full_regression_test_count"] = 18
    assert not verify_platform_completion_receipt(tampered)
    tampered = copy.deepcopy(receipt)
    tampered["gates"]["VERSION_IDENTITY"]["status"] = "FAIL"
    assert not verify_platform_completion_receipt(tampered)


def test_one_failure_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["NORMATIVE_SPEC"] = lambda root: {"status": "FAIL"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["platform_completion"] == "FAIL"
    assert receipt["failed_gates"] == ["NORMATIVE_SPEC"]
    assert verify_platform_completion_receipt(receipt)


def test_full_regression_failure_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["FULL_REGRESSION"] = lambda root: {"status": "FAIL"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["failed_gates"] == ["FULL_REGRESSION"]
    assert verify_platform_completion_receipt(receipt)


def test_invalid_full_regression_pass_receipt_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    invalid = _full_regression_receipt()
    invalid["receipt_sha256"] = "0" * 64
    gates["FULL_REGRESSION"] = lambda root: copy.deepcopy(invalid)
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["gates"]["FULL_REGRESSION"]["reason"] == "INVALID_CHILD_RECEIPT"


def test_invalid_release_pass_receipt_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    invalid = _pass_receipts()["REPRODUCIBLE_RELEASE"]
    invalid["receipt_sha256"] = "0" * 64
    gates["REPRODUCIBLE_RELEASE"] = lambda root: copy.deepcopy(invalid)
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["gates"]["REPRODUCIBLE_RELEASE"]["reason"] == "INVALID_CHILD_RECEIPT"


def test_release_and_regression_identity_mismatch_blocks_completion(tmp_path: Path) -> None:
    gates = _gates()
    gates["FULL_REGRESSION"] = lambda root: _full_regression_receipt(
        source_commit="c" * 40,
        source_tree="d" * 40,
    )
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["failed_gates"] == ["FULL_REGRESSION"]
    assert (
        receipt["gates"]["FULL_REGRESSION"]["reason"]
        == "SOURCE_IDENTITY_MISMATCH_WITH_RELEASE"
    )
    assert "regression_receipt" in receipt["gates"]["FULL_REGRESSION"]
    assert verify_platform_completion_receipt(receipt)


def test_missing_source_identity_on_pass_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    invalid = _pass_receipts()["REPRODUCIBLE_RELEASE"]
    invalid.pop("source_commit")
    body = {key: value for key, value in invalid.items() if key != "receipt_sha256"}
    invalid["receipt_sha256"] = _hash_object(body)
    gates["REPRODUCIBLE_RELEASE"] = lambda root: copy.deepcopy(invalid)
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["gates"]["REPRODUCIBLE_RELEASE"]["reason"] == "INVALID_CHILD_RECEIPT"


def test_release_version_identity_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    version = _pass_receipts()["VERSION_IDENTITY"]
    release = _release_receipt(version, version_identity_sha256="f" * 64)
    gates["REPRODUCIBLE_RELEASE"] = lambda root: copy.deepcopy(release)
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["failed_gates"] == ["REPRODUCIBLE_RELEASE"]
    assert receipt["gates"]["REPRODUCIBLE_RELEASE"]["reason"] == "RELEASE_EVIDENCE_MISMATCH"
    assert receipt["gates"]["REPRODUCIBLE_RELEASE"]["mismatches"] == [
        "VERSION_IDENTITY"
    ]
    assert verify_platform_completion_receipt(receipt)


def test_release_normative_and_conformance_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    version = _pass_receipts()["VERSION_IDENTITY"]
    release = _release_receipt(
        version,
        normative_set_sha256="e" * 64,
        conformance_sha256="f" * 64,
    )
    gates["REPRODUCIBLE_RELEASE"] = lambda root: copy.deepcopy(release)
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["gates"]["REPRODUCIBLE_RELEASE"]["mismatches"] == [
        "CONFORMANCE",
        "NORMATIVE_SPEC",
    ]
    assert verify_platform_completion_receipt(receipt)


def test_hold_never_promotes_to_pass(tmp_path: Path) -> None:
    gates = _gates()
    gates["DIFFERENTIAL_FUZZ"] = lambda root: {"status": "HOLD"}
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "HOLD"
    assert receipt["platform_completion"] == "HOLD"
    assert receipt["hold_gates"] == ["DIFFERENTIAL_FUZZ"]
    assert verify_platform_completion_receipt(receipt)


def test_missing_gate_fails_closed(tmp_path: Path) -> None:
    gates = _gates()
    gates.pop("FULL_REGRESSION")
    receipt = validate_platform_completion(tmp_path, gate_functions=gates)
    assert receipt["status"] == "FAIL"
    assert receipt["missing_gates"] == ["FULL_REGRESSION"]
    assert verify_platform_completion_receipt(receipt)
