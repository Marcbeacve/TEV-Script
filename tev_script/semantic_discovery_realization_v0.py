from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import (
    EvidenceEvaluationV0,
    EvidenceItemV0,
    EvidencePolicyV0,
    evaluate_evidence,
)
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

LAW_SCHEMA_V0 = "TEV_SCRIPT_STRUCTURAL_LAW_CLAIM_V0"
LAW_EQUIVALENCE_SCHEMA_V0 = "TEV_SCRIPT_LAW_EQUIVALENCE_CLAIM_V0"
DISCOVERY_SCHEMA_V0 = "TEV_SCRIPT_DISCOVERY_CLAIM_V0"
MODEL_COMPATIBILITY_SCHEMA_V0 = "TEV_SCRIPT_MODEL_COMPATIBILITY_CLAIM_V0"
DISCOVERY_REALIZATION_CYCLE_SCHEMA_V0 = "TEV_SCRIPT_DISCOVERY_REALIZATION_CYCLE_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class DiscoveryRealizationError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise DiscoveryRealizationError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise DiscoveryRealizationError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class StructuralLawClaimV0:
    law_id: str
    regime_hash: str
    transformation_semantic_hash: str
    validity_boundary_hash: str
    falsifier_profile_hash: str
    evidence_policy_hash: str
    assumption_hashes: tuple[str, ...] = ()
    formulation_hash: str = ""
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "law_id", _stable(self.law_id, "law_id"))
        object.__setattr__(self, "regime_hash", _hash64(self.regime_hash, "regime_hash"))
        object.__setattr__(
            self,
            "transformation_semantic_hash",
            _hash64(self.transformation_semantic_hash, "transformation_semantic_hash"),
        )
        object.__setattr__(
            self,
            "validity_boundary_hash",
            _hash64(self.validity_boundary_hash, "validity_boundary_hash"),
        )
        object.__setattr__(
            self,
            "falsifier_profile_hash",
            _hash64(self.falsifier_profile_hash, "falsifier_profile_hash"),
        )
        object.__setattr__(
            self,
            "evidence_policy_hash",
            _hash64(self.evidence_policy_hash, "evidence_policy_hash"),
        )
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "law assumption hash"),
        )
        object.__setattr__(
            self,
            "formulation_hash",
            _optional_hash(self.formulation_hash, "formulation_hash"),
        )
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_STRUCTURAL_LAW_SEMANTIC_IDENTITY_V0",
            "regime_hash": self.regime_hash,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "validity_boundary_hash": self.validity_boundary_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def law_semantic_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": LAW_SCHEMA_V0,
            "law_id": self.law_id,
            "law_semantic_hash": self.law_semantic_hash,
            "regime_hash": self.regime_hash,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "validity_boundary_hash": self.validity_boundary_hash,
            "falsifier_profile_hash": self.falsifier_profile_hash,
            "evidence_policy_hash": self.evidence_policy_hash,
            "assumption_hashes": list(self.assumption_hashes),
            "formulation_hash": self.formulation_hash,
            "provenance": dict(self.provenance or {}),
        }

    @property
    def law_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.law_claim.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class LawEquivalenceClaimV0:
    left_law_semantic_hash: str
    right_law_semantic_hash: str
    equivalence_relation_hash: str
    semantic_scope_hash: str
    evidence_policy_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        left = _hash64(self.left_law_semantic_hash, "left_law_semantic_hash")
        right = _hash64(self.right_law_semantic_hash, "right_law_semantic_hash")
        if left == right:
            raise DiscoveryRealizationError(
                "LawEquivalenceClaimV0 is for distinct concrete semantic identities"
            )
        ordered = tuple(sorted((left, right)))
        object.__setattr__(self, "left_law_semantic_hash", ordered[0])
        object.__setattr__(self, "right_law_semantic_hash", ordered[1])
        object.__setattr__(
            self,
            "equivalence_relation_hash",
            _hash64(self.equivalence_relation_hash, "equivalence_relation_hash"),
        )
        object.__setattr__(
            self,
            "semantic_scope_hash",
            _hash64(self.semantic_scope_hash, "semantic_scope_hash"),
        )
        object.__setattr__(
            self,
            "evidence_policy_hash",
            _hash64(self.evidence_policy_hash, "evidence_policy_hash"),
        )
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "equivalence assumption hash"),
        )

    @property
    def law_pair(self) -> tuple[str, str]:
        return (self.left_law_semantic_hash, self.right_law_semantic_hash)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": LAW_EQUIVALENCE_SCHEMA_V0,
            "left_law_semantic_hash": self.left_law_semantic_hash,
            "right_law_semantic_hash": self.right_law_semantic_hash,
            "equivalence_relation_hash": self.equivalence_relation_hash,
            "semantic_scope_hash": self.semantic_scope_hash,
            "evidence_policy_hash": self.evidence_policy_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def equivalence_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.law_equivalence.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class DiscoveryClaimV0:
    experience_space_hash: str
    observation_set_hash: str
    intervention_set_hash: str
    candidate_law_semantic_hash: str
    discovery_context_hash: str
    validity_boundary_hash: str
    evidence_policy_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "experience_space_hash",
            "observation_set_hash",
            "intervention_set_hash",
            "candidate_law_semantic_hash",
            "discovery_context_hash",
            "validity_boundary_hash",
            "evidence_policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "discovery assumption hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISCOVERY_SCHEMA_V0,
            "experience_space_hash": self.experience_space_hash,
            "observation_set_hash": self.observation_set_hash,
            "intervention_set_hash": self.intervention_set_hash,
            "candidate_law_semantic_hash": self.candidate_law_semantic_hash,
            "discovery_context_hash": self.discovery_context_hash,
            "validity_boundary_hash": self.validity_boundary_hash,
            "evidence_policy_hash": self.evidence_policy_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def discovery_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.claim.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ModelCompatibilityClaimV0:
    law_semantic_hash: str
    model_hash: str
    regime_hash: str
    validity_boundary_hash: str
    compatibility_relation_hash: str
    evidence_policy_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "law_semantic_hash",
            "model_hash",
            "regime_hash",
            "validity_boundary_hash",
            "compatibility_relation_hash",
            "evidence_policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "model compatibility assumption hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": MODEL_COMPATIBILITY_SCHEMA_V0,
            "law_semantic_hash": self.law_semantic_hash,
            "model_hash": self.model_hash,
            "regime_hash": self.regime_hash,
            "validity_boundary_hash": self.validity_boundary_hash,
            "compatibility_relation_hash": self.compatibility_relation_hash,
            "evidence_policy_hash": self.evidence_policy_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def compatibility_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.model_compatibility.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class DiscoveryRealizationCycleV0:
    source_law_semantic_hash: str
    realization_admission_receipt_hash: str
    observed_history_hash: str
    rediscovery_claim_hash: str
    rediscovered_law_semantic_hash: str
    law_equivalence_claim_hash: str = ""

    def __post_init__(self) -> None:
        for name in (
            "source_law_semantic_hash",
            "realization_admission_receipt_hash",
            "observed_history_hash",
            "rediscovery_claim_hash",
            "rediscovered_law_semantic_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(
            self,
            "law_equivalence_claim_hash",
            _optional_hash(self.law_equivalence_claim_hash, "law_equivalence_claim_hash"),
        )
        same = self.source_law_semantic_hash == self.rediscovered_law_semantic_hash
        if same and self.law_equivalence_claim_hash:
            raise DiscoveryRealizationError(
                "identical law semantic hashes must not require an equivalence claim"
            )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": DISCOVERY_REALIZATION_CYCLE_SCHEMA_V0,
            "source_law_semantic_hash": self.source_law_semantic_hash,
            "realization_admission_receipt_hash": self.realization_admission_receipt_hash,
            "observed_history_hash": self.observed_history_hash,
            "rediscovery_claim_hash": self.rediscovery_claim_hash,
            "rediscovered_law_semantic_hash": self.rediscovered_law_semantic_hash,
            "law_equivalence_claim_hash": self.law_equivalence_claim_hash,
        }

    @property
    def cycle_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.discovery.realization_cycle.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class CycleIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "cycle issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise DiscoveryRealizationError("cycle issue severity")
        subject = str(self.subject)
        if not subject:
            raise DiscoveryRealizationError("cycle issue subject")
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
class CycleEvaluationV0:
    cycle_hash: str
    source_law_semantic_hash: str
    realization_receipt_hash: str
    discovery_evidence_evaluation_hash: str
    equivalence_evidence_evaluation_hash: str
    issues: tuple[CycleIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "cycle_hash",
            "source_law_semantic_hash",
            "realization_receipt_hash",
            "discovery_evidence_evaluation_hash",
            "equivalence_evidence_evaluation_hash",
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
        if self.issues:
            return "PROOF_REQUIRED"
        return "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_DISCOVERY_REALIZATION_CYCLE_EVALUATION_V0",
            "status": self.status,
            "cycle_hash": self.cycle_hash,
            "source_law_semantic_hash": self.source_law_semantic_hash,
            "realization_receipt_hash": self.realization_receipt_hash,
            "discovery_evidence_evaluation_hash": self.discovery_evidence_evaluation_hash,
            "equivalence_evidence_evaluation_hash": self.equivalence_evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def _empty_evaluation(claim_hash: str) -> EvidenceEvaluationV0:
    policy = EvidencePolicyV0(())
    return evaluate_evidence(claim_hash, policy, ())


def _issues_from_evidence(
    evaluation: EvidenceEvaluationV0,
    *,
    prefix: str,
) -> tuple[CycleIssueV0, ...]:
    issues: list[CycleIssueV0] = []
    for item in evaluation.issues:
        severity = "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED"
        issues.append(
            CycleIssueV0(
                prefix + "." + item.kind,
                severity,
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    return tuple(issues)


def evaluate_discovery_realization_cycle(
    cycle: DiscoveryRealizationCycleV0,
    *,
    source_law: StructuralLawClaimV0,
    realization_receipt: RealizationAdmissionReceiptV0,
    rediscovery_claim: DiscoveryClaimV0,
    discovery_evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
    law_equivalence_claim: LawEquivalenceClaimV0 | None = None,
    equivalence_evidence_policy: EvidencePolicyV0 | None = None,
) -> CycleEvaluationV0:
    issues: list[CycleIssueV0] = []
    evidence_items = tuple(evidence)

    if cycle.source_law_semantic_hash != source_law.law_semantic_hash:
        issues.append(
            CycleIssueV0(
                "cycle.source_law_mismatch",
                "REJECT",
                cycle.source_law_semantic_hash,
                {"observed": source_law.law_semantic_hash},
            )
        )
    if cycle.realization_admission_receipt_hash != realization_receipt.receipt_hash:
        issues.append(
            CycleIssueV0(
                "cycle.realization_receipt_mismatch",
                "REJECT",
                cycle.realization_admission_receipt_hash,
                {"observed": realization_receipt.receipt_hash},
            )
        )
    if realization_receipt.status != "PASS":
        issues.append(
            CycleIssueV0(
                "cycle.realization_not_admitted",
                "REJECT",
                realization_receipt.receipt_hash,
                {"status": realization_receipt.status},
            )
        )
    if source_law.transformation_semantic_hash != realization_receipt.transformation_semantic_hash:
        issues.append(
            CycleIssueV0(
                "cycle.realization_transformation_mismatch",
                "REJECT",
                source_law.transformation_semantic_hash,
                {"observed": realization_receipt.transformation_semantic_hash},
            )
        )
    if source_law.regime_hash != realization_receipt.regime_hash:
        issues.append(
            CycleIssueV0(
                "cycle.realization_regime_mismatch",
                "REJECT",
                source_law.regime_hash,
                {"observed": realization_receipt.regime_hash},
            )
        )

    if cycle.rediscovery_claim_hash != rediscovery_claim.discovery_claim_hash:
        issues.append(
            CycleIssueV0(
                "cycle.rediscovery_claim_mismatch",
                "REJECT",
                cycle.rediscovery_claim_hash,
                {"observed": rediscovery_claim.discovery_claim_hash},
            )
        )
    if cycle.rediscovered_law_semantic_hash != rediscovery_claim.candidate_law_semantic_hash:
        issues.append(
            CycleIssueV0(
                "cycle.rediscovered_law_mismatch",
                "REJECT",
                cycle.rediscovered_law_semantic_hash,
                {"observed": rediscovery_claim.candidate_law_semantic_hash},
            )
        )
    if rediscovery_claim.evidence_policy_hash != discovery_evidence_policy.policy_hash:
        issues.append(
            CycleIssueV0(
                "cycle.discovery_evidence_policy_mismatch",
                "REJECT",
                discovery_evidence_policy.policy_hash,
                {"expected": rediscovery_claim.evidence_policy_hash},
            )
        )

    discovery_evaluation = evaluate_evidence(
        rediscovery_claim.discovery_claim_hash,
        discovery_evidence_policy,
        evidence_items,
    )
    issues.extend(_issues_from_evidence(discovery_evaluation, prefix="discovery"))

    same_law = cycle.source_law_semantic_hash == cycle.rediscovered_law_semantic_hash
    if same_law:
        equivalence_evaluation = _empty_evaluation(cycle.cycle_hash)
        if law_equivalence_claim is not None or equivalence_evidence_policy is not None:
            issues.append(
                CycleIssueV0(
                    "cycle.redundant_equivalence_claim",
                    "REJECT",
                    cycle.source_law_semantic_hash,
                    {},
                )
            )
    else:
        if not cycle.law_equivalence_claim_hash:
            equivalence_evaluation = _empty_evaluation(cycle.cycle_hash)
            issues.append(
                CycleIssueV0(
                    "cycle.law_equivalence_required",
                    "PROOF_REQUIRED",
                    cycle.source_law_semantic_hash,
                    {"rediscovered_law_semantic_hash": cycle.rediscovered_law_semantic_hash},
                )
            )
        elif law_equivalence_claim is None or equivalence_evidence_policy is None:
            equivalence_evaluation = _empty_evaluation(cycle.law_equivalence_claim_hash)
            issues.append(
                CycleIssueV0(
                    "cycle.law_equivalence_evidence_required",
                    "PROOF_REQUIRED",
                    cycle.law_equivalence_claim_hash,
                    {},
                )
            )
        else:
            if cycle.law_equivalence_claim_hash != law_equivalence_claim.equivalence_claim_hash:
                issues.append(
                    CycleIssueV0(
                        "cycle.law_equivalence_claim_mismatch",
                        "REJECT",
                        cycle.law_equivalence_claim_hash,
                        {"observed": law_equivalence_claim.equivalence_claim_hash},
                    )
                )
            expected_pair = tuple(
                sorted(
                    (
                        cycle.source_law_semantic_hash,
                        cycle.rediscovered_law_semantic_hash,
                    )
                )
            )
            if law_equivalence_claim.law_pair != expected_pair:
                issues.append(
                    CycleIssueV0(
                        "cycle.law_equivalence_pair_mismatch",
                        "REJECT",
                        law_equivalence_claim.equivalence_claim_hash,
                        {
                            "expected_pair": list(expected_pair),
                            "observed_pair": list(law_equivalence_claim.law_pair),
                        },
                    )
                )
            if law_equivalence_claim.evidence_policy_hash != equivalence_evidence_policy.policy_hash:
                issues.append(
                    CycleIssueV0(
                        "cycle.equivalence_evidence_policy_mismatch",
                        "REJECT",
                        equivalence_evidence_policy.policy_hash,
                        {"expected": law_equivalence_claim.evidence_policy_hash},
                    )
                )
            equivalence_evaluation = evaluate_evidence(
                law_equivalence_claim.equivalence_claim_hash,
                equivalence_evidence_policy,
                evidence_items,
            )
            issues.extend(_issues_from_evidence(equivalence_evaluation, prefix="equivalence"))

    return CycleEvaluationV0(
        cycle.cycle_hash,
        source_law.law_semantic_hash,
        realization_receipt.receipt_hash,
        discovery_evaluation.evaluation_hash,
        equivalence_evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_discovery_realization_cycle(
    evaluation: CycleEvaluationV0,
) -> SemanticFieldV0:
    obstructions = tuple(
        ResidualObstructionV0(
            item.kind,
            item.subject,
            "resolved",
            item.severity,
            dict(item.detail),
            dependency_refs=(
                evaluation.cycle_hash,
                evaluation.source_law_semantic_hash,
                evaluation.realization_receipt_hash,
            ),
        )
        for item in evaluation.issues
    )
    return residual_from_obstructions(
        domain="discovery_realization",
        judgment_id="round_trip_consistency",
        judgment={
            "kind": "discovery_realization_round_trip",
            "cycle_hash": evaluation.cycle_hash,
            "status": evaluation.status,
        },
        source={
            "kind": "discovery_realization_cycle_evaluation",
            "evaluation_hash": evaluation.evaluation_hash,
        },
        obstructions=obstructions,
    )


__all__ = [
    "LAW_SCHEMA_V0",
    "LAW_EQUIVALENCE_SCHEMA_V0",
    "DISCOVERY_SCHEMA_V0",
    "MODEL_COMPATIBILITY_SCHEMA_V0",
    "DISCOVERY_REALIZATION_CYCLE_SCHEMA_V0",
    "DiscoveryRealizationError",
    "StructuralLawClaimV0",
    "LawEquivalenceClaimV0",
    "DiscoveryClaimV0",
    "ModelCompatibilityClaimV0",
    "DiscoveryRealizationCycleV0",
    "CycleIssueV0",
    "CycleEvaluationV0",
    "evaluate_discovery_realization_cycle",
    "residual_from_discovery_realization_cycle",
]
