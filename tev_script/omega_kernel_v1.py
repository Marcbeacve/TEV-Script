from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
import re
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash
from .diagnostics import TevScriptError


KERNEL_IDENTITY_SCHEMA = "TEV_SCRIPT_OMEGA_KERNEL_COMPUTATION_IDENTITY_V1"
PROOF_ENVELOPE_SCHEMA = "TEV_SCRIPT_OMEGA_PROOF_ENVELOPE_V1"
EFFECT_SET_SCHEMA = "TEV_SCRIPT_OMEGA_EFFECT_SET_V1"
AUTHORITY_GRANT_SCHEMA = "TEV_SCRIPT_OMEGA_AUTHORITY_GRANT_V1"
AUTHORITY_USE_SCHEMA = "TEV_SCRIPT_OMEGA_AUTHORITY_USE_V1"
OBSERVATION_EVIDENCE_SCHEMA = "TEV_SCRIPT_OMEGA_OBSERVATION_EVIDENCE_V1"
EPOCH_IDENTITY_SCHEMA = "TEV_SCRIPT_OMEGA_EPOCH_IDENTITY_V1"
CONTINUATION_RECEIPT_SCHEMA = "TEV_SCRIPT_OMEGA_CONTINUATION_RECEIPT_V1"

_RESOURCE_NAMES = (
    "cpu",
    "memory",
    "stack",
    "io",
    "network",
    "gpu",
    "tasks",
    "storage",
    "effects",
    "communication",
)
_RESOURCE_KINDS = frozenset({"exact", "upper", "provider", "unknown"})
_DUPLICATION_POLICIES = frozenset({"reusable", "affine", "linear"})
_EFFECT = re.compile(r"^(?:observe|command|state|compute):[A-Za-z_][A-Za-z0-9_.-]*$")
_CAPABILITY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_TEXT_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/@+-]*$")
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class KernelComputationIdentityV1:
    schema: str
    language_id: str
    language_version: str
    semantic_profile: str
    program_hash: str
    source_semantic_hash: str
    identity_hash: str


@dataclass(frozen=True, slots=True)
class ProofEnvelopeV1:
    schema: str
    claim_kind: str
    subject_hash: str
    proof_system: str
    proof_artifact_hash: str
    admission_authority: bool
    envelope_hash: str


@dataclass(frozen=True, slots=True)
class ResourceBoundV1:
    kind: str
    value: int | None
    authority_hash: str | None


@dataclass(frozen=True, slots=True)
class ResourceVectorV1:
    cpu: ResourceBoundV1
    memory: ResourceBoundV1
    stack: ResourceBoundV1
    io: ResourceBoundV1
    network: ResourceBoundV1
    gpu: ResourceBoundV1
    tasks: ResourceBoundV1
    storage: ResourceBoundV1
    effects: ResourceBoundV1
    communication: ResourceBoundV1
    vector_hash: str


@dataclass(frozen=True, slots=True)
class EffectSetV1:
    schema: str
    effects: tuple[str, ...]
    effect_set_hash: str


@dataclass(frozen=True, slots=True)
class AuthorityGrantV1:
    schema: str
    principal_hash: str
    capability_id: str
    scope_hash: str
    duplication_policy: str
    resources: ResourceVectorV1
    parent_grant_hash: str | None
    grant_hash: str


@dataclass(frozen=True, slots=True)
class AuthorityUseV1:
    schema: str
    grant_hash: str
    operation: str
    subject_hash: str
    resources: ResourceVectorV1
    consumes_grant: bool
    use_hash: str


@dataclass(frozen=True, slots=True)
class ObservationEvidenceV1:
    schema: str
    capability_id: str
    contract_hash: str
    request_hash: str
    result_hash: str
    transcript_hash: str
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class EpochIdentityV1:
    schema: str
    epoch_index: int
    computation_hash: str
    input_state_hash: str
    authority_hash: str
    previous_continuation_hash: str | None
    epoch_hash: str


@dataclass(frozen=True, slots=True)
class ContinuationReceiptV1:
    schema: str
    epoch_hash: str
    epoch_index: int
    previous_continuation_hash: str | None
    result_hash: str
    state_hash: str
    observations_hash: str
    effects_hash: str
    resources_hash: str
    continuation_hash: str


def omega_wire(value: Any) -> Any:
    """Convert an Ω contract value to its canonical JSON-compatible structure."""

    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: omega_wire(getattr(value, item.name))
            for item in fields(value)
        }
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                _fail("TEVS_OMEGA_CANONICAL_KEY", "Omega canonical object keys must be strings")
            result[key] = omega_wire(item)
        return result
    if isinstance(value, (tuple, list)):
        return [omega_wire(item) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    _fail(
        "TEVS_OMEGA_CANONICAL_VALUE",
        f"unsupported Omega canonical value {type(value).__name__}",
    )


def omega_hash(value: Any) -> str:
    """Hash an Ω canonical value using TEV Script's existing canonical authority."""

    return canonical_hash(omega_wire(value))


def kernel_computation_identity(
    *,
    language_id: str,
    language_version: str,
    semantic_profile: str,
    program_hash: str,
    source_semantic_hash: str,
) -> KernelComputationIdentityV1:
    language = _nonempty(language_id, "language_id")
    version = _nonempty(language_version, "language_version")
    profile = _nonempty(semantic_profile, "semantic_profile")
    program = _sha(program_hash, "program_hash")
    source = _sha(source_semantic_hash, "source_semantic_hash")
    payload = {
        "schema": KERNEL_IDENTITY_SCHEMA,
        "language_id": language,
        "language_version": version,
        "semantic_profile": profile,
        "program_hash": program,
        "source_semantic_hash": source,
    }
    return KernelComputationIdentityV1(
        KERNEL_IDENTITY_SCHEMA,
        language,
        version,
        profile,
        program,
        source,
        omega_hash(payload),
    )


def proof_envelope(
    *,
    claim_kind: str,
    subject_hash: str,
    proof_system: str,
    proof_artifact_hash: str,
) -> ProofEnvelopeV1:
    claim = _nonempty(claim_kind, "claim_kind")
    subject = _sha(subject_hash, "subject_hash")
    system = _nonempty(proof_system, "proof_system")
    artifact = _sha(proof_artifact_hash, "proof_artifact_hash")
    payload = {
        "schema": PROOF_ENVELOPE_SCHEMA,
        "claim_kind": claim,
        "subject_hash": subject,
        "proof_system": system,
        "proof_artifact_hash": artifact,
        "admission_authority": False,
    }
    return ProofEnvelopeV1(
        PROOF_ENVELOPE_SCHEMA,
        claim,
        subject,
        system,
        artifact,
        False,
        omega_hash(payload),
    )


def resource_exact(value: int) -> ResourceBoundV1:
    return _resource_bound("exact", value=value, authority_hash=None)


def resource_upper(value: int) -> ResourceBoundV1:
    return _resource_bound("upper", value=value, authority_hash=None)


def resource_provider(value: int, authority_hash: str) -> ResourceBoundV1:
    return _resource_bound("provider", value=value, authority_hash=authority_hash)


def resource_unknown() -> ResourceBoundV1:
    return _resource_bound("unknown", value=None, authority_hash=None)


def resource_vector(
    *,
    cpu: ResourceBoundV1 | None = None,
    memory: ResourceBoundV1 | None = None,
    stack: ResourceBoundV1 | None = None,
    io: ResourceBoundV1 | None = None,
    network: ResourceBoundV1 | None = None,
    gpu: ResourceBoundV1 | None = None,
    tasks: ResourceBoundV1 | None = None,
    storage: ResourceBoundV1 | None = None,
    effects: ResourceBoundV1 | None = None,
    communication: ResourceBoundV1 | None = None,
) -> ResourceVectorV1:
    values = {
        "cpu": cpu,
        "memory": memory,
        "stack": stack,
        "io": io,
        "network": network,
        "gpu": gpu,
        "tasks": tasks,
        "storage": storage,
        "effects": effects,
        "communication": communication,
    }
    normalized: dict[str, ResourceBoundV1] = {}
    for name in _RESOURCE_NAMES:
        raw = values[name]
        bound = resource_unknown() if raw is None else _validate_resource_bound(raw, name)
        normalized[name] = bound
    payload = {name: omega_wire(normalized[name]) for name in _RESOURCE_NAMES}
    return ResourceVectorV1(
        *(normalized[name] for name in _RESOURCE_NAMES),
        omega_hash(payload),
    )


def compose_resource_sequence(
    left: ResourceVectorV1,
    right: ResourceVectorV1,
) -> ResourceVectorV1:
    lvalue = _validate_resource_vector(left, "left")
    rvalue = _validate_resource_vector(right, "right")
    combined = {
        name: _compose_bound(getattr(lvalue, name), getattr(rvalue, name))
        for name in _RESOURCE_NAMES
    }
    return resource_vector(**combined)


def effect_set(effects: Sequence[str]) -> EffectSetV1:
    if isinstance(effects, (str, bytes)):
        _fail("TEVS_OMEGA_EFFECT_SET", "effects must be a sequence, not text")
    normalized: list[str] = []
    for raw in effects:
        if not isinstance(raw, str) or _EFFECT.fullmatch(raw) is None:
            _fail("TEVS_OMEGA_EFFECT", f"invalid effect identifier {raw!r}")
        normalized.append(raw)
    closed = tuple(sorted(set(normalized)))
    payload = {
        "schema": EFFECT_SET_SCHEMA,
        "effects": list(closed),
    }
    return EffectSetV1(EFFECT_SET_SCHEMA, closed, omega_hash(payload))


def authority_grant(
    *,
    principal_hash: str,
    capability_id: str,
    scope_hash: str,
    duplication_policy: str,
    resources: ResourceVectorV1,
    parent_grant_hash: str | None = None,
) -> AuthorityGrantV1:
    principal = _sha(principal_hash, "principal_hash")
    capability = _capability(capability_id, "capability_id")
    scope = _sha(scope_hash, "scope_hash")
    if duplication_policy not in _DUPLICATION_POLICIES:
        _fail(
            "TEVS_OMEGA_AUTHORITY_DUPLICATION",
            f"duplication_policy must be one of {sorted(_DUPLICATION_POLICIES)}",
        )
    vector = _validate_resource_vector(resources, "resources")
    parent = None if parent_grant_hash is None else _sha(parent_grant_hash, "parent_grant_hash")
    payload = {
        "schema": AUTHORITY_GRANT_SCHEMA,
        "principal_hash": principal,
        "capability_id": capability,
        "scope_hash": scope,
        "duplication_policy": duplication_policy,
        "resources": omega_wire(vector),
        "parent_grant_hash": parent,
    }
    return AuthorityGrantV1(
        AUTHORITY_GRANT_SCHEMA,
        principal,
        capability,
        scope,
        duplication_policy,
        vector,
        parent,
        omega_hash(payload),
    )


def authority_use(
    *,
    grant: AuthorityGrantV1,
    operation: str,
    subject_hash: str,
    resources: ResourceVectorV1,
    consume: bool,
) -> AuthorityUseV1:
    active = _validate_authority_grant(grant)
    action = _identifier(operation, "operation")
    subject = _sha(subject_hash, "subject_hash")
    vector = _validate_resource_vector(resources, "resources")
    if not isinstance(consume, bool):
        _fail("TEVS_OMEGA_AUTHORITY_CONSUME", "consume must be bool")
    if active.duplication_policy == "linear" and not consume:
        _fail(
            "TEVS_OMEGA_AUTHORITY_LINEAR",
            "linear authority use must consume its grant",
        )
    payload = {
        "schema": AUTHORITY_USE_SCHEMA,
        "grant_hash": active.grant_hash,
        "operation": action,
        "subject_hash": subject,
        "resources": omega_wire(vector),
        "consumes_grant": consume,
    }
    return AuthorityUseV1(
        AUTHORITY_USE_SCHEMA,
        active.grant_hash,
        action,
        subject,
        vector,
        consume,
        omega_hash(payload),
    )


def observation_evidence(
    *,
    capability_id: str,
    contract_hash: str,
    request_hash: str,
    result_hash: str,
    transcript_hash: str,
) -> ObservationEvidenceV1:
    capability = _capability(capability_id, "capability_id")
    contract = _sha(contract_hash, "contract_hash")
    request = _sha(request_hash, "request_hash")
    result = _sha(result_hash, "result_hash")
    transcript = _sha(transcript_hash, "transcript_hash")
    payload = {
        "schema": OBSERVATION_EVIDENCE_SCHEMA,
        "capability_id": capability,
        "contract_hash": contract,
        "request_hash": request,
        "result_hash": result,
        "transcript_hash": transcript,
    }
    return ObservationEvidenceV1(
        OBSERVATION_EVIDENCE_SCHEMA,
        capability,
        contract,
        request,
        result,
        transcript,
        omega_hash(payload),
    )


def epoch_identity(
    *,
    epoch_index: int,
    computation_hash: str,
    input_state_hash: str,
    authority_hash: str,
    previous_continuation_hash: str | None,
) -> EpochIdentityV1:
    index = _epoch_index(epoch_index)
    computation = _sha(computation_hash, "computation_hash")
    state = _sha(input_state_hash, "input_state_hash")
    authority = _sha(authority_hash, "authority_hash")
    previous = _previous_continuation(index, previous_continuation_hash)
    payload = {
        "schema": EPOCH_IDENTITY_SCHEMA,
        "epoch_index": index,
        "computation_hash": computation,
        "input_state_hash": state,
        "authority_hash": authority,
        "previous_continuation_hash": previous,
    }
    return EpochIdentityV1(
        EPOCH_IDENTITY_SCHEMA,
        index,
        computation,
        state,
        authority,
        previous,
        omega_hash(payload),
    )


def continuation_receipt(
    *,
    epoch: EpochIdentityV1,
    result_hash: str,
    state_hash: str,
    observations_hash: str,
    effects_hash: str,
    resources_hash: str,
) -> ContinuationReceiptV1:
    current = _validate_epoch_identity(epoch)
    result = _sha(result_hash, "result_hash")
    state = _sha(state_hash, "state_hash")
    observations = _sha(observations_hash, "observations_hash")
    effects = _sha(effects_hash, "effects_hash")
    resources = _sha(resources_hash, "resources_hash")
    payload = {
        "schema": CONTINUATION_RECEIPT_SCHEMA,
        "epoch_hash": current.epoch_hash,
        "epoch_index": current.epoch_index,
        "previous_continuation_hash": current.previous_continuation_hash,
        "result_hash": result,
        "state_hash": state,
        "observations_hash": observations,
        "effects_hash": effects,
        "resources_hash": resources,
    }
    return ContinuationReceiptV1(
        CONTINUATION_RECEIPT_SCHEMA,
        current.epoch_hash,
        current.epoch_index,
        current.previous_continuation_hash,
        result,
        state,
        observations,
        effects,
        resources,
        omega_hash(payload),
    )


def validate_continuation_receipt(
    value: ContinuationReceiptV1 | Mapping[str, Any],
) -> ContinuationReceiptV1:
    if isinstance(value, ContinuationReceiptV1):
        wire = omega_wire(value)
    elif isinstance(value, Mapping):
        wire = dict(value)
    else:
        _fail(
            "TEVS_OMEGA_CONTINUATION_SHAPE",
            "continuation receipt must be ContinuationReceiptV1 or mapping",
        )
    expected = {
        "schema",
        "epoch_hash",
        "epoch_index",
        "previous_continuation_hash",
        "result_hash",
        "state_hash",
        "observations_hash",
        "effects_hash",
        "resources_hash",
        "continuation_hash",
    }
    if set(wire) != expected:
        _fail(
            "TEVS_OMEGA_CONTINUATION_SHAPE",
            f"continuation field set mismatch: {sorted(set(wire) ^ expected)}",
        )
    if wire["schema"] != CONTINUATION_RECEIPT_SCHEMA:
        _fail("TEVS_OMEGA_CONTINUATION_SCHEMA", "unsupported continuation schema")
    index = _epoch_index(wire["epoch_index"])
    previous = _previous_continuation(index, wire["previous_continuation_hash"])
    epoch_hash_value = _sha(wire["epoch_hash"], "epoch_hash")
    result = _sha(wire["result_hash"], "result_hash")
    state = _sha(wire["state_hash"], "state_hash")
    observations = _sha(wire["observations_hash"], "observations_hash")
    effects = _sha(wire["effects_hash"], "effects_hash")
    resources = _sha(wire["resources_hash"], "resources_hash")
    declared = _sha(wire["continuation_hash"], "continuation_hash")
    payload = {
        "schema": CONTINUATION_RECEIPT_SCHEMA,
        "epoch_hash": epoch_hash_value,
        "epoch_index": index,
        "previous_continuation_hash": previous,
        "result_hash": result,
        "state_hash": state,
        "observations_hash": observations,
        "effects_hash": effects,
        "resources_hash": resources,
    }
    expected_hash = omega_hash(payload)
    if declared != expected_hash:
        _fail("TEVS_OMEGA_CONTINUATION_HASH", "continuation hash mismatch")
    return ContinuationReceiptV1(
        CONTINUATION_RECEIPT_SCHEMA,
        epoch_hash_value,
        index,
        previous,
        result,
        state,
        observations,
        effects,
        resources,
        declared,
    )


def verify_continuation_link(
    previous: ContinuationReceiptV1,
    current: ContinuationReceiptV1,
) -> bool:
    try:
        left = validate_continuation_receipt(previous)
        right = validate_continuation_receipt(current)
    except TevScriptError:
        return False
    return bool(
        right.epoch_index == left.epoch_index + 1
        and right.previous_continuation_hash == left.continuation_hash
    )


def _resource_bound(
    kind: str,
    *,
    value: int | None,
    authority_hash: str | None,
) -> ResourceBoundV1:
    if kind not in _RESOURCE_KINDS:
        _fail("TEVS_OMEGA_RESOURCE_KIND", f"unsupported resource bound kind {kind!r}")
    if kind == "unknown":
        if value is not None or authority_hash is not None:
            _fail("TEVS_OMEGA_RESOURCE_UNKNOWN", "unknown bound carries no value or authority")
        return ResourceBoundV1(kind, None, None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_OMEGA_RESOURCE_VALUE", "resource bound value must be integer >= 0")
    if kind == "provider":
        authority = _sha(authority_hash, "resource authority_hash")
        return ResourceBoundV1(kind, value, authority)
    if authority_hash is not None:
        _fail("TEVS_OMEGA_RESOURCE_AUTHORITY", f"{kind} resource bound cannot carry authority")
    return ResourceBoundV1(kind, value, None)


def _validate_resource_bound(value: ResourceBoundV1, path: str) -> ResourceBoundV1:
    if not isinstance(value, ResourceBoundV1):
        _fail("TEVS_OMEGA_RESOURCE_BOUND", f"{path} must be ResourceBoundV1")
    return _resource_bound(
        value.kind,
        value=value.value,
        authority_hash=value.authority_hash,
    )


def _validate_resource_vector(value: ResourceVectorV1, path: str) -> ResourceVectorV1:
    if not isinstance(value, ResourceVectorV1):
        _fail("TEVS_OMEGA_RESOURCE_VECTOR", f"{path} must be ResourceVectorV1")
    normalized = {
        name: _validate_resource_bound(getattr(value, name), f"{path}.{name}")
        for name in _RESOURCE_NAMES
    }
    payload = {name: omega_wire(normalized[name]) for name in _RESOURCE_NAMES}
    expected_hash = omega_hash(payload)
    if value.vector_hash != expected_hash:
        _fail("TEVS_OMEGA_RESOURCE_VECTOR_HASH", f"{path} vector hash mismatch")
    return value


def _compose_bound(left: ResourceBoundV1, right: ResourceBoundV1) -> ResourceBoundV1:
    if left.kind == "unknown" or right.kind == "unknown":
        return resource_unknown()
    assert left.value is not None and right.value is not None
    total = left.value + right.value
    if left.kind == right.kind == "exact":
        return resource_exact(total)
    return resource_upper(total)


def _validate_authority_grant(value: AuthorityGrantV1) -> AuthorityGrantV1:
    if not isinstance(value, AuthorityGrantV1):
        _fail("TEVS_OMEGA_AUTHORITY_GRANT", "grant must be AuthorityGrantV1")
    if value.schema != AUTHORITY_GRANT_SCHEMA:
        _fail("TEVS_OMEGA_AUTHORITY_SCHEMA", "unsupported authority grant schema")
    principal = _sha(value.principal_hash, "principal_hash")
    capability = _capability(value.capability_id, "capability_id")
    scope = _sha(value.scope_hash, "scope_hash")
    if value.duplication_policy not in _DUPLICATION_POLICIES:
        _fail("TEVS_OMEGA_AUTHORITY_DUPLICATION", "invalid duplication policy")
    vector = _validate_resource_vector(value.resources, "resources")
    parent = None if value.parent_grant_hash is None else _sha(value.parent_grant_hash, "parent_grant_hash")
    payload = {
        "schema": AUTHORITY_GRANT_SCHEMA,
        "principal_hash": principal,
        "capability_id": capability,
        "scope_hash": scope,
        "duplication_policy": value.duplication_policy,
        "resources": omega_wire(vector),
        "parent_grant_hash": parent,
    }
    if value.grant_hash != omega_hash(payload):
        _fail("TEVS_OMEGA_AUTHORITY_GRANT_HASH", "authority grant hash mismatch")
    return value


def _validate_epoch_identity(value: EpochIdentityV1) -> EpochIdentityV1:
    if not isinstance(value, EpochIdentityV1):
        _fail("TEVS_OMEGA_EPOCH", "epoch must be EpochIdentityV1")
    if value.schema != EPOCH_IDENTITY_SCHEMA:
        _fail("TEVS_OMEGA_EPOCH_SCHEMA", "unsupported epoch schema")
    index = _epoch_index(value.epoch_index)
    computation = _sha(value.computation_hash, "computation_hash")
    state = _sha(value.input_state_hash, "input_state_hash")
    authority = _sha(value.authority_hash, "authority_hash")
    previous = _previous_continuation(index, value.previous_continuation_hash)
    payload = {
        "schema": EPOCH_IDENTITY_SCHEMA,
        "epoch_index": index,
        "computation_hash": computation,
        "input_state_hash": state,
        "authority_hash": authority,
        "previous_continuation_hash": previous,
    }
    if value.epoch_hash != omega_hash(payload):
        _fail("TEVS_OMEGA_EPOCH_HASH", "epoch hash mismatch")
    return value


def _epoch_index(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("TEVS_OMEGA_EPOCH_INDEX", "epoch_index must be integer >= 0")
    return value


def _previous_continuation(index: int, value: Any) -> str | None:
    if index == 0:
        if value is not None:
            _fail("TEVS_OMEGA_EPOCH_PREVIOUS", "epoch 0 must not have previous continuation")
        return None
    return _sha(value, "previous_continuation_hash")


def _sha(value: Any, path: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in _HEX for char in value)
    ):
        _fail("TEVS_OMEGA_HASH_VALUE", f"{path} must be lowercase 64-hex sha256")
    return value


def _nonempty(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("TEVS_OMEGA_TEXT", f"{path} must be non-empty text")
    return value


def _identifier(value: Any, path: str) -> str:
    text = _nonempty(value, path)
    if _TEXT_ID.fullmatch(text) is None:
        _fail("TEVS_OMEGA_IDENTIFIER", f"{path} has invalid identifier {text!r}")
    return text


def _capability(value: Any, path: str) -> str:
    text = _nonempty(value, path)
    if _CAPABILITY.fullmatch(text) is None:
        _fail("TEVS_OMEGA_CAPABILITY", f"{path} has invalid capability id {text!r}")
    return text


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
