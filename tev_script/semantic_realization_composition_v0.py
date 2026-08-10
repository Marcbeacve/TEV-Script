from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    evaluate_evidence,
)
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

REALIZATION_COMPOSITION_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_COMPOSITION_CLAIM_V0"
REALIZATION_COMPOSITION_RECORD_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_COMPOSITION_RECORD_V0"
REALIZATION_COMPOSITION_POLICY_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_COMPOSITION_POLICY_V0"
REALIZATION_COMPOSITION_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_COMPOSITION_EVALUATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class RealizationCompositionError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise RealizationCompositionError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RealizationCompositionError(what)
    return text


def _hashes(values: Iterable[str], what: str, *, deduplicate: bool = True) -> tuple[str, ...]:
    rows = tuple(_hash64(value, what) for value in values)
    return tuple(sorted(set(rows) if deduplicate else rows))


@dataclass(frozen=True, slots=True)
class RealizationCompositionClaimV0:
    target_transformation_semantic_hash: str
    target_regime_binding_hash: str
    component_receipt_hashes: tuple[str, ...]
    composition_relation_hash: str
    composition_scope_hash: str
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "target_transformation_semantic_hash",
            _hash64(
                self.target_transformation_semantic_hash,
                "target_transformation_semantic_hash",
            ),
        )
        object.__setattr__(
            self,
            "target_regime_binding_hash",
            _hash64(self.target_regime_binding_hash, "target_regime_binding_hash"),
        )
        components = _hashes(
            self.component_receipt_hashes,
            "component receipt hash",
            deduplicate=False,
        )
        if not components:
            raise RealizationCompositionError("composition requires at least one component receipt")
        object.__setattr__(self, "component_receipt_hashes", components)
        object.__setattr__(
            self,
            "composition_relation_hash",
            _hash64(self.composition_relation_hash, "composition_relation_hash"),
        )
        object.__setattr__(
            self,
            "composition_scope_hash",
            _hash64(self.composition_scope_hash, "composition_scope_hash"),
        )
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "composition assumption hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REALIZATION_COMPOSITION_CLAIM_SCHEMA_V0,
            "target_transformation_semantic_hash": self.target_transformation_semantic_hash,
            "target_regime_binding_hash": self.target_regime_binding_hash,
            "component_receipt_hashes": list(self.component_receipt_hashes),
            "composition_relation_hash": self.composition_relation_hash,
            "composition_scope_hash": self.composition_scope_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def composition_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.composition_claim.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationCompositionRecordV0:
    claim: RealizationCompositionClaimV0
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_policy_hash",
            _hash64(self.evidence_policy_hash, "evidence_policy_hash"),
        )
        object.__setattr__(
            self,
            "evidence_hashes",
            _hashes(self.evidence_hashes, "composition evidence hash"),
        )
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REALIZATION_COMPOSITION_RECORD_SCHEMA_V0,
            "composition_claim_hash": self.claim.composition_claim_hash,
            "claim": self.claim.to_object(),
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.composition_record.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationCompositionPolicyV0:
    evidence_policy_hash: str
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_policy_hash",
            _hash64(self.evidence_policy_hash, "evidence_policy_hash"),
        )
        object.__setattr__(
            self,
            "accepted_assumption_hashes",
            _hashes(self.accepted_assumption_hashes, "accepted composition assumption hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REALIZATION_COMPOSITION_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationCompositionIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "composition issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RealizationCompositionError("composition issue severity")
        subject = str(self.subject)
        if not subject:
            raise RealizationCompositionError("composition issue subject")
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
class RealizationCompositionEvaluationV0:
    composition_claim_hash: str
    composition_record_hash: str
    policy_hash: str
    evidence_evaluation_hash: str
    issues: tuple[RealizationCompositionIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "composition_claim_hash",
            "composition_record_hash",
            "policy_hash",
            "evidence_evaluation_hash",
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
            "schema": REALIZATION_COMPOSITION_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "composition_claim_hash": self.composition_claim_hash,
            "composition_record_hash": self.composition_record_hash,
            "policy_hash": self.policy_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_realization_composition(
    record: RealizationCompositionRecordV0,
    *,
    policy: RealizationCompositionPolicyV0,
    evidence_policy: EvidencePolicyV0,
    component_receipts: Iterable[RealizationAdmissionReceiptV0],
    evidence: Iterable[EvidenceItemV0],
) -> RealizationCompositionEvaluationV0:
    issues: list[RealizationCompositionIssueV0] = []
    claim = record.claim
    receipts = tuple(component_receipts)
    observed_hashes = tuple(sorted(receipt.receipt_hash for receipt in receipts))

    if observed_hashes != claim.component_receipt_hashes:
        issues.append(
            RealizationCompositionIssueV0(
                "composition.component_receipt_set_mismatch",
                "REJECT",
                claim.composition_claim_hash,
                {
                    "expected": list(claim.component_receipt_hashes),
                    "observed": list(observed_hashes),
                },
            )
        )
    for receipt in receipts:
        if receipt.status != "PASS":
            issues.append(
                RealizationCompositionIssueV0(
                    "composition.component_not_admitted",
                    "REJECT",
                    receipt.receipt_hash,
                    {"status": receipt.status},
                )
            )

    if record.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(
            RealizationCompositionIssueV0(
                "composition.evidence_policy_mismatch",
                "REJECT",
                record.evidence_policy_hash,
                {"observed": evidence_policy.policy_hash},
            )
        )
    if policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(
            RealizationCompositionIssueV0(
                "composition.policy_evidence_mismatch",
                "REJECT",
                policy.policy_hash,
                {"observed": evidence_policy.policy_hash},
            )
        )

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
        issues.append(
            RealizationCompositionIssueV0(
                "composition.assumption_not_accepted",
                "REJECT",
                assumption_hash,
                {},
            )
        )

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(
                RealizationCompositionIssueV0(
                    "composition.evidence_reference_missing",
                    "PROOF_REQUIRED",
                    evidence_hash,
                    {},
                )
            )

    evidence_evaluation = evaluate_evidence(
        claim.composition_claim_hash,
        evidence_policy,
        evidence_items,
    )
    for item in evidence_evaluation.issues:
        issues.append(
            RealizationCompositionIssueV0(
                "composition." + item.kind,
                "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED",
                item.requirement_id,
                {"evidence_hash": item.evidence_hash, **dict(item.detail)},
            )
        )
    for accepted_hash in evidence_evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(
                RealizationCompositionIssueV0(
                    "composition.evidence_unbound_support",
                    "REJECT",
                    accepted_hash,
                    {},
                )
            )
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(
                set(item.assumption_hashes) - accepted_assumptions
            ):
                issues.append(
                    RealizationCompositionIssueV0(
                        "composition.evidence_assumption_not_accepted",
                        "REJECT",
                        assumption_hash,
                        {"evidence_hash": accepted_hash},
                    )
                )

    return RealizationCompositionEvaluationV0(
        claim.composition_claim_hash,
        record.record_hash,
        policy.policy_hash,
        evidence_evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_realization_composition(
    evaluation: RealizationCompositionEvaluationV0,
) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_composition",
        judgment_id="realization_composition_admission",
        judgment={
            "kind": "component_realizations_compose",
            "composition_claim_hash": evaluation.composition_claim_hash,
            "status": evaluation.status,
        },
        source={
            "kind": "realization_composition_evaluation",
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
                    evaluation.composition_claim_hash,
                    evaluation.composition_record_hash,
                ),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "REALIZATION_COMPOSITION_CLAIM_SCHEMA_V0",
    "REALIZATION_COMPOSITION_RECORD_SCHEMA_V0",
    "REALIZATION_COMPOSITION_POLICY_SCHEMA_V0",
    "REALIZATION_COMPOSITION_EVALUATION_SCHEMA_V0",
    "RealizationCompositionError",
    "RealizationCompositionClaimV0",
    "RealizationCompositionRecordV0",
    "RealizationCompositionPolicyV0",
    "RealizationCompositionIssueV0",
    "RealizationCompositionEvaluationV0",
    "evaluate_realization_composition",
    "residual_from_realization_composition",
]
