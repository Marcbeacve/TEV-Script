from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_cost_model_v0 import CostModelAdmissionReceiptV0, EmpiricalCostModelV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_resource_measurement_v0 import (
    ResourceMeasurementClaimV0,
    ResourceMeasurementEvaluationV0,
)
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

COST_MODEL_UPDATE_SCHEMA_V0 = "TEV_SCRIPT_COST_MODEL_UPDATE_V0"
COST_MODEL_UPDATE_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_COST_MODEL_UPDATE_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class CostModelUpdateError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise CostModelUpdateError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise CostModelUpdateError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def model_measurement_basis(model: EmpiricalCostModelV0) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                claim_hash
                for envelope in model.envelopes
                for claim_hash in envelope.measurement_claim_hashes
            }
        )
    )


@dataclass(frozen=True, slots=True)
class CostModelUpdateV0:
    parent_model_hash: str
    parent_model_record_hash: str
    parent_admission_receipt_hash: str
    successor_model_hash: str
    successor_model_record_hash: str
    successor_admission_receipt_hash: str
    new_measurement_claim_hashes: tuple[str, ...]
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "parent_model_hash",
            "parent_model_record_hash",
            "parent_admission_receipt_hash",
            "successor_model_hash",
            "successor_model_record_hash",
            "successor_admission_receipt_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        new_claims = _hashes(self.new_measurement_claim_hashes, "new_measurement_claim_hash")
        if not new_claims:
            raise CostModelUpdateError("cost model update requires new measurements")
        object.__setattr__(self, "new_measurement_claim_hashes", new_claims)
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "cost model update assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_MODEL_UPDATE_SCHEMA_V0,
            "parent_model_hash": self.parent_model_hash,
            "parent_model_record_hash": self.parent_model_record_hash,
            "parent_admission_receipt_hash": self.parent_admission_receipt_hash,
            "successor_model_hash": self.successor_model_hash,
            "successor_model_record_hash": self.successor_model_record_hash,
            "successor_admission_receipt_hash": self.successor_admission_receipt_hash,
            "new_measurement_claim_hashes": list(self.new_measurement_claim_hashes),
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def update_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.cost_model_update.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class CostModelUpdateIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "cost model update issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise CostModelUpdateError("cost model update issue severity")
        subject = str(self.subject)
        if not subject:
            raise CostModelUpdateError("cost model update issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class CostModelUpdateReceiptV0:
    update_hash: str
    parent_model_hash: str
    successor_model_hash: str
    new_measurement_evaluation_hashes: tuple[str, ...]
    issues: tuple[CostModelUpdateIssueV0, ...]

    def __post_init__(self) -> None:
        for name in ("update_hash", "parent_model_hash", "successor_model_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "new_measurement_evaluation_hashes", _hashes(self.new_measurement_evaluation_hashes, "new_measurement_evaluation_hash"))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COST_MODEL_UPDATE_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "update_hash": self.update_hash,
            "parent_model_hash": self.parent_model_hash,
            "successor_model_hash": self.successor_model_hash,
            "new_measurement_evaluation_hashes": list(self.new_measurement_evaluation_hashes),
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.cost_model_update_receipt.v0", self.to_object())


def evaluate_cost_model_update(
    update: CostModelUpdateV0,
    *,
    parent_model: EmpiricalCostModelV0,
    parent_admission: CostModelAdmissionReceiptV0,
    successor_model: EmpiricalCostModelV0,
    successor_admission: CostModelAdmissionReceiptV0,
    new_measurements: Iterable[tuple[ResourceMeasurementClaimV0, ResourceMeasurementEvaluationV0]],
    accepted_assumption_hashes: Iterable[str] = (),
) -> CostModelUpdateReceiptV0:
    issues: list[CostModelUpdateIssueV0] = []
    accepted_assumptions = set(_hashes(accepted_assumption_hashes, "accepted update assumption hash"))

    binding_checks = (
        ("cost_model_update.parent_model_mismatch", update.parent_model_hash, parent_model.model_hash),
        ("cost_model_update.parent_record_mismatch", update.parent_model_record_hash, parent_model.record_hash),
        ("cost_model_update.parent_admission_mismatch", update.parent_admission_receipt_hash, parent_admission.receipt_hash),
        ("cost_model_update.successor_model_mismatch", update.successor_model_hash, successor_model.model_hash),
        ("cost_model_update.successor_record_mismatch", update.successor_model_record_hash, successor_model.record_hash),
        ("cost_model_update.successor_admission_mismatch", update.successor_admission_receipt_hash, successor_admission.receipt_hash),
    )
    for kind, expected, observed in binding_checks:
        if expected != observed:
            issues.append(CostModelUpdateIssueV0(kind, "REJECT", expected, {"observed": observed}))

    if parent_admission.model_hash != parent_model.model_hash or parent_admission.model_record_hash != parent_model.record_hash:
        issues.append(CostModelUpdateIssueV0("cost_model_update.parent_admission_not_bound", "REJECT", parent_admission.receipt_hash, {}))
    if successor_admission.model_hash != successor_model.model_hash or successor_admission.model_record_hash != successor_model.record_hash:
        issues.append(CostModelUpdateIssueV0("cost_model_update.successor_admission_not_bound", "REJECT", successor_admission.receipt_hash, {}))
    if parent_admission.status != "PASS":
        issues.append(CostModelUpdateIssueV0("cost_model_update.parent_not_admitted", "REJECT" if parent_admission.status == "REJECT" else "PROOF_REQUIRED", parent_admission.receipt_hash, {"status": parent_admission.status}))
    if successor_admission.status != "PASS":
        issues.append(CostModelUpdateIssueV0("cost_model_update.successor_not_admitted", "REJECT" if successor_admission.status == "REJECT" else "PROOF_REQUIRED", successor_admission.receipt_hash, {"status": successor_admission.status}))

    if parent_model.realization_hash != successor_model.realization_hash:
        issues.append(CostModelUpdateIssueV0("cost_model_update.realization_changed", "REJECT", successor_model.realization_hash, {"parent": parent_model.realization_hash}))
    if parent_model.resource_catalog_hash != successor_model.resource_catalog_hash:
        issues.append(CostModelUpdateIssueV0("cost_model_update.resource_catalog_changed", "REJECT", successor_model.resource_catalog_hash, {"parent": parent_model.resource_catalog_hash}))
    if parent_model.assumption_hashes != successor_model.assumption_hashes:
        issues.append(CostModelUpdateIssueV0("cost_model_update.model_assumptions_changed", "REJECT", successor_model.model_hash, {"parent_assumptions": list(parent_model.assumption_hashes), "successor_assumptions": list(successor_model.assumption_hashes)}))
    for assumption_hash in sorted(set(update.assumption_hashes) - accepted_assumptions):
        issues.append(CostModelUpdateIssueV0("cost_model_update.assumption_not_accepted", "REJECT", assumption_hash, {}))

    rows = tuple(new_measurements)
    observed_new_claims = tuple(sorted(claim.measurement_claim_hash for claim, _ in rows))
    if observed_new_claims != update.new_measurement_claim_hashes:
        issues.append(CostModelUpdateIssueV0("cost_model_update.new_measurement_set_mismatch", "REJECT", update.update_hash, {"expected": list(update.new_measurement_claim_hashes), "observed": list(observed_new_claims)}))

    evaluation_hashes: list[str] = []
    for claim, evaluation in rows:
        evaluation_hashes.append(evaluation.evaluation_hash)
        if evaluation.measurement_claim_hash != claim.measurement_claim_hash:
            issues.append(CostModelUpdateIssueV0("cost_model_update.measurement_evaluation_mismatch", "REJECT", evaluation.evaluation_hash, {"claim": claim.measurement_claim_hash}))
        if evaluation.status != "PASS":
            issues.append(CostModelUpdateIssueV0("cost_model_update.measurement_not_admitted", "REJECT" if evaluation.status == "REJECT" else "PROOF_REQUIRED", evaluation.evaluation_hash, {"status": evaluation.status}))
        if claim.realization_hash != successor_model.realization_hash:
            issues.append(CostModelUpdateIssueV0("cost_model_update.measurement_realization_mismatch", "REJECT", claim.measurement_claim_hash, {"expected": successor_model.realization_hash, "observed": claim.realization_hash}))
        if claim.resource_catalog_hash != successor_model.resource_catalog_hash:
            issues.append(CostModelUpdateIssueV0("cost_model_update.measurement_catalog_mismatch", "REJECT", claim.measurement_claim_hash, {"expected": successor_model.resource_catalog_hash, "observed": claim.resource_catalog_hash}))

    parent_basis = set(model_measurement_basis(parent_model))
    successor_basis = set(model_measurement_basis(successor_model))
    new_basis = set(update.new_measurement_claim_hashes)
    if parent_basis & new_basis:
        issues.append(CostModelUpdateIssueV0("cost_model_update.measurement_already_in_parent", "REJECT", sorted(parent_basis & new_basis)[0], {}))
    expected_successor_basis = parent_basis | new_basis
    if successor_basis != expected_successor_basis:
        issues.append(CostModelUpdateIssueV0("cost_model_update.successor_basis_mismatch", "REJECT", successor_model.record_hash, {"expected": sorted(expected_successor_basis), "observed": sorted(successor_basis)}))

    return CostModelUpdateReceiptV0(
        update.update_hash,
        parent_model.model_hash,
        successor_model.model_hash,
        tuple(evaluation_hashes),
        tuple(issues),
    )


def residual_from_cost_model_update(receipt: CostModelUpdateReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_cost_model_update",
        judgment_id="cost_model_append_only_update",
        judgment={"kind": "successor_cost_model_extends_parent_basis", "update_hash": receipt.update_hash, "status": receipt.status},
        source={"kind": "cost_model_update_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.update_hash, receipt.parent_model_hash, receipt.successor_model_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "COST_MODEL_UPDATE_SCHEMA_V0",
    "COST_MODEL_UPDATE_RECEIPT_SCHEMA_V0",
    "CostModelUpdateError",
    "CostModelUpdateV0",
    "CostModelUpdateIssueV0",
    "CostModelUpdateReceiptV0",
    "model_measurement_basis",
    "evaluate_cost_model_update",
    "residual_from_cost_model_update",
]
