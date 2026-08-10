from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

RECEIPT_VALIDITY_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_RECEIPT_VALIDITY_CLAIM_V0"
RECEIPT_VALIDITY_RECORD_SCHEMA_V0 = "TEV_SCRIPT_RECEIPT_VALIDITY_RECORD_V0"
RECEIPT_VALIDITY_POLICY_SCHEMA_V0 = "TEV_SCRIPT_RECEIPT_VALIDITY_POLICY_V0"
RECEIPT_VALIDITY_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_RECEIPT_VALIDITY_EVALUATION_V0"
_STATUSES = frozenset({"VALID", "REVOKED", "SUPERSEDED", "UNKNOWN"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ReceiptValidityError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ReceiptValidityError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ReceiptValidityError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class ReceiptValidityClaimV0:
    subject_receipt_hash: str
    subject_contract_hash: str
    validation_epoch_hash: str
    authority_state_hash: str
    validity_status: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "subject_receipt_hash",
            "subject_contract_hash",
            "validation_epoch_hash",
            "authority_state_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.validity_status not in _STATUSES:
            raise ReceiptValidityError("validity_status")
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "receipt validity assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RECEIPT_VALIDITY_CLAIM_SCHEMA_V0,
            "subject_receipt_hash": self.subject_receipt_hash,
            "subject_contract_hash": self.subject_contract_hash,
            "validation_epoch_hash": self.validation_epoch_hash,
            "authority_state_hash": self.authority_state_hash,
            "validity_status": self.validity_status,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def validity_claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ReceiptValidityRecordV0:
    claim: ReceiptValidityClaimV0
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "receipt validity evidence hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RECEIPT_VALIDITY_RECORD_SCHEMA_V0,
            "validity_claim_hash": self.claim.validity_claim_hash,
            "claim": self.claim.to_object(),
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.receipt_validity.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ReceiptValidityPolicyV0:
    evidence_policy_hash: str
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "validity accepted assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RECEIPT_VALIDITY_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ReceiptValidityIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "receipt validity issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ReceiptValidityError("receipt validity issue severity")
        subject = str(self.subject)
        if not subject:
            raise ReceiptValidityError("receipt validity issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ReceiptValidityEvaluationV0:
    validity_claim_hash: str
    validity_record_hash: str
    subject_receipt_hash: str
    subject_contract_hash: str
    validation_epoch_hash: str
    authority_state_hash: str
    evidence_evaluation_hash: str
    issues: tuple[ReceiptValidityIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "validity_claim_hash",
            "validity_record_hash",
            "subject_receipt_hash",
            "subject_contract_hash",
            "validation_epoch_hash",
            "authority_state_hash",
            "evidence_evaluation_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RECEIPT_VALIDITY_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "validity_claim_hash": self.validity_claim_hash,
            "validity_record_hash": self.validity_record_hash,
            "subject_receipt_hash": self.subject_receipt_hash,
            "subject_contract_hash": self.subject_contract_hash,
            "validation_epoch_hash": self.validation_epoch_hash,
            "authority_state_hash": self.authority_state_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_receipt_validity(
    record: ReceiptValidityRecordV0,
    *,
    expected_subject_receipt_hash: str,
    expected_subject_contract_hash: str,
    expected_validation_epoch_hash: str,
    policy: ReceiptValidityPolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> ReceiptValidityEvaluationV0:
    claim = record.claim
    issues: list[ReceiptValidityIssueV0] = []
    expected_subject_receipt_hash = _hash64(expected_subject_receipt_hash, "expected_subject_receipt_hash")
    expected_subject_contract_hash = _hash64(expected_subject_contract_hash, "expected_subject_contract_hash")
    expected_validation_epoch_hash = _hash64(expected_validation_epoch_hash, "expected_validation_epoch_hash")

    for kind, expected, observed in (
        ("validity.subject_receipt_mismatch", expected_subject_receipt_hash, claim.subject_receipt_hash),
        ("validity.subject_contract_mismatch", expected_subject_contract_hash, claim.subject_contract_hash),
        ("validity.validation_epoch_mismatch", expected_validation_epoch_hash, claim.validation_epoch_hash),
    ):
        if expected != observed:
            issues.append(ReceiptValidityIssueV0(kind, "REJECT", observed, {"expected": expected}))

    if claim.validity_status == "UNKNOWN":
        issues.append(ReceiptValidityIssueV0("validity.status_unknown", "PROOF_REQUIRED", claim.validity_claim_hash, {}))
    elif claim.validity_status in {"REVOKED", "SUPERSEDED"}:
        issues.append(ReceiptValidityIssueV0("validity.not_current", "REJECT", claim.validity_status, {}))

    if record.evidence_policy_hash != evidence_policy.policy_hash or policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(ReceiptValidityIssueV0("validity.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"record": record.evidence_policy_hash, "policy": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(ReceiptValidityIssueV0("validity.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
        issues.append(ReceiptValidityIssueV0("validity.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(ReceiptValidityIssueV0("validity.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evaluation = evaluate_evidence(claim.validity_claim_hash, evidence_policy, evidence_items)
    for item in evaluation.issues:
        issues.append(
            ReceiptValidityIssueV0(
                "validity." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(ReceiptValidityIssueV0("validity.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(ReceiptValidityIssueV0("validity.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return ReceiptValidityEvaluationV0(
        claim.validity_claim_hash,
        record.record_hash,
        claim.subject_receipt_hash,
        claim.subject_contract_hash,
        claim.validation_epoch_hash,
        claim.authority_state_hash,
        evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_receipt_validity(evaluation: ReceiptValidityEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="receipt_validity",
        judgment_id="receipt_current_validity",
        judgment={"kind": "historical_receipt_current_for_epoch", "status": evaluation.status},
        source={"kind": "receipt_validity_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(evaluation.validity_claim_hash, evaluation.subject_receipt_hash, evaluation.validation_epoch_hash, evaluation.authority_state_hash),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "RECEIPT_VALIDITY_CLAIM_SCHEMA_V0",
    "RECEIPT_VALIDITY_RECORD_SCHEMA_V0",
    "RECEIPT_VALIDITY_POLICY_SCHEMA_V0",
    "RECEIPT_VALIDITY_EVALUATION_SCHEMA_V0",
    "ReceiptValidityError",
    "ReceiptValidityClaimV0",
    "ReceiptValidityRecordV0",
    "ReceiptValidityPolicyV0",
    "ReceiptValidityIssueV0",
    "ReceiptValidityEvaluationV0",
    "evaluate_receipt_validity",
    "residual_from_receipt_validity",
]
