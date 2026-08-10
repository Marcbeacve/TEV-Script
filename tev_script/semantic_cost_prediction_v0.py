from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_cost_model_v0 import CostModelAdmissionReceiptV0, EmpiricalCostModelV0
from .semantic_evidence_v0 import EvidenceItemV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_resource_algebra_v0 import ResourceVectorV0
from .semantic_resource_evidence_v0 import ResourceEstimateClaimV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

COST_PREDICTION_REQUEST_SCHEMA_V0 = "TEV_SCRIPT_COST_PREDICTION_REQUEST_V0"
COST_PREDICTION_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_COST_PREDICTION_EVALUATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class CostPredictionError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise CostPredictionError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise CostPredictionError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class CostPredictionRequestV0:
    model_hash: str
    model_admission_receipt_hash: str
    execution_context_hash: str
    scope_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "model_hash",
            "model_admission_receipt_hash",
            "execution_context_hash",
            "scope_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "cost prediction assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_PREDICTION_REQUEST_SCHEMA_V0,
            "model_hash": self.model_hash,
            "model_admission_receipt_hash": self.model_admission_receipt_hash,
            "execution_context_hash": self.execution_context_hash,
            "scope_hash": self.scope_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def request_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class CostPredictionIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "cost prediction issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise CostPredictionError("cost prediction issue severity")
        subject = str(self.subject)
        if not subject:
            raise CostPredictionError("cost prediction issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class CostPredictionEvaluationV0:
    request_hash: str
    model_hash: str
    estimate_claim_hash: str
    resource_vector_hash: str
    empirical_evidence_hash: str
    issues: tuple[CostPredictionIssueV0, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_hash", _hash64(self.request_hash, "request_hash"))
        object.__setattr__(self, "model_hash", _hash64(self.model_hash, "model_hash"))
        object.__setattr__(self, "estimate_claim_hash", _optional_hash(self.estimate_claim_hash, "estimate_claim_hash"))
        object.__setattr__(self, "resource_vector_hash", _optional_hash(self.resource_vector_hash, "resource_vector_hash"))
        object.__setattr__(self, "empirical_evidence_hash", _optional_hash(self.empirical_evidence_hash, "empirical_evidence_hash"))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))
        if self.status == "PASS" and not (self.estimate_claim_hash and self.resource_vector_hash and self.empirical_evidence_hash):
            raise CostPredictionError("PASS cost prediction requires estimate/vector/evidence outputs")
        if self.status != "PASS" and (self.estimate_claim_hash or self.resource_vector_hash or self.empirical_evidence_hash):
            raise CostPredictionError("non-PASS cost prediction must not emit authoritative outputs")

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_PREDICTION_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "request_hash": self.request_hash,
            "model_hash": self.model_hash,
            "estimate_claim_hash": self.estimate_claim_hash,
            "resource_vector_hash": self.resource_vector_hash,
            "empirical_evidence_hash": self.empirical_evidence_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.cost_prediction_evaluation.v0", self.to_object())


def evaluate_empirical_cost_prediction(
    request: CostPredictionRequestV0,
    *,
    model: EmpiricalCostModelV0,
    model_admission: CostModelAdmissionReceiptV0,
    evidence_id: str,
) -> tuple[
    CostPredictionEvaluationV0,
    ResourceEstimateClaimV0 | None,
    ResourceVectorV0 | None,
    EvidenceItemV0 | None,
]:
    issues: list[CostPredictionIssueV0] = []

    if request.model_hash != model.model_hash:
        issues.append(CostPredictionIssueV0("cost_prediction.model_mismatch", "REJECT", request.model_hash, {"observed": model.model_hash}))
    if request.model_admission_receipt_hash != model_admission.receipt_hash:
        issues.append(CostPredictionIssueV0("cost_prediction.admission_receipt_mismatch", "REJECT", request.model_admission_receipt_hash, {"observed": model_admission.receipt_hash}))
    if model_admission.model_hash != model.model_hash or model_admission.model_record_hash != model.record_hash:
        issues.append(CostPredictionIssueV0("cost_prediction.model_admission_not_bound", "REJECT", model_admission.receipt_hash, {}))
    if model_admission.status != "PASS":
        issues.append(CostPredictionIssueV0("cost_prediction.model_not_admitted", "REJECT" if model_admission.status == "REJECT" else "PROOF_REQUIRED", model_admission.receipt_hash, {"status": model_admission.status}))

    envelope = model.envelope_for(request.execution_context_hash)
    if envelope is None:
        issues.append(CostPredictionIssueV0("cost_prediction.context_unseen", "PROOF_REQUIRED", request.execution_context_hash, {}))

    if issues:
        evaluation = CostPredictionEvaluationV0(
            request.request_hash,
            model.model_hash,
            "",
            "",
            "",
            tuple(issues),
        )
        return evaluation, None, None, None

    assert envelope is not None
    assumptions = tuple(sorted(set(model.assumption_hashes) | set(request.assumption_hashes)))
    estimate = ResourceEstimateClaimV0(
        model.realization_hash,
        request.execution_context_hash,
        envelope.resource_vector.vector_hash,
        model.resource_catalog_hash,
        "EMPIRICAL_ENVELOPE",
        model.model_hash,
        request.scope_hash,
        assumption_hashes=assumptions,
        detail={
            "cost_model_record_hash": model.record_hash,
            "cost_model_admission_receipt_hash": model_admission.receipt_hash,
            "measurement_basis_count": len(envelope.measurement_claim_hashes),
        },
    )
    evidence = EvidenceItemV0(
        evidence_id,
        estimate.estimate_claim_hash,
        request.scope_hash,
        "EMPIRICAL_OBSERVATION",
        witness_hash=model_admission.receipt_hash,
        assumption_hashes=assumptions,
        coverage={
            "execution_context_hash": request.execution_context_hash,
            "cost_model_hash": model.model_hash,
            "measurement_basis_count": len(envelope.measurement_claim_hashes),
        },
    )
    evaluation = CostPredictionEvaluationV0(
        request.request_hash,
        model.model_hash,
        estimate.estimate_claim_hash,
        envelope.resource_vector.vector_hash,
        evidence.evidence_hash,
        (),
    )
    return evaluation, estimate, envelope.resource_vector, evidence


def residual_from_cost_prediction(evaluation: CostPredictionEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_cost_prediction",
        judgment_id="empirical_cost_prediction",
        judgment={"kind": "admitted_cost_model_predicts_exact_context", "request_hash": evaluation.request_hash, "status": evaluation.status},
        source={"kind": "cost_prediction_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(evaluation.request_hash, evaluation.model_hash),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "COST_PREDICTION_REQUEST_SCHEMA_V0",
    "COST_PREDICTION_EVALUATION_SCHEMA_V0",
    "CostPredictionError",
    "CostPredictionRequestV0",
    "CostPredictionIssueV0",
    "CostPredictionEvaluationV0",
    "evaluate_empirical_cost_prediction",
    "residual_from_cost_prediction",
]
