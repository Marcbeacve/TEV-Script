from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash, to_json_value
from .diagnostics import TevScriptError

FIELD_FACT_SCHEMA = "TEV_SCRIPT_MAX_V3_FIELD_FACT_V1"
SEMANTIC_FIELD_SCHEMA = "TEV_SCRIPT_MAX_V3_SEMANTIC_FIELD_V1"
_RELATION = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_PROFILE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class FieldFactV1:
    relation: str
    arguments: tuple[Any, ...]
    fact_hash: str


@dataclass(frozen=True, slots=True)
class SemanticFieldV1:
    schema: str
    profile: str
    facts: tuple[FieldFactV1, ...]
    field_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        _fail("TEVS_MAX_V3_HASH", f"{name} must be lowercase 64-hex")
    return value


def _stable(value: Any, name: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail("TEVS_MAX_V3_ID", f"{name} is not a stable id")
    return value


def _fact_body(relation: str, arguments: Sequence[Any]) -> dict[str, Any]:
    return {
        "relation": relation,
        "arguments": to_json_value(list(arguments)),
    }


def field_fact(relation: str, arguments: Sequence[Any]) -> FieldFactV1:
    if isinstance(arguments, (str, bytes)):
        _fail("TEVS_MAX_V3_FACT_ARGUMENTS", "fact arguments must be a sequence of canonical values")
    rel = _stable(relation, "relation", _RELATION)
    try:
        canonical_arguments = tuple(to_json_value(item) for item in arguments)
    except (TypeError, ValueError) as exc:
        _fail("TEVS_MAX_V3_FACT_ARGUMENT", str(exc))
    body = _fact_body(rel, canonical_arguments)
    return FieldFactV1(rel, canonical_arguments, canonical_hash(body))


def _field_body(profile: str, facts: Sequence[FieldFactV1]) -> dict[str, Any]:
    return {
        "schema": SEMANTIC_FIELD_SCHEMA,
        "profile": profile,
        "facts": [
            {
                "relation": item.relation,
                "arguments": list(item.arguments),
                "fact_hash": item.fact_hash,
            }
            for item in facts
        ],
    }


def semantic_field(
    facts: Sequence[FieldFactV1],
    *,
    profile: str = "actual",
) -> SemanticFieldV1:
    if isinstance(facts, (str, bytes)):
        _fail("TEVS_MAX_V3_FIELD_FACTS", "field facts must be a sequence")
    prof = _stable(profile, "profile", _PROFILE)
    validated: list[FieldFactV1] = []
    seen: set[str] = set()
    for item in facts:
        current = validate_field_fact(item)
        if current.fact_hash in seen:
            _fail("TEVS_MAX_V3_FIELD_DUPLICATE", "duplicate fact hash in Field")
        seen.add(current.fact_hash)
        validated.append(current)
    ordered = tuple(sorted(validated, key=lambda item: item.fact_hash))
    body = _field_body(prof, ordered)
    return SemanticFieldV1(SEMANTIC_FIELD_SCHEMA, prof, ordered, canonical_hash(body))


def validate_field_fact(value: object) -> FieldFactV1:
    if isinstance(value, FieldFactV1):
        expected = field_fact(value.relation, value.arguments)
        if value.fact_hash != expected.fact_hash:
            _fail("TEVS_MAX_V3_FACT_HASH", "fact hash mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_FACT", "fact must be FieldFactV1 or mapping")
    if set(value) != {"relation", "arguments", "fact_hash"}:
        _fail("TEVS_MAX_V3_FACT_FIELDS", "fact field set mismatch")
    arguments = value.get("arguments")
    if not isinstance(arguments, list):
        _fail("TEVS_MAX_V3_FACT_ARGUMENTS", "fact arguments must be an array")
    expected = field_fact(value.get("relation"), arguments)
    if _sha(value.get("fact_hash"), "fact_hash") != expected.fact_hash:
        _fail("TEVS_MAX_V3_FACT_HASH", "fact hash mismatch")
    return expected


def validate_semantic_field(value: object) -> SemanticFieldV1:
    if isinstance(value, SemanticFieldV1):
        expected = semantic_field(value.facts, profile=value.profile)
        if value.schema != SEMANTIC_FIELD_SCHEMA or value.field_hash != expected.field_hash or value.facts != expected.facts:
            _fail("TEVS_MAX_V3_FIELD_HASH", "semantic Field identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_FIELD", "semantic Field must be SemanticFieldV1 or mapping")
    if set(value) != {"schema", "profile", "facts", "field_hash"}:
        _fail("TEVS_MAX_V3_FIELD_FIELDS", "semantic Field field set mismatch")
    if value.get("schema") != SEMANTIC_FIELD_SCHEMA:
        _fail("TEVS_MAX_V3_FIELD_SCHEMA", "semantic Field schema mismatch")
    facts_raw = value.get("facts")
    if not isinstance(facts_raw, list):
        _fail("TEVS_MAX_V3_FIELD_FACTS", "semantic Field facts must be an array")
    facts = tuple(validate_field_fact(item) for item in facts_raw)
    expected = semantic_field(facts, profile=value.get("profile"))
    if _sha(value.get("field_hash"), "field_hash") != expected.field_hash:
        _fail("TEVS_MAX_V3_FIELD_HASH", "semantic Field hash mismatch")
    if tuple(fact.fact_hash for fact in facts) != tuple(fact.fact_hash for fact in expected.facts):
        _fail("TEVS_MAX_V3_FIELD_ORDER", "semantic Field facts must be canonical hash order")
    return expected

FIELD_TRANSFORMATION_SCHEMA = "TEV_SCRIPT_MAX_V3_FIELD_TRANSFORMATION_V1"


@dataclass(frozen=True, slots=True)
class FieldTransformationV1:
    schema: str
    transformation_id: str
    required_before_hash: str | None
    remove_fact_hashes: tuple[str, ...]
    add_facts: tuple[FieldFactV1, ...]
    effect_set_hash: str
    resource_vector_hash: str
    proof_requirement_hashes: tuple[str, ...]
    transformation_hash: str


def _ordered_unique_hashes(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        _fail("TEVS_MAX_V3_HASH_SEQUENCE", f"{name} must be a sequence")
    checked = tuple(_sha(value, name) for value in values)
    if len(set(checked)) != len(checked):
        _fail("TEVS_MAX_V3_HASH_DUPLICATE", f"{name} contains duplicates")
    return tuple(sorted(checked))


def _transformation_body(
    transformation_id: str,
    required_before_hash: str | None,
    remove_fact_hashes: Sequence[str],
    add_facts: Sequence[FieldFactV1],
    effect_set_hash: str,
    resource_vector_hash: str,
    proof_requirement_hashes: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema": FIELD_TRANSFORMATION_SCHEMA,
        "transformation_id": transformation_id,
        "required_before_hash": required_before_hash,
        "remove_fact_hashes": list(remove_fact_hashes),
        "add_facts": [
            {
                "relation": item.relation,
                "arguments": list(item.arguments),
                "fact_hash": item.fact_hash,
            }
            for item in add_facts
        ],
        "effect_set_hash": effect_set_hash,
        "resource_vector_hash": resource_vector_hash,
        "proof_requirement_hashes": list(proof_requirement_hashes),
    }


def field_transformation(
    *,
    transformation_id: str,
    remove_fact_hashes: Sequence[str] = (),
    add_facts: Sequence[FieldFactV1] = (),
    required_before_hash: str | None = None,
    effect_set_hash: str,
    resource_vector_hash: str,
    proof_requirement_hashes: Sequence[str] = (),
) -> FieldTransformationV1:
    tid = _stable(transformation_id, "transformation_id", _RELATION)
    before = None if required_before_hash is None else _sha(required_before_hash, "required_before_hash")
    removes = _ordered_unique_hashes(remove_fact_hashes, "remove_fact_hash")
    if isinstance(add_facts, (str, bytes)):
        _fail("TEVS_MAX_V3_TRANSFORM_ADDS", "add_facts must be a sequence")
    adds_checked = [validate_field_fact(item) for item in add_facts]
    add_hashes = [item.fact_hash for item in adds_checked]
    if len(set(add_hashes)) != len(add_hashes):
        _fail("TEVS_MAX_V3_TRANSFORM_ADD_DUPLICATE", "add_facts contains duplicates")
    collision = set(removes).intersection(add_hashes)
    if collision:
        _fail("TEVS_MAX_V3_TRANSFORM_COLLISION", "a transformation cannot remove and add the same fact")
    adds = tuple(sorted(adds_checked, key=lambda item: item.fact_hash))
    effects = _sha(effect_set_hash, "effect_set_hash")
    resources = _sha(resource_vector_hash, "resource_vector_hash")
    proofs = _ordered_unique_hashes(proof_requirement_hashes, "proof_requirement_hash")
    body = _transformation_body(tid, before, removes, adds, effects, resources, proofs)
    return FieldTransformationV1(
        FIELD_TRANSFORMATION_SCHEMA,
        tid,
        before,
        removes,
        adds,
        effects,
        resources,
        proofs,
        canonical_hash(body),
    )


def validate_field_transformation(value: object) -> FieldTransformationV1:
    if isinstance(value, FieldTransformationV1):
        expected = field_transformation(
            transformation_id=value.transformation_id,
            remove_fact_hashes=value.remove_fact_hashes,
            add_facts=value.add_facts,
            required_before_hash=value.required_before_hash,
            effect_set_hash=value.effect_set_hash,
            resource_vector_hash=value.resource_vector_hash,
            proof_requirement_hashes=value.proof_requirement_hashes,
        )
        if value.schema != FIELD_TRANSFORMATION_SCHEMA or value != expected:
            _fail("TEVS_MAX_V3_TRANSFORM_HASH", "transformation identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_TRANSFORM", "transformation must be FieldTransformationV1 or mapping")
    expected_fields = {
        "schema", "transformation_id", "required_before_hash", "remove_fact_hashes",
        "add_facts", "effect_set_hash", "resource_vector_hash",
        "proof_requirement_hashes", "transformation_hash",
    }
    if set(value) != expected_fields:
        _fail("TEVS_MAX_V3_TRANSFORM_FIELDS", "transformation field set mismatch")
    if value.get("schema") != FIELD_TRANSFORMATION_SCHEMA:
        _fail("TEVS_MAX_V3_TRANSFORM_SCHEMA", "transformation schema mismatch")
    removes = value.get("remove_fact_hashes")
    adds_raw = value.get("add_facts")
    proofs = value.get("proof_requirement_hashes")
    if not isinstance(removes, list) or not isinstance(adds_raw, list) or not isinstance(proofs, list):
        _fail("TEVS_MAX_V3_TRANSFORM_ARRAY", "transformation arrays malformed")
    adds = tuple(validate_field_fact(item) for item in adds_raw)
    expected = field_transformation(
        transformation_id=value.get("transformation_id"),
        remove_fact_hashes=removes,
        add_facts=adds,
        required_before_hash=value.get("required_before_hash"),
        effect_set_hash=value.get("effect_set_hash"),
        resource_vector_hash=value.get("resource_vector_hash"),
        proof_requirement_hashes=proofs,
    )
    if _sha(value.get("transformation_hash"), "transformation_hash") != expected.transformation_hash:
        _fail("TEVS_MAX_V3_TRANSFORM_HASH", "transformation hash mismatch")
    if tuple(removes) != expected.remove_fact_hashes:
        _fail("TEVS_MAX_V3_TRANSFORM_ORDER", "remove hashes must use canonical order")
    if tuple(item.fact_hash for item in adds) != tuple(item.fact_hash for item in expected.add_facts):
        _fail("TEVS_MAX_V3_TRANSFORM_ORDER", "add facts must use canonical order")
    if tuple(proofs) != expected.proof_requirement_hashes:
        _fail("TEVS_MAX_V3_TRANSFORM_ORDER", "proof requirement hashes must use canonical order")
    return expected

APPLY_RECEIPT_SCHEMA = "TEV_SCRIPT_MAX_V3_APPLY_RECEIPT_V1"
_APPLY_STATUSES = frozenset({"PASS", "PROOF_REQUIRED", "REJECT"})


@dataclass(frozen=True, slots=True)
class ApplyReceiptV1:
    schema: str
    before_field_hash: str
    transformation_hash: str
    after_field_hash: str
    effect_set_hash: str
    resource_vector_hash: str
    proof_requirement_hashes: tuple[str, ...]
    status: str
    receipt_hash: str


def _apply_receipt_body(
    *,
    before_field_hash: str,
    transformation_hash: str,
    after_field_hash: str,
    effect_set_hash: str,
    resource_vector_hash: str,
    proof_requirement_hashes: Sequence[str],
    status: str,
) -> dict[str, Any]:
    return {
        "schema": APPLY_RECEIPT_SCHEMA,
        "before_field_hash": before_field_hash,
        "transformation_hash": transformation_hash,
        "after_field_hash": after_field_hash,
        "effect_set_hash": effect_set_hash,
        "resource_vector_hash": resource_vector_hash,
        "proof_requirement_hashes": list(proof_requirement_hashes),
        "status": status,
    }


def _build_apply_receipt(
    *,
    before_field_hash: str,
    transformation_hash: str,
    after_field_hash: str,
    effect_set_hash: str,
    resource_vector_hash: str,
    proof_requirement_hashes: Sequence[str],
    status: str,
) -> ApplyReceiptV1:
    before = _sha(before_field_hash, "before_field_hash")
    transformation = _sha(transformation_hash, "transformation_hash")
    after = _sha(after_field_hash, "after_field_hash")
    effects = _sha(effect_set_hash, "effect_set_hash")
    resources = _sha(resource_vector_hash, "resource_vector_hash")
    proofs = _ordered_unique_hashes(proof_requirement_hashes, "proof_requirement_hash")
    if status not in _APPLY_STATUSES:
        _fail("TEVS_MAX_V3_APPLY_STATUS", "unknown Apply status")
    if status == "PASS" and proofs:
        _fail("TEVS_MAX_V3_APPLY_PROOF", "PASS cannot contain unresolved proof requirements")
    if status == "PROOF_REQUIRED" and not proofs:
        _fail("TEVS_MAX_V3_APPLY_PROOF", "PROOF_REQUIRED must bind unresolved proof requirements")
    body = _apply_receipt_body(
        before_field_hash=before,
        transformation_hash=transformation,
        after_field_hash=after,
        effect_set_hash=effects,
        resource_vector_hash=resources,
        proof_requirement_hashes=proofs,
        status=status,
    )
    return ApplyReceiptV1(
        APPLY_RECEIPT_SCHEMA,
        before,
        transformation,
        after,
        effects,
        resources,
        proofs,
        status,
        canonical_hash(body),
    )


def apply_field_transformation(
    before: SemanticFieldV1,
    transformation: FieldTransformationV1,
) -> tuple[SemanticFieldV1, ApplyReceiptV1]:
    current = validate_semantic_field(before)
    tx = validate_field_transformation(transformation)
    if tx.required_before_hash is not None and tx.required_before_hash != current.field_hash:
        _fail("TEVS_MAX_V3_APPLY_BEFORE", "transformation before-field pin mismatch")

    remaining = {item.fact_hash: item for item in current.facts}
    for fact_hash in tx.remove_fact_hashes:
        if fact_hash not in remaining:
            _fail("TEVS_MAX_V3_APPLY_REMOVE", "transformation removal target is absent")
        del remaining[fact_hash]

    for fact in tx.add_facts:
        if fact.fact_hash in remaining:
            _fail("TEVS_MAX_V3_APPLY_ADD", "transformation addition duplicates a remaining fact")
        remaining[fact.fact_hash] = fact

    after = semantic_field(tuple(remaining.values()), profile=current.profile)
    status = "PROOF_REQUIRED" if tx.proof_requirement_hashes else "PASS"
    receipt = _build_apply_receipt(
        before_field_hash=current.field_hash,
        transformation_hash=tx.transformation_hash,
        after_field_hash=after.field_hash,
        effect_set_hash=tx.effect_set_hash,
        resource_vector_hash=tx.resource_vector_hash,
        proof_requirement_hashes=tx.proof_requirement_hashes,
        status=status,
    )
    return after, receipt


def validate_apply_receipt(value: object) -> ApplyReceiptV1:
    if isinstance(value, ApplyReceiptV1):
        expected = _build_apply_receipt(
            before_field_hash=value.before_field_hash,
            transformation_hash=value.transformation_hash,
            after_field_hash=value.after_field_hash,
            effect_set_hash=value.effect_set_hash,
            resource_vector_hash=value.resource_vector_hash,
            proof_requirement_hashes=value.proof_requirement_hashes,
            status=value.status,
        )
        if value.schema != APPLY_RECEIPT_SCHEMA or value != expected:
            _fail("TEVS_MAX_V3_APPLY_RECEIPT_HASH", "Apply receipt identity mismatch")
        return value
    if not isinstance(value, Mapping):
        _fail("TEVS_MAX_V3_APPLY_RECEIPT", "Apply receipt must be ApplyReceiptV1 or mapping")
    expected_fields = {
        "schema", "before_field_hash", "transformation_hash", "after_field_hash",
        "effect_set_hash", "resource_vector_hash", "proof_requirement_hashes",
        "status", "receipt_hash",
    }
    if set(value) != expected_fields:
        _fail("TEVS_MAX_V3_APPLY_RECEIPT_FIELDS", "Apply receipt field set mismatch")
    if value.get("schema") != APPLY_RECEIPT_SCHEMA:
        _fail("TEVS_MAX_V3_APPLY_RECEIPT_SCHEMA", "Apply receipt schema mismatch")
    proofs = value.get("proof_requirement_hashes")
    if not isinstance(proofs, list):
        _fail("TEVS_MAX_V3_APPLY_RECEIPT_PROOFS", "Apply proof requirements must be an array")
    expected = _build_apply_receipt(
        before_field_hash=value.get("before_field_hash"),
        transformation_hash=value.get("transformation_hash"),
        after_field_hash=value.get("after_field_hash"),
        effect_set_hash=value.get("effect_set_hash"),
        resource_vector_hash=value.get("resource_vector_hash"),
        proof_requirement_hashes=proofs,
        status=value.get("status"),
    )
    if _sha(value.get("receipt_hash"), "receipt_hash") != expected.receipt_hash:
        _fail("TEVS_MAX_V3_APPLY_RECEIPT_HASH", "Apply receipt hash mismatch")
    if tuple(proofs) != expected.proof_requirement_hashes:
        _fail("TEVS_MAX_V3_APPLY_RECEIPT_ORDER", "Apply proof hashes must use canonical order")
    return expected


def apply_sequence(
    before: SemanticFieldV1,
    transformations: Sequence[FieldTransformationV1],
) -> tuple[SemanticFieldV1, tuple[ApplyReceiptV1, ...]]:
    if isinstance(transformations, (str, bytes)):
        _fail("TEVS_MAX_V3_SEQUENCE", "transformations must be a sequence")
    current = validate_semantic_field(before)
    receipts: list[ApplyReceiptV1] = []
    for transformation in transformations:
        current, receipt = apply_field_transformation(current, transformation)
        receipts.append(receipt)
    return current, tuple(receipts)
