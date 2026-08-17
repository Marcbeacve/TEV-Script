from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable, Mapping

EXPECTED_GATES = frozenset(
    {
        "VERSION_IDENTITY",
        "NORMATIVE_SPEC",
        "CONFORMANCE",
        "DIFFERENTIAL_FUZZ",
        "SEMANTIC_INVARIANTS",
        "VERSION_MATRIX",
        "TOOLING_3X",
        "REPRODUCIBLE_RELEASE",
    }
)
GateFunction = Callable[[Path], dict[str, object]]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _default_gate_functions(
    fuzz_seed: int,
    fuzz_count: int,
) -> dict[str, GateFunction]:
    from .platform_compatibility import validate_version_matrix
    from .platform_conformance import run_platform_conformance
    from .platform_fuzz import run_differential_fuzz
    from .platform_invariants import validate_platform_invariants
    from .platform_release import validate_platform_release
    from .platform_spec import validate_normative_index
    from .platform_tooling import validate_tooling_surface
    from .platform_versioning import validate_current_version_identity

    return {
        "VERSION_IDENTITY": validate_current_version_identity,
        "NORMATIVE_SPEC": validate_normative_index,
        "CONFORMANCE": run_platform_conformance,
        "DIFFERENTIAL_FUZZ": lambda root: run_differential_fuzz(
            root,
            seed=fuzz_seed,
            count=fuzz_count,
        ),
        "SEMANTIC_INVARIANTS": validate_platform_invariants,
        "VERSION_MATRIX": validate_version_matrix,
        "TOOLING_3X": validate_tooling_surface,
        "REPRODUCIBLE_RELEASE": validate_platform_release,
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
            "schema": "TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V1",
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
    for name in sorted(EXPECTED_GATES):
        try:
            receipt = dict(selected[name](root))
        except Exception as error:
            receipt = {"status": "FAIL", "error": type(error).__name__}
        if receipt.get("status") not in {"PASS", "HOLD", "FAIL"}:
            receipt = {"status": "FAIL", "error": "INVALID_GATE_STATUS"}
        outcomes[name] = receipt

    failed = sorted(
        name for name, receipt in outcomes.items() if receipt["status"] == "FAIL"
    )
    held = sorted(
        name for name, receipt in outcomes.items() if receipt["status"] == "HOLD"
    )
    status = "FAIL" if failed else ("HOLD" if held else "PASS")
    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V1",
        "status": status,
        "platform_completion": status,
        "missing_gates": [],
        "extra_gates": [],
        "failed_gates": failed,
        "hold_gates": held,
        "gates": outcomes,
    }
    release = outcomes.get("REPRODUCIBLE_RELEASE", {})
    if release.get("status") == "PASS":
        body["source_commit"] = release.get("source_commit")
        body["source_tree"] = release.get("source_tree")
    return {
        **body,
        "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


__all__ = ["EXPECTED_GATES", "validate_platform_completion"]
