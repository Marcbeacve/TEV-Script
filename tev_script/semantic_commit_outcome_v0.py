from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .causal_model_v1 import CommitResultV1, PreparedReactionV1
from .semantic_causal_bridge_v0 import commit_result_field, residual_from_commit_result_v1
from .semantic_delivery_plan_v0 import DeliveryPlanReceiptV0
from .semantic_dispatch_consumption_v0 import DispatchConsumptionCommitReceiptV0
from .semantic_dispatch_v0 import ExecutionDispatchReceiptV0
from .semantic_execution_observation_v0 import ExecutionObservationClaimV0, ExecutionObservationReceiptV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_prepared_execution_v0 import PreparedExecutionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

COMMIT_OUTCOME_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_CAUSAL_COMMIT_OUTCOME_CLAIM_V0"
COMMIT_OUTCOME_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_CAUSAL_COMMIT_OUTCOME_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class CommitOutcomeError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise CommitOutcomeError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise CommitOutcomeError(what)
    return text


@dataclass(frozen=True, slots=True)
class CausalCommitOutcomeClaimV0:
    dispatch_receipt_hash: str
    dispatch_consumption_commit_receipt_hash: str
    delivery_plan_receipt_hash: str
    prepared_execution_receipt_hash: str
    execution_observation_receipt_hash: str
    causal_commit_result_field_hash: str

    def __post_init__(self) -> None:
        for name in (
            "dispatch_receipt_hash",
            "dispatch_consumption_commit_receipt_hash",
            "delivery_plan_receipt_hash",
            "prepared_execution_receipt_hash",
            "execution_observation_receipt_hash",
            "causal_commit_result_field_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COMMIT_OUTCOME_CLAIM_SCHEMA_V0,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "delivery_plan_receipt_hash": self.delivery_plan_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "execution_observation_receipt_hash": self.execution_observation_receipt_hash,
            "causal_commit_result_field_hash": self.causal_commit_result_field_hash,
        }

    @property
    def claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class CommitOutcomeIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "commit outcome issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise CommitOutcomeError("commit outcome issue severity")
        subject = str(self.subject)
        if not subject:
            raise CommitOutcomeError("commit outcome issue subject")
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
class CausalCommitOutcomeReceiptV0:
    outcome_claim_hash: str
    dispatch_receipt_hash: str
    dispatch_consumption_commit_receipt_hash: str
    delivery_plan_receipt_hash: str
    prepared_execution_receipt_hash: str
    execution_observation_receipt_hash: str
    causal_commit_result_field_hash: str
    causal_commit_residual_field_hash: str
    prepared_reaction_hash: str
    commit_status: str
    state_committed: bool
    external_partial: bool
    committed_effects: int
    expected_effects: int
    issues: tuple[CommitOutcomeIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "outcome_claim_hash",
            "dispatch_receipt_hash",
            "dispatch_consumption_commit_receipt_hash",
            "delivery_plan_receipt_hash",
            "prepared_execution_receipt_hash",
            "execution_observation_receipt_hash",
            "causal_commit_result_field_hash",
            "prepared_reaction_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        residual_hash = str(self.causal_commit_residual_field_hash)
        if residual_hash:
            object.__setattr__(self, "causal_commit_residual_field_hash", _hash64(residual_hash, "causal_commit_residual_field_hash"))
        if self.commit_status not in {"COMMITTED", "ABORTED", "EXTERNAL_PARTIAL", "LAW_VIOLATION"}:
            raise CommitOutcomeError("commit_status")
        if not isinstance(self.state_committed, bool) or not isinstance(self.external_partial, bool):
            raise CommitOutcomeError("commit outcome flags")
        for name in ("committed_effects", "expected_effects"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise CommitOutcomeError(name)
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    @property
    def committed(self) -> bool:
        return self.commit_status == "COMMITTED" and self.status == "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": COMMIT_OUTCOME_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "outcome_claim_hash": self.outcome_claim_hash,
            "dispatch_receipt_hash": self.dispatch_receipt_hash,
            "dispatch_consumption_commit_receipt_hash": self.dispatch_consumption_commit_receipt_hash,
            "delivery_plan_receipt_hash": self.delivery_plan_receipt_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "execution_observation_receipt_hash": self.execution_observation_receipt_hash,
            "causal_commit_result_field_hash": self.causal_commit_result_field_hash,
            "causal_commit_residual_field_hash": self.causal_commit_residual_field_hash,
            "prepared_reaction_hash": self.prepared_reaction_hash,
            "commit_status": self.commit_status,
            "state_committed": self.state_committed,
            "external_partial": self.external_partial,
            "committed_effects": self.committed_effects,
            "expected_effects": self.expected_effects,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.causal_commit_outcome_receipt.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> CommitOutcomeIssueV0 | None:
    if status == "PASS":
        return None
    return CommitOutcomeIssueV0(
        kind,
        "REJECT" if status == "REJECT" else "PROOF_REQUIRED",
        subject,
        {"status": status},
    )


def evaluate_causal_commit_outcome(
    claim: CausalCommitOutcomeClaimV0,
    *,
    dispatch_receipt: ExecutionDispatchReceiptV0,
    consumption_commit_receipt: DispatchConsumptionCommitReceiptV0,
    delivery_plan_receipt: DeliveryPlanReceiptV0,
    prepared_execution_receipt: PreparedExecutionReceiptV0,
    prepared_reaction: PreparedReactionV1,
    execution_observation_claim: ExecutionObservationClaimV0,
    execution_observation_receipt: ExecutionObservationReceiptV0,
    commit_result: CommitResultV1,
) -> CausalCommitOutcomeReceiptV0:
    issues: list[CommitOutcomeIssueV0] = []

    result_field = commit_result_field(commit_result)
    residual_hash = ""
    try:
        result_residual = residual_from_commit_result_v1(commit_result)
        residual_hash = result_residual.field_hash
    except ValueError as error:
        issues.append(
            CommitOutcomeIssueV0(
                "commit_outcome.causal_result_invalid",
                "REJECT",
                result_field.field_hash,
                {"error": str(error)},
            )
        )

    bindings = (
        ("commit_outcome.dispatch_receipt_mismatch", claim.dispatch_receipt_hash, dispatch_receipt.receipt_hash),
        ("commit_outcome.consumption_receipt_mismatch", claim.dispatch_consumption_commit_receipt_hash, consumption_commit_receipt.receipt_hash),
        ("commit_outcome.delivery_plan_receipt_mismatch", claim.delivery_plan_receipt_hash, delivery_plan_receipt.receipt_hash),
        ("commit_outcome.prepared_execution_receipt_mismatch", claim.prepared_execution_receipt_hash, prepared_execution_receipt.receipt_hash),
        ("commit_outcome.execution_observation_receipt_mismatch", claim.execution_observation_receipt_hash, execution_observation_receipt.receipt_hash),
        ("commit_outcome.result_field_mismatch", claim.causal_commit_result_field_hash, result_field.field_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(CommitOutcomeIssueV0(kind, "REJECT", expected, {"observed": observed}))

    for kind, subject, status in (
        ("commit_outcome.dispatch_not_admitted", dispatch_receipt.receipt_hash, dispatch_receipt.status),
        ("commit_outcome.consumption_not_committed", consumption_commit_receipt.receipt_hash, consumption_commit_receipt.status),
        ("commit_outcome.delivery_plan_not_admitted", delivery_plan_receipt.receipt_hash, delivery_plan_receipt.status),
        ("commit_outcome.prepared_execution_not_admitted", prepared_execution_receipt.receipt_hash, prepared_execution_receipt.status),
        ("commit_outcome.execution_observation_not_admitted", execution_observation_receipt.receipt_hash, execution_observation_receipt.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    continuity = (
        ("commit_outcome.consumption_dispatch_mismatch", consumption_commit_receipt.dispatch_receipt_hash, dispatch_receipt.receipt_hash),
        ("commit_outcome.consumption_request_mismatch", consumption_commit_receipt.dispatch_request_hash, dispatch_receipt.dispatch_request_hash),
        ("commit_outcome.dispatch_plan_mismatch", dispatch_receipt.delivery_plan_receipt_hash, delivery_plan_receipt.receipt_hash),
        ("commit_outcome.dispatch_prepared_mismatch", dispatch_receipt.prepared_execution_receipt_hash, prepared_execution_receipt.receipt_hash),
        ("commit_outcome.plan_prepared_mismatch", delivery_plan_receipt.prepared_execution_receipt_hash, prepared_execution_receipt.receipt_hash),
        ("commit_outcome.prepared_reaction_mismatch", prepared_execution_receipt.prepared_reaction_hash, prepared_reaction.prepared_reaction_hash),
        ("commit_outcome.result_prepared_reaction_mismatch", commit_result.prepared_reaction_hash, prepared_reaction.prepared_reaction_hash),
        ("commit_outcome.observation_claim_receipt_mismatch", execution_observation_receipt.observation_claim_hash, execution_observation_claim.observation_claim_hash),
        ("commit_outcome.observation_activation_mismatch", execution_observation_receipt.activation_receipt_hash, dispatch_receipt.activation_receipt_hash),
        ("commit_outcome.observation_context_mismatch", execution_observation_receipt.execution_context_hash, dispatch_receipt.execution_context_hash),
        ("commit_outcome.observed_result_field_mismatch", execution_observation_claim.causal_result_field_hash, result_field.field_hash),
    )
    if residual_hash:
        continuity = (*continuity, (
            "commit_outcome.observed_residual_field_mismatch",
            execution_observation_claim.causal_residual_field_hash,
            residual_hash,
        ))
    for kind, observed, expected in continuity:
        if observed != expected:
            issues.append(CommitOutcomeIssueV0(kind, "REJECT", observed, {"expected": expected}))

    expected_effects = len(prepared_reaction.effect_intents)
    if commit_result.committed_effects > expected_effects:
        issues.append(
            CommitOutcomeIssueV0(
                "commit_outcome.committed_effect_count_exceeds_prepared",
                "REJECT",
                str(commit_result.committed_effects),
                {"expected_maximum": expected_effects},
            )
        )
    if commit_result.status == "COMMITTED" and commit_result.committed_effects != expected_effects:
        issues.append(
            CommitOutcomeIssueV0(
                "commit_outcome.committed_effect_count_mismatch",
                "REJECT",
                str(commit_result.committed_effects),
                {"expected": expected_effects},
            )
        )
    if commit_result.status == "ABORTED" and commit_result.committed_effects != 0:
        issues.append(
            CommitOutcomeIssueV0(
                "commit_outcome.aborted_with_committed_effects",
                "REJECT",
                str(commit_result.committed_effects),
                {},
            )
        )

    return CausalCommitOutcomeReceiptV0(
        claim.claim_hash,
        dispatch_receipt.receipt_hash,
        consumption_commit_receipt.receipt_hash,
        delivery_plan_receipt.receipt_hash,
        prepared_execution_receipt.receipt_hash,
        execution_observation_receipt.receipt_hash,
        result_field.field_hash,
        residual_hash,
        prepared_reaction.prepared_reaction_hash,
        str(commit_result.status),
        bool(commit_result.state_committed),
        bool(commit_result.external_partial),
        int(commit_result.committed_effects),
        expected_effects,
        tuple(issues),
    )


def residual_from_causal_commit_outcome(receipt: CausalCommitOutcomeReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="causal_commit_outcome",
        judgment_id="causal_commit_outcome_binding",
        judgment={
            "kind": "observed_causal_commit_outcome_is_authentic",
            "commit_status": receipt.commit_status,
            "status": receipt.status,
        },
        source={"kind": "causal_commit_outcome_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    receipt.outcome_claim_hash,
                    receipt.dispatch_receipt_hash,
                    receipt.dispatch_consumption_commit_receipt_hash,
                    receipt.delivery_plan_receipt_hash,
                    receipt.prepared_execution_receipt_hash,
                    receipt.execution_observation_receipt_hash,
                    receipt.causal_commit_result_field_hash,
                ),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "COMMIT_OUTCOME_CLAIM_SCHEMA_V0",
    "COMMIT_OUTCOME_RECEIPT_SCHEMA_V0",
    "CommitOutcomeError",
    "CausalCommitOutcomeClaimV0",
    "CommitOutcomeIssueV0",
    "CausalCommitOutcomeReceiptV0",
    "evaluate_causal_commit_outcome",
    "residual_from_causal_commit_outcome",
]
