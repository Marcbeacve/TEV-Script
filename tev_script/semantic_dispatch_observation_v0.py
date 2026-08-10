from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_dispatch_consumption_v0 import DispatchConsumptionCommitReceiptV0
from .semantic_dispatch_v0 import ExecutionDispatchReceiptV0
from .semantic_execution_observation_v0 import ExecutionObservationReceiptV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DISPATCHED_OBSERVATION_BINDING_SCHEMA_V0 = "TEV_SCRIPT_DISPATCHED_EXECUTION_OBSERVATION_BINDING_V0"
DISPATCHED_OBSERVATION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_DISPATCHED_EXECUTION_OBSERVATION_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DispatchObservationError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DispatchObservationError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DispatchObservationError(what)
    return text


@dataclass(frozen=True, slots=True)
class DispatchedExecutionObservationBindingV0:
    dispatch_receipt_hash: str
    dispatch_consumption_commit_receipt_hash: str
    execution_observation_receipt_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "dispatch_receipt_hash", _hash64(self.dispatch_receipt_hash, "dispatch_receipt_hash"))
        object.__setattr__(self, "dispatch_consumption_commit_receipt_hash", _hash64(self.dispatch_consumption_commit_receipt_hash, "dispatch_consumption_commit_receipt_hash"))
        object.__setattr__(self, "execution_observation_receipt_hash", _hash64(self.execution_observation_receipt_hash, "execution_observation_receipt_hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCHED_OBSERVATION_BINDING_SCHEMA_V0,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "execution_observation_receipt_hash": self.execution_observation_receipt_hash,
        }

    @property
    def binding_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchObservationIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "dispatch observation issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DispatchObservationError("dispatch observation issue severity")
        subject = str(self.subject)
        if not subject:
            raise DispatchObservationError("dispatch observation issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class DispatchedExecutionObservationReceiptV0:
    binding_hash: str
    dispatch_receipt_hash: str
    dispatch_consumption_commit_receipt_hash: str
    dispatch_request_hash: str
    dispatch_epoch_hash: str
    consumption_after_state_hash: str
    consumption_storage_authority_hash: str
    execution_observation_receipt_hash: str
    activation_receipt_hash: str
    realization_receipt_hash: str
    realization_hash: str
    execution_context_hash: str
    observed_history_hash: str
    issues: tuple[DispatchObservationIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "binding_hash",
            "dispatch_receipt_hash",
            "dispatch_consumption_commit_receipt_hash",
            "dispatch_request_hash",
            "dispatch_epoch_hash",
            "consumption_after_state_hash",
            "consumption_storage_authority_hash",
            "execution_observation_receipt_hash",
            "activation_receipt_hash",
            "realization_receipt_hash",
            "realization_hash",
            "execution_context_hash",
            "observed_history_hash",
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
            "schema": DISPATCHED_OBSERVATION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "binding_hash": self.binding_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "dispatch_request_hash": self.dispatch_request_hash,
            "dispatch_epoch_hash": self.dispatch_epoch_hash,
            "consumption_after_state_hash": self.consumption_after_state_hash,
            "consumption_storage_authority_hash": self.consumption_storage_authority_hash,
            "execution_observation_receipt_hash": self.execution_observation_receipt_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "observed_history_hash": self.observed_history_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.dispatched_execution_observation.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> DispatchObservationIssueV0 | None:
    if status == "PASS":
        return None
    return DispatchObservationIssueV0(kind, "REJECT" if status == "REJECT" else "PROOF_REQUIRED", subject, {"status": status})


def evaluate_dispatched_execution_observation(
    binding: DispatchedExecutionObservationBindingV0,
    *,
    dispatch_receipt: ExecutionDispatchReceiptV0,
    dispatch_consumption_commit_receipt: DispatchConsumptionCommitReceiptV0,
    execution_observation_receipt: ExecutionObservationReceiptV0,
) -> DispatchedExecutionObservationReceiptV0:
    issues: list[DispatchObservationIssueV0] = []

    binding_checks = (
        ("dispatch_observation.dispatch_receipt_mismatch", binding.dispatch_receipt_hash, dispatch_receipt.receipt_hash),
        ("dispatch_observation.consumption_commit_receipt_mismatch", binding.dispatch_consumption_commit_receipt_hash, dispatch_consumption_commit_receipt.receipt_hash),
        ("dispatch_observation.observation_receipt_mismatch", binding.execution_observation_receipt_hash, execution_observation_receipt.receipt_hash),
    )
    for kind, expected, observed in binding_checks:
        if expected != observed:
            issues.append(DispatchObservationIssueV0(kind, "REJECT", expected, {"observed": observed}))

    for kind, subject, status in (
        ("dispatch_observation.dispatch_not_admitted", dispatch_receipt.receipt_hash, dispatch_receipt.status),
        ("dispatch_observation.consumption_not_committed", dispatch_consumption_commit_receipt.receipt_hash, dispatch_consumption_commit_receipt.status),
        ("dispatch_observation.observation_not_admitted", execution_observation_receipt.receipt_hash, execution_observation_receipt.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if dispatch_consumption_commit_receipt.dispatch_receipt_hash != dispatch_receipt.receipt_hash:
        issues.append(DispatchObservationIssueV0("dispatch_observation.consumption_dispatch_mismatch", "REJECT", dispatch_consumption_commit_receipt.dispatch_receipt_hash, {"observed": dispatch_receipt.receipt_hash}))
    if dispatch_consumption_commit_receipt.dispatch_request_hash != dispatch_receipt.dispatch_request_hash:
        issues.append(DispatchObservationIssueV0("dispatch_observation.consumption_request_mismatch", "REJECT", dispatch_consumption_commit_receipt.dispatch_request_hash, {"observed": dispatch_receipt.dispatch_request_hash}))
    if dispatch_receipt.activation_receipt_hash != execution_observation_receipt.activation_receipt_hash:
        issues.append(DispatchObservationIssueV0("dispatch_observation.activation_mismatch", "REJECT", dispatch_receipt.activation_receipt_hash, {"observed": execution_observation_receipt.activation_receipt_hash}))
    if dispatch_receipt.execution_context_hash != execution_observation_receipt.execution_context_hash:
        issues.append(DispatchObservationIssueV0("dispatch_observation.execution_context_mismatch", "REJECT", dispatch_receipt.execution_context_hash, {"observed": execution_observation_receipt.execution_context_hash}))

    return DispatchedExecutionObservationReceiptV0(
        binding.binding_hash,
        dispatch_receipt.receipt_hash,
        dispatch_consumption_commit_receipt.receipt_hash,
        dispatch_receipt.dispatch_request_hash,
        dispatch_receipt.dispatch_epoch_hash,
        dispatch_consumption_commit_receipt.after_state_hash,
        dispatch_consumption_commit_receipt.storage_authority_hash,
        execution_observation_receipt.receipt_hash,
        dispatch_receipt.activation_receipt_hash,
        dispatch_receipt.realization_receipt_hash,
        dispatch_receipt.realization_hash,
        dispatch_receipt.execution_context_hash,
        execution_observation_receipt.observed_history_hash,
        tuple(issues),
    )


def residual_from_dispatched_execution_observation(receipt: DispatchedExecutionObservationReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="dispatch_execution_observation",
        judgment_id="dispatch_execution_observation_binding",
        judgment={"kind": "consumed_dispatch_produced_observation", "dispatch_request_hash": receipt.dispatch_request_hash, "status": receipt.status},
        source={"kind": "dispatched_execution_observation_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    receipt.binding_hash,
                    receipt.dispatch_receipt_hash,
                    receipt.dispatch_consumption_commit_receipt_hash,
                    receipt.execution_observation_receipt_hash,
                    receipt.execution_context_hash,
                    receipt.observed_history_hash,
                ),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "DISPATCHED_OBSERVATION_BINDING_SCHEMA_V0",
    "DISPATCHED_OBSERVATION_RECEIPT_SCHEMA_V0",
    "DispatchObservationError",
    "DispatchedExecutionObservationBindingV0",
    "DispatchObservationIssueV0",
    "DispatchedExecutionObservationReceiptV0",
    "evaluate_dispatched_execution_observation",
    "residual_from_dispatched_execution_observation",
]
