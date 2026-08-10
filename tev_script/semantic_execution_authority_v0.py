from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .causal_model_v1 import (
    CapabilityLawCatalogV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from .causal_refinement_v1 import verify_structural_refinement
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_regime_v0 import TransformationRegimeBindingV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

TRANSFORMATION_PROGRAM_BINDING_SCHEMA_V0 = "TEV_SCRIPT_TRANSFORMATION_PROGRAM_BINDING_CLAIM_V0"
EXECUTION_AUTHORITY_RECORD_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_AUTHORITY_RECORD_V0"
EXECUTION_AUTHORITY_POLICY_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_AUTHORITY_POLICY_V0"
EXECUTION_AUTHORITY_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_EXECUTION_AUTHORITY_RECEIPT_V0"
_BINDING_RELATIONS = frozenset({"EXACT_EQUIVALENT", "REFINEMENT", "PROJECTION"})
_REALIZATION_RELATIONS = frozenset({"EXACT_EQUIVALENT", "REFINEMENT", "APPROXIMATION", "SIMULATION", "PROJECTION"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ExecutionAuthorityError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ExecutionAuthorityError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ExecutionAuthorityError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class TransformationProgramBindingClaimV0:
    transformation_semantic_hash: str
    program_semantic_hash: str
    relation: str
    scope_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "transformation_semantic_hash", _hash64(self.transformation_semantic_hash, "transformation_semantic_hash"))
        object.__setattr__(self, "program_semantic_hash", _hash64(self.program_semantic_hash, "program_semantic_hash"))
        if self.relation not in _BINDING_RELATIONS:
            raise ExecutionAuthorityError("unsupported transformation/program relation")
        object.__setattr__(self, "scope_hash", _hash64(self.scope_hash, "scope_hash"))
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "authority binding assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": TRANSFORMATION_PROGRAM_BINDING_SCHEMA_V0,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "program_semantic_hash": self.program_semantic_hash,
            "relation": self.relation,
            "scope_hash": self.scope_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def binding_claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionAuthorityRecordV0:
    realization_receipt_hash: str
    binding_claim: TransformationProgramBindingClaimV0
    reaction_contract_hash: str
    reaction_footprint_hash: str
    law_catalog_hash: str
    refinement_receipt_hash: str
    binding_evidence_policy_hash: str
    binding_evidence_hashes: tuple[str, ...] = ()
    provenance_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "realization_receipt_hash",
            "reaction_contract_hash",
            "reaction_footprint_hash",
            "law_catalog_hash",
            "refinement_receipt_hash",
            "binding_evidence_policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "binding_evidence_hashes", _hashes(self.binding_evidence_hashes, "binding evidence hash"))
        object.__setattr__(self, "provenance_hashes", _hashes(self.provenance_hashes, "authority provenance hash"))

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_EXECUTION_AUTHORITY_IDENTITY_V0",
            "realization_receipt_hash": self.realization_receipt_hash,
            "binding_claim_hash": self.binding_claim.binding_claim_hash,
            "reaction_contract_hash": self.reaction_contract_hash,
            "reaction_footprint_hash": self.reaction_footprint_hash,
            "law_catalog_hash": self.law_catalog_hash,
            "refinement_receipt_hash": self.refinement_receipt_hash,
        }

    @property
    def authority_claim_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_AUTHORITY_RECORD_SCHEMA_V0,
            "authority_claim_hash": self.authority_claim_hash,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "binding_claim": self.binding_claim.to_object(),
            "binding_evidence_policy_hash": self.binding_evidence_policy_hash,
            "binding_evidence_hashes": list(self.binding_evidence_hashes),
            "provenance_hashes": list(self.provenance_hashes),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionAuthorityPolicyV0:
    binding_evidence_policy_hash: str
    allowed_relations: tuple[str, ...] = ("EXACT_EQUIVALENT",)
    accepted_assumption_hashes: tuple[str, ...] = ()
    require_complete_law_catalog: bool = True
    allowed_effectful_realization_relations: tuple[str, ...] = ("EXACT_EQUIVALENT", "REFINEMENT")

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_evidence_policy_hash", _hash64(self.binding_evidence_policy_hash, "binding_evidence_policy_hash"))
        relations = tuple(sorted(set(str(item) for item in self.allowed_relations)))
        if not relations or any(item not in _BINDING_RELATIONS for item in relations):
            raise ExecutionAuthorityError("allowed_relations")
        object.__setattr__(self, "allowed_relations", relations)
        effectful_relations = tuple(sorted(set(str(item) for item in self.allowed_effectful_realization_relations)))
        if not effectful_relations or any(item not in _REALIZATION_RELATIONS for item in effectful_relations):
            raise ExecutionAuthorityError("allowed_effectful_realization_relations")
        object.__setattr__(self, "allowed_effectful_realization_relations", effectful_relations)
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "accepted authority assumption hash"))
        if not isinstance(self.require_complete_law_catalog, bool):
            raise ExecutionAuthorityError("require_complete_law_catalog must be bool")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_AUTHORITY_POLICY_SCHEMA_V0,
            "binding_evidence_policy_hash": self.binding_evidence_policy_hash,
            "allowed_relations": list(self.allowed_relations),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
            "require_complete_law_catalog": self.require_complete_law_catalog,
            "allowed_effectful_realization_relations": list(self.allowed_effectful_realization_relations),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutionAuthorityIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "execution authority issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise ExecutionAuthorityError("execution authority issue severity")
        subject = str(self.subject)
        if not subject:
            raise ExecutionAuthorityError("execution authority issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class ExecutionAuthorityReceiptV0:
    authority_claim_hash: str
    authority_record_hash: str
    realization_receipt_hash: str
    realization_hash: str
    transformation_semantic_hash: str
    transformation_regime_binding_hash: str
    semantic_scope_hash: str
    program_semantic_hash: str
    reaction_contract_hash: str
    reaction_footprint_hash: str
    law_catalog_hash: str
    refinement_receipt_hash: str
    binding_evidence_evaluation_hash: str
    policy_hash: str
    issues: tuple[ExecutionAuthorityIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "authority_claim_hash",
            "authority_record_hash",
            "realization_receipt_hash",
            "realization_hash",
            "transformation_semantic_hash",
            "transformation_regime_binding_hash",
            "semantic_scope_hash",
            "program_semantic_hash",
            "reaction_contract_hash",
            "reaction_footprint_hash",
            "law_catalog_hash",
            "refinement_receipt_hash",
            "binding_evidence_evaluation_hash",
            "policy_hash",
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
            "schema": EXECUTION_AUTHORITY_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "authority_claim_hash": self.authority_claim_hash,
            "authority_record_hash": self.authority_record_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "realization_hash": self.realization_hash,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "transformation_regime_binding_hash": self.transformation_regime_binding_hash,
            "semantic_scope_hash": self.semantic_scope_hash,
            "program_semantic_hash": self.program_semantic_hash,
            "reaction_contract_hash": self.reaction_contract_hash,
            "reaction_footprint_hash": self.reaction_footprint_hash,
            "law_catalog_hash": self.law_catalog_hash,
            "refinement_receipt_hash": self.refinement_receipt_hash,
            "binding_evidence_evaluation_hash": self.binding_evidence_evaluation_hash,
            "policy_hash": self.policy_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.execution_authority_receipt.v0", self.to_object())


def evaluate_execution_authority(
    record: ExecutionAuthorityRecordV0,
    *,
    realization_receipt: RealizationAdmissionReceiptV0,
    transformation_regime_binding: TransformationRegimeBindingV0,
    reaction_contract: ReactionContractV1,
    reaction_footprint: ReactionFootprintV1,
    law_catalog: CapabilityLawCatalogV1,
    refinement_receipt: RefinementReceiptV1,
    policy: ExecutionAuthorityPolicyV0,
    binding_evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> ExecutionAuthorityReceiptV0:
    issues: list[ExecutionAuthorityIssueV0] = []
    binding = record.binding_claim

    bindings = (
        ("authority.realization_receipt_mismatch", record.realization_receipt_hash, realization_receipt.receipt_hash),
        ("authority.contract_mismatch", record.reaction_contract_hash, reaction_contract.contract_hash),
        ("authority.footprint_mismatch", record.reaction_footprint_hash, reaction_footprint.footprint_hash),
        ("authority.law_catalog_mismatch", record.law_catalog_hash, law_catalog.catalog_hash),
        ("authority.refinement_receipt_mismatch", record.refinement_receipt_hash, refinement_receipt.receipt_hash),
    )
    for kind, expected, observed in bindings:
        if expected != observed:
            issues.append(ExecutionAuthorityIssueV0(kind, "REJECT", expected, {"observed": observed}))

    if realization_receipt.status != "PASS":
        issues.append(ExecutionAuthorityIssueV0("authority.realization_not_admitted", "REJECT" if realization_receipt.status == "REJECT" else "PROOF_REQUIRED", realization_receipt.receipt_hash, {"status": realization_receipt.status}))

    if realization_receipt.transformation_regime_binding_hash != transformation_regime_binding.binding_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.regime_binding_mismatch", "REJECT", realization_receipt.transformation_regime_binding_hash, {"observed": transformation_regime_binding.binding_hash}))
    if transformation_regime_binding.transformation_semantic_hash != realization_receipt.transformation_semantic_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.regime_binding_transformation_mismatch", "REJECT", transformation_regime_binding.transformation_semantic_hash, {"realization": realization_receipt.transformation_semantic_hash}))
    if binding.transformation_semantic_hash != realization_receipt.transformation_semantic_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.transformation_binding_mismatch", "REJECT", binding.transformation_semantic_hash, {"realization": realization_receipt.transformation_semantic_hash}))
    if binding.transformation_semantic_hash != transformation_regime_binding.transformation_semantic_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.binding_regime_transformation_mismatch", "REJECT", binding.transformation_semantic_hash, {"regime_binding": transformation_regime_binding.transformation_semantic_hash}))
    if binding.scope_hash != transformation_regime_binding.semantic_scope_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.binding_scope_mismatch", "REJECT", binding.scope_hash, {"regime_scope": transformation_regime_binding.semantic_scope_hash}))
    if binding.program_semantic_hash != reaction_footprint.program_semantic_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.program_footprint_mismatch", "REJECT", binding.program_semantic_hash, {"footprint": reaction_footprint.program_semantic_hash}))

    structural_refinement = verify_structural_refinement(reaction_contract, reaction_footprint, law_catalog)
    if structural_refinement.status != "PASS":
        issues.append(
            ExecutionAuthorityIssueV0(
                "authority.structural_refinement_not_admitted",
                "REJECT" if structural_refinement.status == "REJECT" else "PROOF_REQUIRED",
                structural_refinement.receipt_hash,
                {"status": structural_refinement.status},
            )
        )

    refinement_bindings = (
        ("authority.refinement_program_mismatch", refinement_receipt.candidate_program_semantic_hash, binding.program_semantic_hash),
        ("authority.refinement_contract_mismatch", refinement_receipt.contract_hash, reaction_contract.contract_hash),
        ("authority.refinement_footprint_mismatch", refinement_receipt.footprint_hash, reaction_footprint.footprint_hash),
        ("authority.refinement_law_catalog_mismatch", refinement_receipt.law_catalog_hash, law_catalog.catalog_hash),
    )
    for kind, observed, expected in refinement_bindings:
        if observed != expected:
            issues.append(ExecutionAuthorityIssueV0(kind, "REJECT", observed, {"expected": expected}))
    if refinement_receipt.status != "PASS":
        issues.append(ExecutionAuthorityIssueV0("authority.refinement_not_admitted", "REJECT" if refinement_receipt.status == "REJECT" else "PROOF_REQUIRED", refinement_receipt.receipt_hash, {"status": refinement_receipt.status}))

    effectful = bool(
        reaction_footprint.state_writes
        or reaction_footprint.effects
        or reaction_footprint.emitted_events
    )
    if effectful and realization_receipt.semantic_relation not in policy.allowed_effectful_realization_relations:
        issues.append(
            ExecutionAuthorityIssueV0(
                "authority.effectful_realization_relation_not_allowed",
                "REJECT",
                realization_receipt.semantic_relation,
                {"allowed": list(policy.allowed_effectful_realization_relations)},
            )
        )

    if policy.require_complete_law_catalog and not law_catalog.complete:
        issues.append(ExecutionAuthorityIssueV0("authority.law_catalog_incomplete", "PROOF_REQUIRED", law_catalog.catalog_hash, {}))
    if binding.relation not in policy.allowed_relations:
        issues.append(ExecutionAuthorityIssueV0("authority.binding_relation_not_allowed", "REJECT", binding.relation, {"allowed": list(policy.allowed_relations)}))
    if record.binding_evidence_policy_hash != binding_evidence_policy.policy_hash or policy.binding_evidence_policy_hash != binding_evidence_policy.policy_hash:
        issues.append(ExecutionAuthorityIssueV0("authority.binding_evidence_policy_mismatch", "REJECT", binding_evidence_policy.policy_hash, {"record": record.binding_evidence_policy_hash, "policy": policy.binding_evidence_policy_hash}))
    if not binding_evidence_policy.requirements:
        issues.append(ExecutionAuthorityIssueV0("authority.binding_evidence_policy_empty", "REJECT", binding_evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(binding.assumption_hashes) - accepted_assumptions):
        issues.append(ExecutionAuthorityIssueV0("authority.binding_assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.binding_evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(ExecutionAuthorityIssueV0("authority.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    binding_evaluation = evaluate_evidence(binding.binding_claim_hash, binding_evidence_policy, evidence_items)
    for item in binding_evaluation.issues:
        issues.append(ExecutionAuthorityIssueV0("authority." + item.kind, "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED", item.requirement_id, {"evidence_hash": item.evidence_hash, **dict(item.detail)}))
    for accepted_hash in binding_evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.binding_evidence_hashes:
            issues.append(ExecutionAuthorityIssueV0("authority.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(ExecutionAuthorityIssueV0("authority.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return ExecutionAuthorityReceiptV0(
        record.authority_claim_hash,
        record.record_hash,
        realization_receipt.receipt_hash,
        realization_receipt.realization_hash,
        realization_receipt.transformation_semantic_hash,
        transformation_regime_binding.binding_hash,
        transformation_regime_binding.semantic_scope_hash,
        binding.program_semantic_hash,
        reaction_contract.contract_hash,
        reaction_footprint.footprint_hash,
        law_catalog.catalog_hash,
        refinement_receipt.receipt_hash,
        binding_evaluation.evaluation_hash,
        policy.policy_hash,
        tuple(issues),
    )


def residual_from_execution_authority(receipt: ExecutionAuthorityReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_execution_authority",
        judgment_id="execution_least_authority",
        judgment={"kind": "realization_authorized_by_causal_refinement", "authority_claim_hash": receipt.authority_claim_hash, "status": receipt.status},
        source={"kind": "execution_authority_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.authority_claim_hash, receipt.realization_receipt_hash, receipt.transformation_regime_binding_hash, receipt.reaction_contract_hash, receipt.reaction_footprint_hash, receipt.law_catalog_hash, receipt.refinement_receipt_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "TRANSFORMATION_PROGRAM_BINDING_SCHEMA_V0",
    "EXECUTION_AUTHORITY_RECORD_SCHEMA_V0",
    "EXECUTION_AUTHORITY_POLICY_SCHEMA_V0",
    "EXECUTION_AUTHORITY_RECEIPT_SCHEMA_V0",
    "ExecutionAuthorityError",
    "TransformationProgramBindingClaimV0",
    "ExecutionAuthorityRecordV0",
    "ExecutionAuthorityPolicyV0",
    "ExecutionAuthorityIssueV0",
    "ExecutionAuthorityReceiptV0",
    "evaluate_execution_authority",
    "residual_from_execution_authority",
]
