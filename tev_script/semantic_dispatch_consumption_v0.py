from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_dispatch_v0 import ExecutionDispatchReceiptV0
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DISPATCH_CONSUMPTION_STATE_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_STATE_V0"
DISPATCH_CONSUMPTION_ATTEMPT_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_ATTEMPT_V0"
DISPATCH_CONSUMPTION_TRANSITION_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_TRANSITION_V0"
DISPATCH_CONSUMPTION_COMMIT_RECORD_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_COMMIT_RECORD_V0"
DISPATCH_CONSUMPTION_COMMIT_POLICY_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_COMMIT_POLICY_V0"
DISPATCH_CONSUMPTION_COMMIT_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_COMMIT_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DispatchConsumptionError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DispatchConsumptionError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DispatchConsumptionError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class DispatchConsumptionStateV0:
    dispatch_domain_hash: str
    consumed_dispatch_request_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "dispatch_domain_hash", _hash64(self.dispatch_domain_hash, "dispatch_domain_hash"))
        object.__setattr__(self, "consumed_dispatch_request_hashes", _hashes(self.consumed_dispatch_request_hashes, "consumed dispatch request hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_CONSUMPTION_STATE_SCHEMA_V0,
            "dispatch_domain_hash": self.dispatch_domain_hash,
            "consumed_dispatch_request_hashes": list(self.consumed_dispatch_request_hashes),
        }

    @property
    def state_hash(self) -> str:
        return canonical_hash(self.to_object())

    def contains(self, dispatch_request_hash: str) -> bool:
        return _hash64(dispatch_request_hash, "dispatch_request_hash") in self.consumed_dispatch_request_hashes

    def after_consuming(self, dispatch_request_hash: str) -> "DispatchConsumptionStateV0":
        request = _hash64(dispatch_request_hash, "dispatch_request_hash")
        if request in self.consumed_dispatch_request_hashes:
            raise DispatchConsumptionError("dispatch request already consumed")
        return DispatchConsumptionStateV0(
            self.dispatch_domain_hash,
            (*self.consumed_dispatch_request_hashes, request),
        )

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.dispatch_consumption_state.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchConsumptionAttemptV0:
    dispatch_receipt_hash: str
    dispatch_request_hash: str
    dispatch_domain_hash: str
    before_state_hash: str

    def __post_init__(self) -> None:
        for name in (
            "dispatch_receipt_hash",
            "dispatch_request_hash",
            "dispatch_domain_hash",
            "before_state_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_CONSUMPTION_ATTEMPT_SCHEMA_V0,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_request_hash": self.dispatch_request_hash,
            "dispatch_domain_hash": self.dispatch_domain_hash,
            "before_state_hash": self.before_state_hash,
        }

    @property
    def attempt_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchConsumptionIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "dispatch consumption issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DispatchConsumptionError("dispatch consumption issue severity")
        subject = str(self.subject)
        if not subject:
            raise DispatchConsumptionError("dispatch consumption issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class DispatchConsumptionTransitionV0:
    attempt_hash: str
    dispatch_receipt_hash: str
    dispatch_request_hash: str
    dispatch_domain_hash: str
    before_state_hash: str
    after_state_hash: str
    issues: tuple[DispatchConsumptionIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "attempt_hash",
            "dispatch_receipt_hash",
            "dispatch_request_hash",
            "dispatch_domain_hash",
            "before_state_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.after_state_hash:
            object.__setattr__(self, "after_state_hash", _hash64(self.after_state_hash, "after_state_hash"))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))
        if self.status == "PASS" and not self.after_state_hash:
            raise DispatchConsumptionError("PASS transition requires after_state_hash")
        if self.status != "PASS" and self.after_state_hash:
            raise DispatchConsumptionError("non-PASS transition must not expose after_state_hash")

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_CONSUMPTION_TRANSITION_SCHEMA_V0,
            "status": self.status,
            "attempt_hash": self.attempt_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_request_hash": self.dispatch_request_hash,
            "dispatch_domain_hash": self.dispatch_domain_hash,
            "before_state_hash": self.before_state_hash,
            "after_state_hash": self.after_state_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def transition_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_dispatch_consumption_transition(
    attempt: DispatchConsumptionAttemptV0,
    *,
    before_state: DispatchConsumptionStateV0,
    dispatch_receipt: ExecutionDispatchReceiptV0,
) -> tuple[DispatchConsumptionTransitionV0, DispatchConsumptionStateV0 | None]:
    issues: list[DispatchConsumptionIssueV0] = []

    if attempt.dispatch_receipt_hash != dispatch_receipt.receipt_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.dispatch_receipt_mismatch", "REJECT", attempt.dispatch_receipt_hash, {"observed": dispatch_receipt.receipt_hash}))
    if attempt.dispatch_request_hash != dispatch_receipt.dispatch_request_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.dispatch_request_mismatch", "REJECT", attempt.dispatch_request_hash, {"observed": dispatch_receipt.dispatch_request_hash}))
    if attempt.dispatch_domain_hash != dispatch_receipt.dispatch_consumption_domain_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.request_domain_mismatch", "REJECT", attempt.dispatch_domain_hash, {"expected": dispatch_receipt.dispatch_consumption_domain_hash}))
    if before_state.dispatch_domain_hash != dispatch_receipt.dispatch_consumption_domain_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.ledger_domain_mismatch", "REJECT", before_state.dispatch_domain_hash, {"expected": dispatch_receipt.dispatch_consumption_domain_hash}))
    if attempt.dispatch_domain_hash != before_state.dispatch_domain_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.domain_mismatch", "REJECT", attempt.dispatch_domain_hash, {"observed": before_state.dispatch_domain_hash}))
    if attempt.before_state_hash != before_state.state_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.before_state_mismatch", "REJECT", attempt.before_state_hash, {"observed": before_state.state_hash}))
    if dispatch_receipt.status != "PASS":
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.dispatch_not_admitted", "REJECT" if dispatch_receipt.status == "REJECT" else "PROOF_REQUIRED", dispatch_receipt.receipt_hash, {"status": dispatch_receipt.status}))
    if before_state.contains(attempt.dispatch_request_hash):
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.replay", "REJECT", attempt.dispatch_request_hash, {}))

    if issues:
        transition = DispatchConsumptionTransitionV0(
            attempt.attempt_hash,
            dispatch_receipt.receipt_hash,
            dispatch_receipt.dispatch_request_hash,
            before_state.dispatch_domain_hash,
            before_state.state_hash,
            "",
            tuple(issues),
        )
        return transition, None

    after_state = before_state.after_consuming(attempt.dispatch_request_hash)
    transition = DispatchConsumptionTransitionV0(
        attempt.attempt_hash,
        dispatch_receipt.receipt_hash,
        dispatch_receipt.dispatch_request_hash,
        before_state.dispatch_domain_hash,
        before_state.state_hash,
        after_state.state_hash,
        (),
    )
    return transition, after_state


@dataclass(frozen=True, slots=True)
class DispatchConsumptionCommitRecordV0:
    transition_hash: str
    storage_authority_hash: str
    commit_epoch_hash: str
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("transition_hash", "storage_authority_hash", "commit_epoch_hash", "evidence_policy_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "dispatch consumption evidence hash"))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "dispatch consumption assumption hash"))

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_DISPATCH_CONSUMPTION_COMMIT_IDENTITY_V0",
            "transition_hash": self.transition_hash,
            "storage_authority_hash": self.storage_authority_hash,
            "commit_epoch_hash": self.commit_epoch_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def commit_claim_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_CONSUMPTION_COMMIT_RECORD_SCHEMA_V0,
            "commit_claim_hash": self.commit_claim_hash,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchConsumptionCommitPolicyV0:
    evidence_policy_hash: str
    trusted_storage_authority_hashes: tuple[str, ...]
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        trusted = _hashes(self.trusted_storage_authority_hashes, "trusted storage authority hash")
        if not trusted:
            raise DispatchConsumptionError("consumption commit requires trusted storage authority")
        object.__setattr__(self, "trusted_storage_authority_hashes", trusted)
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "accepted dispatch consumption assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_CONSUMPTION_COMMIT_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "trusted_storage_authority_hashes": list(self.trusted_storage_authority_hashes),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchConsumptionCommitReceiptV0:
    commit_claim_hash: str
    commit_record_hash: str
    transition_hash: str
    dispatch_receipt_hash: str
    dispatch_request_hash: str
    before_state_hash: str
    after_state_hash: str
    storage_authority_hash: str
    commit_epoch_hash: str
    evidence_evaluation_hash: str
    policy_hash: str
    issues: tuple[DispatchConsumptionIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "commit_claim_hash",
            "commit_record_hash",
            "transition_hash",
            "dispatch_receipt_hash",
            "dispatch_request_hash",
            "before_state_hash",
            "after_state_hash",
            "storage_authority_hash",
            "commit_epoch_hash",
            "evidence_evaluation_hash",
            "policy_hash",
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
            "schema": DISPATCH_CONSUMPTION_COMMIT_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "commit_claim_hash": self.commit_claim_hash,
            "commit_record_hash": self.commit_record_hash,
            "transition_hash": self.transition_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_request_hash": self.dispatch_request_hash,
            "before_state_hash": self.before_state_hash,
            "after_state_hash": self.after_state_hash,
            "storage_authority_hash": self.storage_authority_hash,
            "commit_epoch_hash": self.commit_epoch_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "policy_hash": self.policy_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.dispatch_consumption_commit_receipt.v0", self.to_object())


def evaluate_dispatch_consumption_commit(
    record: DispatchConsumptionCommitRecordV0,
    *,
    transition: DispatchConsumptionTransitionV0,
    policy: DispatchConsumptionCommitPolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> DispatchConsumptionCommitReceiptV0:
    issues: list[DispatchConsumptionIssueV0] = []

    if record.transition_hash != transition.transition_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.transition_mismatch", "REJECT", record.transition_hash, {"observed": transition.transition_hash}))
    if transition.status != "PASS":
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.transition_not_admitted", "REJECT" if transition.status == "REJECT" else "PROOF_REQUIRED", transition.transition_hash, {"status": transition.status}))
    if record.storage_authority_hash not in policy.trusted_storage_authority_hashes:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.storage_authority_untrusted", "REJECT", record.storage_authority_hash, {"trusted": list(policy.trusted_storage_authority_hashes)}))
    if record.evidence_policy_hash != evidence_policy.policy_hash or policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"record": record.evidence_policy_hash, "policy": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(record.assumption_hashes) - accepted_assumptions):
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(DispatchConsumptionIssueV0("dispatch_consumption.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evaluation = evaluate_evidence(record.commit_claim_hash, evidence_policy, evidence_items)
    for item in evaluation.issues:
        issues.append(DispatchConsumptionIssueV0("dispatch_consumption." + item.kind, "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED", item.requirement_id, {"evidence_hash": item.evidence_hash, **dict(item.detail)}))
    for accepted_hash in evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(DispatchConsumptionIssueV0("dispatch_consumption.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(DispatchConsumptionIssueV0("dispatch_consumption.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    after_state_hash = transition.after_state_hash if transition.after_state_hash else canonical_hash({"schema": "TEV_SCRIPT_NO_DISPATCH_CONSUMPTION_AFTER_STATE_V0", "transition_hash": transition.transition_hash})
    return DispatchConsumptionCommitReceiptV0(
        record.commit_claim_hash,
        record.record_hash,
        transition.transition_hash,
        transition.dispatch_receipt_hash,
        transition.dispatch_request_hash,
        transition.before_state_hash,
        after_state_hash,
        record.storage_authority_hash,
        record.commit_epoch_hash,
        evaluation.evaluation_hash,
        policy.policy_hash,
        tuple(issues),
    )


def residual_from_dispatch_consumption_transition(transition: DispatchConsumptionTransitionV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="dispatch_consumption_transition",
        judgment_id="dispatch_consumption_transition",
        judgment={"kind": "dispatch_request_not_previously_consumed", "dispatch_request_hash": transition.dispatch_request_hash, "status": transition.status},
        source={"kind": "dispatch_consumption_transition", "transition_hash": transition.transition_hash},
        obstructions=(
            ResidualObstructionV0(item.kind, item.subject, "resolved", item.severity, dict(item.detail), dependency_refs=(transition.attempt_hash, transition.dispatch_receipt_hash, transition.dispatch_domain_hash, transition.before_state_hash))
            for item in transition.issues
        ),
    )


def residual_from_dispatch_consumption_commit(receipt: DispatchConsumptionCommitReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="dispatch_consumption_commit",
        judgment_id="dispatch_consumption_commit",
        judgment={"kind": "dispatch_consumption_state_transition_committed", "dispatch_request_hash": receipt.dispatch_request_hash, "status": receipt.status},
        source={"kind": "dispatch_consumption_commit_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(item.kind, item.subject, "resolved", item.severity, dict(item.detail), dependency_refs=(receipt.transition_hash, receipt.before_state_hash, receipt.after_state_hash, receipt.storage_authority_hash))
            for item in receipt.issues
        ),
    )


__all__ = [
    "DISPATCH_CONSUMPTION_STATE_SCHEMA_V0",
    "DISPATCH_CONSUMPTION_ATTEMPT_SCHEMA_V0",
    "DISPATCH_CONSUMPTION_TRANSITION_SCHEMA_V0",
    "DISPATCH_CONSUMPTION_COMMIT_RECORD_SCHEMA_V0",
    "DISPATCH_CONSUMPTION_COMMIT_POLICY_SCHEMA_V0",
    "DISPATCH_CONSUMPTION_COMMIT_RECEIPT_SCHEMA_V0",
    "DispatchConsumptionError",
    "DispatchConsumptionStateV0",
    "DispatchConsumptionAttemptV0",
    "DispatchConsumptionIssueV0",
    "DispatchConsumptionTransitionV0",
    "DispatchConsumptionCommitRecordV0",
    "DispatchConsumptionCommitPolicyV0",
    "DispatchConsumptionCommitReceiptV0",
    "evaluate_dispatch_consumption_transition",
    "evaluate_dispatch_consumption_commit",
    "residual_from_dispatch_consumption_transition",
    "residual_from_dispatch_consumption_commit",
]
