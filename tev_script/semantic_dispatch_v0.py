from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_activation_v0 import ACTIVATION_RECEIPT_SCHEMA_V0, ExecutionActivationReceiptV0
from .semantic_execution_authority_v0 import (
    EXECUTION_AUTHORITY_RECEIPT_SCHEMA_V0,
    ExecutionAuthorityReceiptV0,
)
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_prepared_execution_v0 import (
    PREPARED_EXECUTION_RECEIPT_SCHEMA_V0,
    PreparedExecutionReceiptV0,
)
from .semantic_receipt_validity_v0 import ReceiptValidityEvaluationV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

DISPATCH_CANDIDATE_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_DISPATCH_CANDIDATE_V0"
DISPATCH_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_DISPATCH_RECEIPT_V0"
DISPATCH_CONSUMPTION_DOMAIN_SCHEMA_V0 = "TEV_SCRIPT_DISPATCH_CONSUMPTION_DOMAIN_V0"
ACTIVATION_RECEIPT_CONTRACT_HASH_V0 = canonical_hash(
    {"schema": "TEV_SCRIPT_CONTRACT_IDENTITY_V0", "contract_schema": ACTIVATION_RECEIPT_SCHEMA_V0}
)
AUTHORITY_RECEIPT_CONTRACT_HASH_V0 = canonical_hash(
    {"schema": "TEV_SCRIPT_CONTRACT_IDENTITY_V0", "contract_schema": EXECUTION_AUTHORITY_RECEIPT_SCHEMA_V0}
)
PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0 = canonical_hash(
    {"schema": "TEV_SCRIPT_CONTRACT_IDENTITY_V0", "contract_schema": PREPARED_EXECUTION_RECEIPT_SCHEMA_V0}
)
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DispatchSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DispatchSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DispatchSemanticsError(what)
    return text


def dispatch_consumption_domain_hash(dispatch_request_hash: str) -> str:
    return canonical_hash(
        {
            "schema": DISPATCH_CONSUMPTION_DOMAIN_SCHEMA_V0,
            "dispatch_request_hash": _hash64(dispatch_request_hash, "dispatch_request_hash"),
        }
    )


@dataclass(frozen=True, slots=True)
class ExecutionDispatchCandidateV0:
    dispatch_request_hash: str
    activation_receipt_hash: str
    activation_validity_evaluation_hash: str
    execution_authority_receipt_hash: str
    execution_authority_validity_evaluation_hash: str
    prepared_execution_receipt_hash: str
    prepared_execution_validity_evaluation_hash: str
    dispatch_epoch_hash: str
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "dispatch_request_hash",
            "activation_receipt_hash",
            "activation_validity_evaluation_hash",
            "execution_authority_receipt_hash",
            "execution_authority_validity_evaluation_hash",
            "prepared_execution_receipt_hash",
            "prepared_execution_validity_evaluation_hash",
            "dispatch_epoch_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_EXECUTION_DISPATCH_IDENTITY_V0",
            "dispatch_request_hash": self.dispatch_request_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "activation_validity_evaluation_hash": self.activation_validity_evaluation_hash,
            "execution_authority_receipt_hash": self.execution_authority_receipt_hash,
            "execution_authority_validity_evaluation_hash": self.execution_authority_validity_evaluation_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "prepared_execution_validity_evaluation_hash": self.prepared_execution_validity_evaluation_hash,
            "dispatch_epoch_hash": self.dispatch_epoch_hash,
        }

    @property
    def dispatch_candidate_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_CANDIDATE_SCHEMA_V0,
            "dispatch_candidate_hash": self.dispatch_candidate_hash,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class DispatchIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "dispatch issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DispatchSemanticsError("dispatch issue severity")
        subject = str(self.subject)
        if not subject:
            raise DispatchSemanticsError("dispatch issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExecutionDispatchReceiptV0:
    dispatch_candidate_hash: str
    dispatch_record_hash: str
    dispatch_request_hash: str
    dispatch_epoch_hash: str
    activation_receipt_hash: str
    activation_validity_evaluation_hash: str
    activation_authority_state_hash: str
    execution_authority_receipt_hash: str
    execution_authority_claim_hash: str
    execution_authority_validity_evaluation_hash: str
    execution_authority_state_hash: str
    prepared_execution_receipt_hash: str
    prepared_execution_claim_hash: str
    prepared_execution_validity_evaluation_hash: str
    prepared_execution_authority_state_hash: str
    invocation_workload_hash: str
    before_checkpoint_hash: str
    after_checkpoint_hash: str
    dispatch_consumption_domain_hash: str
    realization_receipt_hash: str
    realization_hash: str
    execution_context_hash: str
    machine_instance_hash: str
    placement_context_hash: str
    runtime_state_claim_hash: str
    issues: tuple[DispatchIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "dispatch_candidate_hash",
            "dispatch_record_hash",
            "dispatch_request_hash",
            "dispatch_epoch_hash",
            "activation_receipt_hash",
            "activation_validity_evaluation_hash",
            "activation_authority_state_hash",
            "execution_authority_receipt_hash",
            "execution_authority_claim_hash",
            "execution_authority_validity_evaluation_hash",
            "execution_authority_state_hash",
            "prepared_execution_receipt_hash",
            "prepared_execution_claim_hash",
            "prepared_execution_validity_evaluation_hash",
            "prepared_execution_authority_state_hash",
            "invocation_workload_hash",
            "before_checkpoint_hash",
            "after_checkpoint_hash",
            "dispatch_consumption_domain_hash",
            "realization_receipt_hash",
            "realization_hash",
            "execution_context_hash",
            "machine_instance_hash",
            "placement_context_hash",
            "runtime_state_claim_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        expected_domain = dispatch_consumption_domain_hash(self.dispatch_request_hash)
        if self.dispatch_consumption_domain_hash != expected_domain:
            raise DispatchSemanticsError("dispatch consumption domain not derived from request identity")
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    @property
    def authority_state_hash(self) -> str:
        states = (
            self.activation_authority_state_hash,
            self.execution_authority_state_hash,
            self.prepared_execution_authority_state_hash,
        )
        if len(set(states)) == 1:
            return states[0]
        return canonical_hash(
            {
                "schema": "TEV_SCRIPT_DISPATCH_COMBINED_AUTHORITY_STATE_V0",
                "activation": self.activation_authority_state_hash,
                "execution_authority": self.execution_authority_state_hash,
                "prepared_execution": self.prepared_execution_authority_state_hash,
            }
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISPATCH_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "dispatch_candidate_hash": self.dispatch_candidate_hash,
            "dispatch_record_hash": self.dispatch_record_hash,
            "dispatch_request_hash": self.dispatch_request_hash,
            "dispatch_epoch_hash": self.dispatch_epoch_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "activation_validity_evaluation_hash": self.activation_validity_evaluation_hash,
            "activation_authority_state_hash": self.activation_authority_state_hash,
            "execution_authority_receipt_hash": self.execution_authority_receipt_hash,
            "execution_authority_claim_hash": self.execution_authority_claim_hash,
            "execution_authority_validity_evaluation_hash": self.execution_authority_validity_evaluation_hash,
            "execution_authority_state_hash": self.execution_authority_state_hash,
            "prepared_execution_receipt_hash": self.prepared_execution_receipt_hash,
            "prepared_execution_claim_hash": self.prepared_execution_claim_hash,
            "prepared_execution_validity_evaluation_hash": self.prepared_execution_validity_evaluation_hash,
            "prepared_execution_authority_state_hash": self.prepared_execution_authority_state_hash,
            "invocation_workload_hash": self.invocation_workload_hash,
            "before_checkpoint_hash": self.before_checkpoint_hash,
            "after_checkpoint_hash": self.after_checkpoint_hash,
            "dispatch_consumption_domain_hash": self.dispatch_consumption_domain_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "machine_instance_hash": self.machine_instance_hash,
            "placement_context_hash": self.placement_context_hash,
            "runtime_state_claim_hash": self.runtime_state_claim_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_dispatch_receipt.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> DispatchIssueV0 | None:
    if status == "PASS":
        return None
    return DispatchIssueV0(kind, "REJECT" if status == "REJECT" else "PROOF_REQUIRED", subject, {"status": status})


def _validate_current_receipt(
    issues: list[DispatchIssueV0],
    *,
    prefix: str,
    subject_receipt_hash: str,
    subject_contract_hash: str,
    candidate_evaluation_hash: str,
    candidate_epoch_hash: str,
    validity: ReceiptValidityEvaluationV0,
) -> None:
    if candidate_evaluation_hash != validity.evaluation_hash:
        issues.append(DispatchIssueV0(f"dispatch.{prefix}_validity_evaluation_mismatch", "REJECT", candidate_evaluation_hash, {"observed": validity.evaluation_hash}))
    if validity.subject_receipt_hash != subject_receipt_hash:
        issues.append(DispatchIssueV0(f"dispatch.{prefix}_validity_subject_mismatch", "REJECT", validity.subject_receipt_hash, {"observed": subject_receipt_hash}))
    if validity.subject_contract_hash != subject_contract_hash:
        issues.append(DispatchIssueV0(f"dispatch.{prefix}_validity_contract_mismatch", "REJECT", validity.subject_contract_hash, {"expected": subject_contract_hash}))
    if validity.validation_epoch_hash != candidate_epoch_hash:
        issues.append(DispatchIssueV0(f"dispatch.{prefix}_validity_epoch_mismatch", "REJECT", validity.validation_epoch_hash, {"dispatch_epoch_hash": candidate_epoch_hash}))


def evaluate_execution_dispatch(
    candidate: ExecutionDispatchCandidateV0,
    *,
    activation_receipt: ExecutionActivationReceiptV0,
    activation_validity: ReceiptValidityEvaluationV0,
    execution_authority_receipt: ExecutionAuthorityReceiptV0,
    execution_authority_validity: ReceiptValidityEvaluationV0,
    prepared_execution_receipt: PreparedExecutionReceiptV0,
    prepared_execution_validity: ReceiptValidityEvaluationV0,
) -> ExecutionDispatchReceiptV0:
    issues: list[DispatchIssueV0] = []

    bindings = (
        ("dispatch.activation_receipt_mismatch", candidate.activation_receipt_hash, activation_receipt.receipt_hash),
        ("dispatch.execution_authority_receipt_mismatch", candidate.execution_authority_receipt_hash, execution_authority_receipt.receipt_hash),
        ("dispatch.prepared_execution_receipt_mismatch", candidate.prepared_execution_receipt_hash, prepared_execution_receipt.receipt_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(DispatchIssueV0(kind, "REJECT", expected, {"observed": observed}))

    _validate_current_receipt(
        issues,
        prefix="activation",
        subject_receipt_hash=activation_receipt.receipt_hash,
        subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
        candidate_evaluation_hash=candidate.activation_validity_evaluation_hash,
        candidate_epoch_hash=candidate.dispatch_epoch_hash,
        validity=activation_validity,
    )
    _validate_current_receipt(
        issues,
        prefix="execution_authority",
        subject_receipt_hash=execution_authority_receipt.receipt_hash,
        subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
        candidate_evaluation_hash=candidate.execution_authority_validity_evaluation_hash,
        candidate_epoch_hash=candidate.dispatch_epoch_hash,
        validity=execution_authority_validity,
    )
    _validate_current_receipt(
        issues,
        prefix="prepared_execution",
        subject_receipt_hash=prepared_execution_receipt.receipt_hash,
        subject_contract_hash=PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0,
        candidate_evaluation_hash=candidate.prepared_execution_validity_evaluation_hash,
        candidate_epoch_hash=candidate.dispatch_epoch_hash,
        validity=prepared_execution_validity,
    )

    for kind, subject, status in (
        ("dispatch.activation_not_admitted", activation_receipt.receipt_hash, activation_receipt.status),
        ("dispatch.activation_not_current", activation_validity.evaluation_hash, activation_validity.status),
        ("dispatch.execution_authority_not_admitted", execution_authority_receipt.receipt_hash, execution_authority_receipt.status),
        ("dispatch.execution_authority_not_current", execution_authority_validity.evaluation_hash, execution_authority_validity.status),
        ("dispatch.prepared_execution_not_admitted", prepared_execution_receipt.receipt_hash, prepared_execution_receipt.status),
        ("dispatch.prepared_execution_not_current", prepared_execution_validity.evaluation_hash, prepared_execution_validity.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if execution_authority_receipt.realization_receipt_hash != activation_receipt.realization_receipt_hash:
        issues.append(DispatchIssueV0("dispatch.execution_authority_realization_receipt_mismatch", "REJECT", execution_authority_receipt.realization_receipt_hash, {"activation": activation_receipt.realization_receipt_hash}))
    if execution_authority_receipt.realization_hash != activation_receipt.realization_hash:
        issues.append(DispatchIssueV0("dispatch.execution_authority_realization_mismatch", "REJECT", execution_authority_receipt.realization_hash, {"activation": activation_receipt.realization_hash}))

    prepared_bindings = (
        ("dispatch.prepared_activation_mismatch", prepared_execution_receipt.activation_receipt_hash, activation_receipt.receipt_hash),
        ("dispatch.prepared_authority_mismatch", prepared_execution_receipt.execution_authority_receipt_hash, execution_authority_receipt.receipt_hash),
        ("dispatch.prepared_realization_receipt_mismatch", prepared_execution_receipt.realization_receipt_hash, activation_receipt.realization_receipt_hash),
        ("dispatch.prepared_realization_mismatch", prepared_execution_receipt.realization_hash, activation_receipt.realization_hash),
        ("dispatch.prepared_execution_context_mismatch", prepared_execution_receipt.execution_context_hash, activation_receipt.execution_context_hash),
    )
    for kind, observed, expected in prepared_bindings:
        if observed != expected:
            issues.append(DispatchIssueV0(kind, "REJECT", observed, {"expected": expected}))

    consumption_domain_hash = dispatch_consumption_domain_hash(candidate.dispatch_request_hash)
    return ExecutionDispatchReceiptV0(
        candidate.dispatch_candidate_hash,
        candidate.record_hash,
        candidate.dispatch_request_hash,
        candidate.dispatch_epoch_hash,
        activation_receipt.receipt_hash,
        activation_validity.evaluation_hash,
        activation_validity.authority_state_hash,
        execution_authority_receipt.receipt_hash,
        execution_authority_receipt.authority_claim_hash,
        execution_authority_validity.evaluation_hash,
        execution_authority_validity.authority_state_hash,
        prepared_execution_receipt.receipt_hash,
        prepared_execution_receipt.prepared_execution_claim_hash,
        prepared_execution_validity.evaluation_hash,
        prepared_execution_validity.authority_state_hash,
        prepared_execution_receipt.invocation_workload_hash,
        prepared_execution_receipt.before_checkpoint_hash,
        prepared_execution_receipt.after_checkpoint_hash,
        consumption_domain_hash,
        activation_receipt.realization_receipt_hash,
        activation_receipt.realization_hash,
        activation_receipt.execution_context_hash,
        activation_receipt.machine_instance_hash,
        activation_receipt.placement_context_hash,
        activation_receipt.runtime_state_claim_hash,
        tuple(issues),
    )


def residual_from_execution_dispatch(receipt: ExecutionDispatchReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_dispatch",
        judgment_id="execution_dispatch",
        judgment={"kind": "prepared_execution_may_dispatch_now", "dispatch_request_hash": receipt.dispatch_request_hash, "status": receipt.status},
        source={"kind": "execution_dispatch_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    receipt.dispatch_candidate_hash,
                    receipt.dispatch_request_hash,
                    receipt.dispatch_consumption_domain_hash,
                    receipt.activation_receipt_hash,
                    receipt.activation_validity_evaluation_hash,
                    receipt.execution_authority_receipt_hash,
                    receipt.execution_authority_claim_hash,
                    receipt.execution_authority_validity_evaluation_hash,
                    receipt.prepared_execution_receipt_hash,
                    receipt.prepared_execution_claim_hash,
                    receipt.prepared_execution_validity_evaluation_hash,
                    receipt.dispatch_epoch_hash,
                ),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "DISPATCH_CANDIDATE_SCHEMA_V0",
    "DISPATCH_RECEIPT_SCHEMA_V0",
    "DISPATCH_CONSUMPTION_DOMAIN_SCHEMA_V0",
    "ACTIVATION_RECEIPT_CONTRACT_HASH_V0",
    "AUTHORITY_RECEIPT_CONTRACT_HASH_V0",
    "PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0",
    "dispatch_consumption_domain_hash",
    "DispatchSemanticsError",
    "ExecutionDispatchCandidateV0",
    "DispatchIssueV0",
    "ExecutionDispatchReceiptV0",
    "evaluate_execution_dispatch",
    "residual_from_execution_dispatch",
]
