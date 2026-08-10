from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .causal_model_v1 import CapabilityLawCatalogV1, PreparedReactionV1
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_execution_request_v0 import DELIVERY_GUARANTEES_V0, ExecutionRequestAdmissionReceiptV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_prepared_execution_v0 import PreparedExecutionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DELIVERY_PARTICIPANT_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_PARTICIPANT_V0"
DELIVERY_PARTICIPANT_MANIFEST_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_PARTICIPANT_MANIFEST_V0"
DELIVERY_PLAN_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_PLAN_CLAIM_V0"
DELIVERY_PLAN_POLICY_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_PLAN_POLICY_V0"
DELIVERY_PLAN_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_DELIVERY_PLAN_RECEIPT_V0"
_PARTICIPANT_KINDS = frozenset({"DISPATCH_LEDGER", "RUNTIME_STATE_COMMIT", "EXTERNAL_EFFECT"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DeliveryPlanError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DeliveryPlanError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DeliveryPlanError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True, order=True)
class DeliveryParticipantV0:
    kind: str
    occurrence_index: int
    subject_hash: str

    def __post_init__(self) -> None:
        if self.kind not in _PARTICIPANT_KINDS:
            raise DeliveryPlanError("delivery participant kind")
        if not isinstance(self.occurrence_index, int) or isinstance(self.occurrence_index, bool) or self.occurrence_index < 0:
            raise DeliveryPlanError("delivery participant occurrence_index")
        object.__setattr__(self, "subject_hash", _hash64(self.subject_hash, "delivery participant subject_hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_PARTICIPANT_SCHEMA_V0,
            "kind": self.kind,
            "occurrence_index": self.occurrence_index,
            "subject_hash": self.subject_hash,
        }


@dataclass(frozen=True, slots=True)
class DeliveryParticipantManifestV0:
    execution_request_hash: str
    prepared_reaction_hash: str
    participants: tuple[DeliveryParticipantV0, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_request_hash", _hash64(self.execution_request_hash, "execution_request_hash"))
        object.__setattr__(self, "prepared_reaction_hash", _hash64(self.prepared_reaction_hash, "prepared_reaction_hash"))
        participants = tuple(sorted(self.participants))
        if not participants:
            raise DeliveryPlanError("delivery manifest requires participants")
        if len(set(participants)) != len(participants):
            raise DeliveryPlanError("duplicate delivery participant")
        if not any(item.kind == "DISPATCH_LEDGER" for item in participants):
            raise DeliveryPlanError("delivery manifest requires dispatch ledger participant")
        object.__setattr__(self, "participants", participants)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_PARTICIPANT_MANIFEST_SCHEMA_V0,
            "execution_request_hash": self.execution_request_hash,
            "prepared_reaction_hash": self.prepared_reaction_hash,
            "participants": [item.to_object() for item in self.participants],
        }

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.delivery_participant_manifest.v0", self.to_object())


def derive_delivery_participant_manifest(
    execution_request_hash: str,
    prepared_reaction: PreparedReactionV1,
) -> DeliveryParticipantManifestV0:
    request_hash = _hash64(execution_request_hash, "execution_request_hash")
    participants: list[DeliveryParticipantV0] = [
        DeliveryParticipantV0("DISPATCH_LEDGER", 0, request_hash)
    ]

    runtime_subject = canonical_hash(
        {
            "schema": "TEV_SCRIPT_RUNTIME_STATE_DELIVERY_PARTICIPANT_V0",
            "before_checkpoint_hash": prepared_reaction.before_checkpoint_hash,
            "after_checkpoint_hash": prepared_reaction.after_checkpoint_hash,
            "emitted_events": [dict(item) for item in prepared_reaction.emitted_events],
        }
    )
    if (
        prepared_reaction.before_checkpoint_hash != prepared_reaction.after_checkpoint_hash
        or prepared_reaction.emitted_events
    ):
        participants.append(DeliveryParticipantV0("RUNTIME_STATE_COMMIT", 0, runtime_subject))

    for index, intent in enumerate(prepared_reaction.effect_intents):
        participants.append(
            DeliveryParticipantV0(
                "EXTERNAL_EFFECT",
                index,
                canonical_hash(
                    {
                        "schema": "TEV_SCRIPT_EXTERNAL_EFFECT_DELIVERY_PARTICIPANT_V0",
                        "intent": dict(intent),
                    }
                ),
            )
        )

    return DeliveryParticipantManifestV0(
        request_hash,
        prepared_reaction.prepared_reaction_hash,
        tuple(participants),
    )


@dataclass(frozen=True, slots=True)
class DeliveryPlanClaimV0:
    execution_request_receipt_hash: str
    prepared_execution_receipt_hash: str
    participant_manifest_hash: str
    requested_guarantee: str
    coordinator_hash: str = ""
    atomic_commit_domain_hash: str = ""
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "execution_request_receipt_hash",
            "prepared_execution_receipt_hash",
            "participant_manifest_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.requested_guarantee not in DELIVERY_GUARANTEES_V0:
            raise DeliveryPlanError("requested_guarantee")
        object.__setattr__(self, "coordinator_hash", _optional_hash(self.coordinator_hash, "coordinator_hash"))
        object.__setattr__(self, "atomic_commit_domain_hash", _optional_hash(self.atomic_commit_domain_hash, "atomic_commit_domain_hash"))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "delivery plan assumption hash"))
        if self.requested_guarantee == "AT_MOST_ONCE_DISPATCH":
            if self.coordinator_hash or self.atomic_commit_domain_hash:
                raise DeliveryPlanError("at-most-once plan must not claim atomic coordinator")
        elif not self.coordinator_hash or not self.atomic_commit_domain_hash:
            raise DeliveryPlanError("exactly-once plan requires coordinator and atomic commit domain")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_PLAN_CLAIM_SCHEMA_V0,
            "execution_request_receipt_hash": self.execution_request_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "participant_manifest_hash": self.participant_manifest_hash,
            "requested_guarantee": self.requested_guarantee,
            "coordinator_hash": self.coordinator_hash,
            "atomic_commit_domain_hash": self.atomic_commit_domain_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DeliveryPlanPolicyV0:
    evidence_policy_hash: str
    trusted_coordinator_hashes: tuple[str, ...] = ()
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "trusted_coordinator_hashes", _hashes(self.trusted_coordinator_hashes, "trusted coordinator hash"))
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "accepted delivery plan assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_PLAN_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "trusted_coordinator_hashes": list(self.trusted_coordinator_hashes),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DeliveryPlanIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "delivery plan issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DeliveryPlanError("delivery plan issue severity")
        subject = str(self.subject)
        if not subject:
            raise DeliveryPlanError("delivery plan issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class DeliveryPlanReceiptV0:
    plan_claim_hash: str
    execution_request_receipt_hash: str
    prepared_execution_receipt_hash: str
    participant_manifest_hash: str
    requested_guarantee: str
    coordinator_hash: str
    atomic_commit_domain_hash: str
    evidence_evaluation_hash: str
    policy_hash: str
    issues: tuple[DeliveryPlanIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "plan_claim_hash",
            "execution_request_receipt_hash",
            "prepared_execution_receipt_hash",
            "participant_manifest_hash",
            "policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.requested_guarantee not in DELIVERY_GUARANTEES_V0:
            raise DeliveryPlanError("requested_guarantee")
        object.__setattr__(self, "coordinator_hash", _optional_hash(self.coordinator_hash, "coordinator_hash"))
        object.__setattr__(self, "atomic_commit_domain_hash", _optional_hash(self.atomic_commit_domain_hash, "atomic_commit_domain_hash"))
        object.__setattr__(self, "evidence_evaluation_hash", _optional_hash(self.evidence_evaluation_hash, "evidence_evaluation_hash"))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DELIVERY_PLAN_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "plan_claim_hash": self.plan_claim_hash,
            "execution_request_receipt_hash": self.execution_request_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "participant_manifest_hash": self.participant_manifest_hash,
            "requested_guarantee": self.requested_guarantee,
            "coordinator_hash": self.coordinator_hash,
            "atomic_commit_domain_hash": self.atomic_commit_domain_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "policy_hash": self.policy_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.delivery_plan_receipt.v0", self.to_object())


def evaluate_delivery_plan(
    claim: DeliveryPlanClaimV0,
    *,
    execution_request_receipt: ExecutionRequestAdmissionReceiptV0,
    prepared_execution_receipt: PreparedExecutionReceiptV0,
    participant_manifest: DeliveryParticipantManifestV0,
    prepared_reaction: PreparedReactionV1,
    law_catalog: CapabilityLawCatalogV1,
    policy: DeliveryPlanPolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0] = (),
) -> DeliveryPlanReceiptV0:
    issues: list[DeliveryPlanIssueV0] = []

    bindings = (
        ("delivery_plan.request_receipt_mismatch", claim.execution_request_receipt_hash, execution_request_receipt.receipt_hash),
        ("delivery_plan.prepared_execution_receipt_mismatch", claim.prepared_execution_receipt_hash, prepared_execution_receipt.receipt_hash),
        ("delivery_plan.manifest_mismatch", claim.participant_manifest_hash, participant_manifest.manifest_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(DeliveryPlanIssueV0(kind, "REJECT", expected, {"observed": observed}))

    if execution_request_receipt.status != "PASS":
        issues.append(DeliveryPlanIssueV0("delivery_plan.request_not_admitted", "REJECT" if execution_request_receipt.status == "REJECT" else "PROOF_REQUIRED", execution_request_receipt.receipt_hash, {"status": execution_request_receipt.status}))
    if prepared_execution_receipt.status != "PASS":
        issues.append(DeliveryPlanIssueV0("delivery_plan.prepared_execution_not_admitted", "REJECT" if prepared_execution_receipt.status == "REJECT" else "PROOF_REQUIRED", prepared_execution_receipt.receipt_hash, {"status": prepared_execution_receipt.status}))
    if claim.requested_guarantee != execution_request_receipt.requested_delivery_guarantee:
        issues.append(DeliveryPlanIssueV0("delivery_plan.requested_guarantee_mismatch", "REJECT", claim.requested_guarantee, {"request": execution_request_receipt.requested_delivery_guarantee}))
    if execution_request_receipt.invocation_workload_hash != prepared_execution_receipt.invocation_workload_hash:
        issues.append(DeliveryPlanIssueV0("delivery_plan.workload_mismatch", "REJECT", execution_request_receipt.invocation_workload_hash, {"prepared": prepared_execution_receipt.invocation_workload_hash}))
    if prepared_execution_receipt.prepared_reaction_hash != prepared_reaction.prepared_reaction_hash:
        issues.append(DeliveryPlanIssueV0("delivery_plan.prepared_reaction_mismatch", "REJECT", prepared_execution_receipt.prepared_reaction_hash, {"reaction": prepared_reaction.prepared_reaction_hash}))
    if prepared_reaction.law_catalog_hash != law_catalog.catalog_hash:
        issues.append(DeliveryPlanIssueV0("delivery_plan.law_catalog_mismatch", "REJECT", prepared_reaction.law_catalog_hash, {"catalog": law_catalog.catalog_hash}))

    derived = derive_delivery_participant_manifest(execution_request_receipt.request_hash, prepared_reaction)
    if participant_manifest.manifest_hash != derived.manifest_hash:
        issues.append(DeliveryPlanIssueV0("delivery_plan.participant_manifest_not_derived", "REJECT", participant_manifest.manifest_hash, {"derived": derived.manifest_hash}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
        issues.append(DeliveryPlanIssueV0("delivery_plan.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_hash = ""
    if claim.requested_guarantee != "AT_MOST_ONCE_DISPATCH":
        if prepared_reaction.atomicity not in {"transactional", "durable_transactional"}:
            issues.append(DeliveryPlanIssueV0("delivery_plan.atomicity_insufficient", "REJECT", prepared_reaction.atomicity, {"required": "transactional"}))
        if claim.requested_guarantee == "DURABLE_EXACTLY_ONCE_COMMIT" and prepared_reaction.atomicity != "durable_transactional":
            issues.append(DeliveryPlanIssueV0("delivery_plan.durable_atomicity_required", "REJECT", prepared_reaction.atomicity, {"required": "durable_transactional"}))
        if claim.coordinator_hash not in policy.trusted_coordinator_hashes:
            issues.append(DeliveryPlanIssueV0("delivery_plan.coordinator_untrusted", "REJECT", claim.coordinator_hash or "missing", {"trusted": list(policy.trusted_coordinator_hashes)}))

        for intent in prepared_reaction.effect_intents:
            capability_id = str(intent.get("capability_id", ""))
            law = law_catalog.law(capability_id)
            if law is None:
                issues.append(DeliveryPlanIssueV0("delivery_plan.effect_law_missing", "PROOF_REQUIRED", capability_id or "missing", {}))
                continue
            if law.effect_protocol != "prepare_commit_abort" or not law.commit_total_after_prepare:
                issues.append(DeliveryPlanIssueV0("delivery_plan.effect_not_exactly_once_capable", "REJECT", capability_id, {"effect_protocol": law.effect_protocol, "commit_total_after_prepare": law.commit_total_after_prepare}))
            if claim.requested_guarantee == "DURABLE_EXACTLY_ONCE_COMMIT" and not law.durable_recovery:
                issues.append(DeliveryPlanIssueV0("delivery_plan.effect_not_durably_recoverable", "REJECT", capability_id, {}))

        if policy.evidence_policy_hash != evidence_policy.policy_hash:
            issues.append(DeliveryPlanIssueV0("delivery_plan.evidence_policy_mismatch", "REJECT", policy.evidence_policy_hash, {"observed": evidence_policy.policy_hash}))
        if not evidence_policy.requirements:
            issues.append(DeliveryPlanIssueV0("delivery_plan.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))
        evaluation = evaluate_evidence(claim.claim_hash, evidence_policy, tuple(evidence))
        evidence_hash = evaluation.evaluation_hash
        for item in evaluation.issues:
            issues.append(DeliveryPlanIssueV0("delivery_plan." + item.kind, "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED", item.requirement_id, {"evidence_hash": item.evidence_hash, **dict(item.detail)}))

    return DeliveryPlanReceiptV0(
        claim.claim_hash,
        execution_request_receipt.receipt_hash,
        prepared_execution_receipt.receipt_hash,
        participant_manifest.manifest_hash,
        claim.requested_guarantee,
        claim.coordinator_hash,
        claim.atomic_commit_domain_hash,
        evidence_hash,
        policy.policy_hash,
        tuple(issues),
    )


def residual_from_delivery_plan(receipt: DeliveryPlanReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="delivery_plan",
        judgment_id="delivery_plan_admission",
        judgment={
            "kind": "requested_delivery_protocol_is_admissible_before_dispatch",
            "requested_guarantee": receipt.requested_guarantee,
            "status": receipt.status,
        },
        source={"kind": "delivery_plan_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.plan_claim_hash, receipt.execution_request_receipt_hash, receipt.prepared_execution_receipt_hash, receipt.participant_manifest_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "DELIVERY_PARTICIPANT_SCHEMA_V0",
    "DELIVERY_PARTICIPANT_MANIFEST_SCHEMA_V0",
    "DELIVERY_PLAN_CLAIM_SCHEMA_V0",
    "DELIVERY_PLAN_POLICY_SCHEMA_V0",
    "DELIVERY_PLAN_RECEIPT_SCHEMA_V0",
    "DeliveryPlanError",
    "DeliveryParticipantV0",
    "DeliveryParticipantManifestV0",
    "derive_delivery_participant_manifest",
    "DeliveryPlanClaimV0",
    "DeliveryPlanPolicyV0",
    "DeliveryPlanIssueV0",
    "DeliveryPlanReceiptV0",
    "evaluate_delivery_plan",
    "residual_from_delivery_plan",
]
