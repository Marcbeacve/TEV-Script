from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_activation_v0 import ExecutionActivationReceiptV0
from .semantic_discovery_realization_v0 import (
    CycleEvaluationV0,
    DiscoveryClaimV0,
    DiscoveryRealizationCycleV0,
    LawEquivalenceClaimV0,
    StructuralLawClaimV0,
    evaluate_discovery_realization_cycle,
)
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0
from .semantic_execution_observation_v0 import ExecutionObservationReceiptV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

GROUNDED_DISCOVERY_CYCLE_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_GROUNDED_DISCOVERY_CYCLE_V0"
GROUNDED_DISCOVERY_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_GROUNDED_DISCOVERY_EVALUATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class GroundedDiscoveryError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise GroundedDiscoveryError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise GroundedDiscoveryError(what)
    return text


@dataclass(frozen=True, slots=True)
class ExecutionGroundedDiscoveryCycleV0:
    epistemic_cycle_hash: str
    activation_receipt_hash: str
    execution_observation_receipt_hash: str

    def __post_init__(self) -> None:
        for name in (
            "epistemic_cycle_hash",
            "activation_receipt_hash",
            "execution_observation_receipt_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": GROUNDED_DISCOVERY_CYCLE_SCHEMA_V0,
            "epistemic_cycle_hash": self.epistemic_cycle_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "execution_observation_receipt_hash": self.execution_observation_receipt_hash,
        }

    @property
    def grounded_cycle_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.execution_grounded_cycle.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class GroundedDiscoveryIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "grounded discovery issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise GroundedDiscoveryError("grounded discovery issue severity")
        subject = str(self.subject)
        if not subject:
            raise GroundedDiscoveryError("grounded discovery issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "subject": self.subject,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class ExecutionGroundedDiscoveryEvaluationV0:
    grounded_cycle_hash: str
    epistemic_evaluation_hash: str
    activation_receipt_hash: str
    execution_observation_receipt_hash: str
    realization_receipt_hash: str
    observed_history_hash: str
    issues: tuple[GroundedDiscoveryIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "grounded_cycle_hash",
            "epistemic_evaluation_hash",
            "activation_receipt_hash",
            "execution_observation_receipt_hash",
            "realization_receipt_hash",
            "observed_history_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(
            self,
            "issues",
            tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))),
        )

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": GROUNDED_DISCOVERY_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "grounded_cycle_hash": self.grounded_cycle_hash,
            "epistemic_evaluation_hash": self.epistemic_evaluation_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "execution_observation_receipt_hash": self.execution_observation_receipt_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "observed_history_hash": self.observed_history_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.execution_grounded_evaluation.v0", self.to_object())


def _upstream_issue(kind: str, subject: str, status: str) -> GroundedDiscoveryIssueV0 | None:
    if status == "PASS":
        return None
    return GroundedDiscoveryIssueV0(
        kind,
        "REJECT" if status == "REJECT" else "PROOF_REQUIRED",
        subject,
        {"status": status},
    )


def _copy_epistemic_issues(evaluation: CycleEvaluationV0) -> tuple[GroundedDiscoveryIssueV0, ...]:
    return tuple(
        GroundedDiscoveryIssueV0(
            "grounded." + item.kind,
            item.severity,
            item.subject,
            dict(item.detail),
        )
        for item in evaluation.issues
    )


def evaluate_execution_grounded_discovery_cycle(
    grounded_cycle: ExecutionGroundedDiscoveryCycleV0,
    *,
    epistemic_cycle: DiscoveryRealizationCycleV0,
    source_law: StructuralLawClaimV0,
    realization_receipt: RealizationAdmissionReceiptV0,
    activation_receipt: ExecutionActivationReceiptV0,
    execution_observation_receipt: ExecutionObservationReceiptV0,
    rediscovered_law: StructuralLawClaimV0,
    rediscovery_claim: DiscoveryClaimV0,
    discovery_evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
    law_equivalence_claim: LawEquivalenceClaimV0 | None = None,
    equivalence_evidence_policy: EvidencePolicyV0 | None = None,
) -> ExecutionGroundedDiscoveryEvaluationV0:
    issues: list[GroundedDiscoveryIssueV0] = []

    if grounded_cycle.epistemic_cycle_hash != epistemic_cycle.cycle_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.epistemic_cycle_mismatch",
                "REJECT",
                grounded_cycle.epistemic_cycle_hash,
                {"observed": epistemic_cycle.cycle_hash},
            )
        )
    if grounded_cycle.activation_receipt_hash != activation_receipt.receipt_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.activation_receipt_mismatch",
                "REJECT",
                grounded_cycle.activation_receipt_hash,
                {"observed": activation_receipt.receipt_hash},
            )
        )
    if grounded_cycle.execution_observation_receipt_hash != execution_observation_receipt.receipt_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.execution_observation_receipt_mismatch",
                "REJECT",
                grounded_cycle.execution_observation_receipt_hash,
                {"observed": execution_observation_receipt.receipt_hash},
            )
        )

    for kind, subject, status in (
        ("grounded.realization_not_admitted", realization_receipt.receipt_hash, realization_receipt.status),
        ("grounded.activation_not_admitted", activation_receipt.receipt_hash, activation_receipt.status),
        (
            "grounded.execution_observation_not_admitted",
            execution_observation_receipt.receipt_hash,
            execution_observation_receipt.status,
        ),
    ):
        issue = _upstream_issue(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if activation_receipt.realization_receipt_hash != realization_receipt.receipt_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.activation_realization_receipt_mismatch",
                "REJECT",
                activation_receipt.realization_receipt_hash,
                {"observed": realization_receipt.receipt_hash},
            )
        )
    if activation_receipt.realization_hash != realization_receipt.realization_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.activation_realization_identity_mismatch",
                "REJECT",
                activation_receipt.realization_hash,
                {"observed": realization_receipt.realization_hash},
            )
        )
    if execution_observation_receipt.activation_receipt_hash != activation_receipt.receipt_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.observation_activation_mismatch",
                "REJECT",
                execution_observation_receipt.activation_receipt_hash,
                {"observed": activation_receipt.receipt_hash},
            )
        )
    if execution_observation_receipt.execution_context_hash != activation_receipt.execution_context_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.observation_execution_context_mismatch",
                "REJECT",
                execution_observation_receipt.execution_context_hash,
                {"observed": activation_receipt.execution_context_hash},
            )
        )
    if epistemic_cycle.realization_admission_receipt_hash != realization_receipt.receipt_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.epistemic_realization_receipt_mismatch",
                "REJECT",
                epistemic_cycle.realization_admission_receipt_hash,
                {"observed": realization_receipt.receipt_hash},
            )
        )
    if epistemic_cycle.observed_history_hash != execution_observation_receipt.observed_history_hash:
        issues.append(
            GroundedDiscoveryIssueV0(
                "grounded.observed_history_mismatch",
                "REJECT",
                epistemic_cycle.observed_history_hash,
                {"observed": execution_observation_receipt.observed_history_hash},
            )
        )

    epistemic_evaluation = evaluate_discovery_realization_cycle(
        epistemic_cycle,
        source_law=source_law,
        realization_receipt=realization_receipt,
        rediscovered_law=rediscovered_law,
        rediscovery_claim=rediscovery_claim,
        discovery_evidence_policy=discovery_evidence_policy,
        evidence=tuple(evidence),
        law_equivalence_claim=law_equivalence_claim,
        equivalence_evidence_policy=equivalence_evidence_policy,
    )
    issues.extend(_copy_epistemic_issues(epistemic_evaluation))

    return ExecutionGroundedDiscoveryEvaluationV0(
        grounded_cycle.grounded_cycle_hash,
        epistemic_evaluation.evaluation_hash,
        activation_receipt.receipt_hash,
        execution_observation_receipt.receipt_hash,
        realization_receipt.receipt_hash,
        execution_observation_receipt.observed_history_hash,
        tuple(issues),
    )


def residual_from_execution_grounded_discovery(
    evaluation: ExecutionGroundedDiscoveryEvaluationV0,
) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="execution_grounded_discovery",
        judgment_id="execution_grounded_discovery_cycle",
        judgment={
            "kind": "physical_execution_supports_rediscovery",
            "grounded_cycle_hash": evaluation.grounded_cycle_hash,
            "status": evaluation.status,
        },
        source={
            "kind": "execution_grounded_discovery_evaluation",
            "evaluation_hash": evaluation.evaluation_hash,
        },
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    evaluation.grounded_cycle_hash,
                    evaluation.epistemic_evaluation_hash,
                    evaluation.activation_receipt_hash,
                    evaluation.execution_observation_receipt_hash,
                    evaluation.realization_receipt_hash,
                    evaluation.observed_history_hash,
                ),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "GROUNDED_DISCOVERY_CYCLE_SCHEMA_V0",
    "GROUNDED_DISCOVERY_EVALUATION_SCHEMA_V0",
    "GroundedDiscoveryError",
    "ExecutionGroundedDiscoveryCycleV0",
    "GroundedDiscoveryIssueV0",
    "ExecutionGroundedDiscoveryEvaluationV0",
    "evaluate_execution_grounded_discovery_cycle",
    "residual_from_execution_grounded_discovery",
]
