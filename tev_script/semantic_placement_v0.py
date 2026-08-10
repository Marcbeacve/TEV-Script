from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

MACHINE_INSTANCE_SCHEMA_V0 = "TEV_SCRIPT_MACHINE_INSTANCE_V0"
MACHINE_INSTANCE_IDENTITY_SCHEMA_V0 = "TEV_SCRIPT_MACHINE_INSTANCE_IDENTITY_V0"
PLACEMENT_CONTEXT_SCHEMA_V0 = "TEV_SCRIPT_PLACEMENT_CONTEXT_V0"
PLACEMENT_POLICY_SCHEMA_V0 = "TEV_SCRIPT_PLACEMENT_POLICY_V0"
PLACEMENT_CANDIDATE_SCHEMA_V0 = "TEV_SCRIPT_PLACEMENT_CANDIDATE_V0"
PLACEMENT_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_PLACEMENT_EVALUATION_V0"
EXECUTION_CONTEXT_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_CONTEXT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class PlacementSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise PlacementSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise PlacementSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class MachineInstanceV0:
    """Claim about one concrete substrate principal bound to one machine profile."""

    instance_id: str
    machine_profile_hash: str
    instance_principal_hash: str
    immutable_attribute_claim_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "instance_id", _stable(self.instance_id, "instance_id"))
        object.__setattr__(self, "machine_profile_hash", _hash64(self.machine_profile_hash, "machine_profile_hash"))
        object.__setattr__(self, "instance_principal_hash", _hash64(self.instance_principal_hash, "instance_principal_hash"))
        object.__setattr__(self, "immutable_attribute_claim_hashes", _hashes(self.immutable_attribute_claim_hashes, "immutable attribute claim hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": MACHINE_INSTANCE_IDENTITY_SCHEMA_V0,
            "machine_profile_hash": self.machine_profile_hash,
            "instance_principal_hash": self.instance_principal_hash,
            "immutable_attribute_claim_hashes": list(self.immutable_attribute_claim_hashes),
        }

    @property
    def machine_instance_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": MACHINE_INSTANCE_SCHEMA_V0,
            "machine_instance_hash": self.machine_instance_hash,
            "instance_id": self.instance_id,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.machine_instance.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class PlacementContextV0:
    machine_instance_hash: str
    location_hash: str = ""
    authority_domain_hash: str = ""
    fault_domain_hash: str = ""
    communication_domain_hash: str = ""
    policy_context_hash: str = ""
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_instance_hash", _hash64(self.machine_instance_hash, "machine_instance_hash"))
        for name in (
            "location_hash",
            "authority_domain_hash",
            "fault_domain_hash",
            "communication_domain_hash",
            "policy_context_hash",
        ):
            object.__setattr__(self, name, _optional_hash(getattr(self, name), name))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "placement assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": PLACEMENT_CONTEXT_SCHEMA_V0,
            "machine_instance_hash": self.machine_instance_hash,
            "location_hash": self.location_hash,
            "authority_domain_hash": self.authority_domain_hash,
            "fault_domain_hash": self.fault_domain_hash,
            "communication_domain_hash": self.communication_domain_hash,
            "policy_context_hash": self.policy_context_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def placement_context_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.placement_context.v0", self.to_object())


def execution_context_hash(
    *,
    realization_hash: str,
    machine_instance_hash: str,
    placement_context_hash: str,
    workload_hash: str,
    environment_hash: str = "",
) -> str:
    return canonical_hash(
        {
            "schema": EXECUTION_CONTEXT_SCHEMA_V0,
            "realization_hash": _hash64(realization_hash, "realization_hash"),
            "machine_instance_hash": _hash64(machine_instance_hash, "machine_instance_hash"),
            "placement_context_hash": _hash64(placement_context_hash, "placement_context_hash"),
            "workload_hash": _hash64(workload_hash, "workload_hash"),
            "environment_hash": _optional_hash(environment_hash, "environment_hash"),
        }
    )


@dataclass(frozen=True, slots=True)
class PlacementPolicyV0:
    instance_evidence_policy_hash: str
    accepted_assumption_hashes: tuple[str, ...] = ()
    allowed_location_hashes: tuple[str, ...] = ()
    allowed_authority_domain_hashes: tuple[str, ...] = ()
    allowed_fault_domain_hashes: tuple[str, ...] = ()
    allowed_communication_domain_hashes: tuple[str, ...] = ()
    required_instance_attribute_claim_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "instance_evidence_policy_hash", _hash64(self.instance_evidence_policy_hash, "instance_evidence_policy_hash"))
        for name in (
            "accepted_assumption_hashes",
            "allowed_location_hashes",
            "allowed_authority_domain_hashes",
            "allowed_fault_domain_hashes",
            "allowed_communication_domain_hashes",
            "required_instance_attribute_claim_hashes",
        ):
            object.__setattr__(self, name, _hashes(getattr(self, name), name))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": PLACEMENT_POLICY_SCHEMA_V0,
            "instance_evidence_policy_hash": self.instance_evidence_policy_hash,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
            "allowed_location_hashes": list(self.allowed_location_hashes),
            "allowed_authority_domain_hashes": list(self.allowed_authority_domain_hashes),
            "allowed_fault_domain_hashes": list(self.allowed_fault_domain_hashes),
            "allowed_communication_domain_hashes": list(self.allowed_communication_domain_hashes),
            "required_instance_attribute_claim_hashes": list(self.required_instance_attribute_claim_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class PlacementCandidateV0:
    realization_admission_receipt_hash: str
    placement_context_hash: str
    assumption_hashes: tuple[str, ...] = ()
    evidence_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "realization_admission_receipt_hash", _hash64(self.realization_admission_receipt_hash, "realization_admission_receipt_hash"))
        object.__setattr__(self, "placement_context_hash", _hash64(self.placement_context_hash, "placement_context_hash"))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "placement candidate assumption hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "placement evidence hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_PLACEMENT_CANDIDATE_IDENTITY_V0",
            "realization_admission_receipt_hash": self.realization_admission_receipt_hash,
            "placement_context_hash": self.placement_context_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def placement_candidate_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": PLACEMENT_CANDIDATE_SCHEMA_V0,
            "placement_candidate_hash": self.placement_candidate_hash,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "evidence_hashes": list(self.evidence_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class PlacementIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "placement issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise PlacementSemanticsError("placement issue severity")
        subject = str(self.subject)
        if not subject:
            raise PlacementSemanticsError("placement issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class PlacementEvaluationV0:
    placement_candidate_hash: str
    placement_record_hash: str
    realization_receipt_hash: str
    machine_instance_hash: str
    placement_context_hash: str
    policy_hash: str
    instance_evidence_evaluation_hash: str
    issues: tuple[PlacementIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "placement_candidate_hash",
            "placement_record_hash",
            "realization_receipt_hash",
            "machine_instance_hash",
            "placement_context_hash",
            "policy_hash",
            "instance_evidence_evaluation_hash",
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
            "schema": PLACEMENT_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "placement_candidate_hash": self.placement_candidate_hash,
            "placement_record_hash": self.placement_record_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "machine_instance_hash": self.machine_instance_hash,
            "placement_context_hash": self.placement_context_hash,
            "policy_hash": self.policy_hash,
            "instance_evidence_evaluation_hash": self.instance_evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_placement(
    candidate: PlacementCandidateV0,
    *,
    realization_receipt: RealizationAdmissionReceiptV0,
    machine_instance: MachineInstanceV0,
    placement_context: PlacementContextV0,
    policy: PlacementPolicyV0,
    instance_evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> PlacementEvaluationV0:
    issues: list[PlacementIssueV0] = []

    if candidate.realization_admission_receipt_hash != realization_receipt.receipt_hash:
        issues.append(PlacementIssueV0("placement.realization_receipt_mismatch", "REJECT", candidate.realization_admission_receipt_hash, {"observed": realization_receipt.receipt_hash}))
    if realization_receipt.status != "PASS":
        issues.append(PlacementIssueV0("placement.realization_not_admitted", "REJECT", realization_receipt.receipt_hash, {"status": realization_receipt.status}))
    if candidate.placement_context_hash != placement_context.placement_context_hash:
        issues.append(PlacementIssueV0("placement.context_mismatch", "REJECT", candidate.placement_context_hash, {"observed": placement_context.placement_context_hash}))
    if placement_context.machine_instance_hash != machine_instance.machine_instance_hash:
        issues.append(PlacementIssueV0("placement.instance_mismatch", "REJECT", placement_context.machine_instance_hash, {"observed": machine_instance.machine_instance_hash}))
    if realization_receipt.machine_hash != machine_instance.machine_profile_hash:
        issues.append(PlacementIssueV0("placement.machine_profile_mismatch", "REJECT", machine_instance.machine_profile_hash, {"required": realization_receipt.machine_hash}))
    if policy.instance_evidence_policy_hash != instance_evidence_policy.policy_hash:
        issues.append(PlacementIssueV0("placement.evidence_policy_mismatch", "REJECT", instance_evidence_policy.policy_hash, {"expected": policy.instance_evidence_policy_hash}))
    if not instance_evidence_policy.requirements:
        issues.append(PlacementIssueV0("placement.instance_evidence_policy_empty", "REJECT", instance_evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted((set(candidate.assumption_hashes) | set(placement_context.assumption_hashes)) - accepted_assumptions):
        issues.append(PlacementIssueV0("placement.assumption_not_accepted", "REJECT", assumption_hash, {}))

    for attribute_hash in sorted(set(policy.required_instance_attribute_claim_hashes) - set(machine_instance.immutable_attribute_claim_hashes)):
        issues.append(PlacementIssueV0("placement.instance_attribute_missing", "REJECT", attribute_hash, {}))

    domain_checks = (
        ("placement.location_not_allowed", placement_context.location_hash, policy.allowed_location_hashes),
        ("placement.authority_not_allowed", placement_context.authority_domain_hash, policy.allowed_authority_domain_hashes),
        ("placement.fault_domain_not_allowed", placement_context.fault_domain_hash, policy.allowed_fault_domain_hashes),
        ("placement.communication_domain_not_allowed", placement_context.communication_domain_hash, policy.allowed_communication_domain_hashes),
    )
    for kind, observed, allowed in domain_checks:
        if allowed and (not observed or observed not in allowed):
            issues.append(PlacementIssueV0(kind, "REJECT", observed or "missing", {"allowed": list(allowed)}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in candidate.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(PlacementIssueV0("placement.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    instance_evaluation = evaluate_evidence(machine_instance.machine_instance_hash, instance_evidence_policy, evidence_items)
    for item in instance_evaluation.issues:
        issues.append(
            PlacementIssueV0(
                "placement." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in instance_evaluation.accepted_evidence_hashes:
        if accepted_hash not in candidate.evidence_hashes:
            issues.append(PlacementIssueV0("placement.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(PlacementIssueV0("placement.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return PlacementEvaluationV0(
        candidate.placement_candidate_hash,
        candidate.record_hash,
        realization_receipt.receipt_hash,
        machine_instance.machine_instance_hash,
        placement_context.placement_context_hash,
        policy.policy_hash,
        instance_evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_placement(evaluation: PlacementEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_placement",
        judgment_id="placement_admission",
        judgment={
            "kind": "realization_placement_admissible",
            "placement_candidate_hash": evaluation.placement_candidate_hash,
            "status": evaluation.status,
        },
        source={"kind": "placement_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    evaluation.placement_candidate_hash,
                    evaluation.placement_record_hash,
                    evaluation.realization_receipt_hash,
                    evaluation.machine_instance_hash,
                    evaluation.placement_context_hash,
                ),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "MACHINE_INSTANCE_SCHEMA_V0",
    "MACHINE_INSTANCE_IDENTITY_SCHEMA_V0",
    "PLACEMENT_CONTEXT_SCHEMA_V0",
    "PLACEMENT_POLICY_SCHEMA_V0",
    "PLACEMENT_CANDIDATE_SCHEMA_V0",
    "PLACEMENT_EVALUATION_SCHEMA_V0",
    "EXECUTION_CONTEXT_SCHEMA_V0",
    "PlacementSemanticsError",
    "MachineInstanceV0",
    "PlacementContextV0",
    "PlacementPolicyV0",
    "PlacementCandidateV0",
    "PlacementIssueV0",
    "PlacementEvaluationV0",
    "execution_context_hash",
    "evaluate_placement",
    "residual_from_placement",
]
