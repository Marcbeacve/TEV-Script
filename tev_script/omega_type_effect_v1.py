from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash
from .diagnostics import TevScriptError
from .omega_semantic_basis_v1 import (
    FieldFactV1,
    SemanticFieldV1,
    field_fact,
    semantic_field,
)

EPISTEMIC_TYPE_SCHEMA = "TEV_SCRIPT_MAX_V3_EPISTEMIC_TYPE_V1"
EPISTEMIC_REFINEMENT_SCHEMA = "TEV_SCRIPT_MAX_V3_EPISTEMIC_REFINEMENT_RECEIPT_V1"
EFFECT_ROW_SCHEMA = "TEV_SCRIPT_MAX_V3_EFFECT_ROW_V1"
EPISTEMIC_QUALIFIERS = frozenset(
    {"Observed", "Inferred", "Predicted", "Hypothesis", "Verified"}
)
_REFINEMENT_STATUSES = frozenset({"PASS", "PROOF_REQUIRED", "REJECT"})
_HEX = frozenset("0123456789abcdef")
_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:<>,]*$")
_EFFECT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_CAPABILITY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")


@dataclass(frozen=True, slots=True)
class EpistemicTypeV1:
    schema: str
    base_type: str
    qualifier: str
    type_hash: str


@dataclass(frozen=True, slots=True)
class EpistemicRefinementReceiptV1:
    schema: str
    source_type_hash: str
    target_type_hash: str
    transformation_hash: str
    observation_evidence_hash: str | None
    model_evidence_hash: str | None
    provenance_evidence_hash: str | None
    proof_witness_hashes: tuple[str, ...]
    status: str
    reason: str
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class EffectRowV1:
    schema: str
    effects: tuple[str, ...]
    capabilities: tuple[str, ...]
    grants_authority: bool
    row_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        _fail("TEVS_MAX_V3_TYPE_EFFECT_HASH", f"{name} must be lowercase 64-hex")
    return value


def _optional_sha(value: Any, name: str) -> str | None:
    return None if value is None else _sha(value, name)


def _closed_unique_ids(
    values: Sequence[str],
    *,
    name: str,
    pattern: re.Pattern[str],
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        _fail("TEVS_MAX_V3_TYPE_EFFECT_SEQUENCE", f"{name} must be a sequence")
    checked: list[str] = []
    for value in values:
        if not isinstance(value, str) or pattern.fullmatch(value) is None:
            _fail("TEVS_MAX_V3_TYPE_EFFECT_ID", f"invalid {name} id")
        checked.append(value)
    if len(set(checked)) != len(checked):
        _fail("TEVS_MAX_V3_TYPE_EFFECT_DUPLICATE", f"duplicate {name} id")
    return tuple(sorted(checked))


def epistemic_type(base_type: str, qualifier: str) -> EpistemicTypeV1:
    if not isinstance(base_type, str) or _TYPE.fullmatch(base_type) is None:
        _fail("TEVS_MAX_V3_EPISTEMIC_BASE_TYPE", "invalid epistemic base type")
    if qualifier not in EPISTEMIC_QUALIFIERS:
        _fail("TEVS_MAX_V3_EPISTEMIC_QUALIFIER", "unknown epistemic qualifier")
    body = {
        "schema": EPISTEMIC_TYPE_SCHEMA,
        "base_type": base_type,
        "qualifier": qualifier,
    }
    return EpistemicTypeV1(
        EPISTEMIC_TYPE_SCHEMA,
        base_type,
        qualifier,
        canonical_hash(body),
    )


def validate_epistemic_type(value: object) -> EpistemicTypeV1:
    if isinstance(value, EpistemicTypeV1):
        expected = epistemic_type(value.base_type, value.qualifier)
        if value != expected:
            _fail("TEVS_MAX_V3_EPISTEMIC_TYPE_HASH", "epistemic type identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_EPISTEMIC_TYPE", "epistemic type must be object")
    if set(value) != {"schema", "base_type", "qualifier", "type_hash"}:
        _fail("TEVS_MAX_V3_EPISTEMIC_TYPE_FIELDS", "epistemic type fields mismatch")
    if value.get("schema") != EPISTEMIC_TYPE_SCHEMA:
        _fail("TEVS_MAX_V3_EPISTEMIC_TYPE_SCHEMA", "epistemic type schema mismatch")
    expected = epistemic_type(value.get("base_type"), value.get("qualifier"))
    if _sha(value.get("type_hash"), "type_hash") != expected.type_hash:
        _fail("TEVS_MAX_V3_EPISTEMIC_TYPE_HASH", "epistemic type hash mismatch")
    return expected


def can_implicitly_assign_epistemic(
    source: EpistemicTypeV1,
    target: EpistemicTypeV1,
) -> bool:
    left = validate_epistemic_type(source)
    right = validate_epistemic_type(target)
    return left.base_type == right.base_type and left.qualifier == right.qualifier


def _proofs(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        _fail("TEVS_MAX_V3_EPISTEMIC_PROOFS", "proof witnesses must be a sequence")
    checked = tuple(_sha(value, "proof_witness_hash") for value in values)
    if len(set(checked)) != len(checked):
        _fail("TEVS_MAX_V3_EPISTEMIC_PROOF_DUPLICATE", "duplicate proof witness")
    return tuple(sorted(checked))


def _refinement_status(
    source: EpistemicTypeV1,
    target: EpistemicTypeV1,
    *,
    observation_evidence_hash: str | None,
    model_evidence_hash: str | None,
    provenance_evidence_hash: str | None,
    proof_witness_hashes: Sequence[str],
) -> tuple[str, str]:
    if source == target:
        return "PASS", "identity"
    if target.qualifier == "Observed" and observation_evidence_hash is None:
        return "REJECT", "observation_evidence_required"
    if target.qualifier == "Predicted" and model_evidence_hash is None:
        return "REJECT", "model_evidence_required"
    if target.qualifier == "Hypothesis" and provenance_evidence_hash is None:
        return "REJECT", "provenance_evidence_required"
    if target.qualifier == "Verified" and not proof_witness_hashes:
        return "PROOF_REQUIRED", "verification_proof_required"
    return "PASS", "explicit_refinement_admitted"


def _build_refinement(
    source: EpistemicTypeV1,
    target: EpistemicTypeV1,
    *,
    transformation_hash: str,
    observation_evidence_hash: str | None,
    model_evidence_hash: str | None,
    provenance_evidence_hash: str | None,
    proof_witness_hashes: Sequence[str],
) -> EpistemicRefinementReceiptV1:
    left = validate_epistemic_type(source)
    right = validate_epistemic_type(target)
    if left.base_type != right.base_type:
        _fail("TEVS_MAX_V3_EPISTEMIC_BASE_MISMATCH", "epistemic refinement cannot change base type")
    transformation = _sha(transformation_hash, "transformation_hash")
    observation = _optional_sha(observation_evidence_hash, "observation_evidence_hash")
    model = _optional_sha(model_evidence_hash, "model_evidence_hash")
    provenance = _optional_sha(provenance_evidence_hash, "provenance_evidence_hash")
    proofs = _proofs(proof_witness_hashes)
    status, reason = _refinement_status(
        left,
        right,
        observation_evidence_hash=observation,
        model_evidence_hash=model,
        provenance_evidence_hash=provenance,
        proof_witness_hashes=proofs,
    )
    body = {
        "schema": EPISTEMIC_REFINEMENT_SCHEMA,
        "source_type_hash": left.type_hash,
        "target_type_hash": right.type_hash,
        "transformation_hash": transformation,
        "observation_evidence_hash": observation,
        "model_evidence_hash": model,
        "provenance_evidence_hash": provenance,
        "proof_witness_hashes": list(proofs),
        "status": status,
        "reason": reason,
    }
    return EpistemicRefinementReceiptV1(
        EPISTEMIC_REFINEMENT_SCHEMA,
        left.type_hash,
        right.type_hash,
        transformation,
        observation,
        model,
        provenance,
        proofs,
        status,
        reason,
        canonical_hash(body),
    )


def refine_epistemic_type(
    source: EpistemicTypeV1,
    target: EpistemicTypeV1,
    *,
    transformation_hash: str,
    observation_evidence_hash: str | None = None,
    model_evidence_hash: str | None = None,
    provenance_evidence_hash: str | None = None,
    proof_witness_hashes: Sequence[str] = (),
) -> EpistemicRefinementReceiptV1:
    return _build_refinement(
        source,
        target,
        transformation_hash=transformation_hash,
        observation_evidence_hash=observation_evidence_hash,
        model_evidence_hash=model_evidence_hash,
        provenance_evidence_hash=provenance_evidence_hash,
        proof_witness_hashes=proof_witness_hashes,
    )


def validate_epistemic_refinement(value: object) -> EpistemicRefinementReceiptV1:
    if isinstance(value, EpistemicRefinementReceiptV1):
        body = {
            "schema": value.schema,
            "source_type_hash": _sha(value.source_type_hash, "source_type_hash"),
            "target_type_hash": _sha(value.target_type_hash, "target_type_hash"),
            "transformation_hash": _sha(value.transformation_hash, "transformation_hash"),
            "observation_evidence_hash": _optional_sha(value.observation_evidence_hash, "observation_evidence_hash"),
            "model_evidence_hash": _optional_sha(value.model_evidence_hash, "model_evidence_hash"),
            "provenance_evidence_hash": _optional_sha(value.provenance_evidence_hash, "provenance_evidence_hash"),
            "proof_witness_hashes": list(_proofs(value.proof_witness_hashes)),
            "status": value.status,
            "reason": value.reason,
        }
        if value.schema != EPISTEMIC_REFINEMENT_SCHEMA or value.status not in _REFINEMENT_STATUSES:
            _fail("TEVS_MAX_V3_EPISTEMIC_REFINEMENT", "invalid refinement receipt")
        if canonical_hash(body) != value.receipt_hash:
            _fail("TEVS_MAX_V3_EPISTEMIC_REFINEMENT_HASH", "refinement receipt hash mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_EPISTEMIC_REFINEMENT", "refinement receipt must be object")
    expected_fields = {
        "schema", "source_type_hash", "target_type_hash", "transformation_hash",
        "observation_evidence_hash", "model_evidence_hash", "provenance_evidence_hash",
        "proof_witness_hashes", "status", "reason", "receipt_hash",
    }
    if set(value) != expected_fields or value.get("schema") != EPISTEMIC_REFINEMENT_SCHEMA:
        _fail("TEVS_MAX_V3_EPISTEMIC_REFINEMENT_FIELDS", "refinement receipt fields mismatch")
    proofs_raw = value.get("proof_witness_hashes")
    if not isinstance(proofs_raw, list):
        _fail("TEVS_MAX_V3_EPISTEMIC_PROOFS", "proof witnesses must be an array")
    proofs = _proofs(proofs_raw)
    status = value.get("status")
    reason = value.get("reason")
    if status not in _REFINEMENT_STATUSES or not isinstance(reason, str) or not reason:
        _fail("TEVS_MAX_V3_EPISTEMIC_REFINEMENT_STATUS", "invalid refinement status/reason")
    body = {
        "schema": EPISTEMIC_REFINEMENT_SCHEMA,
        "source_type_hash": _sha(value.get("source_type_hash"), "source_type_hash"),
        "target_type_hash": _sha(value.get("target_type_hash"), "target_type_hash"),
        "transformation_hash": _sha(value.get("transformation_hash"), "transformation_hash"),
        "observation_evidence_hash": _optional_sha(value.get("observation_evidence_hash"), "observation_evidence_hash"),
        "model_evidence_hash": _optional_sha(value.get("model_evidence_hash"), "model_evidence_hash"),
        "provenance_evidence_hash": _optional_sha(value.get("provenance_evidence_hash"), "provenance_evidence_hash"),
        "proof_witness_hashes": list(proofs),
        "status": status,
        "reason": reason,
    }
    if tuple(proofs_raw) != proofs:
        _fail("TEVS_MAX_V3_EPISTEMIC_PROOF_ORDER", "proof witnesses must be canonical")
    if _sha(value.get("receipt_hash"), "receipt_hash") != canonical_hash(body):
        _fail("TEVS_MAX_V3_EPISTEMIC_REFINEMENT_HASH", "refinement receipt hash mismatch")
    return EpistemicRefinementReceiptV1(
        EPISTEMIC_REFINEMENT_SCHEMA,
        body["source_type_hash"],
        body["target_type_hash"],
        body["transformation_hash"],
        body["observation_evidence_hash"],
        body["model_evidence_hash"],
        body["provenance_evidence_hash"],
        proofs,
        status,
        reason,
        value["receipt_hash"],
    )


def effect_row(
    *,
    effects: Sequence[str] = (),
    capabilities: Sequence[str] = (),
) -> EffectRowV1:
    effect_ids = _closed_unique_ids(effects, name="effect", pattern=_EFFECT)
    capability_ids = _closed_unique_ids(capabilities, name="capability", pattern=_CAPABILITY)
    body = {
        "schema": EFFECT_ROW_SCHEMA,
        "effects": list(effect_ids),
        "capabilities": list(capability_ids),
        "grants_authority": False,
    }
    return EffectRowV1(
        EFFECT_ROW_SCHEMA,
        effect_ids,
        capability_ids,
        False,
        canonical_hash(body),
    )


def validate_effect_row(value: object) -> EffectRowV1:
    if isinstance(value, EffectRowV1):
        expected = effect_row(effects=value.effects, capabilities=value.capabilities)
        if value != expected:
            _fail("TEVS_MAX_V3_EFFECT_ROW_HASH", "effect row identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_EFFECT_ROW", "effect row must be object")
    if set(value) != {"schema", "effects", "capabilities", "grants_authority", "row_hash"}:
        _fail("TEVS_MAX_V3_EFFECT_ROW_FIELDS", "effect row fields mismatch")
    if value.get("schema") != EFFECT_ROW_SCHEMA or value.get("grants_authority") is not False:
        _fail("TEVS_MAX_V3_EFFECT_ROW_AUTHORITY", "effect row cannot grant authority")
    effects = value.get("effects")
    capabilities = value.get("capabilities")
    if not isinstance(effects, list) or not isinstance(capabilities, list):
        _fail("TEVS_MAX_V3_EFFECT_ROW_ARRAY", "effect row arrays malformed")
    expected = effect_row(effects=effects, capabilities=capabilities)
    if tuple(effects) != expected.effects or tuple(capabilities) != expected.capabilities:
        _fail("TEVS_MAX_V3_EFFECT_ROW_ORDER", "effect row must be canonical")
    if _sha(value.get("row_hash"), "row_hash") != expected.row_hash:
        _fail("TEVS_MAX_V3_EFFECT_ROW_HASH", "effect row hash mismatch")
    return expected


def effect_row_substitutable(actual: EffectRowV1, allowed: EffectRowV1) -> bool:
    actual_row = validate_effect_row(actual)
    allowed_row = validate_effect_row(allowed)
    return set(actual_row.effects).issubset(allowed_row.effects) and set(
        actual_row.capabilities
    ).issubset(allowed_row.capabilities)


def _lower_one(value: object) -> FieldFactV1:
    if isinstance(value, EpistemicTypeV1):
        item = validate_epistemic_type(value)
        return field_fact("tev.type.epistemic", (item.type_hash, item.base_type, item.qualifier))
    if isinstance(value, EffectRowV1):
        item = validate_effect_row(value)
        return field_fact(
            "tev.type.effect_row",
            (item.row_hash, list(item.effects), list(item.capabilities), item.grants_authority),
        )
    if isinstance(value, EpistemicRefinementReceiptV1):
        item = validate_epistemic_refinement(value)
        return field_fact(
            "tev.type.epistemic_refinement",
            (
                item.receipt_hash,
                item.source_type_hash,
                item.target_type_hash,
                item.transformation_hash,
                item.status,
            ),
        )
    _fail("TEVS_MAX_V3_TYPE_EFFECT_LOWER", "unsupported type/effect object")


def lower_type_effect_to_field(*values: object) -> SemanticFieldV1:
    if not values:
        _fail("TEVS_MAX_V3_TYPE_EFFECT_LOWER_EMPTY", "at least one type/effect object is required")
    return semantic_field(tuple(_lower_one(value) for value in values), profile="type_effect")


__all__ = [
    "EPISTEMIC_QUALIFIERS",
    "EffectRowV1",
    "EpistemicRefinementReceiptV1",
    "EpistemicTypeV1",
    "can_implicitly_assign_epistemic",
    "effect_row",
    "effect_row_substitutable",
    "epistemic_type",
    "lower_type_effect_to_field",
    "refine_epistemic_type",
    "validate_effect_row",
    "validate_epistemic_refinement",
    "validate_epistemic_type",
]
