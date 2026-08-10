from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any, Iterable, Mapping, Sequence

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import (
    EvidenceEvaluationV0,
    EvidenceItemV0,
    EvidencePolicyV0,
    evaluate_evidence,
)
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_machine_v0 import (
    MachineCompatibilityV0,
    MachineFieldV0,
    MachineRequirementV0,
    evaluate_machine_compatibility,
)
from .semantic_regime_v0 import (
    RegimeContractV0,
    RegimeEvaluationV0,
    RegimePreservationClaimV0,
    TransformationRegimeBindingV0,
    evaluate_regime_preservation,
)
from .semantic_resource_algebra_v0 import (
    ResourceAlgebraError,
    ResourceCatalogV0,
    ResourceCeilingIssueV0,
    ResourceCeilingV0,
    ResourceVectorV0,
    evaluate_resource_ceilings,
    validate_resource_ceilings,
)
from .semantic_resource_evidence_v0 import ResourceEstimateClaimV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

REALIZATION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_CANDIDATE_V0"
REALIZATION_POLICY_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_POLICY_V0"
REALIZATION_PROBLEM_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_PROBLEM_V0"
REALIZATION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_ADMISSION_RECEIPT_V0"
RESOURCE_OBSERVATION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_RESOURCE_OBSERVATION_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_RELATIONS = frozenset(
    {"EXACT_EQUIVALENT", "REFINEMENT", "APPROXIMATION", "SIMULATION", "PROJECTION"}
)
_GUARANTEES = frozenset({"DETERMINISTIC_BOUND", "PROBABILISTIC_BOUND", "EMPIRICAL_BOUND"})


class RealizationSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise RealizationSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RealizationSemanticsError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def _nonnegative_fraction(value: Fraction | int, what: str) -> Fraction:
    result = value if isinstance(value, Fraction) else Fraction(value)
    if result < 0:
        raise RealizationSemanticsError(f"{what} must be non-negative")
    return result


def _probability(value: Fraction | int, what: str) -> Fraction:
    result = _nonnegative_fraction(value, what)
    if result > 1:
        raise RealizationSemanticsError(f"{what} must be <= 1")
    return result


def _fraction_object(value: Fraction) -> dict[str, list[str]]:
    return {"$rat": [str(value.numerator), str(value.denominator)]}


@dataclass(frozen=True, slots=True)
class ApproximationContractV0:
    metric_hash: str
    domain_hash: str
    error_upper_bound: Fraction | int
    guarantee_kind: str
    confidence_lower_bound: Fraction | int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_hash", _hash64(self.metric_hash, "metric_hash"))
        object.__setattr__(self, "domain_hash", _hash64(self.domain_hash, "domain_hash"))
        object.__setattr__(
            self,
            "error_upper_bound",
            _nonnegative_fraction(self.error_upper_bound, "error_upper_bound"),
        )
        if self.guarantee_kind not in _GUARANTEES:
            raise RealizationSemanticsError("unsupported approximation guarantee")
        if self.confidence_lower_bound is not None:
            object.__setattr__(
                self,
                "confidence_lower_bound",
                _probability(self.confidence_lower_bound, "confidence_lower_bound"),
            )
        if self.guarantee_kind == "DETERMINISTIC_BOUND" and self.confidence_lower_bound is not None:
            raise RealizationSemanticsError("deterministic bound must not carry confidence")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_APPROXIMATION_CONTRACT_V0",
            "metric_hash": self.metric_hash,
            "domain_hash": self.domain_hash,
            "error_upper_bound": _fraction_object(self.error_upper_bound),
            "guarantee_kind": self.guarantee_kind,
            "confidence_lower_bound": (
                None
                if self.confidence_lower_bound is None
                else _fraction_object(self.confidence_lower_bound)
            ),
        }

    @property
    def contract_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ApproximationPolicyV0:
    metric_hash: str
    domain_hash: str
    maximum_error: Fraction | int
    accepted_guarantee_kinds: tuple[str, ...]
    minimum_confidence: Fraction | int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_hash", _hash64(self.metric_hash, "metric_hash"))
        object.__setattr__(self, "domain_hash", _hash64(self.domain_hash, "domain_hash"))
        object.__setattr__(
            self,
            "maximum_error",
            _nonnegative_fraction(self.maximum_error, "maximum_error"),
        )
        guarantees = tuple(sorted(set(str(item) for item in self.accepted_guarantee_kinds)))
        if not guarantees or any(item not in _GUARANTEES for item in guarantees):
            raise RealizationSemanticsError("accepted_guarantee_kinds")
        object.__setattr__(self, "accepted_guarantee_kinds", guarantees)
        if self.minimum_confidence is not None:
            object.__setattr__(
                self,
                "minimum_confidence",
                _probability(self.minimum_confidence, "minimum_confidence"),
            )

    def to_object(self) -> dict[str, object]:
        return {
            "metric_hash": self.metric_hash,
            "domain_hash": self.domain_hash,
            "maximum_error": _fraction_object(self.maximum_error),
            "accepted_guarantee_kinds": list(self.accepted_guarantee_kinds),
            "minimum_confidence": (
                None if self.minimum_confidence is None else _fraction_object(self.minimum_confidence)
            ),
        }


@dataclass(frozen=True, slots=True)
class RealizationPolicyV0:
    allowed_relations: tuple[str, ...]
    realization_evidence_policy_hash: str
    regime_evidence_policy_hash: str
    resource_evidence_policy_hash: str
    resource_catalog_hash: str
    accepted_assumption_hashes: tuple[str, ...] = ()
    resource_ceilings: tuple[ResourceCeilingV0, ...] = ()
    approximation_policy: ApproximationPolicyV0 | None = None

    def __post_init__(self) -> None:
        relations = tuple(sorted(set(str(item) for item in self.allowed_relations)))
        if not relations or any(item not in _RELATIONS for item in relations):
            raise RealizationSemanticsError("allowed_relations")
        object.__setattr__(self, "allowed_relations", relations)
        for name in (
            "realization_evidence_policy_hash",
            "regime_evidence_policy_hash",
            "resource_evidence_policy_hash",
            "resource_catalog_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(
            self,
            "accepted_assumption_hashes",
            _hashes(self.accepted_assumption_hashes, "accepted assumption hash"),
        )
        ceilings = tuple(sorted(self.resource_ceilings, key=lambda item: item.dimension_id))
        if len({item.dimension_id for item in ceilings}) != len(ceilings):
            raise RealizationSemanticsError("duplicate resource ceiling")
        if any(item.catalog_hash != self.resource_catalog_hash for item in ceilings):
            raise RealizationSemanticsError("resource ceiling catalog does not match policy")
        object.__setattr__(self, "resource_ceilings", ceilings)
        if "APPROXIMATION" in relations and self.approximation_policy is None:
            raise RealizationSemanticsError(
                "APPROXIMATION relation requires an approximation policy"
            )
        if "APPROXIMATION" not in relations and self.approximation_policy is not None:
            raise RealizationSemanticsError(
                "approximation policy present while APPROXIMATION is not allowed"
            )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REALIZATION_POLICY_SCHEMA_V0,
            "allowed_relations": list(self.allowed_relations),
            "realization_evidence_policy_hash": self.realization_evidence_policy_hash,
            "regime_evidence_policy_hash": self.regime_evidence_policy_hash,
            "resource_evidence_policy_hash": self.resource_evidence_policy_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
            "resource_ceilings": [item.to_object() for item in self.resource_ceilings],
            "approximation_policy": (
                None if self.approximation_policy is None else self.approximation_policy.to_object()
            ),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.policy.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationProblemV0:
    transformation_semantic_hash: str
    transformation_regime_binding_hash: str
    context_hash: str
    policy_hash: str
    available_machine_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transformation_semantic_hash",
            _hash64(self.transformation_semantic_hash, "transformation_semantic_hash"),
        )
        object.__setattr__(
            self,
            "transformation_regime_binding_hash",
            _hash64(
                self.transformation_regime_binding_hash,
                "transformation_regime_binding_hash",
            ),
        )
        object.__setattr__(self, "context_hash", _hash64(self.context_hash, "context_hash"))
        object.__setattr__(self, "policy_hash", _hash64(self.policy_hash, "policy_hash"))
        machines = _hashes(self.available_machine_hashes, "available machine hash")
        if not machines:
            raise RealizationSemanticsError("at least one available machine is required")
        object.__setattr__(self, "available_machine_hashes", machines)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REALIZATION_PROBLEM_SCHEMA_V0,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "transformation_regime_binding_hash": self.transformation_regime_binding_hash,
            "context_hash": self.context_hash,
            "policy_hash": self.policy_hash,
            "available_machine_hashes": list(self.available_machine_hashes),
        }

    @property
    def problem_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.problem.v0", self.to_object())


def realization_semantic_claim_object(
    *,
    transformation_semantic_hash: str,
    transformation_regime_binding_hash: str,
    machine_hash: str,
    artifact_hashes: Iterable[str],
    machine_requirement: MachineRequirementV0,
    semantic_relation: str,
    approximation_contract: ApproximationContractV0 | None = None,
    assumption_hashes: Iterable[str] = (),
) -> dict[str, object]:
    transformation_semantic_hash = _hash64(
        transformation_semantic_hash, "transformation_semantic_hash"
    )
    transformation_regime_binding_hash = _hash64(
        transformation_regime_binding_hash, "transformation_regime_binding_hash"
    )
    machine_hash = _hash64(machine_hash, "machine_hash")
    artifacts = _hashes(artifact_hashes, "artifact hash")
    if not artifacts:
        raise RealizationSemanticsError("semantic claim requires at least one artifact hash")
    if semantic_relation not in _RELATIONS:
        raise RealizationSemanticsError("unsupported semantic relation")
    if semantic_relation == "APPROXIMATION" and approximation_contract is None:
        raise RealizationSemanticsError("APPROXIMATION requires approximation contract")
    if semantic_relation != "APPROXIMATION" and approximation_contract is not None:
        raise RealizationSemanticsError(
            "non-approximate realization must not carry approximation contract"
        )
    assumptions = _hashes(assumption_hashes, "candidate assumption hash")
    return {
        "schema": "TEV_SCRIPT_REALIZATION_SEMANTIC_CLAIM_V0",
        "transformation_semantic_hash": transformation_semantic_hash,
        "transformation_regime_binding_hash": transformation_regime_binding_hash,
        "machine_hash": machine_hash,
        "artifact_hashes": list(artifacts),
        "machine_requirement": machine_requirement.to_object(),
        "semantic_relation": semantic_relation,
        "approximation_contract_hash": (
            "" if approximation_contract is None else approximation_contract.contract_hash
        ),
        "assumption_hashes": list(assumptions),
    }


def realization_semantic_claim_hash(**kwargs: Any) -> str:
    return canonical_hash(realization_semantic_claim_object(**kwargs))


def realization_identity_object(
    *,
    realization_kind: str,
    transformation_semantic_hash: str,
    transformation_regime_binding_hash: str,
    machine_hash: str,
    artifact_hashes: Iterable[str],
    machine_requirement: MachineRequirementV0,
    semantic_relation: str,
    approximation_contract: ApproximationContractV0 | None = None,
    assumption_hashes: Iterable[str] = (),
) -> dict[str, object]:
    return {
        **realization_semantic_claim_object(
            transformation_semantic_hash=transformation_semantic_hash,
            transformation_regime_binding_hash=transformation_regime_binding_hash,
            machine_hash=machine_hash,
            artifact_hashes=artifact_hashes,
            machine_requirement=machine_requirement,
            semantic_relation=semantic_relation,
            approximation_contract=approximation_contract,
            assumption_hashes=assumption_hashes,
        ),
        "schema": "TEV_SCRIPT_REALIZATION_IDENTITY_V0",
        "realization_kind": _stable(realization_kind, "realization_kind"),
    }


def realization_identity_hash(**kwargs: Any) -> str:
    return canonical_hash(realization_identity_object(**kwargs))


@dataclass(frozen=True, slots=True)
class RealizationCandidateV0:
    transformation_semantic_hash: str
    transformation_regime_binding_hash: str
    realization_kind: str
    machine_hash: str
    artifact_hashes: tuple[str, ...]
    machine_requirement: MachineRequirementV0
    semantic_relation: str
    approximation_contract: ApproximationContractV0 | None = None
    assumption_hashes: tuple[str, ...] = ()
    provenance_hashes: tuple[str, ...] = ()
    predicted_resources: ResourceVectorV0 = ResourceVectorV0()
    resource_estimate_claim_hash: str = ""
    evidence_hashes: tuple[str, ...] = ()
    regime_preservation_claim_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transformation_semantic_hash",
            _hash64(self.transformation_semantic_hash, "transformation_semantic_hash"),
        )
        object.__setattr__(
            self,
            "transformation_regime_binding_hash",
            _hash64(
                self.transformation_regime_binding_hash,
                "transformation_regime_binding_hash",
            ),
        )
        object.__setattr__(self, "realization_kind", _stable(self.realization_kind, "realization_kind"))
        object.__setattr__(self, "machine_hash", _hash64(self.machine_hash, "machine_hash"))
        artifacts = _hashes(self.artifact_hashes, "artifact hash")
        if not artifacts:
            raise RealizationSemanticsError("candidate requires at least one artifact hash")
        object.__setattr__(self, "artifact_hashes", artifacts)
        if self.semantic_relation not in _RELATIONS:
            raise RealizationSemanticsError("unsupported semantic relation")
        if self.semantic_relation == "APPROXIMATION" and self.approximation_contract is None:
            raise RealizationSemanticsError("APPROXIMATION requires approximation contract")
        if self.semantic_relation != "APPROXIMATION" and self.approximation_contract is not None:
            raise RealizationSemanticsError(
                "non-approximate realization must not carry approximation contract"
            )
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "candidate assumption hash"),
        )
        object.__setattr__(
            self,
            "provenance_hashes",
            _hashes(self.provenance_hashes, "provenance hash"),
        )
        object.__setattr__(
            self,
            "resource_estimate_claim_hash",
            _hash64(self.resource_estimate_claim_hash, "resource_estimate_claim_hash"),
        )
        object.__setattr__(
            self,
            "evidence_hashes",
            _hashes(self.evidence_hashes, "evidence hash"),
        )
        object.__setattr__(
            self,
            "regime_preservation_claim_hash",
            _hash64(
                self.regime_preservation_claim_hash,
                "regime_preservation_claim_hash",
            ),
        )

    @property
    def semantic_claim_hash(self) -> str:
        return realization_semantic_claim_hash(
            transformation_semantic_hash=self.transformation_semantic_hash,
            transformation_regime_binding_hash=self.transformation_regime_binding_hash,
            machine_hash=self.machine_hash,
            artifact_hashes=self.artifact_hashes,
            machine_requirement=self.machine_requirement,
            semantic_relation=self.semantic_relation,
            approximation_contract=self.approximation_contract,
            assumption_hashes=self.assumption_hashes,
        )

    @property
    def realization_hash(self) -> str:
        return realization_identity_hash(
            realization_kind=self.realization_kind,
            transformation_semantic_hash=self.transformation_semantic_hash,
            transformation_regime_binding_hash=self.transformation_regime_binding_hash,
            machine_hash=self.machine_hash,
            artifact_hashes=self.artifact_hashes,
            machine_requirement=self.machine_requirement,
            semantic_relation=self.semantic_relation,
            approximation_contract=self.approximation_contract,
            assumption_hashes=self.assumption_hashes,
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REALIZATION_SCHEMA_V0,
            "realization_hash": self.realization_hash,
            "semantic_claim_hash": self.semantic_claim_hash,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "transformation_regime_binding_hash": self.transformation_regime_binding_hash,
            "realization_kind": self.realization_kind,
            "machine_hash": self.machine_hash,
            "artifact_hashes": list(self.artifact_hashes),
            "machine_requirement": self.machine_requirement.to_object(),
            "semantic_relation": self.semantic_relation,
            "approximation_contract": (
                None if self.approximation_contract is None else self.approximation_contract.to_object()
            ),
            "assumption_hashes": list(self.assumption_hashes),
            "provenance_hashes": list(self.provenance_hashes),
            "predicted_resources": self.predicted_resources.to_object(),
            "resource_estimate_claim_hash": self.resource_estimate_claim_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "regime_preservation_claim_hash": self.regime_preservation_claim_hash,
        }

    @property
    def candidate_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.candidate.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "realization issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RealizationSemanticsError("realization issue severity")
        subject = str(self.subject)
        if not subject:
            raise RealizationSemanticsError("realization issue subject")
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
class RealizationAdmissionReceiptV0:
    problem_hash: str
    candidate_hash: str
    realization_hash: str
    semantic_claim_hash: str
    transformation_semantic_hash: str
    transformation_regime_binding_hash: str
    semantic_relation: str
    regime_preservation_claim_hash: str
    resource_estimate_claim_hash: str
    machine_hash: str
    policy_hash: str
    regime_hash: str
    resource_catalog_hash: str
    machine_compatibility_hash: str
    regime_evaluation_hash: str
    realization_evidence_evaluation_hash: str
    regime_evidence_evaluation_hash: str
    resource_evidence_evaluation_hash: str
    issues: tuple[RealizationIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "problem_hash",
            "candidate_hash",
            "realization_hash",
            "semantic_claim_hash",
            "transformation_semantic_hash",
            "transformation_regime_binding_hash",
            "regime_preservation_claim_hash",
            "resource_estimate_claim_hash",
            "machine_hash",
            "policy_hash",
            "regime_hash",
            "resource_catalog_hash",
            "machine_compatibility_hash",
            "regime_evaluation_hash",
            "realization_evidence_evaluation_hash",
            "regime_evidence_evaluation_hash",
            "resource_evidence_evaluation_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.semantic_relation not in _RELATIONS:
            raise RealizationSemanticsError("receipt semantic relation")
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
            "schema": REALIZATION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "problem_hash": self.problem_hash,
            "candidate_hash": self.candidate_hash,
            "realization_hash": self.realization_hash,
            "semantic_claim_hash": self.semantic_claim_hash,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "transformation_regime_binding_hash": self.transformation_regime_binding_hash,
            "semantic_relation": self.semantic_relation,
            "regime_preservation_claim_hash": self.regime_preservation_claim_hash,
            "resource_estimate_claim_hash": self.resource_estimate_claim_hash,
            "machine_hash": self.machine_hash,
            "policy_hash": self.policy_hash,
            "regime_hash": self.regime_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "machine_compatibility_hash": self.machine_compatibility_hash,
            "regime_evaluation_hash": self.regime_evaluation_hash,
            "realization_evidence_evaluation_hash": self.realization_evidence_evaluation_hash,
            "regime_evidence_evaluation_hash": self.regime_evidence_evaluation_hash,
            "resource_evidence_evaluation_hash": self.resource_evidence_evaluation_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.admission_receipt.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceObservationV0:
    realization_hash: str
    execution_context_hash: str
    observed_resources: ResourceVectorV0
    observation_source_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "realization_hash", _hash64(self.realization_hash, "realization_hash"))
        object.__setattr__(
            self,
            "execution_context_hash",
            _hash64(self.execution_context_hash, "execution_context_hash"),
        )
        object.__setattr__(
            self,
            "observation_source_hash",
            _hash64(self.observation_source_hash, "observation_source_hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_OBSERVATION_SCHEMA_V0,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "observed_resources": self.observed_resources.to_object(),
            "observation_source_hash": self.observation_source_hash,
        }

    @property
    def observation_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ParetoEntryV0:
    candidate_hash: str
    realization_hash: str
    resource_vector_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_hash", _hash64(self.candidate_hash, "candidate_hash"))
        object.__setattr__(self, "realization_hash", _hash64(self.realization_hash, "realization_hash"))
        object.__setattr__(
            self,
            "resource_vector_hash",
            _hash64(self.resource_vector_hash, "resource_vector_hash"),
        )


def _issue(kind: str, severity: str, subject: str, **detail: Any) -> RealizationIssueV0:
    return RealizationIssueV0(kind, severity, subject, detail)


def _evaluate_approximation(
    candidate: RealizationCandidateV0,
    policy: RealizationPolicyV0,
) -> tuple[RealizationIssueV0, ...]:
    if candidate.semantic_relation != "APPROXIMATION":
        return ()
    contract = candidate.approximation_contract
    approximation_policy = policy.approximation_policy
    assert contract is not None
    assert approximation_policy is not None
    issues: list[RealizationIssueV0] = []
    if contract.metric_hash != approximation_policy.metric_hash:
        issues.append(
            _issue(
                "approximation.metric_mismatch",
                "REJECT",
                contract.metric_hash,
                expected=approximation_policy.metric_hash,
            )
        )
    if contract.domain_hash != approximation_policy.domain_hash:
        issues.append(
            _issue(
                "approximation.domain_mismatch",
                "REJECT",
                contract.domain_hash,
                expected=approximation_policy.domain_hash,
            )
        )
    if contract.error_upper_bound > approximation_policy.maximum_error:
        issues.append(
            _issue(
                "approximation.bound_exceeded",
                "REJECT",
                contract.contract_hash,
                observed=_fraction_object(contract.error_upper_bound),
                maximum=_fraction_object(approximation_policy.maximum_error),
            )
        )
    if contract.guarantee_kind not in approximation_policy.accepted_guarantee_kinds:
        issues.append(
            _issue(
                "approximation.guarantee_unaccepted",
                "REJECT",
                contract.guarantee_kind,
                accepted=list(approximation_policy.accepted_guarantee_kinds),
            )
        )
    if approximation_policy.minimum_confidence is not None:
        if contract.confidence_lower_bound is None:
            issues.append(
                _issue(
                    "approximation.confidence_missing",
                    "REJECT",
                    contract.contract_hash,
                    minimum=_fraction_object(approximation_policy.minimum_confidence),
                )
            )
        elif contract.confidence_lower_bound < approximation_policy.minimum_confidence:
            issues.append(
                _issue(
                    "approximation.confidence_too_low",
                    "REJECT",
                    contract.contract_hash,
                    observed=_fraction_object(contract.confidence_lower_bound),
                    minimum=_fraction_object(approximation_policy.minimum_confidence),
                )
            )
    return tuple(issues)


def _issues_from_machine(
    compatibility: MachineCompatibilityV0,
) -> tuple[RealizationIssueV0, ...]:
    issues: list[RealizationIssueV0] = []
    for item in compatibility.missing_capability_semantic_hashes:
        issues.append(_issue("machine.operation_missing", "REJECT", item))
    for item in compatibility.missing_numeric_model_ids:
        issues.append(_issue("machine.numeric_model_missing", "REJECT", item))
    for item in compatibility.missing_executable_formats:
        issues.append(_issue("machine.format_missing", "REJECT", item))
    return tuple(issues)


def _issues_from_regime(evaluation: RegimeEvaluationV0) -> tuple[RealizationIssueV0, ...]:
    return tuple(
        RealizationIssueV0(item.kind, item.severity, item.subject, item.detail)
        for item in evaluation.issues
    )


def _issues_from_evidence(
    evaluation: EvidenceEvaluationV0,
    *,
    prefix: str,
) -> tuple[RealizationIssueV0, ...]:
    issues: list[RealizationIssueV0] = []
    for item in evaluation.issues:
        severity = "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED"
        issues.append(
            _issue(
                prefix + "." + item.kind,
                severity,
                item.requirement_id,
                evidence_hash=item.evidence_hash,
                **dict(item.detail),
            )
        )
    return tuple(issues)


def _issues_from_resources(
    issues: Iterable[ResourceCeilingIssueV0],
) -> tuple[RealizationIssueV0, ...]:
    result: list[RealizationIssueV0] = []
    for item in issues:
        if item.kind == "UNKNOWN":
            result.append(
                _issue(
                    "resource.bound_unknown",
                    "PROOF_REQUIRED",
                    item.dimension_id,
                    maximum=_fraction_object(item.maximum),
                )
            )
        else:
            result.append(
                _issue(
                    "resource.ceiling_exceeded",
                    "REJECT",
                    item.dimension_id,
                    maximum=_fraction_object(item.maximum),
                    observed_upper=(
                        None
                        if item.observed_upper is None
                        else _fraction_object(item.observed_upper)
                    ),
                )
            )
    return tuple(result)


def _reject_unaccepted_assumptions(
    issues: list[RealizationIssueV0],
    values: Iterable[str],
    accepted: set[str],
    *,
    kind: str,
) -> None:
    for assumption_hash in sorted(set(values) - accepted):
        issues.append(_issue(kind, "REJECT", assumption_hash))


def admit_realization(
    problem: RealizationProblemV0,
    candidate: RealizationCandidateV0,
    *,
    machine: MachineFieldV0,
    policy: RealizationPolicyV0,
    resource_catalog: ResourceCatalogV0,
    resource_estimate_claim: ResourceEstimateClaimV0,
    regime: RegimeContractV0,
    binding: TransformationRegimeBindingV0,
    preservation_claim: RegimePreservationClaimV0,
    realization_evidence_policy: EvidencePolicyV0,
    regime_evidence_policy: EvidencePolicyV0,
    resource_evidence_policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> RealizationAdmissionReceiptV0:
    issues: list[RealizationIssueV0] = []

    if problem.policy_hash != policy.policy_hash:
        issues.append(
            _issue(
                "realization.policy_mismatch",
                "REJECT",
                problem.policy_hash,
                observed=policy.policy_hash,
            )
        )
    if problem.transformation_semantic_hash != candidate.transformation_semantic_hash:
        issues.append(
            _issue(
                "realization.transformation_mismatch",
                "REJECT",
                candidate.transformation_semantic_hash,
                expected=problem.transformation_semantic_hash,
            )
        )
    if problem.transformation_regime_binding_hash != binding.binding_hash:
        issues.append(
            _issue(
                "regime.problem_binding_mismatch",
                "REJECT",
                problem.transformation_regime_binding_hash,
                observed=binding.binding_hash,
            )
        )
    if candidate.transformation_regime_binding_hash != binding.binding_hash:
        issues.append(
            _issue(
                "regime.candidate_binding_mismatch",
                "REJECT",
                candidate.transformation_regime_binding_hash,
                observed=binding.binding_hash,
            )
        )
    if candidate.regime_preservation_claim_hash != preservation_claim.preservation_claim_hash:
        issues.append(
            _issue(
                "regime.preservation_claim_mismatch",
                "REJECT",
                candidate.regime_preservation_claim_hash,
                observed=preservation_claim.preservation_claim_hash,
            )
        )
    if candidate.resource_estimate_claim_hash != resource_estimate_claim.estimate_claim_hash:
        issues.append(
            _issue(
                "resource.estimate_claim_mismatch",
                "REJECT",
                candidate.resource_estimate_claim_hash,
                observed=resource_estimate_claim.estimate_claim_hash,
            )
        )
    if candidate.machine_hash != machine.machine_hash:
        issues.append(
            _issue(
                "machine.identity_mismatch",
                "REJECT",
                candidate.machine_hash,
                observed=machine.machine_hash,
            )
        )
    if machine.machine_hash not in problem.available_machine_hashes:
        issues.append(
            _issue(
                "machine.not_available",
                "REJECT",
                machine.machine_hash,
                available=list(problem.available_machine_hashes),
            )
        )
    if candidate.semantic_relation not in policy.allowed_relations:
        issues.append(
            _issue(
                "relation.not_allowed",
                "REJECT",
                candidate.semantic_relation,
                allowed=list(policy.allowed_relations),
            )
        )

    policy_pairs = (
        (
            "evidence.realization_policy_mismatch",
            policy.realization_evidence_policy_hash,
            realization_evidence_policy.policy_hash,
        ),
        (
            "evidence.regime_policy_mismatch",
            policy.regime_evidence_policy_hash,
            regime_evidence_policy.policy_hash,
        ),
        (
            "evidence.resource_policy_mismatch",
            policy.resource_evidence_policy_hash,
            resource_evidence_policy.policy_hash,
        ),
    )
    for kind, expected, observed in policy_pairs:
        if expected != observed:
            issues.append(_issue(kind, "REJECT", observed, expected=expected))

    resource_policy_valid = True
    if policy.resource_catalog_hash != resource_catalog.catalog_hash:
        resource_policy_valid = False
        issues.append(
            _issue(
                "resource.catalog_policy_mismatch",
                "REJECT",
                resource_catalog.catalog_hash,
                expected=policy.resource_catalog_hash,
            )
        )
    try:
        validate_resource_ceilings(policy.resource_ceilings, resource_catalog)
    except ResourceAlgebraError as error:
        resource_policy_valid = False
        issues.append(
            _issue(
                "resource.policy_invalid",
                "REJECT",
                policy.policy_hash,
                detail=str(error),
            )
        )
    if policy.resource_ceilings and not resource_evidence_policy.requirements:
        resource_policy_valid = False
        issues.append(
            _issue(
                "resource.evidence_policy_empty",
                "REJECT",
                resource_evidence_policy.policy_hash,
            )
        )

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    _reject_unaccepted_assumptions(
        issues,
        candidate.assumption_hashes,
        accepted_assumptions,
        kind="assumption.not_accepted",
    )
    _reject_unaccepted_assumptions(
        issues,
        preservation_claim.assumption_hashes,
        accepted_assumptions,
        kind="regime.assumption_not_accepted_by_policy",
    )
    _reject_unaccepted_assumptions(
        issues,
        resource_estimate_claim.assumption_hashes,
        accepted_assumptions,
        kind="resource.estimate_assumption_not_accepted",
    )

    issues.extend(_evaluate_approximation(candidate, policy))

    machine_evaluation = evaluate_machine_compatibility(machine, candidate.machine_requirement)
    issues.extend(_issues_from_machine(machine_evaluation))

    regime_evaluation = evaluate_regime_preservation(
        regime,
        binding,
        preservation_claim,
        transformation_semantic_hash=problem.transformation_semantic_hash,
        realization_semantic_claim_hash=candidate.semantic_claim_hash,
        semantic_relation=candidate.semantic_relation,
    )
    issues.extend(_issues_from_regime(regime_evaluation))

    resource_vector_valid = True
    try:
        candidate.predicted_resources.validate_against(resource_catalog)
    except ResourceAlgebraError as error:
        resource_vector_valid = False
        issues.append(
            _issue(
                "resource.vector_invalid",
                "REJECT",
                candidate.predicted_resources.vector_hash,
                detail=str(error),
            )
        )
    if not resource_estimate_claim.validates_vector(
        realization_hash=candidate.realization_hash,
        execution_context_hash=problem.context_hash,
        vector=candidate.predicted_resources,
    ):
        resource_vector_valid = False
        issues.append(
            _issue(
                "resource.estimate_binding_mismatch",
                "REJECT",
                resource_estimate_claim.estimate_claim_hash,
            )
        )

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in candidate.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(_issue("evidence.reference_missing", "PROOF_REQUIRED", evidence_hash))

    realization_evaluation = evaluate_evidence(
        candidate.semantic_claim_hash,
        realization_evidence_policy,
        evidence_items,
    )
    regime_evaluation_evidence = evaluate_evidence(
        preservation_claim.preservation_claim_hash,
        regime_evidence_policy,
        evidence_items,
    )
    resource_evaluation = evaluate_evidence(
        resource_estimate_claim.estimate_claim_hash,
        resource_evidence_policy,
        evidence_items,
    )
    accepted_support = (
        set(realization_evaluation.accepted_evidence_hashes)
        | set(regime_evaluation_evidence.accepted_evidence_hashes)
        | set(resource_evaluation.accepted_evidence_hashes)
    )
    for accepted_hash in sorted(accepted_support):
        if accepted_hash not in candidate.evidence_hashes:
            issues.append(_issue("evidence.unbound_support", "REJECT", accepted_hash))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            _reject_unaccepted_assumptions(
                issues,
                item.assumption_hashes,
                accepted_assumptions,
                kind="evidence.assumption_not_accepted",
            )

    issues.extend(_issues_from_evidence(realization_evaluation, prefix="realization"))
    issues.extend(_issues_from_evidence(regime_evaluation_evidence, prefix="regime"))
    issues.extend(_issues_from_evidence(resource_evaluation, prefix="resource"))

    if resource_policy_valid and resource_vector_valid:
        resource_issues = evaluate_resource_ceilings(
            candidate.predicted_resources,
            policy.resource_ceilings,
        )
        issues.extend(_issues_from_resources(resource_issues))

    return RealizationAdmissionReceiptV0(
        problem.problem_hash,
        candidate.candidate_hash,
        candidate.realization_hash,
        candidate.semantic_claim_hash,
        candidate.transformation_semantic_hash,
        candidate.transformation_regime_binding_hash,
        candidate.semantic_relation,
        candidate.regime_preservation_claim_hash,
        candidate.resource_estimate_claim_hash,
        machine.machine_hash,
        policy.policy_hash,
        regime.regime_hash,
        resource_catalog.catalog_hash,
        machine_evaluation.compatibility_hash,
        regime_evaluation.evaluation_hash,
        realization_evaluation.evaluation_hash,
        regime_evaluation_evidence.evaluation_hash,
        resource_evaluation.evaluation_hash,
        tuple(issues),
    )


def residual_from_realization_admission(
    receipt: RealizationAdmissionReceiptV0,
) -> SemanticFieldV0:
    obstructions = tuple(
        ResidualObstructionV0(
            item.kind,
            item.subject,
            "resolved",
            item.severity,
            dict(item.detail),
            dependency_refs=(
                receipt.problem_hash,
                receipt.candidate_hash,
                receipt.policy_hash,
                receipt.regime_hash,
                receipt.resource_catalog_hash,
                receipt.resource_estimate_claim_hash,
            ),
        )
        for item in receipt.issues
    )
    return residual_from_obstructions(
        domain="realization",
        judgment_id="realization_admission",
        judgment={
            "kind": "candidate_admissible",
            "problem_hash": receipt.problem_hash,
            "candidate_hash": receipt.candidate_hash,
            "realization_hash": receipt.realization_hash,
            "transformation_semantic_hash": receipt.transformation_semantic_hash,
            "semantic_relation": receipt.semantic_relation,
            "status": receipt.status,
        },
        source={
            "kind": "realization_admission_receipt",
            "receipt_hash": receipt.receipt_hash,
        },
        obstructions=obstructions,
    )


def semantic_memoization_key(
    *,
    transformation_semantic_hash: str,
    canonical_input_hash: str,
    semantic_environment_hash: str,
) -> str:
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_SEMANTIC_MEMOIZATION_KEY_V0",
            "transformation_semantic_hash": _hash64(
                transformation_semantic_hash, "transformation_semantic_hash"
            ),
            "canonical_input_hash": _hash64(canonical_input_hash, "canonical_input_hash"),
            "semantic_environment_hash": _hash64(
                semantic_environment_hash, "semantic_environment_hash"
            ),
        }
    )


def _dominates(
    left: ResourceVectorV0,
    right: ResourceVectorV0,
    dimensions: Sequence[str],
) -> bool:
    if left.catalog_hash != right.catalog_hash:
        return False
    strictly_better = False
    for dimension_id in dimensions:
        left_bound = left.effective_bound(dimension_id)
        right_bound = right.effective_bound(dimension_id)
        if left_bound.upper is None or right_bound.upper is None:
            return False
        if left_bound.upper > right_bound.upper:
            return False
        if left_bound.upper < right_bound.upper:
            strictly_better = True
    return strictly_better


def pareto_front(
    entries: Iterable[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0]],
    *,
    dimensions: Sequence[str],
) -> tuple[ParetoEntryV0, ...]:
    selected_dimensions = tuple(_stable(item, "resource dimension") for item in dimensions)
    if not selected_dimensions:
        raise RealizationSemanticsError("Pareto extraction requires dimensions")
    if len(set(selected_dimensions)) != len(selected_dimensions):
        raise RealizationSemanticsError("duplicate Pareto dimension")

    eligible: list[RealizationCandidateV0] = []
    for candidate, receipt in entries:
        if receipt.candidate_hash != candidate.candidate_hash:
            raise RealizationSemanticsError("candidate/receipt mismatch")
        if receipt.status == "PASS":
            if receipt.resource_catalog_hash != candidate.predicted_resources.catalog_hash:
                raise RealizationSemanticsError("candidate/receipt resource catalog mismatch")
            eligible.append(candidate)

    front: list[RealizationCandidateV0] = []
    for candidate in sorted(eligible, key=lambda item: item.candidate_hash):
        dominated = any(
            other.candidate_hash != candidate.candidate_hash
            and _dominates(
                other.predicted_resources,
                candidate.predicted_resources,
                selected_dimensions,
            )
            for other in eligible
        )
        if not dominated:
            front.append(candidate)

    return tuple(
        ParetoEntryV0(
            candidate.candidate_hash,
            candidate.realization_hash,
            candidate.predicted_resources.vector_hash,
        )
        for candidate in front
    )


__all__ = [
    "REALIZATION_SCHEMA_V0",
    "REALIZATION_POLICY_SCHEMA_V0",
    "REALIZATION_PROBLEM_SCHEMA_V0",
    "REALIZATION_RECEIPT_SCHEMA_V0",
    "RESOURCE_OBSERVATION_SCHEMA_V0",
    "RealizationSemanticsError",
    "ApproximationContractV0",
    "ApproximationPolicyV0",
    "RealizationPolicyV0",
    "RealizationProblemV0",
    "realization_semantic_claim_object",
    "realization_semantic_claim_hash",
    "realization_identity_object",
    "realization_identity_hash",
    "RealizationCandidateV0",
    "RealizationIssueV0",
    "RealizationAdmissionReceiptV0",
    "ResourceObservationV0",
    "ParetoEntryV0",
    "admit_realization",
    "residual_from_realization_admission",
    "semantic_memoization_key",
    "pareto_front",
]
