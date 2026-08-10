from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_resource_algebra_v0 import (
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceVectorV0,
)
from .semantic_resource_measurement_v0 import (
    ResourceMeasurementClaimV0,
    ResourceMeasurementEvaluationV0,
)
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

COST_MODEL_SCHEMA_V0 = "TEV_SCRIPT_EMPIRICAL_COST_MODEL_V0"
COST_MODEL_IDENTITY_SCHEMA_V0 = "TEV_SCRIPT_EMPIRICAL_COST_MODEL_IDENTITY_V0"
COST_CONTEXT_ENVELOPE_SCHEMA_V0 = "TEV_SCRIPT_COST_CONTEXT_ENVELOPE_V0"
COST_CONTEXT_ENVELOPE_IDENTITY_SCHEMA_V0 = "TEV_SCRIPT_COST_CONTEXT_ENVELOPE_IDENTITY_V0"
COST_MODEL_POLICY_SCHEMA_V0 = "TEV_SCRIPT_COST_MODEL_POLICY_V0"
COST_MODEL_ADMISSION_SCHEMA_V0 = "TEV_SCRIPT_COST_MODEL_ADMISSION_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class CostModelSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise CostModelSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise CostModelSemanticsError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def _envelope_bound(bounds: Iterable[ResourceBoundV0], dimension_id: str) -> ResourceBoundV0:
    rows = tuple(bounds)
    if not rows:
        raise CostModelSemanticsError("cannot build envelope from zero bounds")
    lower = min(item.lower for item in rows)
    upper = None if any(item.upper is None for item in rows) else max(item.upper for item in rows if item.upper is not None)
    return ResourceBoundV0(dimension_id, lower, upper)


def empirical_envelope(vectors: Iterable[ResourceVectorV0], catalog: ResourceCatalogV0) -> ResourceVectorV0:
    rows = tuple(vectors)
    if not rows:
        raise CostModelSemanticsError("empirical envelope requires measurements")
    for vector in rows:
        vector.validate_against(catalog)
    bounds = tuple(
        _envelope_bound(
            tuple(vector.effective_bound(dimension.dimension_id) for vector in rows),
            dimension.dimension_id,
        )
        for dimension in catalog.dimensions
    )
    return ResourceVectorV0(bounds, complete=True, catalog_hash=catalog.catalog_hash)


@dataclass(frozen=True, slots=True)
class CostContextEnvelopeV0:
    execution_context_hash: str
    resource_vector: ResourceVectorV0
    measurement_claim_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_context_hash", _hash64(self.execution_context_hash, "execution_context_hash"))
        claims = _hashes(self.measurement_claim_hashes, "measurement_claim_hash")
        if not claims:
            raise CostModelSemanticsError("cost context envelope requires measurement basis")
        object.__setattr__(self, "measurement_claim_hashes", claims)

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": COST_CONTEXT_ENVELOPE_IDENTITY_SCHEMA_V0,
            "execution_context_hash": self.execution_context_hash,
            "resource_vector": self.resource_vector.to_object(),
        }

    @property
    def envelope_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_CONTEXT_ENVELOPE_SCHEMA_V0,
            "envelope_hash": self.envelope_hash,
            "execution_context_hash": self.execution_context_hash,
            "resource_vector": self.resource_vector.to_object(),
            "measurement_claim_hashes": list(self.measurement_claim_hashes),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class EmpiricalCostModelV0:
    model_id: str
    realization_hash: str
    resource_catalog_hash: str
    envelopes: tuple[CostContextEnvelopeV0, ...]
    assumption_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _stable(self.model_id, "model_id"))
        object.__setattr__(self, "realization_hash", _hash64(self.realization_hash, "realization_hash"))
        object.__setattr__(self, "resource_catalog_hash", _hash64(self.resource_catalog_hash, "resource_catalog_hash"))
        envelopes = tuple(sorted(self.envelopes, key=lambda item: item.execution_context_hash))
        if not envelopes:
            raise CostModelSemanticsError("cost model requires at least one context envelope")
        if len({item.execution_context_hash for item in envelopes}) != len(envelopes):
            raise CostModelSemanticsError("duplicate execution context in cost model")
        if any(item.resource_vector.catalog_hash != self.resource_catalog_hash for item in envelopes):
            raise CostModelSemanticsError("cost model envelope catalog mismatch")
        object.__setattr__(self, "envelopes", envelopes)
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "cost model assumption hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def envelope_for(self, execution_context_hash: str) -> CostContextEnvelopeV0 | None:
        target = _hash64(execution_context_hash, "execution_context_hash")
        for envelope in self.envelopes:
            if envelope.execution_context_hash == target:
                return envelope
        return None

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": COST_MODEL_IDENTITY_SCHEMA_V0,
            "realization_hash": self.realization_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "envelopes": [item.semantic_object() for item in self.envelopes],
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def model_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_MODEL_SCHEMA_V0,
            "model_hash": self.model_hash,
            "model_id": self.model_id,
            "realization_hash": self.realization_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "envelopes": [item.to_object() for item in self.envelopes],
            "assumption_hashes": list(self.assumption_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.empirical_cost_model.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class CostModelPolicyV0:
    accepted_assumption_hashes: tuple[str, ...] = ()
    minimum_measurements_per_context: int = 1
    require_complete_measurements: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "accepted cost model assumption hash"))
        if not isinstance(self.minimum_measurements_per_context, int) or isinstance(self.minimum_measurements_per_context, bool) or self.minimum_measurements_per_context <= 0:
            raise CostModelSemanticsError("minimum_measurements_per_context must be positive integer")
        if not isinstance(self.require_complete_measurements, bool):
            raise CostModelSemanticsError("require_complete_measurements must be bool")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_MODEL_POLICY_SCHEMA_V0,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
            "minimum_measurements_per_context": self.minimum_measurements_per_context,
            "require_complete_measurements": self.require_complete_measurements,
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class CostModelIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "cost model issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise CostModelSemanticsError("cost model issue severity")
        subject = str(self.subject)
        if not subject:
            raise CostModelSemanticsError("cost model issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class CostModelAdmissionReceiptV0:
    model_hash: str
    model_record_hash: str
    realization_hash: str
    resource_catalog_hash: str
    policy_hash: str
    measurement_evaluation_hashes: tuple[str, ...]
    issues: tuple[CostModelIssueV0, ...]

    def __post_init__(self) -> None:
        for name in ("model_hash", "model_record_hash", "realization_hash", "resource_catalog_hash", "policy_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "measurement_evaluation_hashes", _hashes(self.measurement_evaluation_hashes, "measurement_evaluation_hash"))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_MODEL_ADMISSION_SCHEMA_V0,
            "status": self.status,
            "model_hash": self.model_hash,
            "model_record_hash": self.model_record_hash,
            "realization_hash": self.realization_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "policy_hash": self.policy_hash,
            "measurement_evaluation_hashes": list(self.measurement_evaluation_hashes),
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.cost_model_admission.v0", self.to_object())


def evaluate_empirical_cost_model(
    model: EmpiricalCostModelV0,
    *,
    policy: CostModelPolicyV0,
    resource_catalog: ResourceCatalogV0,
    measurements: Iterable[
        tuple[ResourceMeasurementClaimV0, ResourceMeasurementEvaluationV0, ResourceVectorV0]
    ],
) -> CostModelAdmissionReceiptV0:
    issues: list[CostModelIssueV0] = []
    rows = tuple(measurements)
    if not rows:
        raise CostModelSemanticsError("cost model evaluation requires measurements")

    if model.resource_catalog_hash != resource_catalog.catalog_hash:
        issues.append(CostModelIssueV0("cost_model.resource_catalog_mismatch", "REJECT", model.resource_catalog_hash, {"observed": resource_catalog.catalog_hash}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(model.assumption_hashes) - accepted_assumptions):
        issues.append(CostModelIssueV0("cost_model.assumption_not_accepted", "REJECT", assumption_hash, {}))

    seen_claims: set[str] = set()
    by_context: dict[str, list[tuple[ResourceMeasurementClaimV0, ResourceMeasurementEvaluationV0, ResourceVectorV0]]] = {}
    evaluation_hashes: list[str] = []
    for claim, evaluation, vector in rows:
        if claim.measurement_claim_hash in seen_claims:
            issues.append(CostModelIssueV0("cost_model.duplicate_measurement_claim", "REJECT", claim.measurement_claim_hash, {}))
            continue
        seen_claims.add(claim.measurement_claim_hash)
        evaluation_hashes.append(evaluation.evaluation_hash)

        if evaluation.measurement_claim_hash != claim.measurement_claim_hash:
            issues.append(CostModelIssueV0("cost_model.measurement_evaluation_mismatch", "REJECT", evaluation.evaluation_hash, {"claim": claim.measurement_claim_hash}))
        if evaluation.status != "PASS":
            issues.append(CostModelIssueV0("cost_model.measurement_not_admitted", "REJECT" if evaluation.status == "REJECT" else "PROOF_REQUIRED", evaluation.evaluation_hash, {"status": evaluation.status}))
        if claim.realization_hash != model.realization_hash or evaluation.realization_hash != model.realization_hash:
            issues.append(CostModelIssueV0("cost_model.measurement_realization_mismatch", "REJECT", claim.measurement_claim_hash, {"expected": model.realization_hash, "claim": claim.realization_hash, "evaluation": evaluation.realization_hash}))
        if claim.resource_catalog_hash != model.resource_catalog_hash or evaluation.resource_catalog_hash != model.resource_catalog_hash:
            issues.append(CostModelIssueV0("cost_model.measurement_catalog_mismatch", "REJECT", claim.measurement_claim_hash, {"expected": model.resource_catalog_hash}))
        try:
            vector.validate_against(resource_catalog)
        except Exception as error:
            issues.append(CostModelIssueV0("cost_model.measurement_vector_invalid", "REJECT", vector.vector_hash, {"detail": str(error)}))
        if claim.observed_resource_vector_hash != vector.vector_hash:
            issues.append(CostModelIssueV0("cost_model.measurement_vector_mismatch", "REJECT", claim.measurement_claim_hash, {"expected": claim.observed_resource_vector_hash, "observed": vector.vector_hash}))
        if policy.require_complete_measurements and not vector.complete:
            issues.append(CostModelIssueV0("cost_model.measurement_incomplete", "PROOF_REQUIRED", claim.measurement_claim_hash, {}))
        for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
            issues.append(CostModelIssueV0("cost_model.measurement_assumption_not_accepted", "REJECT", assumption_hash, {"measurement_claim_hash": claim.measurement_claim_hash}))
        by_context.setdefault(claim.execution_context_hash, []).append((claim, evaluation, vector))

    envelope_by_context = {item.execution_context_hash: item for item in model.envelopes}
    observed_contexts = set(by_context)
    modeled_contexts = set(envelope_by_context)
    for context_hash in sorted(modeled_contexts - observed_contexts):
        issues.append(CostModelIssueV0("cost_model.context_without_measurements", "REJECT", context_hash, {}))
    for context_hash in sorted(observed_contexts - modeled_contexts):
        issues.append(CostModelIssueV0("cost_model.measurement_context_unmodeled", "REJECT", context_hash, {}))

    for context_hash in sorted(observed_contexts & modeled_contexts):
        entries = by_context[context_hash]
        envelope = envelope_by_context[context_hash]
        expected_claims = tuple(sorted(claim.measurement_claim_hash for claim, _, _ in entries))
        if envelope.measurement_claim_hashes != expected_claims:
            issues.append(CostModelIssueV0("cost_model.measurement_basis_mismatch", "REJECT", context_hash, {"expected": list(expected_claims), "observed": list(envelope.measurement_claim_hashes)}))
        if len(entries) < policy.minimum_measurements_per_context:
            issues.append(CostModelIssueV0("cost_model.insufficient_measurements", "PROOF_REQUIRED", context_hash, {"minimum": policy.minimum_measurements_per_context, "observed": len(entries)}))
        try:
            expected_vector = empirical_envelope((vector for _, _, vector in entries), resource_catalog)
        except Exception as error:
            issues.append(CostModelIssueV0("cost_model.envelope_construction_failed", "REJECT", context_hash, {"detail": str(error)}))
            continue
        if canonical_json(envelope.resource_vector.to_object()) != canonical_json(expected_vector.to_object()):
            issues.append(CostModelIssueV0("cost_model.envelope_mismatch", "REJECT", context_hash, {"expected_vector_hash": expected_vector.vector_hash, "observed_vector_hash": envelope.resource_vector.vector_hash}))

    return CostModelAdmissionReceiptV0(
        model.model_hash,
        model.record_hash,
        model.realization_hash,
        model.resource_catalog_hash,
        policy.policy_hash,
        tuple(evaluation_hashes),
        tuple(issues),
    )


def residual_from_cost_model_admission(receipt: CostModelAdmissionReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_cost_model",
        judgment_id="empirical_cost_model_admission",
        judgment={"kind": "empirical_cost_model_matches_admitted_measurements", "model_hash": receipt.model_hash, "status": receipt.status},
        source={"kind": "cost_model_admission_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.model_hash, receipt.model_record_hash, receipt.resource_catalog_hash, receipt.policy_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "COST_MODEL_SCHEMA_V0",
    "COST_MODEL_IDENTITY_SCHEMA_V0",
    "COST_CONTEXT_ENVELOPE_SCHEMA_V0",
    "COST_CONTEXT_ENVELOPE_IDENTITY_SCHEMA_V0",
    "COST_MODEL_POLICY_SCHEMA_V0",
    "COST_MODEL_ADMISSION_SCHEMA_V0",
    "CostModelSemanticsError",
    "CostContextEnvelopeV0",
    "EmpiricalCostModelV0",
    "CostModelPolicyV0",
    "CostModelIssueV0",
    "CostModelAdmissionReceiptV0",
    "empirical_envelope",
    "evaluate_empirical_cost_model",
    "residual_from_cost_model_admission",
]
