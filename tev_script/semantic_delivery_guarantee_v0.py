from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .causal_model_v1 import CapabilityLawCatalogV1, PreparedReactionV1
from .semantic_dispatch_consumption_v0 import DispatchConsumptionCommitReceiptV0
from .semantic_dispatch_v0 import ExecutionDispatchReceiptV0
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_execution_request_v0 import DELIVERY_GUARANTEES_V0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_prepared_execution_v0 import PreparedExecutionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DELIVERY_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_GUARANTEE_CLAIM_V0"
ATOMIC_DELIVERY_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_ATOMIC_DELIVERY_COMMIT_CLAIM_V0"
DELIVERY_POLICY_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_GUARANTEE_POLICY_V0"
DELIVERY_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_GUARANTEE_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DeliveryGuaranteeError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DeliveryGuaranteeError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DeliveryGuaranteeError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class AtomicDeliveryCommitClaimV0:
    dispatch_consumption_commit_receipt_hash: str
    prepared_execution_receipt_hash: str
    atomic_commit_domain_hash: str
    participant_manifest_hash: str
    coordinator_hash: str
    durable: bool
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "dispatch_consumption_commit_receipt_hash",
            "prepared_execution_receipt_hash",
            "atomic_commit_domain_hash",
            "participant_manifest_hash",
            "coordinator_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if not isinstance(self.durable, bool):
            raise DeliveryGuaranteeError("durable must be bool")
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "atomic delivery assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": ATOMIC_DELIVERY_CLAIM_SCHEMA_V0,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "atomic_commit_domain_hash": self.atomic_commit_domain_hash,
            "participant_manifest_hash": self.participant_manifest_hash,
            "coordinator_hash": self.coordinator_hash,
            "durable": self.durable,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DeliveryGuaranteeClaimV0:
    dispatch_receipt_hash: str
    dispatch_consumption_commit_receipt_hash: str
    prepared_execution_receipt_hash: str
    requested_guarantee: str
    atomic_delivery_claim_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "dispatch_receipt_hash",
            "dispatch_consumption_commit_receipt_hash",
            "prepared_execution_receipt_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.requested_guarantee not in DELIVERY_GUARANTEES_V0:
            raise DeliveryGuaranteeError("unsupported delivery guarantee")
        object.__setattr__(
            self,
            "atomic_delivery_claim_hash",
            _optional_hash(self.atomic_delivery_claim_hash, "atomic_delivery_claim_hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_CLAIM_SCHEMA_V0,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "requested_guarantee": self.requested_guarantee,
            "atomic_delivery_claim_hash": self.atomic_delivery_claim_hash,
        }

    @property
    def claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DeliveryGuaranteePolicyV0:
    atomic_evidence_policy_hash: str
    trusted_coordinator_hashes: tuple[str, ...] = ()
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "atomic_evidence_policy_hash", _hash64(self.atomic_evidence_policy_hash, "atomic_evidence_policy_hash"))
        object.__setattr__(self, "trusted_coordinator_hashes", _hashes(self.trusted_coordinator_hashes, "trusted coordinator hash"))
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "delivery accepted assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_POLICY_SCHEMA_V0,
            "atomic_evidence_policy_hash": self.atomic_evidence_policy_hash,
            "trusted_coordinator_hashes": list(self.trusted_coordinator_hashes),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DeliveryGuaranteeIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "delivery issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DeliveryGuaranteeError("delivery issue severity")
        subject = str(self.subject)
        if not subject:
            raise DeliveryGuaranteeError("delivery issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class DeliveryGuaranteeReceiptV0:
    delivery_claim_hash: str
    requested_guarantee: str
    dispatch_receipt_hash: str
    dispatch_consumption_commit_receipt_hash: str
    prepared_execution_receipt_hash: str
    atomic_delivery_claim_hash: str
    atomic_evidence_evaluation_hash: str
    policy_hash: str
    issues: tuple[DeliveryGuaranteeIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "delivery_claim_hash",
            "dispatch_receipt_hash",
            "dispatch_consumption_commit_receipt_hash",
            "prepared_execution_receipt_hash",
            "policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.requested_guarantee not in DELIVERY_GUARANTEES_V0:
            raise DeliveryGuaranteeError("requested_guarantee")
        for name in ("atomic_delivery_claim_hash", "atomic_evidence_evaluation_hash"):
            object.__setattr__(self, name, _optional_hash(getattr(self, name), name))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "delivery_claim_hash": self.delivery_claim_hash,
            "requested_guarantee": self.requested_guarantee,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "atomic_delivery_claim_hash": self.atomic_delivery_claim_hash,
            "atomic_evidence_evaluation_hash": self.atomic_evidence_evaluation_hash,
            "policy_hash": self.policy_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.delivery_guarantee_receipt.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> DeliveryGuaranteeIssueV0 | None:
    if status == "PASS":
        return None
    return DeliveryGuaranteeIssueV0(
        kind,
        "REJECT" if status == "REJECT" else "PROOF_REQUIRED",
        subject,
        {"status": status},
    )


def evaluate_delivery_guarantee(
    claim: DeliveryGuaranteeClaimV0,
    *,
    dispatch_receipt: ExecutionDispatchReceiptV0,
    consumption_commit_receipt: DispatchConsumptionCommitReceiptV0,
    prepared_execution_receipt: PreparedExecutionReceiptV0,
    prepared_reaction: PreparedReactionV1,
    law_catalog: CapabilityLawCatalogV1,
    policy: DeliveryGuaranteePolicyV0,
    atomic_delivery_claim: AtomicDeliveryCommitClaimV0 | None = None,
    atomic_evidence_policy: EvidencePolicyV0 | None = None,
    evidence: Iterable[EvidenceItemV0] = (),
) -> DeliveryGuaranteeReceiptV0:
    issues: list[DeliveryGuaranteeIssueV0] = []

    bindings = (
        ("delivery.dispatch_receipt_mismatch", claim.dispatch_receipt_hash, dispatch_receipt.receipt_hash),
        ("delivery.consumption_receipt_mismatch", claim.dispatch_consumption_commit_receipt_hash, consumption_commit_receipt.receipt_hash),
        ("delivery.prepared_execution_receipt_mismatch", claim.prepared_execution_receipt_hash, prepared_execution_receipt.receipt_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(DeliveryGuaranteeIssueV0(kind, "REJECT", expected, {"observed": observed}))

    if claim.requested_guarantee != dispatch_receipt.requested_delivery_guarantee:
        issues.append(
            DeliveryGuaranteeIssueV0(
                "delivery.requested_guarantee_mismatch",
                "REJECT",
                claim.requested_guarantee,
                {"execution_request": dispatch_receipt.requested_delivery_guarantee},
            )
        )

    for kind, subject, status in (
        ("delivery.dispatch_not_admitted", dispatch_receipt.receipt_hash, dispatch_receipt.status),
        ("delivery.consumption_not_committed", consumption_commit_receipt.receipt_hash, consumption_commit_receipt.status),
        ("delivery.prepared_execution_not_admitted", prepared_execution_receipt.receipt_hash, prepared_execution_receipt.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if consumption_commit_receipt.dispatch_receipt_hash != dispatch_receipt.receipt_hash:
        issues.append(DeliveryGuaranteeIssueV0("delivery.consumption_dispatch_mismatch", "REJECT", consumption_commit_receipt.dispatch_receipt_hash, {"dispatch": dispatch_receipt.receipt_hash}))
    if consumption_commit_receipt.dispatch_request_hash != dispatch_receipt.dispatch_request_hash:
        issues.append(DeliveryGuaranteeIssueV0("delivery.consumption_request_mismatch", "REJECT", consumption_commit_receipt.dispatch_request_hash, {"dispatch": dispatch_receipt.dispatch_request_hash}))
    if dispatch_receipt.prepared_execution_receipt_hash != prepared_execution_receipt.receipt_hash:
        issues.append(DeliveryGuaranteeIssueV0("delivery.dispatch_prepared_mismatch", "REJECT", dispatch_receipt.prepared_execution_receipt_hash, {"prepared": prepared_execution_receipt.receipt_hash}))
    if prepared_execution_receipt.prepared_reaction_hash != prepared_reaction.prepared_reaction_hash:
        issues.append(DeliveryGuaranteeIssueV0("delivery.prepared_reaction_mismatch", "REJECT", prepared_execution_receipt.prepared_reaction_hash, {"prepared_reaction": prepared_reaction.prepared_reaction_hash}))
    if prepared_reaction.law_catalog_hash != law_catalog.catalog_hash:
        issues.append(DeliveryGuaranteeIssueV0("delivery.law_catalog_mismatch", "REJECT", prepared_reaction.law_catalog_hash, {"catalog": law_catalog.catalog_hash}))

    if claim.requested_guarantee == "AT_MOST_ONCE_DISPATCH":
        return DeliveryGuaranteeReceiptV0(
            claim.claim_hash,
            claim.requested_guarantee,
            dispatch_receipt.receipt_hash,
            consumption_commit_receipt.receipt_hash,
            prepared_execution_receipt.receipt_hash,
            "",
            "",
            policy.policy_hash,
            tuple(issues),
        )

    if prepared_reaction.atomicity not in {"transactional", "durable_transactional"}:
        issues.append(DeliveryGuaranteeIssueV0("delivery.atomicity_insufficient", "REJECT", prepared_reaction.atomicity, {"required": "transactional"}))
    if claim.requested_guarantee == "DURABLE_EXACTLY_ONCE_COMMIT" and prepared_reaction.atomicity != "durable_transactional":
        issues.append(DeliveryGuaranteeIssueV0("delivery.durable_atomicity_required", "REJECT", prepared_reaction.atomicity, {"required": "durable_transactional"}))

    for intent in prepared_reaction.effect_intents:
        capability_id = str(intent.get("capability_id", ""))
        law = law_catalog.law(capability_id)
        if law is None:
            issues.append(DeliveryGuaranteeIssueV0("delivery.effect_law_missing", "PROOF_REQUIRED", capability_id or "missing", {}))
            continue
        if law.effect_protocol != "prepare_commit_abort" or not law.commit_total_after_prepare:
            issues.append(DeliveryGuaranteeIssueV0(
                "delivery.effect_not_exactly_once_capable",
                "REJECT",
                capability_id,
                {"effect_protocol": law.effect_protocol, "commit_total_after_prepare": law.commit_total_after_prepare},
            ))
        if claim.requested_guarantee == "DURABLE_EXACTLY_ONCE_COMMIT" and not law.durable_recovery:
            issues.append(DeliveryGuaranteeIssueV0("delivery.effect_not_durably_recoverable", "REJECT", capability_id, {}))

    if atomic_delivery_claim is None:
        issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_commit_witness_required", "PROOF_REQUIRED", claim.claim_hash, {}))
        atomic_hash = ""
        evidence_hash = ""
    else:
        atomic_hash = atomic_delivery_claim.claim_hash
        if claim.atomic_delivery_claim_hash != atomic_hash:
            issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_claim_mismatch", "REJECT", claim.atomic_delivery_claim_hash or "missing", {"observed": atomic_hash}))
        if atomic_delivery_claim.dispatch_consumption_commit_receipt_hash != consumption_commit_receipt.receipt_hash:
            issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_claim_consumption_mismatch", "REJECT", atomic_delivery_claim.dispatch_consumption_commit_receipt_hash, {"observed": consumption_commit_receipt.receipt_hash}))
        if atomic_delivery_claim.prepared_execution_receipt_hash != prepared_execution_receipt.receipt_hash:
            issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_claim_prepared_mismatch", "REJECT", atomic_delivery_claim.prepared_execution_receipt_hash, {"observed": prepared_execution_receipt.receipt_hash}))
        if atomic_delivery_claim.coordinator_hash not in policy.trusted_coordinator_hashes:
            issues.append(DeliveryGuaranteeIssueV0("delivery.coordinator_untrusted", "REJECT", atomic_delivery_claim.coordinator_hash, {"trusted": list(policy.trusted_coordinator_hashes)}))
        if claim.requested_guarantee == "DURABLE_EXACTLY_ONCE_COMMIT" and not atomic_delivery_claim.durable:
            issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_commit_not_durable", "REJECT", atomic_hash, {}))
        accepted_assumptions = set(policy.accepted_assumption_hashes)
        for assumption_hash in sorted(set(atomic_delivery_claim.assumption_hashes) - accepted_assumptions):
            issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_assumption_not_accepted", "REJECT", assumption_hash, {}))

        if atomic_evidence_policy is None:
            issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_evidence_policy_required", "PROOF_REQUIRED", atomic_hash, {}))
            evidence_hash = ""
        else:
            if policy.atomic_evidence_policy_hash != atomic_evidence_policy.policy_hash:
                issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_evidence_policy_mismatch", "REJECT", policy.atomic_evidence_policy_hash, {"observed": atomic_evidence_policy.policy_hash}))
            if not atomic_evidence_policy.requirements:
                issues.append(DeliveryGuaranteeIssueV0("delivery.atomic_evidence_policy_empty", "REJECT", atomic_evidence_policy.policy_hash, {}))
            evaluation = evaluate_evidence(atomic_hash, atomic_evidence_policy, tuple(evidence))
            evidence_hash = evaluation.evaluation_hash
            for item in evaluation.issues:
                issues.append(DeliveryGuaranteeIssueV0(
                    "delivery." + item.kind,
                    "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                    item.requirement_id,
                    {"evidence_hash": item.evidence_hash, **dict(item.detail)},
                ))

    return DeliveryGuaranteeReceiptV0(
        claim.claim_hash,
        claim.requested_guarantee,
        dispatch_receipt.receipt_hash,
        consumption_commit_receipt.receipt_hash,
        prepared_execution_receipt.receipt_hash,
        atomic_hash,
        evidence_hash,
        policy.policy_hash,
        tuple(issues),
    )


def residual_from_delivery_guarantee(receipt: DeliveryGuaranteeReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="delivery_guarantee",
        judgment_id="delivery_guarantee",
        judgment={"kind": "requested_delivery_guarantee_is_supported", "requested_guarantee": receipt.requested_guarantee, "status": receipt.status},
        source={"kind": "delivery_guarantee_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.delivery_claim_hash, receipt.dispatch_receipt_hash, receipt.dispatch_consumption_commit_receipt_hash, receipt.prepared_execution_receipt_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "DELIVERY_CLAIM_SCHEMA_V0",
    "ATOMIC_DELIVERY_CLAIM_SCHEMA_V0",
    "DELIVERY_POLICY_SCHEMA_V0",
    "DELIVERY_RECEIPT_SCHEMA_V0",
    "DeliveryGuaranteeError",
    "AtomicDeliveryCommitClaimV0",
    "DeliveryGuaranteeClaimV0",
    "DeliveryGuaranteePolicyV0",
    "DeliveryGuaranteeIssueV0",
    "DeliveryGuaranteeReceiptV0",
    "evaluate_delivery_guarantee",
    "residual_from_delivery_guarantee",
]
