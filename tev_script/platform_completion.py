from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Mapping

GATE_ORDER = (
    "VERSION_IDENTITY",
    "NORMATIVE_SPEC",
    "VERSION_MATRIX",
    "TOOLING_3X",
    "CONFORMANCE",
    "DIFFERENTIAL_FUZZ",
    "SEMANTIC_INVARIANTS",
    "REPRODUCIBLE_RELEASE",
    "FULL_REGRESSION",
)
EXPECTED_GATES = frozenset(GATE_ORDER)
GateFunction = Callable[[Path], dict[str, object]]
_COMPLETION_FIELDS = frozenset(
    {
        "schema",
        "status",
        "platform_completion",
        "missing_gates",
        "extra_gates",
        "failed_gates",
        "hold_gates",
        "gates",
        "source_commit",
        "source_tree",
        "full_regression_receipt_sha256",
        "full_regression_test_count",
        "receipt_sha256",
    }
)
_BINDING_FIELDS = (
    "source_commit",
    "source_tree",
    "full_regression_receipt_sha256",
    "full_regression_test_count",
)


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


def _is_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _is_git_sha(value: object) -> bool:
    return _is_hex(value, 40)


def _default_gate_functions(
    fuzz_seed: int,
    fuzz_count: int,
) -> dict[str, GateFunction]:
    from .platform_compatibility import validate_version_matrix
    from .platform_conformance import run_platform_conformance
    from .platform_fuzz import run_differential_fuzz
    from .platform_invariants import validate_platform_invariants
    from .platform_regression import run_full_regression
    from .platform_release import validate_platform_release
    from .platform_spec import validate_normative_index
    from .platform_tooling import validate_tooling_surface
    from .platform_versioning import validate_current_version_identity

    return {
        "VERSION_IDENTITY": validate_current_version_identity,
        "NORMATIVE_SPEC": validate_normative_index,
        "VERSION_MATRIX": validate_version_matrix,
        "TOOLING_3X": validate_tooling_surface,
        "CONFORMANCE": run_platform_conformance,
        "DIFFERENTIAL_FUZZ": lambda root: run_differential_fuzz(
            root,
            seed=fuzz_seed,
            count=fuzz_count,
        ),
        "SEMANTIC_INVARIANTS": validate_platform_invariants,
        "REPRODUCIBLE_RELEASE": validate_platform_release,
        "FULL_REGRESSION": run_full_regression,
    }


def _enforce_child_receipt_integrity(
    outcomes: dict[str, dict[str, object]],
) -> None:
    from .platform_regression import verify_full_regression_receipt
    from .platform_release_receipt import verify_platform_release_receipt

    checks = {
        "REPRODUCIBLE_RELEASE": verify_platform_release_receipt,
        "FULL_REGRESSION": verify_full_regression_receipt,
    }
    for name, verifier in checks.items():
        receipt = outcomes[name]
        if receipt.get("status") != "PASS":
            continue
        if not verifier(receipt):
            outcomes[name] = {
                "status": "FAIL",
                "reason": "INVALID_CHILD_RECEIPT",
                "upstream_receipt": receipt,
            }


def _enforce_source_identity(outcomes: dict[str, dict[str, object]]) -> None:
    for name in ("REPRODUCIBLE_RELEASE", "FULL_REGRESSION"):
        receipt = outcomes[name]
        if receipt.get("status") != "PASS":
            continue
        if not _is_git_sha(receipt.get("source_commit")) or not _is_git_sha(
            receipt.get("source_tree")
        ):
            outcomes[name] = {
                "status": "FAIL",
                "reason": "SOURCE_IDENTITY_MISSING",
                "upstream_receipt": receipt,
            }

    release = outcomes["REPRODUCIBLE_RELEASE"]
    regression = outcomes["FULL_REGRESSION"]
    if release.get("status") != "PASS" or regression.get("status") != "PASS":
        return
    release_identity = (release["source_commit"], release["source_tree"])
    regression_identity = (regression["source_commit"], regression["source_tree"])
    if release_identity != regression_identity:
        outcomes["FULL_REGRESSION"] = {
            "status": "FAIL",
            "reason": "SOURCE_IDENTITY_MISMATCH_WITH_RELEASE",
            "release_source_commit": release["source_commit"],
            "release_source_tree": release["source_tree"],
            "regression_receipt": regression,
        }


def _enforce_release_evidence_binding(
    outcomes: dict[str, dict[str, object]],
) -> None:
    release = outcomes["REPRODUCIBLE_RELEASE"]
    if release.get("status") != "PASS":
        return
    version = outcomes["VERSION_IDENTITY"]
    normative = outcomes["NORMATIVE_SPEC"]
    conformance = outcomes["CONFORMANCE"]
    if any(
        receipt.get("status") != "PASS"
        for receipt in (version, normative, conformance)
    ):
        return

    expected_version = _hash_object(version)
    expected_normative = normative.get("normative_set_sha256")
    expected_conformance = conformance.get("receipt_sha256")
    mismatches: list[str] = []
    if not _is_hex(expected_normative, 64) or release.get(
        "normative_set_sha256"
    ) != expected_normative:
        mismatches.append("NORMATIVE_SPEC")
    if not _is_hex(expected_conformance, 64) or release.get(
        "conformance_sha256"
    ) != expected_conformance:
        mismatches.append("CONFORMANCE")
    if release.get("version_identity_sha256") != expected_version:
        mismatches.append("VERSION_IDENTITY")
    if mismatches:
        outcomes["REPRODUCIBLE_RELEASE"] = {
            "status": "FAIL",
            "reason": "RELEASE_EVIDENCE_MISMATCH",
            "mismatches": sorted(mismatches),
            "release_receipt": release,
        }


def _release_evidence_matches(
    gate_map: dict[str, Mapping[str, object]],
) -> bool:
    release = gate_map["REPRODUCIBLE_RELEASE"]
    version = gate_map["VERSION_IDENTITY"]
    normative = gate_map["NORMATIVE_SPEC"]
    conformance = gate_map["CONFORMANCE"]
    expected_normative = normative.get("normative_set_sha256")
    expected_conformance = conformance.get("receipt_sha256")
    return bool(
        _is_hex(expected_normative, 64)
        and _is_hex(expected_conformance, 64)
        and release.get("version_identity_sha256") == _hash_object(version)
        and release.get("normative_set_sha256") == expected_normative
        and release.get("conformance_sha256") == expected_conformance
    )


def _verify_bound_children(
    receipt: dict[str, object],
    gate_map: dict[str, Mapping[str, object]],
) -> bool:
    from .platform_regression import verify_full_regression_receipt
    from .platform_release_receipt import verify_platform_release_receipt

    release = gate_map["REPRODUCIBLE_RELEASE"]
    regression = gate_map["FULL_REGRESSION"]
    if release.get("status") == "PASS" and not verify_platform_release_receipt(release):
        return False
    if regression.get("status") == "PASS" and not verify_full_regression_receipt(
        regression
    ):
        return False

    dependencies_pass = all(
        gate_map[name].get("status") == "PASS"
        for name in ("VERSION_IDENTITY", "NORMATIVE_SPEC", "CONFORMANCE")
    )
    if release.get("status") == "PASS" and dependencies_pass:
        if not _release_evidence_matches(gate_map):
            return False

    both_pass = release.get("status") == "PASS" and regression.get("status") == "PASS"
    if not both_pass:
        return not any(name in receipt for name in _BINDING_FIELDS)

    if (release.get("source_commit"), release.get("source_tree")) != (
        regression.get("source_commit"),
        regression.get("source_tree"),
    ):
        return False
    return bool(
        receipt.get("source_commit") == release.get("source_commit")
        and receipt.get("source_tree") == release.get("source_tree")
        and receipt.get("full_regression_receipt_sha256")
        == regression.get("receipt_sha256")
        and receipt.get("full_regression_test_count") == regression.get("test_count")
    )


def verify_platform_completion_receipt(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    receipt = dict(value)
    if set(receipt) - _COMPLETION_FIELDS:
        return False
    observed_hash = receipt.pop("receipt_sha256", None)
    if not _is_hex(observed_hash, 64):
        return False
    if _hash_object(receipt) != observed_hash:
        return False
    if receipt.get("schema") != "TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V2":
        return False
    status = receipt.get("status")
    if status not in {"PASS", "HOLD", "FAIL"}:
        return False
    if receipt.get("platform_completion") != status:
        return False
    for name in ("missing_gates", "extra_gates", "failed_gates", "hold_gates"):
        rows = receipt.get(name)
        if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
            return False
        if rows != sorted(set(rows)):
            return False

    missing = receipt["missing_gates"]
    extra = receipt["extra_gates"]
    gates = receipt.get("gates")
    if not isinstance(gates, Mapping):
        return False
    gate_map = dict(gates)
    if set(gate_map) - EXPECTED_GATES:
        return False
    if missing or extra:
        return bool(
            status == "FAIL"
            and receipt["failed_gates"] == []
            and receipt["hold_gates"] == []
            and gate_map == {}
            and not any(name in receipt for name in _BINDING_FIELDS)
        )
    if set(gate_map) != EXPECTED_GATES:
        return False

    for gate_receipt in gate_map.values():
        if not isinstance(gate_receipt, Mapping):
            return False
        if gate_receipt.get("status") not in {"PASS", "HOLD", "FAIL"}:
            return False

    failed = sorted(
        name for name, gate_receipt in gate_map.items() if gate_receipt["status"] == "FAIL"
    )
    held = sorted(
        name for name, gate_receipt in gate_map.items() if gate_receipt["status"] == "HOLD"
    )
    expected_status = "FAIL" if failed else ("HOLD" if held else "PASS")
    if receipt["failed_gates"] != failed or receipt["hold_gates"] != held:
        return False
    if status != expected_status:
        return False
    return _verify_bound_children(receipt, gate_map)


def validate_platform_completion(
    root: Path,
    *,
    fuzz_seed: int = 31031,
    fuzz_count: int = 128,
    gate_functions: Mapping[str, GateFunction] | None = None,
) -> dict[str, object]:
    root = Path(root)
    selected = (
        _default_gate_functions(fuzz_seed, fuzz_count)
        if gate_functions is None
        else dict(gate_functions)
    )
    missing = sorted(EXPECTED_GATES - set(selected))
    extra = sorted(set(selected) - EXPECTED_GATES)
    if missing or extra:
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V2",
            "status": "FAIL",
            "platform_completion": "FAIL",
            "missing_gates": missing,
            "extra_gates": extra,
            "failed_gates": [],
            "hold_gates": [],
            "gates": {},
        }
        return {**body, "receipt_sha256": _hash_object(body)}

    outcomes: dict[str, dict[str, object]] = {}
    for name in GATE_ORDER:
        try:
            receipt = dict(selected[name](root))
        except Exception as error:
            receipt = {"status": "FAIL", "error": type(error).__name__}
        if receipt.get("status") not in {"PASS", "HOLD", "FAIL"}:
            receipt = {"status": "FAIL", "error": "INVALID_GATE_STATUS"}
        outcomes[name] = receipt

    _enforce_child_receipt_integrity(outcomes)
    _enforce_source_identity(outcomes)
    _enforce_release_evidence_binding(outcomes)

    failed = sorted(
        name for name, receipt in outcomes.items() if receipt["status"] == "FAIL"
    )
    held = sorted(
        name for name, receipt in outcomes.items() if receipt["status"] == "HOLD"
    )
    status = "FAIL" if failed else ("HOLD" if held else "PASS")
    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V2",
        "status": status,
        "platform_completion": status,
        "missing_gates": [],
        "extra_gates": [],
        "failed_gates": failed,
        "hold_gates": held,
        "gates": outcomes,
    }
    release = outcomes["REPRODUCIBLE_RELEASE"]
    regression = outcomes["FULL_REGRESSION"]
    if release.get("status") == "PASS" and regression.get("status") == "PASS":
        body["source_commit"] = release["source_commit"]
        body["source_tree"] = release["source_tree"]
        body["full_regression_receipt_sha256"] = regression.get("receipt_sha256")
        body["full_regression_test_count"] = regression.get("test_count")
    return {**body, "receipt_sha256": _hash_object(body)}


__all__ = [
    "GATE_ORDER",
    "EXPECTED_GATES",
    "validate_platform_completion",
    "verify_platform_completion_receipt",
]
