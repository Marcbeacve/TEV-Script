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


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _is_git_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


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


def _enforce_source_identity(outcomes: dict[str, dict[str, object]]) -> None:
    for name in ("REPRODUCIBLE_RELEASE", "FULL_REGRESSION"):
        receipt = outcomes[name]
        if receipt.get("status") != "PASS":
            continue
        if not _is_git_sha(receipt.get("source_commit")) or not _is_git_sha(
            receipt.get("source_tree")
        ):
            outcomes[name] = {
                **receipt,
                "status": "FAIL",
                "reason": "SOURCE_IDENTITY_MISSING",
            }

    release = outcomes["REPRODUCIBLE_RELEASE"]
    regression = outcomes["FULL_REGRESSION"]
    if release.get("status") != "PASS" or regression.get("status") != "PASS":
        return
    release_identity = (release["source_commit"], release["source_tree"])
    regression_identity = (regression["source_commit"], regression["source_tree"])
    if release_identity != regression_identity:
        outcomes["FULL_REGRESSION"] = {
            **regression,
            "status": "FAIL",
            "reason": "SOURCE_IDENTITY_MISMATCH_WITH_RELEASE",
            "release_source_commit": release["source_commit"],
            "release_source_tree": release["source_tree"],
        }


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
            "gates": {},
        }
        return {
            **body,
            "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
        }

    outcomes: dict[str, dict[str, object]] = {}
    for name in GATE_ORDER:
        try:
            receipt = dict(selected[name](root))
        except Exception as error:
            receipt = {"status": "FAIL", "error": type(error).__name__}
        if receipt.get("status") not in {"PASS", "HOLD", "FAIL"}:
            receipt = {"status": "FAIL", "error": "INVALID_GATE_STATUS"}
        outcomes[name] = receipt

    _enforce_source_identity(outcomes)

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
    return {
        **body,
        "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


__all__ = ["GATE_ORDER", "EXPECTED_GATES", "validate_platform_completion"]
