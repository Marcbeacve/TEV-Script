from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_activation_v0 import ExecutionActivationReceiptV0
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, is_residual_field, residual_from_obstructions

EXECUTION_OBSERVATION_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_OBSERVATION_CLAIM_V0"
EXECUTION_OBSERVATION_RECORD_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_OBSERVATION_RECORD_V0"
EXECUTION_OBSERVATION_POLICY_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_OBSERVATION_POLICY_V0"
EXECUTION_OBSERVATION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_OBSERVATION_RECEIPT_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ExecutionObservationSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ExecutionObservationSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ExecutionObservationSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class ExecutionObservationClaimV0:
    activation_receipt_hash: str
    execution_context_hash: str
    causal_result_field_hash: str
    causal_residual_field_hash: str
    observed_history_hash: str
    trace_hash: str = ""
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "activation_receipt_hash",
            "execution_context_hash",
            "causal_result_field_hash",
            "causal_residual_field_hash",
            "observed_history_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "trace_hash", _optional_hash(self.trace_hash, "trace_hash"))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "execution observation assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_OBSERVATION_CLAIM_SCHEMA_V0,
            "activation_receipt_hash": self.activation_receipt_hash,
            "execution_context_hash": self.execution_context_hash,
            "causal_result_field_hash": self.causal_result_field_hash,
            "causal_residual_field_hash": self.causal_residual_field_hash,
            "observed_history_hash": self.observed_history_hash,
            "trace_hash": self.trace_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def observation_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_observation_claim.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionObservationRecordV0:
    claim: ExecutionObservationClaimV0
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "execution observation evidence hash"))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_OBSERVATION_RECORD_SCHEMA_V0,
            "observation_claim_hash": self.claim.observation_claim_hash,
            "claim": self.claim.to_object(),
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionObservationPolicyV0:
    evidence_policy_hash: str
    accepted_assumption_hashes: tuple[str, ...] = ()
    require_trace: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "execution observation accepted assumption hash"))
        if not isinstance(self.require_trace, bool):
            raise ExecutionObservationSemanticsError("require_trace must be bool")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_OBSERVATION_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
            "require_trace": self.require_trace,
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionObservationIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "execution observation issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ExecutionObservationSemanticsError("execution observation issue severity")
        subject = str(self.subject)
        if not subject:
            raise ExecutionObservationSemanticsError("execution observation issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExecutionObservationReceiptV0:
    observation_claim_hash: str
    observation_record_hash: str
    activation_receipt_hash: str
    execution_context_hash: str
    observed_history_hash: str
    evidence_evaluation_hash: str
    issues: tuple[ExecutionObservationIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "observation_claim_hash",
            "observation_record_hash",
            "activation_receipt_hash",
            "execution_context_hash",
            "observed_history_hash",
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
            "schema": EXECUTION_OBSERVATION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "observation_claim_hash": self.observation_claim_hash,
            "observation_record_hash": self.observation_record_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "execution_context_hash": self.execution_context_hash,
            "observed_history_hash": self.observed_history_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_observation_receipt.v0", self.to_object())


def evaluate_execution_observation(
    record: ExecutionObservationRecordV0,
    *,
    activation_receipt: ExecutionActivationReceiptV0,
    causal_result_field: SemanticFieldV0,
    causal_residual_field: SemanticFieldV0,
    observed_history: SemanticFieldV0,
    policy: ExecutionObservationPolicyV0,
    evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> ExecutionObservationReceiptV0:
    issues: list[ExecutionObservationIssueV0] = []
    claim = record.claim

    if claim.activation_receipt_hash != activation_receipt.receipt_hash:
        issues.append(ExecutionObservationIssueV0("observation.activation_receipt_mismatch", "REJECT", claim.activation_receipt_hash, {"observed": activation_receipt.receipt_hash}))
    if activation_receipt.status != "PASS":
        issues.append(ExecutionObservationIssueV0("observation.activation_not_admitted", "REJECT" if activation_receipt.status == "REJECT" else "PROOF_REQUIRED", activation_receipt.receipt_hash, {"status": activation_receipt.status}))
    if claim.execution_context_hash != activation_receipt.execution_context_hash:
        issues.append(ExecutionObservationIssueV0("observation.execution_context_mismatch", "REJECT", claim.execution_context_hash, {"observed": activation_receipt.execution_context_hash}))
    if claim.causal_result_field_hash != causal_result_field.field_hash:
        issues.append(ExecutionObservationIssueV0("observation.causal_result_mismatch", "REJECT", claim.causal_result_field_hash, {"observed": causal_result_field.field_hash}))
    if claim.causal_residual_field_hash != causal_residual_field.field_hash:
        issues.append(ExecutionObservationIssueV0("observation.causal_residual_mismatch", "REJECT", claim.causal_residual_field_hash, {"observed": causal_residual_field.field_hash}))
    if not is_residual_field(causal_residual_field):
        issues.append(ExecutionObservationIssueV0("observation.causal_residual_not_residual_field", "REJECT", causal_residual_field.field_hash, {}))
    if claim.observed_history_hash != observed_history.field_hash:
        issues.append(ExecutionObservationIssueV0("observation.history_mismatch", "REJECT", claim.observed_history_hash, {"observed": observed_history.field_hash}))
    if policy.require_trace and not claim.trace_hash:
        issues.append(ExecutionObservationIssueV0("observation.trace_required", "PROOF_REQUIRED", claim.observation_claim_hash, {}))
    if record.evidence_policy_hash != evidence_policy.policy_hash or policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(ExecutionObservationIssueV0("observation.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"record": record.evidence_policy_hash, "policy": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(ExecutionObservationIssueV0("observation.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
        issues.append(ExecutionObservationIssueV0("observation.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(ExecutionObservationIssueV0("observation.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evaluation = evaluate_evidence(claim.observation_claim_hash, evidence_policy, evidence_items)
    for item in evaluation.issues:
        issues.append(
            ExecutionObservationIssueV0(
                "observation." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(ExecutionObservationIssueV0("observation.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(ExecutionObservationIssueV0("observation.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return ExecutionObservationReceiptV0(
        claim.observation_claim_hash,
        record.record_hash,
        activation_receipt.receipt_hash,
        activation_receipt.execution_context_hash,
        observed_history.field_hash,
        evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_execution_observation(receipt: ExecutionObservationReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_execution_observation",
        judgment_id="execution_observation_binding",
        judgment={
            "kind": "activated_execution_observed",
            "observation_claim_hash": receipt.observation_claim_hash,
            "status": receipt.status,
        },
        source={"kind": "execution_observation_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.observation_claim_hash, receipt.activation_receipt_hash, receipt.execution_context_hash, receipt.observed_history_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "EXECUTION_OBSERVATION_CLAIM_SCHEMA_V0",
    "EXECUTION_OBSERVATION_RECORD_SCHEMA_V0",
    "EXECUTION_OBSERVATION_POLICY_SCHEMA_V0",
    "EXECUTION_OBSERVATION_RECEIPT_SCHEMA_V0",
    "ExecutionObservationSemanticsError",
    "ExecutionObservationClaimV0",
    "ExecutionObservationRecordV0",
    "ExecutionObservationPolicyV0",
    "ExecutionObservationIssueV0",
    "ExecutionObservationReceiptV0",
    "evaluate_execution_observation",
    "residual_from_execution_observation",
]
