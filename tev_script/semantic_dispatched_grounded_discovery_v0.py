from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_dispatch_observation_v0 import DispatchedExecutionObservationReceiptV0
from .semantic_grounded_discovery_v0 import ExecutionGroundedDiscoveryEvaluationV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DISPATCHED_GROUNDED_DISCOVERY_SCHEMA_V0 = "TEV_SCRIPT_DISPATCHED_GROUNDED_DISCOVERY_V0"
DISPATCHED_GROUNDED_DISCOVERY_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_DISPATCHED_GROUNDED_DISCOVERY_EVALUATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DispatchedGroundedDiscoveryError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DispatchedGroundedDiscoveryError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DispatchedGroundedDiscoveryError(what)
    return text


@dataclass(frozen=True, slots=True)
class DispatchedGroundedDiscoveryV0:
    grounded_discovery_evaluation_hash: str
    dispatched_execution_observation_receipt_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "grounded_discovery_evaluation_hash", _hash64(self.grounded_discovery_evaluation_hash, "grounded_discovery_evaluation_hash"))
        object.__setattr__(self, "dispatched_execution_observation_receipt_hash", _hash64(self.dispatched_execution_observation_receipt_hash, "dispatched_execution_observation_receipt_hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCHED_GROUNDED_DISCOVERY_SCHEMA_V0,
            "grounded_discovery_evaluation_hash": self.grounded_discovery_evaluation_hash,
            "dispatched_execution_observation_receipt_hash": self.dispatched_execution_observation_receipt_hash,
        }

    @property
    def cycle_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchedGroundedDiscoveryIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "dispatched grounded discovery issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DispatchedGroundedDiscoveryError("dispatched grounded discovery issue severity")
        subject = str(self.subject)
        if not subject:
            raise DispatchedGroundedDiscoveryError("dispatched grounded discovery issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class DispatchedGroundedDiscoveryEvaluationV0:
    cycle_hash: str
    grounded_discovery_evaluation_hash: str
    dispatched_execution_observation_receipt_hash: str
    dispatch_receipt_hash: str
    dispatch_request_hash: str
    realization_receipt_hash: str
    realization_hash: str
    observed_history_hash: str
    issues: tuple[DispatchedGroundedDiscoveryIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "cycle_hash",
            "grounded_discovery_evaluation_hash",
            "dispatched_execution_observation_receipt_hash",
            "dispatch_receipt_hash",
            "dispatch_request_hash",
            "realization_receipt_hash",
            "realization_hash",
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
            "schema": DISPATCHED_GROUNDED_DISCOVERY_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "cycle_hash": self.cycle_hash,
            "grounded_discovery_evaluation_hash": self.grounded_discovery_evaluation_hash,
            "dispatched_execution_observation_receipt_hash": self.dispatched_execution_observation_receipt_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_request_hash": self.dispatch_request_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "realization_hash": self.realization_hash,
            "observed_history_hash": self.observed_history_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.dispatched_grounded_evaluation.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> DispatchedGroundedDiscoveryIssueV0 | None:
    if status == "PASS":
        return None
    return DispatchedGroundedDiscoveryIssueV0(kind, "REJECT" if status == "REJECT" else "PROOF_REQUIRED", subject, {"status": status})


def evaluate_dispatched_grounded_discovery(
    cycle: DispatchedGroundedDiscoveryV0,
    *,
    grounded_discovery_evaluation: ExecutionGroundedDiscoveryEvaluationV0,
    dispatched_execution_observation_receipt: DispatchedExecutionObservationReceiptV0,
) -> DispatchedGroundedDiscoveryEvaluationV0:
    issues: list[DispatchedGroundedDiscoveryIssueV0] = []

    if cycle.grounded_discovery_evaluation_hash != grounded_discovery_evaluation.evaluation_hash:
        issues.append(DispatchedGroundedDiscoveryIssueV0("dispatched_grounded.grounded_evaluation_mismatch", "REJECT", cycle.grounded_discovery_evaluation_hash, {"observed": grounded_discovery_evaluation.evaluation_hash}))
    if cycle.dispatched_execution_observation_receipt_hash != dispatched_execution_observation_receipt.receipt_hash:
        issues.append(DispatchedGroundedDiscoveryIssueV0("dispatched_grounded.dispatch_observation_mismatch", "REJECT", cycle.dispatched_execution_observation_receipt_hash, {"observed": dispatched_execution_observation_receipt.receipt_hash}))

    for kind, subject, status in (
        ("dispatched_grounded.grounded_discovery_not_admitted", grounded_discovery_evaluation.evaluation_hash, grounded_discovery_evaluation.status),
        ("dispatched_grounded.dispatch_observation_not_admitted", dispatched_execution_observation_receipt.receipt_hash, dispatched_execution_observation_receipt.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if grounded_discovery_evaluation.execution_observation_receipt_hash != dispatched_execution_observation_receipt.execution_observation_receipt_hash:
        issues.append(DispatchedGroundedDiscoveryIssueV0("dispatched_grounded.execution_observation_receipt_mismatch", "REJECT", grounded_discovery_evaluation.execution_observation_receipt_hash, {"observed": dispatched_execution_observation_receipt.execution_observation_receipt_hash}))
    if grounded_discovery_evaluation.realization_receipt_hash != dispatched_execution_observation_receipt.realization_receipt_hash:
        issues.append(DispatchedGroundedDiscoveryIssueV0("dispatched_grounded.realization_receipt_mismatch", "REJECT", grounded_discovery_evaluation.realization_receipt_hash, {"observed": dispatched_execution_observation_receipt.realization_receipt_hash}))
    if grounded_discovery_evaluation.observed_history_hash != dispatched_execution_observation_receipt.observed_history_hash:
        issues.append(DispatchedGroundedDiscoveryIssueV0("dispatched_grounded.history_mismatch", "REJECT", grounded_discovery_evaluation.observed_history_hash, {"observed": dispatched_execution_observation_receipt.observed_history_hash}))

    return DispatchedGroundedDiscoveryEvaluationV0(
        cycle.cycle_hash,
        grounded_discovery_evaluation.evaluation_hash,
        dispatched_execution_observation_receipt.receipt_hash,
        dispatched_execution_observation_receipt.dispatch_receipt_hash,
        dispatched_execution_observation_receipt.dispatch_request_hash,
        dispatched_execution_observation_receipt.realization_receipt_hash,
        dispatched_execution_observation_receipt.realization_hash,
        dispatched_execution_observation_receipt.observed_history_hash,
        tuple(issues),
    )


def residual_from_dispatched_grounded_discovery(evaluation: DispatchedGroundedDiscoveryEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="dispatched_grounded_discovery",
        judgment_id="dispatched_grounded_discovery",
        judgment={"kind": "dispatched_physical_execution_supports_rediscovery", "dispatch_request_hash": evaluation.dispatch_request_hash, "status": evaluation.status},
        source={"kind": "dispatched_grounded_discovery_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(evaluation.cycle_hash, evaluation.grounded_discovery_evaluation_hash, evaluation.dispatched_execution_observation_receipt_hash, evaluation.dispatch_receipt_hash, evaluation.realization_receipt_hash, evaluation.observed_history_hash),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "DISPATCHED_GROUNDED_DISCOVERY_SCHEMA_V0",
    "DISPATCHED_GROUNDED_DISCOVERY_EVALUATION_SCHEMA_V0",
    "DispatchedGroundedDiscoveryError",
    "DispatchedGroundedDiscoveryV0",
    "DispatchedGroundedDiscoveryIssueV0",
    "DispatchedGroundedDiscoveryEvaluationV0",
    "evaluate_dispatched_grounded_discovery",
    "residual_from_dispatched_grounded_discovery",
]
