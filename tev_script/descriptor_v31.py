from __future__ import annotations

import hmac
from typing import Any, Mapping

from .canonical import canonical_hash

DESCRIPTOR_SCHEMA_V31 = "TEV_SCRIPT_V31_DESCRIPTOR_V1"


def v31_descriptor() -> dict[str, Any]:
    body = {
        "schema": DESCRIPTOR_SCHEMA_V31,
        "language_id": "TEV-Script",
        "language_version": "3.1.0",
        "release_name": "TEVScript MAX",
        "stable": False,
        "promotion_authority": False,
        "program_ir_version": 5,
        "profiles": ["total_core"],
        "predecessor_v3": "3.0.0",
        "v2_units_embedded_without_reinterpretation": True,
        "proof_admission_external_only": True,
        "physical_effect_commit_inside_runtime": False,
        "semantic_basis": ["Field", "Transformation", "Apply"],
        "open_computation": "BOUNDED_QUANTA_WITH_OMEGA_CONTINUATIONS_V1",
        "runtime_targets": ["python_reference", "javascript_independent_required"],
    }
    return {**body, "descriptor_hash": canonical_hash(body)}


def verify_v31_descriptor(value: Mapping[str, Any]) -> bool:
    try:
        observed = dict(value)
        embedded = observed.pop("descriptor_hash")
        expected = v31_descriptor()
        expected_hash = expected.pop("descriptor_hash")
        return bool(
            isinstance(embedded, str)
            and hmac.compare_digest(embedded, expected_hash)
            and observed == expected
        )
    except (TypeError, KeyError):
        return False


__all__ = [
    "DESCRIPTOR_SCHEMA_V31",
    "v31_descriptor",
    "verify_v31_descriptor",
]
