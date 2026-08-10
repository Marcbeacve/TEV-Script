from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_resource_algebra_v0 import ResourceBoundV0, ResourceCatalogV0, ResourceVectorV0
from .semantic_resource_evidence_v0 import ResourceEstimateClaimV0
from .semantic_resource_measurement_v0 import (
    ResourceMeasurementClaimV0,
    ResourceMeasurementEvaluationV0,
)
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

RESOURCE_CALIBRATION_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_CALIBRATION_V0"
RESOURCE_CALIBRATION_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_CALIBRATION_EVALUATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_VERDICTS = frozenset({"SUPPORTED", "FALSIFIED", "INCONCLUSIVE"})
_DIMENSION_VERDICTS = frozenset({"WITHIN_BOUND", "BOUND_VIOLATED", "INCONCLUSIVE", "UNPREDICTED"})


class ResourceCalibrationError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ResourceCalibrationError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ResourceCalibrationError(what)
    return text


@dataclass(frozen=True, slots=True)
class ResourceDimensionCalibrationV0:
    dimension_id: str
    verdict: str
    predicted_bound_hash: str
    observed_bound_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension_id", _stable(self.dimension_id, "dimension_id"))
        if self.verdict not in _DIMENSION_VERDICTS:
            raise ResourceCalibrationError("dimension calibration verdict")
        object.__setattr__(self, "predicted_bound_hash", _hash64(self.predicted_bound_hash, "predicted_bound_hash"))
        object.__setattr__(self, "observed_bound_hash", _hash64(self.observed_bound_hash, "observed_bound_hash"))

    def to_object(self) -> dict[str, str]:
        return {
            "dimension_id": self.dimension_id,
            "verdict": self.verdict,
            "predicted_bound_hash": self.predicted_bound_hash,
            "observed_bound_hash": self.observed_bound_hash,
        }


def _bound_hash(bound: ResourceBoundV0) -> str:
    return canonical_hash({"schema": "TEV_SCRIPT_RESOURCE_BOUND_IDENTITY_V0", **bound.to_object()})


def _dimension_verdict(predicted: ResourceBoundV0, observed: ResourceBoundV0) -> str:
    # A measured interval proves a bound false only when the whole possible
    # observed interval lies below the predicted lower bound, or the measured
    # lower bound lies above a finite predicted upper bound.
    if observed.upper is not None and observed.upper < predicted.lower:
        return "BOUND_VIOLATED"
    if predicted.upper is not None and observed.lower > predicted.upper:
        return "BOUND_VIOLATED"

    # Full containment is positive compatibility evidence for this measurement.
    lower_inside = observed.lower >= predicted.lower
    upper_inside = predicted.upper is None or (
        observed.upper is not None and observed.upper <= predicted.upper
    )
    if lower_inside and upper_inside:
        return "WITHIN_BOUND"

    # Interval overlap, unknown observed upper, or absent finite prediction is
    # not silently converted into support or falsification.
    return "INCONCLUSIVE"


@dataclass(frozen=True, slots=True)
class ResourceCalibrationV0:
    realization_receipt_hash: str
    resource_estimate_claim_hash: str
    resource_measurement_claim_hash: str
    resource_catalog_hash: str

    def __post_init__(self) -> None:
        for name in (
            "realization_receipt_hash",
            "resource_estimate_claim_hash",
            "resource_measurement_claim_hash",
            "resource_catalog_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_CALIBRATION_SCHEMA_V0,
            "realization_receipt_hash": self.realization_receipt_hash,
            "resource_estimate_claim_hash": self.resource_estimate_claim_hash,
            "resource_measurement_claim_hash": self.resource_measurement_claim_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
        }

    @property
    def calibration_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceCalibrationIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "resource calibration issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ResourceCalibrationError("resource calibration issue severity")
        subject = str(self.subject)
        if not subject:
            raise ResourceCalibrationError("resource calibration issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ResourceCalibrationEvaluationV0:
    calibration_hash: str
    verdict: str
    dimension_results: tuple[ResourceDimensionCalibrationV0, ...]
    issues: tuple[ResourceCalibrationIssueV0, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "calibration_hash", _hash64(self.calibration_hash, "calibration_hash"))
        if self.verdict not in _VERDICTS:
            raise ResourceCalibrationError("resource calibration verdict")
        object.__setattr__(self, "dimension_results", tuple(sorted(self.dimension_results, key=lambda item: item.dimension_id)))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))
        expected = "SUPPORTED"
        if any(item.severity == "REJECT" for item in self.issues) or any(item.verdict == "BOUND_VIOLATED" for item in self.dimension_results):
            expected = "FALSIFIED"
        elif self.issues or any(item.verdict in {"INCONCLUSIVE", "UNPREDICTED"} for item in self.dimension_results):
            expected = "INCONCLUSIVE"
        if self.verdict != expected:
            raise ResourceCalibrationError("calibration verdict inconsistent")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_CALIBRATION_EVALUATION_SCHEMA_V0,
            "verdict": self.verdict,
            "calibration_hash": self.calibration_hash,
            "dimension_results": [item.to_object() for item in self.dimension_results],
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.resource_calibration.v0", self.to_object())


def evaluate_resource_calibration(
    calibration: ResourceCalibrationV0,
    *,
    realization_receipt: RealizationAdmissionReceiptV0,
    estimate_claim: ResourceEstimateClaimV0,
    predicted_resources: ResourceVectorV0,
    measurement_claim: ResourceMeasurementClaimV0,
    measurement_evaluation: ResourceMeasurementEvaluationV0,
    observed_resources: ResourceVectorV0,
    resource_catalog: ResourceCatalogV0,
    dimensions: Iterable[str] | None = None,
) -> ResourceCalibrationEvaluationV0:
    issues: list[ResourceCalibrationIssueV0] = []

    checks = (
        ("calibration.realization_receipt_mismatch", calibration.realization_receipt_hash, realization_receipt.receipt_hash),
        ("calibration.estimate_claim_mismatch", calibration.resource_estimate_claim_hash, estimate_claim.estimate_claim_hash),
        ("calibration.measurement_claim_mismatch", calibration.resource_measurement_claim_hash, measurement_claim.measurement_claim_hash),
        ("calibration.resource_catalog_mismatch", calibration.resource_catalog_hash, resource_catalog.catalog_hash),
    )
    for kind, expected, observed in checks:
        if expected != observed:
            issues.append(ResourceCalibrationIssueV0(kind, "REJECT", expected, {"observed": observed}))

    if realization_receipt.status != "PASS":
        issues.append(ResourceCalibrationIssueV0("calibration.realization_not_admitted", "REJECT" if realization_receipt.status == "REJECT" else "PROOF_REQUIRED", realization_receipt.receipt_hash, {"status": realization_receipt.status}))
    if realization_receipt.resource_estimate_claim_hash != estimate_claim.estimate_claim_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.receipt_estimate_mismatch", "REJECT", realization_receipt.resource_estimate_claim_hash, {"observed": estimate_claim.estimate_claim_hash}))
    if measurement_evaluation.measurement_claim_hash != measurement_claim.measurement_claim_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.measurement_evaluation_mismatch", "REJECT", measurement_evaluation.measurement_claim_hash, {"observed": measurement_claim.measurement_claim_hash}))
    if measurement_evaluation.status != "PASS":
        issues.append(ResourceCalibrationIssueV0("calibration.measurement_not_admitted", "REJECT" if measurement_evaluation.status == "REJECT" else "PROOF_REQUIRED", measurement_evaluation.measurement_claim_hash, {"status": measurement_evaluation.status}))

    if estimate_claim.realization_hash != realization_receipt.realization_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.estimate_realization_mismatch", "REJECT", estimate_claim.realization_hash, {"observed": realization_receipt.realization_hash}))
    if measurement_claim.realization_hash != realization_receipt.realization_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.measurement_realization_mismatch", "REJECT", measurement_claim.realization_hash, {"observed": realization_receipt.realization_hash}))
    if estimate_claim.execution_context_hash != measurement_claim.execution_context_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.execution_context_mismatch", "REJECT", estimate_claim.execution_context_hash, {"observed": measurement_claim.execution_context_hash}))

    predicted_resources.validate_against(resource_catalog)
    observed_resources.validate_against(resource_catalog)
    if estimate_claim.resource_vector_hash != predicted_resources.vector_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.predicted_vector_mismatch", "REJECT", estimate_claim.resource_vector_hash, {"observed": predicted_resources.vector_hash}))
    if measurement_claim.observed_resource_vector_hash != observed_resources.vector_hash:
        issues.append(ResourceCalibrationIssueV0("calibration.observed_vector_mismatch", "REJECT", measurement_claim.observed_resource_vector_hash, {"observed": observed_resources.vector_hash}))

    selected = tuple(resource_catalog.dimension_ids if dimensions is None else tuple(str(item) for item in dimensions))
    if not selected:
        raise ResourceCalibrationError("calibration requires at least one dimension")
    if len(set(selected)) != len(selected):
        raise ResourceCalibrationError("duplicate calibration dimension")
    outside = set(selected) - set(resource_catalog.dimension_ids)
    if outside:
        raise ResourceCalibrationError("calibration dimension outside resource catalog")

    results: list[ResourceDimensionCalibrationV0] = []
    for dimension_id in selected:
        predicted = predicted_resources.bound(dimension_id)
        observed = observed_resources.bound(dimension_id)
        if observed is None:
            # A complete admitted measurement should normally cover the measured
            # catalog, but incomplete measurement surfaces remain explicitly open.
            observed = observed_resources.effective_bound(dimension_id)
        if predicted is None:
            results.append(
                ResourceDimensionCalibrationV0(
                    dimension_id,
                    "UNPREDICTED",
                    _bound_hash(predicted_resources.effective_bound(dimension_id)),
                    _bound_hash(observed),
                )
            )
            continue
        results.append(
            ResourceDimensionCalibrationV0(
                dimension_id,
                _dimension_verdict(predicted, observed),
                _bound_hash(predicted),
                _bound_hash(observed),
            )
        )

    verdict = "SUPPORTED"
    if any(item.severity == "REJECT" for item in issues) or any(item.verdict == "BOUND_VIOLATED" for item in results):
        verdict = "FALSIFIED"
    elif issues or any(item.verdict in {"INCONCLUSIVE", "UNPREDICTED"} for item in results):
        verdict = "INCONCLUSIVE"

    return ResourceCalibrationEvaluationV0(calibration.calibration_hash, verdict, tuple(results), tuple(issues))


def residual_from_resource_calibration(evaluation: ResourceCalibrationEvaluationV0) -> SemanticFieldV0:
    obstructions: list[ResidualObstructionV0] = []
    for issue in evaluation.issues:
        obstructions.append(
            ResidualObstructionV0(
                issue.kind,
                issue.subject,
                "resolved",
                issue.severity,
                dict(issue.detail),
                dependency_refs=(evaluation.calibration_hash,),
            )
        )
    for result in evaluation.dimension_results:
        if result.verdict == "BOUND_VIOLATED":
            obstructions.append(
                ResidualObstructionV0(
                    "resource.prediction_falsified",
                    result.dimension_id,
                    result.predicted_bound_hash,
                    result.observed_bound_hash,
                    {"dimension_verdict": result.verdict},
                    dependency_refs=(evaluation.calibration_hash,),
                )
            )
        elif result.verdict in {"INCONCLUSIVE", "UNPREDICTED"}:
            obstructions.append(
                ResidualObstructionV0(
                    "resource.calibration_inconclusive",
                    result.dimension_id,
                    result.predicted_bound_hash,
                    result.observed_bound_hash,
                    {"dimension_verdict": result.verdict},
                    dependency_refs=(evaluation.calibration_hash,),
                )
            )
    return residual_from_obstructions(
        domain="realization_resource_calibration",
        judgment_id="resource_prediction_calibration",
        judgment={"kind": "prediction_consistent_with_admitted_measurement", "verdict": evaluation.verdict},
        source={"kind": "resource_calibration_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=tuple(obstructions),
    )


__all__ = [
    "RESOURCE_CALIBRATION_SCHEMA_V0",
    "RESOURCE_CALIBRATION_EVALUATION_SCHEMA_V0",
    "ResourceCalibrationError",
    "ResourceDimensionCalibrationV0",
    "ResourceCalibrationV0",
    "ResourceCalibrationIssueV0",
    "ResourceCalibrationEvaluationV0",
    "evaluate_resource_calibration",
    "residual_from_resource_calibration",
]
