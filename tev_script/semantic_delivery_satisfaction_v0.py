from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_commit_outcome_v0 import CausalCommitOutcomeReceiptV0
from .semantic_delivery_guarantee_v0 import DeliveryGuaranteeReceiptV0
from .semantic_dispatch_v0 import ExecutionDispatchReceiptV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DELIVERY_SATISFACTION_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_SATISFACTION_CLAIM_V0"
DELIVERY_SATISFACTION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_SATISFACTION_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DeliverySatisfactionError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DeliverySatisfactionError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DeliverySatisfactionError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


@dataclass(frozen=True, slots=True)
class DeliverySatisfactionClaimV0:
    delivery_guarantee_receipt_hash: str
    dispatch_receipt_hash: str
    requested_guarantee: str
    causal_commit_outcome_receipt_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "delivery_guarantee_receipt_hash", _hash64(self.delivery_guarantee_receipt_hash, "delivery_guarantee_receipt_hash"))
        object.__setattr__(self, "dispatch_receipt_hash", _hash64(self.dispatch_receipt_hash, "dispatch_receipt_hash"))
        if self.requested_guarantee not in {
            "AT_MOST_ONCE_DISPATCH",
            "EXACTLY_ONCE_COMMIT",
            "DURABLE_EXACTLY_ONCE_COMMIT",
        }:
            raise DeliverySatisfactionError("requested_guarantee")
        object.__setattr__(
            self,
            "causal_commit_outcome_receipt_hash",
            _optional_hash(self.causal_commit_outcome_receipt_hash, "causal_commit_outcome_receipt_hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_SATISFACTION_CLAIM_SCHEMA_V0,
            "delivery_guarantee_receipt_hash": self.delivery_guarantee_receipt_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "requested_guarantee": self.requested_guarantee,
            "causal_commit_outcome_receipt_hash": self.causal_commit_outcome_receipt_hash,
        }

    @property
    def claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DeliverySatisfactionIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "delivery satisfaction issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DeliverySatisfactionError("delivery satisfaction issue severity")
        subject = str(self.subject)
        if not subject:
            raise DeliverySatisfactionError("delivery satisfaction issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "subject": self.subject,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class DeliverySatisfactionReceiptV0:
    satisfaction_claim_hash: str
    delivery_guarantee_receipt_hash: str
    dispatch_receipt_hash: str
    requested_guarantee: str
    causal_commit_outcome_receipt_hash: str
    commit_status: str
    issues: tuple[DeliverySatisfactionIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "satisfaction_claim_hash",
            "delivery_guarantee_receipt_hash",
            "dispatch_receipt_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(
            self,
            "causal_commit_outcome_receipt_hash",
            _optional_hash(self.causal_commit_outcome_receipt_hash, "causal_commit_outcome_receipt_hash"),
        )
        if self.requested_guarantee not in {
            "AT_MOST_ONCE_DISPATCH",
            "EXACTLY_ONCE_COMMIT",
            "DURABLE_EXACTLY_ONCE_COMMIT",
        }:
            raise DeliverySatisfactionError("requested_guarantee")
        if self.commit_status and self.commit_status not in {"COMMITTED", "ABORTED", "EXTERNAL_PARTIAL", "LAW_VIOLATION"}:
            raise DeliverySatisfactionError("commit_status")
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_SATISFACTION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "satisfaction_claim_hash": self.satisfaction_claim_hash,
            "delivery_guarantee_receipt_hash": self.delivery_guarantee_receipt_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "requested_guarantee": self.requested_guarantee,
            "causal_commit_outcome_receipt_hash": self.causal_commit_outcome_receipt_hash,
            "commit_status": self.commit_status,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.delivery_satisfaction_receipt.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> DeliverySatisfactionIssueV0 | None:
    if status == "PASS":
        return None
    return DeliverySatisfactionIssueV0(
        kind,
        "REJECT" if status == "REJECT" else "PROOF_REQUIRED",
        subject,
        {"status": status},
    )


def evaluate_delivery_satisfaction(
    claim: DeliverySatisfactionClaimV0,
    *,
    delivery_guarantee_receipt: DeliveryGuaranteeReceiptV0,
    dispatch_receipt: ExecutionDispatchReceiptV0,
    causal_commit_outcome_receipt: CausalCommitOutcomeReceiptV0 | None = None,
) -> DeliverySatisfactionReceiptV0:
    issues: list[DeliverySatisfactionIssueV0] = []

    if claim.delivery_guarantee_receipt_hash != delivery_guarantee_receipt.receipt_hash:
        issues.append(DeliverySatisfactionIssueV0(
            "delivery_satisfaction.guarantee_receipt_mismatch",
            "REJECT",
            claim.delivery_guarantee_receipt_hash,
            {"observed": delivery_guarantee_receipt.receipt_hash},
        ))
    if claim.dispatch_receipt_hash != dispatch_receipt.receipt_hash:
        issues.append(DeliverySatisfactionIssueV0(
            "delivery_satisfaction.dispatch_receipt_mismatch",
            "REJECT",
            claim.dispatch_receipt_hash,
            {"observed": dispatch_receipt.receipt_hash},
        ))
    if claim.requested_guarantee != delivery_guarantee_receipt.requested_guarantee:
        issues.append(DeliverySatisfactionIssueV0(
            "delivery_satisfaction.claim_guarantee_mismatch",
            "REJECT",
            claim.requested_guarantee,
            {"guarantee_receipt": delivery_guarantee_receipt.requested_guarantee},
        ))
    if claim.requested_guarantee != dispatch_receipt.requested_delivery_guarantee:
        issues.append(DeliverySatisfactionIssueV0(
            "delivery_satisfaction.dispatch_guarantee_mismatch",
            "REJECT",
            claim.requested_guarantee,
            {"dispatch": dispatch_receipt.requested_delivery_guarantee},
        ))
    if delivery_guarantee_receipt.dispatch_receipt_hash != dispatch_receipt.receipt_hash:
        issues.append(DeliverySatisfactionIssueV0(
            "delivery_satisfaction.guarantee_dispatch_mismatch",
            "REJECT",
            delivery_guarantee_receipt.dispatch_receipt_hash,
            {"dispatch": dispatch_receipt.receipt_hash},
        ))

    for kind, subject, status in (
        ("delivery_satisfaction.guarantee_not_admitted", delivery_guarantee_receipt.receipt_hash, delivery_guarantee_receipt.status),
        ("delivery_satisfaction.dispatch_not_admitted", dispatch_receipt.receipt_hash, dispatch_receipt.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    outcome_hash = ""
    commit_status = ""
    if claim.requested_guarantee == "AT_MOST_ONCE_DISPATCH":
        if claim.causal_commit_outcome_receipt_hash:
            if causal_commit_outcome_receipt is None:
                issues.append(DeliverySatisfactionIssueV0(
                    "delivery_satisfaction.outcome_reference_missing",
                    "PROOF_REQUIRED",
                    claim.causal_commit_outcome_receipt_hash,
                    {},
                ))
            elif claim.causal_commit_outcome_receipt_hash != causal_commit_outcome_receipt.receipt_hash:
                issues.append(DeliverySatisfactionIssueV0(
                    "delivery_satisfaction.outcome_receipt_mismatch",
                    "REJECT",
                    claim.causal_commit_outcome_receipt_hash,
                    {"observed": causal_commit_outcome_receipt.receipt_hash},
                ))
            else:
                outcome_hash = causal_commit_outcome_receipt.receipt_hash
                commit_status = causal_commit_outcome_receipt.commit_status
    else:
        if causal_commit_outcome_receipt is None:
            issues.append(DeliverySatisfactionIssueV0(
                "delivery_satisfaction.commit_outcome_required",
                "PROOF_REQUIRED",
                delivery_guarantee_receipt.receipt_hash,
                {},
            ))
        else:
            outcome_hash = causal_commit_outcome_receipt.receipt_hash
            commit_status = causal_commit_outcome_receipt.commit_status
            if not claim.causal_commit_outcome_receipt_hash:
                issues.append(DeliverySatisfactionIssueV0(
                    "delivery_satisfaction.outcome_claim_missing",
                    "PROOF_REQUIRED",
                    outcome_hash,
                    {},
                ))
            elif claim.causal_commit_outcome_receipt_hash != outcome_hash:
                issues.append(DeliverySatisfactionIssueV0(
                    "delivery_satisfaction.outcome_receipt_mismatch",
                    "REJECT",
                    claim.causal_commit_outcome_receipt_hash,
                    {"observed": outcome_hash},
                ))

            issue = _upstream(
                "delivery_satisfaction.commit_outcome_not_admitted",
                outcome_hash,
                causal_commit_outcome_receipt.status,
            )
            if issue is not None:
                issues.append(issue)

            continuity = (
                ("delivery_satisfaction.outcome_dispatch_mismatch", causal_commit_outcome_receipt.dispatch_receipt_hash, dispatch_receipt.receipt_hash),
                ("delivery_satisfaction.outcome_consumption_mismatch", causal_commit_outcome_receipt.dispatch_consumption_commit_receipt_hash, delivery_guarantee_receipt.dispatch_consumption_commit_receipt_hash),
                ("delivery_satisfaction.outcome_plan_mismatch", causal_commit_outcome_receipt.delivery_plan_receipt_hash, delivery_guarantee_receipt.delivery_plan_receipt_hash),
                ("delivery_satisfaction.outcome_prepared_mismatch", causal_commit_outcome_receipt.prepared_execution_receipt_hash, delivery_guarantee_receipt.prepared_execution_receipt_hash),
            )
            for kind, observed, expected in continuity:
                if observed != expected:
                    issues.append(DeliverySatisfactionIssueV0(kind, "REJECT", observed, {"expected": expected}))

            if causal_commit_outcome_receipt.commit_status != "COMMITTED":
                issues.append(DeliverySatisfactionIssueV0(
                    "delivery_satisfaction.commit_not_committed",
                    "REJECT",
                    causal_commit_outcome_receipt.commit_status,
                    {"required": "COMMITTED"},
                ))
            elif not causal_commit_outcome_receipt.committed:
                issues.append(DeliverySatisfactionIssueV0(
                    "delivery_satisfaction.commit_not_authentic_success",
                    "REJECT",
                    outcome_hash,
                    {},
                ))

    return DeliverySatisfactionReceiptV0(
        claim.claim_hash,
        delivery_guarantee_receipt.receipt_hash,
        dispatch_receipt.receipt_hash,
        claim.requested_guarantee,
        outcome_hash,
        commit_status,
        tuple(issues),
    )


def residual_from_delivery_satisfaction(receipt: DeliverySatisfactionReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="delivery_satisfaction",
        judgment_id="delivery_satisfaction",
        judgment={
            "kind": "execution_satisfied_requested_delivery_guarantee",
            "requested_guarantee": receipt.requested_guarantee,
            "commit_status": receipt.commit_status,
            "status": receipt.status,
        },
        source={"kind": "delivery_satisfaction_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    receipt.satisfaction_claim_hash,
                    receipt.delivery_guarantee_receipt_hash,
                    receipt.dispatch_receipt_hash,
                    *(tuple([receipt.causal_commit_outcome_receipt_hash]) if receipt.causal_commit_outcome_receipt_hash else ()),
                ),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "DELIVERY_SATISFACTION_CLAIM_SCHEMA_V0",
    "DELIVERY_SATISFACTION_RECEIPT_SCHEMA_V0",
    "DeliverySatisfactionError",
    "DeliverySatisfactionClaimV0",
    "DeliverySatisfactionIssueV0",
    "DeliverySatisfactionReceiptV0",
    "evaluate_delivery_satisfaction",
    "residual_from_delivery_satisfaction",
]
