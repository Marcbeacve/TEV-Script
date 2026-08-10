from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .causal_model_v1 import (
    CapabilityLawCatalogV1,
    PreparedReactionV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from .causal_refinement_v1 import verify_prepared_refinement
from .semantic_activation_v0 import ExecutionActivationCandidateV0, ExecutionActivationReceiptV0
from .semantic_execution_authority_v0 import ExecutionAuthorityReceiptV0
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

PREPARED_EXECUTION_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_PREPARED_EXECUTION_CLAIM_V0"
PREPARED_EXECUTION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_PREPARED_EXECUTION_RECEIPT_V0"
CAUSAL_INVOCATION_WORKLOAD_SCHEMA_V0 = "TEV_SCRIPT_CAUSAL_INVOCATION_WORKLOAD_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class PreparedExecutionError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise PreparedExecutionError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise PreparedExecutionError(what)
    return text


def causal_invocation_workload_hash(prepared: PreparedReactionV1) -> str:
    """Identity of the requested causal invocation, excluding mutable world state.

    The prepared reaction remains a stronger state-bound object.  This workload
    identity is deliberately only program + reaction + typed arguments so an
    Activation can be created for the invocation before state-dependent
    preparation completes.
    """

    return canonical_hash(
        {
            "schema": CAUSAL_INVOCATION_WORKLOAD_SCHEMA_V0,
            "program_semantic_hash": prepared.program_semantic_hash,
            "entity_id": prepared.entity_id,
            "trigger_event": prepared.trigger_event,
            "arguments": [dict(item) for item in prepared.arguments],
        }
    )


@dataclass(frozen=True, slots=True)
class PreparedExecutionClaimV0:
    activation_receipt_hash: str
    execution_authority_receipt_hash: str
    prepared_reaction_hash: str
    prepared_refinement_receipt_hash: str

    def __post_init__(self) -> None:
        for name in (
            "activation_receipt_hash",
            "execution_authority_receipt_hash",
            "prepared_reaction_hash",
            "prepared_refinement_receipt_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": PREPARED_EXECUTION_CLAIM_SCHEMA_V0,
            "activation_receipt_hash": self.activation_receipt_hash,
            "execution_authority_receipt_hash": self.execution_authority_receipt_hash,
            "prepared_reaction_hash": self.prepared_reaction_hash,
            "prepared_refinement_receipt_hash": self.prepared_refinement_receipt_hash,
        }

    @property
    def claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.prepared_execution_claim.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class PreparedExecutionIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "prepared execution issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise PreparedExecutionError("prepared execution issue severity")
        subject = str(self.subject)
        if not subject:
            raise PreparedExecutionError("prepared execution issue subject")
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
class PreparedExecutionReceiptV0:
    prepared_execution_claim_hash: str
    activation_receipt_hash: str
    execution_authority_receipt_hash: str
    realization_receipt_hash: str
    realization_hash: str
    execution_context_hash: str
    invocation_workload_hash: str
    prepared_reaction_hash: str
    prepared_refinement_receipt_hash: str
    before_checkpoint_hash: str
    after_checkpoint_hash: str
    program_semantic_hash: str
    reaction_contract_hash: str
    reaction_footprint_hash: str
    law_catalog_hash: str
    issues: tuple[PreparedExecutionIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "prepared_execution_claim_hash",
            "activation_receipt_hash",
            "execution_authority_receipt_hash",
            "realization_receipt_hash",
            "realization_hash",
            "execution_context_hash",
            "invocation_workload_hash",
            "prepared_reaction_hash",
            "prepared_refinement_receipt_hash",
            "before_checkpoint_hash",
            "after_checkpoint_hash",
            "program_semantic_hash",
            "reaction_contract_hash",
            "reaction_footprint_hash",
            "law_catalog_hash",
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
            "schema": PREPARED_EXECUTION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "prepared_execution_claim_hash": self.prepared_execution_claim_hash,
            "activation_receipt_hash": self.activation_receipt_hash,
            "execution_authority_receipt_hash": self.execution_authority_receipt_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "invocation_workload_hash": self.invocation_workload_hash,
            "prepared_reaction_hash": self.prepared_reaction_hash,
            "prepared_refinement_receipt_hash": self.prepared_refinement_receipt_hash,
            "before_checkpoint_hash": self.before_checkpoint_hash,
            "after_checkpoint_hash": self.after_checkpoint_hash,
            "program_semantic_hash": self.program_semantic_hash,
            "reaction_contract_hash": self.reaction_contract_hash,
            "reaction_footprint_hash": self.reaction_footprint_hash,
            "law_catalog_hash": self.law_catalog_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.prepared_execution_receipt.v0", self.to_object())


def _upstream(kind: str, subject: str, status: str) -> PreparedExecutionIssueV0 | None:
    if status == "PASS":
        return None
    return PreparedExecutionIssueV0(
        kind,
        "REJECT" if status == "REJECT" else "PROOF_REQUIRED",
        subject,
        {"status": status},
    )


def evaluate_prepared_execution(
    claim: PreparedExecutionClaimV0,
    *,
    activation_candidate: ExecutionActivationCandidateV0,
    activation_receipt: ExecutionActivationReceiptV0,
    execution_authority_receipt: ExecutionAuthorityReceiptV0,
    prepared_reaction: PreparedReactionV1,
    prepared_refinement_receipt: RefinementReceiptV1,
    reaction_contract: ReactionContractV1,
    reaction_footprint: ReactionFootprintV1,
    law_catalog: CapabilityLawCatalogV1,
) -> PreparedExecutionReceiptV0:
    issues: list[PreparedExecutionIssueV0] = []

    bindings = (
        ("prepared_execution.activation_receipt_mismatch", claim.activation_receipt_hash, activation_receipt.receipt_hash),
        ("prepared_execution.execution_authority_receipt_mismatch", claim.execution_authority_receipt_hash, execution_authority_receipt.receipt_hash),
        ("prepared_execution.prepared_reaction_mismatch", claim.prepared_reaction_hash, prepared_reaction.prepared_reaction_hash),
        ("prepared_execution.prepared_refinement_receipt_mismatch", claim.prepared_refinement_receipt_hash, prepared_refinement_receipt.receipt_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(PreparedExecutionIssueV0(kind, "REJECT", expected, {"observed": observed}))

    for kind, subject, status in (
        ("prepared_execution.activation_not_admitted", activation_receipt.receipt_hash, activation_receipt.status),
        ("prepared_execution.execution_authority_not_admitted", execution_authority_receipt.receipt_hash, execution_authority_receipt.status),
    ):
        issue = _upstream(kind, subject, status)
        if issue is not None:
            issues.append(issue)

    if activation_candidate.activation_candidate_hash != activation_receipt.activation_candidate_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.activation_candidate_mismatch",
                "REJECT",
                activation_candidate.activation_candidate_hash,
                {"receipt": activation_receipt.activation_candidate_hash},
            )
        )
    if activation_candidate.record_hash != activation_receipt.activation_record_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.activation_record_mismatch",
                "REJECT",
                activation_candidate.record_hash,
                {"receipt": activation_receipt.activation_record_hash},
            )
        )

    if execution_authority_receipt.realization_receipt_hash != activation_receipt.realization_receipt_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.realization_receipt_mismatch",
                "REJECT",
                execution_authority_receipt.realization_receipt_hash,
                {"activation": activation_receipt.realization_receipt_hash},
            )
        )
    if execution_authority_receipt.realization_hash != activation_receipt.realization_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.realization_mismatch",
                "REJECT",
                execution_authority_receipt.realization_hash,
                {"activation": activation_receipt.realization_hash},
            )
        )

    causal_bindings = (
        ("prepared_execution.program_mismatch", prepared_reaction.program_semantic_hash, execution_authority_receipt.program_semantic_hash),
        ("prepared_execution.contract_mismatch", prepared_reaction.contract_hash, execution_authority_receipt.reaction_contract_hash),
        ("prepared_execution.footprint_mismatch", prepared_reaction.footprint_hash, execution_authority_receipt.reaction_footprint_hash),
        ("prepared_execution.law_catalog_mismatch", prepared_reaction.law_catalog_hash, execution_authority_receipt.law_catalog_hash),
        ("prepared_execution.contract_object_mismatch", reaction_contract.contract_hash, execution_authority_receipt.reaction_contract_hash),
        ("prepared_execution.footprint_object_mismatch", reaction_footprint.footprint_hash, execution_authority_receipt.reaction_footprint_hash),
        ("prepared_execution.law_catalog_object_mismatch", law_catalog.catalog_hash, execution_authority_receipt.law_catalog_hash),
    )
    for kind, observed, expected in causal_bindings:
        if observed != expected:
            issues.append(PreparedExecutionIssueV0(kind, "REJECT", observed, {"expected": expected}))

    refinement_bindings = (
        ("prepared_execution.refinement_program_mismatch", prepared_refinement_receipt.candidate_program_semantic_hash, prepared_reaction.program_semantic_hash),
        ("prepared_execution.refinement_contract_mismatch", prepared_refinement_receipt.contract_hash, prepared_reaction.contract_hash),
        ("prepared_execution.refinement_footprint_mismatch", prepared_refinement_receipt.footprint_hash, prepared_reaction.footprint_hash),
        ("prepared_execution.refinement_law_catalog_mismatch", prepared_refinement_receipt.law_catalog_hash, prepared_reaction.law_catalog_hash),
    )
    for kind, observed, expected in refinement_bindings:
        if observed != expected:
            issues.append(PreparedExecutionIssueV0(kind, "REJECT", observed, {"expected": expected}))

    if prepared_reaction.refinement_receipt_hash != prepared_refinement_receipt.receipt_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.prepared_refinement_binding_mismatch",
                "REJECT",
                prepared_reaction.refinement_receipt_hash,
                {"observed": prepared_refinement_receipt.receipt_hash},
            )
        )

    recomputed = verify_prepared_refinement(
        reaction_contract,
        reaction_footprint,
        law_catalog,
        prepared_reaction.before_checkpoint,
        prepared_reaction.after_checkpoint,
        prepared_reaction.atomicity,
    )
    if recomputed.receipt_hash != prepared_refinement_receipt.receipt_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.refinement_revalidation_mismatch",
                "REJECT",
                prepared_refinement_receipt.receipt_hash,
                {"recomputed": recomputed.receipt_hash},
            )
        )
    if recomputed.status != "PASS":
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.prepared_refinement_not_admitted",
                "REJECT" if recomputed.status == "REJECT" else "PROOF_REQUIRED",
                recomputed.receipt_hash,
                {"status": recomputed.status},
            )
        )

    workload_hash = causal_invocation_workload_hash(prepared_reaction)
    if activation_candidate.workload_hash != workload_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.workload_mismatch",
                "REJECT",
                activation_candidate.workload_hash,
                {"prepared_invocation": workload_hash},
            )
        )
    if activation_candidate.execution_context_hash != activation_receipt.execution_context_hash:
        issues.append(
            PreparedExecutionIssueV0(
                "prepared_execution.execution_context_mismatch",
                "REJECT",
                activation_candidate.execution_context_hash,
                {"receipt": activation_receipt.execution_context_hash},
            )
        )

    return PreparedExecutionReceiptV0(
        claim.claim_hash,
        activation_receipt.receipt_hash,
        execution_authority_receipt.receipt_hash,
        activation_receipt.realization_receipt_hash,
        activation_receipt.realization_hash,
        activation_receipt.execution_context_hash,
        workload_hash,
        prepared_reaction.prepared_reaction_hash,
        prepared_refinement_receipt.receipt_hash,
        prepared_reaction.before_checkpoint_hash,
        prepared_reaction.after_checkpoint_hash,
        prepared_reaction.program_semantic_hash,
        prepared_reaction.contract_hash,
        prepared_reaction.footprint_hash,
        prepared_reaction.law_catalog_hash,
        tuple(issues),
    )


def residual_from_prepared_execution(receipt: PreparedExecutionReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="prepared_execution",
        judgment_id="prepared_execution_binding",
        judgment={
            "kind": "prepared_causal_invocation_matches_activation_and_authority",
            "prepared_execution_claim_hash": receipt.prepared_execution_claim_hash,
            "status": receipt.status,
        },
        source={"kind": "prepared_execution_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(
                    receipt.prepared_execution_claim_hash,
                    receipt.activation_receipt_hash,
                    receipt.execution_authority_receipt_hash,
                    receipt.prepared_reaction_hash,
                    receipt.prepared_refinement_receipt_hash,
                    receipt.execution_context_hash,
                ),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "PREPARED_EXECUTION_CLAIM_SCHEMA_V0",
    "PREPARED_EXECUTION_RECEIPT_SCHEMA_V0",
    "CAUSAL_INVOCATION_WORKLOAD_SCHEMA_V0",
    "PreparedExecutionError",
    "PreparedExecutionClaimV0",
    "PreparedExecutionIssueV0",
    "PreparedExecutionReceiptV0",
    "causal_invocation_workload_hash",
    "evaluate_prepared_execution",
    "residual_from_prepared_execution",
]
