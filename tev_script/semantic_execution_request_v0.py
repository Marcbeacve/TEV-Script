from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

EXECUTION_INTENT_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_INTENT_V0"
EXECUTION_REQUEST_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_REQUEST_V0"
EXECUTION_REQUEST_RECORD_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_REQUEST_RECORD_V0"
EXECUTION_REQUEST_POLICY_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_REQUEST_POLICY_V0"
EXECUTION_REQUEST_ADMISSION_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_REQUEST_ADMISSION_V0"

DELIVERY_GUARANTEES_V0 = frozenset(
    {
        "AT_MOST_ONCE_DISPATCH",
        "EXACTLY_ONCE_COMMIT",
        "DURABLE_EXACTLY_ONCE_COMMIT",
    }
)
IDEMPOTENCY_SCOPES_V0 = frozenset({"INTENT_SINGLETON", "OCCURRENCE_SCOPED"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ExecutionRequestError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ExecutionRequestError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ExecutionRequestError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class ExecutionIntentV0:
    invocation_workload_hash: str
    requester_principal_hash: str
    purpose_hash: str
    policy_context_hash: str
    requested_delivery_guarantee: str = "AT_MOST_ONCE_DISPATCH"
    idempotency_scope: str = "OCCURRENCE_SCOPED"
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "invocation_workload_hash",
            "requester_principal_hash",
            "purpose_hash",
            "policy_context_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.requested_delivery_guarantee not in DELIVERY_GUARANTEES_V0:
            raise ExecutionRequestError("requested_delivery_guarantee")
        if self.idempotency_scope not in IDEMPOTENCY_SCOPES_V0:
            raise ExecutionRequestError("idempotency_scope")
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "execution intent assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_INTENT_SCHEMA_V0,
            "invocation_workload_hash": self.invocation_workload_hash,
            "requester_principal_hash": self.requester_principal_hash,
            "purpose_hash": self.purpose_hash,
            "policy_context_hash": self.policy_context_hash,
            "requested_delivery_guarantee": self.requested_delivery_guarantee,
            "idempotency_scope": self.idempotency_scope,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def intent_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_intent.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionRequestV0:
    intent: ExecutionIntentV0
    occurrence_key_hash: str = ""

    def __post_init__(self) -> None:
        occurrence = _optional_hash(self.occurrence_key_hash, "occurrence_key_hash")
        if self.intent.idempotency_scope == "INTENT_SINGLETON":
            if occurrence:
                raise ExecutionRequestError("INTENT_SINGLETON request must not carry occurrence key")
        elif not occurrence:
            raise ExecutionRequestError("OCCURRENCE_SCOPED request requires occurrence key")
        object.__setattr__(self, "occurrence_key_hash", occurrence)

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_REQUEST_SCHEMA_V0,
            "intent_hash": self.intent.intent_hash,
            "occurrence_key_hash": self.occurrence_key_hash,
        }

    @property
    def request_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            **self.identity_object(),
            "request_hash": self.request_hash,
            "intent": self.intent.to_object(),
        }

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_request.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionRequestRecordV0:
    request: ExecutionRequestV0
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "execution request evidence hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_REQUEST_RECORD_SCHEMA_V0,
            "request_hash": self.request.request_hash,
            "request": self.request.to_object(),
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionRequestPolicyV0:
    evidence_policy_hash: str
    trusted_requester_principal_hashes: tuple[str, ...]
    allowed_delivery_guarantees: tuple[str, ...] = tuple(sorted(DELIVERY_GUARANTEES_V0))
    allowed_idempotency_scopes: tuple[str, ...] = tuple(sorted(IDEMPOTENCY_SCOPES_V0))
    allowed_purpose_hashes: tuple[str, ...] = ()
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        principals = _hashes(self.trusted_requester_principal_hashes, "trusted requester principal hash")
        if not principals:
            raise ExecutionRequestError("request policy requires trusted requester principal")
        object.__setattr__(self, "trusted_requester_principal_hashes", principals)
        delivery = tuple(sorted(set(str(item) for item in self.allowed_delivery_guarantees)))
        if not delivery or any(item not in DELIVERY_GUARANTEES_V0 for item in delivery):
            raise ExecutionRequestError("allowed_delivery_guarantees")
        object.__setattr__(self, "allowed_delivery_guarantees", delivery)
        idempotency = tuple(sorted(set(str(item) for item in self.allowed_idempotency_scopes)))
        if not idempotency or any(item not in IDEMPOTENCY_SCOPES_V0 for item in idempotency):
            raise ExecutionRequestError("allowed_idempotency_scopes")
        object.__setattr__(self, "allowed_idempotency_scopes", idempotency)
        object.__setattr__(self, "allowed_purpose_hashes", _hashes(self.allowed_purpose_hashes, "allowed purpose hash"))
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "accepted execution request assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_REQUEST_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "trusted_requester_principal_hashes": list(self.trusted_requester_principal_hashes),
            "allowed_delivery_guarantees": list(self.allowed_delivery_guarantees),
            "allowed_idempotency_scopes": list(self.allowed_idempotency_scopes),
            "allowed_purpose_hashes": list(self.allowed_purpose_hashes),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionRequestIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "execution request issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ExecutionRequestError("execution request issue severity")
        subject = str(self.subject)
        if not subject:
            raise ExecutionRequestError("execution request issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExecutionRequestAdmissionReceiptV0:
    request_hash: str
    request_record_hash: str
    intent_hash: str
    invocation_workload_hash: str
    requester_principal_hash: str
    purpose_hash: str
    policy_context_hash: str
    requested_delivery_guarantee: str
    idempotency_scope: str
    evidence_evaluation_hash: str
    policy_hash: str
    issues: tuple[ExecutionRequestIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "request_hash",
            "request_record_hash",
            "intent_hash",
            "invocation_workload_hash",
            "requester_principal_hash",
            "purpose_hash",
            "policy_context_hash",
            "evidence_evaluation_hash",
            "policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.requested_delivery_guarantee not in DELIVERY_GUARANTEES_V0:
            raise ExecutionRequestError("requested_delivery_guarantee")
        if self.idempotency_scope not in IDEMPOTENCY_SCOPES_V0:
            raise ExecutionRequestError("idempotency_scope")
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_REQUEST_ADMISSION_SCHEMA_V0,
            "status": self.status,
            "request_hash": self.request_hash,
            "request_record_hash": self.request_record_hash,
            "intent_hash": self.intent_hash,
            "invocation_workload_hash": self.invocation_workload_hash,
            "requester_principal_hash": self.requester_principal_hash,
            "purpose_hash": self.purpose_hash,
            "policy_context_hash": self.policy_context_hash,
            "requested_delivery_guarantee": self.requested_delivery_guarantee,
            "idempotency_scope": self.idempotency_scope,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "policy_hash": self.policy_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_request_admission.v0", self.to_object())


def evaluate_execution_request(
    record: ExecutionRequestRecordV0,
    *,
    policy: ExecutionRequestPolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> ExecutionRequestAdmissionReceiptV0:
    request = record.request
    intent = request.intent
    issues: list[ExecutionRequestIssueV0] = []

    if record.evidence_policy_hash != evidence_policy.policy_hash or policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(ExecutionRequestIssueV0("request.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"record": record.evidence_policy_hash, "policy": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(ExecutionRequestIssueV0("request.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))
    if intent.requester_principal_hash not in policy.trusted_requester_principal_hashes:
        issues.append(ExecutionRequestIssueV0("request.requester_untrusted", "REJECT", intent.requester_principal_hash, {"trusted": list(policy.trusted_requester_principal_hashes)}))
    if intent.requested_delivery_guarantee not in policy.allowed_delivery_guarantees:
        issues.append(ExecutionRequestIssueV0("request.delivery_guarantee_not_allowed", "REJECT", intent.requested_delivery_guarantee, {"allowed": list(policy.allowed_delivery_guarantees)}))
    if intent.idempotency_scope not in policy.allowed_idempotency_scopes:
        issues.append(ExecutionRequestIssueV0("request.idempotency_scope_not_allowed", "REJECT", intent.idempotency_scope, {"allowed": list(policy.allowed_idempotency_scopes)}))
    if policy.allowed_purpose_hashes and intent.purpose_hash not in policy.allowed_purpose_hashes:
        issues.append(ExecutionRequestIssueV0("request.purpose_not_allowed", "REJECT", intent.purpose_hash, {"allowed": list(policy.allowed_purpose_hashes)}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(intent.assumption_hashes) - accepted_assumptions):
        issues.append(ExecutionRequestIssueV0("request.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(ExecutionRequestIssueV0("request.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evaluation = evaluate_evidence(request.request_hash, evidence_policy, evidence_items)
    for item in evaluation.issues:
        issues.append(
            ExecutionRequestIssueV0(
                "request." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(ExecutionRequestIssueV0("request.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(ExecutionRequestIssueV0("request.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return ExecutionRequestAdmissionReceiptV0(
        request.request_hash,
        record.record_hash,
        intent.intent_hash,
        intent.invocation_workload_hash,
        intent.requester_principal_hash,
        intent.purpose_hash,
        intent.policy_context_hash,
        intent.requested_delivery_guarantee,
        intent.idempotency_scope,
        evaluation.evaluation_hash,
        policy.policy_hash,
        tuple(issues),
    )


def residual_from_execution_request(receipt: ExecutionRequestAdmissionReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="execution_request",
        judgment_id="execution_request_admission",
        judgment={
            "kind": "execution_request_is_authorized_and_well_formed",
            "request_hash": receipt.request_hash,
            "status": receipt.status,
        },
        source={"kind": "execution_request_admission_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.request_hash, receipt.intent_hash, receipt.policy_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "EXECUTION_INTENT_SCHEMA_V0",
    "EXECUTION_REQUEST_SCHEMA_V0",
    "EXECUTION_REQUEST_RECORD_SCHEMA_V0",
    "EXECUTION_REQUEST_POLICY_SCHEMA_V0",
    "EXECUTION_REQUEST_ADMISSION_SCHEMA_V0",
    "DELIVERY_GUARANTEES_V0",
    "IDEMPOTENCY_SCOPES_V0",
    "ExecutionRequestError",
    "ExecutionIntentV0",
    "ExecutionRequestV0",
    "ExecutionRequestRecordV0",
    "ExecutionRequestPolicyV0",
    "ExecutionRequestIssueV0",
    "ExecutionRequestAdmissionReceiptV0",
    "evaluate_execution_request",
    "residual_from_execution_request",
]
