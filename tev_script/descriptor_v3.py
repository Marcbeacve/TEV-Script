from __future__ import annotations
import hmac
from typing import Any, Mapping
from .canonical import canonical_hash

DESCRIPTOR_SCHEMA = "TEV_SCRIPT_V3_DESCRIPTOR_V1"

def v3_descriptor() -> dict[str, Any]:
    body = {
        "schema": DESCRIPTOR_SCHEMA,
        "language_id": "TEV-Script",
        "language_version": "3.0.0",
        "release_name": "TEVScript MAX",
        "stable": False,
        "promotion_authority": False,
        "source_profiles": ["semantic_process", "v2_explicit_compatibility"],
        "program_ir_profiles": ["TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1", "V2_PROGRAM_IR_V4_EXPLICIT_COMPATIBILITY"],
        "semantic_basis": ["Field", "Transformation", "Apply"],
        "open_computation": "BOUNDED_QUANTA_WITH_OMEGA_CONTINUATIONS_V1",
        "implicit_unbounded_execution": False,
        "ambient_authority": False,
        "epistemic_qualifiers": ["Hypothesis", "Inferred", "Observed", "Predicted", "Verified"],
        "derived_stdlib": ["Residual", "Admission", "Selection", "Discovery", "Realization"],
    }
    return {**body, "descriptor_hash": canonical_hash(body)}

def verify_v3_descriptor(value: Mapping[str, Any]) -> bool:
    try:
        observed = dict(value)
        embedded = observed.pop("descriptor_hash")
        expected = v3_descriptor()
        expected_hash = expected.pop("descriptor_hash")
        return bool(isinstance(embedded, str) and hmac.compare_digest(embedded, expected_hash) and observed == expected)
    except (TypeError, KeyError):
        return False
