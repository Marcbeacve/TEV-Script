from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_activation_v0 import ExecutionActivationReceiptV0
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions
from .semantic_resource_algebra_v0 import ResourceAlgebraError, ResourceCatalogV0, ResourceVectorV0

RESOURCE_MEASUREMENT_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_MEASUREMENT_CLAIM_V0"
RESOURCE_MEASUREMENT_RECORD_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_MEASUREMENT_RECORD_V0"
RESOURCE_MEASUREMENT_POLICY_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_MEASUREMENT_POLICY_V0"
RESOURCE_MEASUREMENT_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_MEASUREMENT_EVALUATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ResourceMeasurementError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ResourceMeasurementError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ResourceMeasurementError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class ResourceMeasurementClaimV0:
    activation_receipt_hash: str
    realization_hash: str
    execution_context_hash: str
    resource_catalog_hash: str
    observed_resource_vector_hash: str
    measurement_epoch_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "activation_receipt_hash",
            "realization_hash",
            "execution_context_hash",
            "resource_catalog_hash",
            "observed_resource_vector_hash",
            "measurement_epoch_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "resource measurement assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_MEASUREMENT_CLAIM_SCHEMA_V0,
            "activation_receipt_hash": self.activation_receipt_hash,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "observed_resource_vector_hash": self.observed_resource_vector_hash,
            "measurement_epoch_hash": self.measurement_epoch_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def measurement_claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceMeasurementRecordV0:
    claim: ResourceMeasurementClaimV0
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    observer_hash: str = ""
    detail: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "resource measurement evidence hash"))
        object.__setattr__(self, "observer_hash", _optional_hash(self.observer_hash, "observer_hash"))
        detail = {} if self.detail is None else dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_MEASUREMENT_RECORD_SCHEMA_V0,
            "measurement_claim_hash": self.claim.measurement_claim_hash,
            "claim": self.claim.to_object(),
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "observer_hash": self.observer_hash,
            "detail": dict(self.detail or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.resource_measurement.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceMeasurementPolicyV0:
    evidence_policy_hash: str
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "resource measurement accepted assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_MEASUREMENT_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceMeasurementIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "resource measurement issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ResourceMeasurementError("resource measurement issue severity")
        subject = str(self.subject)
        if not subject:
            raise ResourceMeasurementError("resource measurement issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ResourceMeasurementEvaluationV0:
    measurement_claim_hash: str
    measurement_record_hash: str
    activation_receipt_hash: str
    realization_hash: str
    execution_context_hash: str
    resource_catalog_hash: str
    evidence_evaluation_hash: str
    issues: tuple[ResourceMeasurementIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "measurement_claim_hash",
            "measurement_record_hash",
            "activation_receipt_hash",
            "realization_hash",
            "execution_context_hash",
            "resource_catalog_hash",
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
            "schema": RESOURCE_MEASUREMENT_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "measurement_claim_hash": self.measurement_claim_hash,
            "measurement_record_hash": self.measurement_record_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_resource_measurement(
    record: ResourceMeasurementRecordV0,
    *,
    activation_receipt: ExecutionActivationReceiptV0,
    observed_resources: ResourceVectorV0,
    resource_catalog: ResourceCatalogV0,
    policy: ResourceMeasurementPolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> ResourceMeasurementEvaluationV0:
    issues: list[ResourceMeasurementIssueV0] = []
    claim = record.claim

    if claim.activation_receipt_hash != activation_receipt.receipt_hash:
        issues.append(ResourceMeasurementIssueV0("measurement.activation_mismatch", "REJECT", claim.activation_receipt_hash, {"observed": activation_receipt.receipt_hash}))
    if activation_receipt.status != "PASS":
        issues.append(ResourceMeasurementIssueV0("measurement.activation_not_admitted", "REJECT" if activation_receipt.status == "REJECT" else "PROOF_REQUIRED", activation_receipt.receipt_hash, {"status": activation_receipt.status}))
    if claim.realization_hash != activation_receipt.realization_hash:
        issues.append(ResourceMeasurementIssueV0("measurement.realization_mismatch", "REJECT", claim.realization_hash, {"observed": activation_receipt.realization_hash}))
    if claim.execution_context_hash != activation_receipt.execution_context_hash:
        issues.append(ResourceMeasurementIssueV0("measurement.execution_context_mismatch", "REJECT", claim.execution_context_hash, {"observed": activation_receipt.execution_context_hash}))
    if claim.resource_catalog_hash != resource_catalog.catalog_hash:
        issues.append(ResourceMeasurementIssueV0("measurement.resource_catalog_mismatch", "REJECT", claim.resource_catalog_hash, {"observed": resource_catalog.catalog_hash}))
    try:
        observed_resources.validate_against(resource_catalog)
    except ResourceAlgebraError as error:
        issues.append(ResourceMeasurementIssueV0("measurement.resource_vector_invalid", "REJECT", observed_resources.vector_hash, {"detail": str(error)}))
    if claim.observed_resource_vector_hash != observed_resources.vector_hash:
        issues.append(ResourceMeasurementIssueV0("measurement.resource_vector_mismatch", "REJECT", claim.observed_resource_vector_hash, {"observed": observed_resources.vector_hash}))

    if record.evidence_policy_hash != evidence_policy.policy_hash or policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(ResourceMeasurementIssueV0("measurement.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"record": record.evidence_policy_hash, "policy": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(ResourceMeasurementIssueV0("measurement.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
        issues.append(ResourceMeasurementIssueV0("measurement.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(ResourceMeasurementIssueV0("measurement.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evaluation = evaluate_evidence(claim.measurement_claim_hash, evidence_policy, evidence_items)
    for item in evaluation.issues:
        issues.append(
            ResourceMeasurementIssueV0(
                "measurement." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(ResourceMeasurementIssueV0("measurement.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(ResourceMeasurementIssueV0("measurement.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return ResourceMeasurementEvaluationV0(
        claim.measurement_claim_hash,
        record.record_hash,
        activation_receipt.receipt_hash,
        activation_receipt.realization_hash,
        activation_receipt.execution_context_hash,
        resource_catalog.catalog_hash,
        evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_resource_measurement(evaluation: ResourceMeasurementEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_resource_measurement",
        judgment_id="resource_measurement_binding",
        judgment={
            "kind": "execution_resource_measurement_authentic",
            "measurement_claim_hash": evaluation.measurement_claim_hash,
            "status": evaluation.status,
        },
        source={"kind": "resource_measurement_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    evaluation.measurement_claim_hash,
                    evaluation.activation_receipt_hash,
                    evaluation.realization_hash,
                    evaluation.execution_context_hash,
                    evaluation.resource_catalog_hash,
                ),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "RESOURCE_MEASUREMENT_CLAIM_SCHEMA_V0",
    "RESOURCE_MEASUREMENT_RECORD_SCHEMA_V0",
    "RESOURCE_MEASUREMENT_POLICY_SCHEMA_V0",
    "RESOURCE_MEASUREMENT_EVALUATION_SCHEMA_V0",
    "ResourceMeasurementError",
    "ResourceMeasurementClaimV0",
    "ResourceMeasurementRecordV0",
    "ResourceMeasurementPolicyV0",
    "ResourceMeasurementIssueV0",
    "ResourceMeasurementEvaluationV0",
    "evaluate_resource_measurement",
    "residual_from_resource_measurement",
]
