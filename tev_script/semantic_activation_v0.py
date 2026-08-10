from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_placement_v0 import PlacementContextV0, PlacementEvaluationV0, execution_context_hash
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions
from .semantic_runtime_state_v0 import RuntimeStateEvaluationV0, RuntimeStateObservationV0

ACTIVATION_CANDIDATE_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_ACTIVATION_CANDIDATE_V0"
ACTIVATION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_ACTIVATION_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ActivationSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ActivationSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ActivationSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


@dataclass(frozen=True, slots=True)
class ExecutionActivationCandidateV0:
    realization_receipt_hash: str
    placement_evaluation_hash: str
    runtime_state_evaluation_hash: str
    runtime_state_claim_hash: str
    execution_context_hash: str
    workload_hash: str
    environment_hash: str = ""
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "realization_receipt_hash",
            "placement_evaluation_hash",
            "runtime_state_evaluation_hash",
            "runtime_state_claim_hash",
            "execution_context_hash",
            "workload_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "environment_hash", _optional_hash(self.environment_hash, "environment_hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_EXECUTION_ACTIVATION_IDENTITY_V0",
            "realization_receipt_hash": self.realization_receipt_hash,
            "placement_evaluation_hash": self.placement_evaluation_hash,
            "runtime_state_evaluation_hash": self.runtime_state_evaluation_hash,
            "runtime_state_claim_hash": self.runtime_state_claim_hash,
            "execution_context_hash": self.execution_context_hash,
            "workload_hash": self.workload_hash,
            "environment_hash": self.environment_hash,
        }

    @property
    def activation_candidate_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": ACTIVATION_CANDIDATE_SCHEMA_V0,
            "activation_candidate_hash": self.activation_candidate_hash,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ActivationIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "activation issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ActivationSemanticsError("activation issue severity")
        subject = str(self.subject)
        if not subject:
            raise ActivationSemanticsError("activation issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExecutionActivationReceiptV0:
    activation_candidate_hash: str
    activation_record_hash: str
    realization_receipt_hash: str
    realization_hash: str
    placement_evaluation_hash: str
    machine_instance_hash: str
    placement_context_hash: str
    runtime_state_evaluation_hash: str
    runtime_state_claim_hash: str
    execution_context_hash: str
    issues: tuple[ActivationIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "activation_candidate_hash",
            "activation_record_hash",
            "realization_receipt_hash",
            "realization_hash",
            "placement_evaluation_hash",
            "machine_instance_hash",
            "placement_context_hash",
            "runtime_state_evaluation_hash",
            "runtime_state_claim_hash",
            "execution_context_hash",
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
            "schema": ACTIVATION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "activation_candidate_hash": self.activation_candidate_hash,
            "activation_record_hash": self.activation_record_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "realization_hash": self.realization_hash,
            "placement_evaluation_hash": self.placement_evaluation_hash,
            "machine_instance_hash": self.machine_instance_hash,
            "placement_context_hash": self.placement_context_hash,
            "runtime_state_evaluation_hash": self.runtime_state_evaluation_hash,
            "runtime_state_claim_hash": self.runtime_state_claim_hash,
            "execution_context_hash": self.execution_context_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_activation_receipt.v0", self.to_object())


def _upstream_issue(kind: str, subject: str, status: str) -> ActivationIssueV0 | None:
    if status == "PASS":
        return None
    severity = "REJECT" if status == "REJECT" else "PROOF_REQUIRED"
    return ActivationIssueV0(kind, severity, subject, {"status": status})


def evaluate_execution_activation(
    candidate: ExecutionActivationCandidateV0,
    *,
    realization_receipt: RealizationAdmissionReceiptV0,
    placement_evaluation: PlacementEvaluationV0,
    placement_context: PlacementContextV0,
    runtime_state_evaluation: RuntimeStateEvaluationV0,
    runtime_state_observation: RuntimeStateObservationV0,
) -> ExecutionActivationReceiptV0:
    issues: list[ActivationIssueV0] = []

    bindings = (
        ("activation.realization_receipt_mismatch", candidate.realization_receipt_hash, realization_receipt.receipt_hash),
        ("activation.placement_evaluation_mismatch", candidate.placement_evaluation_hash, placement_evaluation.evaluation_hash),
        ("activation.runtime_evaluation_mismatch", candidate.runtime_state_evaluation_hash, runtime_state_evaluation.evaluation_hash),
        ("activation.runtime_claim_mismatch", candidate.runtime_state_claim_hash, runtime_state_observation.runtime_state_claim_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(ActivationIssueV0(kind, "REJECT", expected, {"observed": observed}))

    for kind, subject, status in (
        ("activation.realization_not_admitted", realization_receipt.receipt_hash, realization_receipt.status),
        ("activation.placement_not_admitted", placement_evaluation.evaluation_hash, placement_evaluation.status),
        ("activation.runtime_state_not_admitted", runtime_state_evaluation.evaluation_hash, runtime_state_evaluation.status),
    ):
        issue = _upstream_issue(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if placement_evaluation.realization_receipt_hash != realization_receipt.receipt_hash:
        issues.append(ActivationIssueV0("activation.placement_realization_mismatch", "REJECT", placement_evaluation.realization_receipt_hash, {"observed": realization_receipt.receipt_hash}))
    if placement_evaluation.placement_context_hash != placement_context.placement_context_hash:
        issues.append(ActivationIssueV0("activation.placement_context_mismatch", "REJECT", placement_evaluation.placement_context_hash, {"observed": placement_context.placement_context_hash}))
    if placement_context.machine_instance_hash != placement_evaluation.machine_instance_hash:
        issues.append(ActivationIssueV0("activation.placement_instance_mismatch", "REJECT", placement_context.machine_instance_hash, {"observed": placement_evaluation.machine_instance_hash}))
    if runtime_state_evaluation.runtime_state_claim_hash != runtime_state_observation.runtime_state_claim_hash:
        issues.append(ActivationIssueV0("activation.runtime_state_claim_evaluation_mismatch", "REJECT", runtime_state_evaluation.runtime_state_claim_hash, {"observed": runtime_state_observation.runtime_state_claim_hash}))
    if runtime_state_observation.machine_instance_hash != placement_evaluation.machine_instance_hash:
        issues.append(ActivationIssueV0("activation.runtime_instance_mismatch", "REJECT", runtime_state_observation.machine_instance_hash, {"observed": placement_evaluation.machine_instance_hash}))

    expected_context = execution_context_hash(
        realization_hash=realization_receipt.realization_hash,
        machine_instance_hash=placement_evaluation.machine_instance_hash,
        placement_context_hash=placement_evaluation.placement_context_hash,
        workload_hash=candidate.workload_hash,
        environment_hash=candidate.environment_hash,
    )
    if candidate.execution_context_hash != expected_context:
        issues.append(ActivationIssueV0("activation.execution_context_mismatch", "REJECT", candidate.execution_context_hash, {"expected": expected_context}))

    return ExecutionActivationReceiptV0(
        candidate.activation_candidate_hash,
        candidate.record_hash,
        realization_receipt.receipt_hash,
        realization_receipt.realization_hash,
        placement_evaluation.evaluation_hash,
        placement_evaluation.machine_instance_hash,
        placement_evaluation.placement_context_hash,
        runtime_state_evaluation.evaluation_hash,
        runtime_state_observation.runtime_state_claim_hash,
        expected_context,
        tuple(issues),
    )


def residual_from_execution_activation(receipt: ExecutionActivationReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_activation",
        judgment_id="execution_activation",
        judgment={
            "kind": "execution_may_activate",
            "activation_candidate_hash": receipt.activation_candidate_hash,
            "status": receipt.status,
        },
        source={"kind": "execution_activation_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    receipt.activation_candidate_hash,
                    receipt.realization_receipt_hash,
                    receipt.placement_evaluation_hash,
                    receipt.runtime_state_evaluation_hash,
                    receipt.execution_context_hash,
                ),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "ACTIVATION_CANDIDATE_SCHEMA_V0",
    "ACTIVATION_RECEIPT_SCHEMA_V0",
    "ActivationSemanticsError",
    "ExecutionActivationCandidateV0",
    "ActivationIssueV0",
    "ExecutionActivationReceiptV0",
    "evaluate_execution_activation",
    "residual_from_execution_activation",
]
