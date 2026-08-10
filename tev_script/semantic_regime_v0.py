from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping

REGIME_SCHEMA_V0 = "TEV_SCRIPT_REGIME_CONTRACT_V0"
REGIME_SEMANTIC_SCHEMA_V0 = "TEV_SCRIPT_REGIME_SEMANTIC_IDENTITY_V0"
REGIME_CONSTRAINT_SEMANTIC_SCHEMA_V0 = "TEV_SCRIPT_REGIME_CONSTRAINT_SEMANTIC_V0"
REGIME_BINDING_SCHEMA_V0 = "TEV_SCRIPT_TRANSFORMATION_REGIME_BINDING_V0"
REGIME_BINDING_SEMANTIC_SCHEMA_V0 = "TEV_SCRIPT_TRANSFORMATION_REGIME_BINDING_SEMANTIC_V0"
REGIME_PRESERVATION_SCHEMA_V0 = "TEV_SCRIPT_REGIME_PRESERVATION_CLAIM_V0"
REGIME_PRESERVATION_RECORD_SCHEMA_V0 = "TEV_SCRIPT_REGIME_PRESERVATION_RECORD_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_PRESERVATION = frozenset({"PRESERVED", "VIOLATED", "UNRESOLVED", "NOT_REQUIRED"})
_RELATIONS = frozenset(
    {"EXACT_EQUIVALENT", "REFINEMENT", "APPROXIMATION", "SIMULATION", "PROJECTION"}
)


class RegimeSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise RegimeSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RegimeSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class RegimeConstraintV0:
    constraint_id: str
    kind: str
    claim_hash: str
    scope_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraint_id", _stable(self.constraint_id, "constraint_id"))
        object.__setattr__(self, "kind", _stable(self.kind, "constraint kind"))
        object.__setattr__(self, "claim_hash", _hash64(self.claim_hash, "constraint claim_hash"))
        object.__setattr__(self, "scope_hash", _hash64(self.scope_hash, "constraint scope_hash"))

    def semantic_object(self) -> dict[str, str]:
        return {
            "schema": REGIME_CONSTRAINT_SEMANTIC_SCHEMA_V0,
            "kind": self.kind,
            "claim_hash": self.claim_hash,
            "scope_hash": self.scope_hash,
        }

    @property
    def constraint_semantic_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, str]:
        return {
            "constraint_id": self.constraint_id,
            "constraint_semantic_hash": self.constraint_semantic_hash,
            "kind": self.kind,
            "claim_hash": self.claim_hash,
            "scope_hash": self.scope_hash,
        }


@dataclass(frozen=True, slots=True)
class RegimeContractV0:
    regime_id: str
    possibility_space_hash: str
    history_space_hash: str
    constraints: tuple[RegimeConstraintV0, ...] = ()
    causal_structure_hash: str = ""
    equivalence_relation_hash: str = ""
    observable_profile_hash: str = ""
    invariant_claim_hashes: tuple[str, ...] = ()
    assumption_hashes: tuple[str, ...] = ()
    provenance: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "regime_id", _stable(self.regime_id, "regime_id"))
        object.__setattr__(
            self,
            "possibility_space_hash",
            _hash64(self.possibility_space_hash, "possibility_space_hash"),
        )
        object.__setattr__(
            self,
            "history_space_hash",
            _hash64(self.history_space_hash, "history_space_hash"),
        )
        constraints = tuple(
            sorted(self.constraints, key=lambda item: (item.constraint_semantic_hash, item.constraint_id))
        )
        if len({item.constraint_id for item in constraints}) != len(constraints):
            raise RegimeSemanticsError("duplicate regime constraint id")
        if len({item.constraint_semantic_hash for item in constraints}) != len(constraints):
            raise RegimeSemanticsError("duplicate regime constraint semantics")
        object.__setattr__(self, "constraints", constraints)
        object.__setattr__(
            self,
            "causal_structure_hash",
            _optional_hash(self.causal_structure_hash, "causal_structure_hash"),
        )
        object.__setattr__(
            self,
            "equivalence_relation_hash",
            _optional_hash(self.equivalence_relation_hash, "equivalence_relation_hash"),
        )
        object.__setattr__(
            self,
            "observable_profile_hash",
            _optional_hash(self.observable_profile_hash, "observable_profile_hash"),
        )
        object.__setattr__(
            self,
            "invariant_claim_hashes",
            _hashes(self.invariant_claim_hashes, "invariant claim hash"),
        )
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "regime assumption hash"),
        )
        provenance = {} if self.provenance is None else dict(self.provenance)
        canonical_json(provenance)
        object.__setattr__(self, "provenance", provenance)

    @property
    def constraint_semantic_hashes(self) -> tuple[str, ...]:
        return tuple(item.constraint_semantic_hash for item in self.constraints)

    @property
    def constraint_claim_hashes(self) -> tuple[str, ...]:
        return tuple(item.claim_hash for item in self.constraints)

    def semantic_object(self) -> dict[str, object]:
        return {
            "schema": REGIME_SEMANTIC_SCHEMA_V0,
            "possibility_space_hash": self.possibility_space_hash,
            "history_space_hash": self.history_space_hash,
            "constraints": [
                item.semantic_object()
                for item in sorted(
                    self.constraints,
                    key=lambda item: canonical_json(item.semantic_object()),
                )
            ],
            "causal_structure_hash": self.causal_structure_hash,
            "equivalence_relation_hash": self.equivalence_relation_hash,
            "observable_profile_hash": self.observable_profile_hash,
            "invariant_claim_hashes": list(self.invariant_claim_hashes),
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def regime_semantic_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    @property
    def regime_hash(self) -> str:
        return self.regime_semantic_hash

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REGIME_SCHEMA_V0,
            "regime_semantic_hash": self.regime_semantic_hash,
            "regime_id": self.regime_id,
            "possibility_space_hash": self.possibility_space_hash,
            "history_space_hash": self.history_space_hash,
            "constraints": [item.to_object() for item in self.constraints],
            "causal_structure_hash": self.causal_structure_hash,
            "equivalence_relation_hash": self.equivalence_relation_hash,
            "observable_profile_hash": self.observable_profile_hash,
            "invariant_claim_hashes": list(self.invariant_claim_hashes),
            "assumption_hashes": list(self.assumption_hashes),
            "provenance": dict(self.provenance or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.regime.contract.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class TransformationRegimeBindingV0:
    transformation_semantic_hash: str
    regime_hash: str
    semantic_scope_hash: str
    binding_id: str = "primary"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transformation_semantic_hash",
            _hash64(self.transformation_semantic_hash, "transformation_semantic_hash"),
        )
        object.__setattr__(self, "regime_hash", _hash64(self.regime_hash, "regime_hash"))
        object.__setattr__(
            self,
            "semantic_scope_hash",
            _hash64(self.semantic_scope_hash, "semantic_scope_hash"),
        )
        object.__setattr__(self, "binding_id", _stable(self.binding_id, "binding_id"))

    def semantic_object(self) -> dict[str, str]:
        return {
            "schema": REGIME_BINDING_SEMANTIC_SCHEMA_V0,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "regime_hash": self.regime_hash,
            "semantic_scope_hash": self.semantic_scope_hash,
        }

    @property
    def binding_hash(self) -> str:
        return canonical_hash(self.semantic_object())

    def to_object(self) -> dict[str, str]:
        return {
            "schema": REGIME_BINDING_SCHEMA_V0,
            "binding_hash": self.binding_hash,
            "binding_id": self.binding_id,
            "transformation_semantic_hash": self.transformation_semantic_hash,
            "regime_hash": self.regime_hash,
            "semantic_scope_hash": self.semantic_scope_hash,
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.regime.binding.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RegimePreservationClaimV0:
    realization_semantic_claim_hash: str
    transformation_regime_binding_hash: str
    regime_hash: str
    semantic_relation: str
    preserved_constraint_hashes: tuple[str, ...] = ()
    violated_constraint_hashes: tuple[str, ...] = ()
    preserved_invariant_hashes: tuple[str, ...] = ()
    violated_invariant_hashes: tuple[str, ...] = ()
    causal_preservation: str = "NOT_REQUIRED"
    equivalence_preservation: str = "NOT_REQUIRED"
    assumption_hashes: tuple[str, ...] = ()
    detail: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "realization_semantic_claim_hash",
            _hash64(self.realization_semantic_claim_hash, "realization_semantic_claim_hash"),
        )
        object.__setattr__(
            self,
            "transformation_regime_binding_hash",
            _hash64(
                self.transformation_regime_binding_hash,
                "transformation_regime_binding_hash",
            ),
        )
        object.__setattr__(self, "regime_hash", _hash64(self.regime_hash, "regime_hash"))
        if self.semantic_relation not in _RELATIONS:
            raise RegimeSemanticsError("unsupported semantic relation")
        for name in (
            "preserved_constraint_hashes",
            "violated_constraint_hashes",
            "preserved_invariant_hashes",
            "violated_invariant_hashes",
            "assumption_hashes",
        ):
            object.__setattr__(self, name, _hashes(getattr(self, name), name))
        if set(self.preserved_constraint_hashes) & set(self.violated_constraint_hashes):
            raise RegimeSemanticsError("constraint cannot be both preserved and violated")
        if set(self.preserved_invariant_hashes) & set(self.violated_invariant_hashes):
            raise RegimeSemanticsError("invariant cannot be both preserved and violated")
        if self.causal_preservation not in _PRESERVATION:
            raise RegimeSemanticsError("causal_preservation")
        if self.equivalence_preservation not in _PRESERVATION:
            raise RegimeSemanticsError("equivalence_preservation")
        detail = {} if self.detail is None else dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def claim_object(self) -> dict[str, object]:
        return {
            "schema": REGIME_PRESERVATION_SCHEMA_V0,
            "realization_semantic_claim_hash": self.realization_semantic_claim_hash,
            "transformation_regime_binding_hash": self.transformation_regime_binding_hash,
            "regime_hash": self.regime_hash,
            "semantic_relation": self.semantic_relation,
            "preserved_constraint_hashes": list(self.preserved_constraint_hashes),
            "violated_constraint_hashes": list(self.violated_constraint_hashes),
            "preserved_invariant_hashes": list(self.preserved_invariant_hashes),
            "violated_invariant_hashes": list(self.violated_invariant_hashes),
            "causal_preservation": self.causal_preservation,
            "equivalence_preservation": self.equivalence_preservation,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def preservation_claim_hash(self) -> str:
        return canonical_hash(self.claim_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": REGIME_PRESERVATION_RECORD_SCHEMA_V0,
            "preservation_claim_hash": self.preservation_claim_hash,
            **{key: value for key, value in self.claim_object().items() if key != "schema"},
            "detail": dict(self.detail or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.regime.preservation.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class RegimeIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "regime issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RegimeSemanticsError("regime issue severity")
        subject = str(self.subject)
        if not subject:
            raise RegimeSemanticsError("regime issue subject")
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
class RegimeEvaluationV0:
    regime_hash: str
    binding_hash: str
    preservation_claim_hash: str
    issues: tuple[RegimeIssueV0, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "regime_hash", _hash64(self.regime_hash, "regime_hash"))
        object.__setattr__(self, "binding_hash", _hash64(self.binding_hash, "binding_hash"))
        object.__setattr__(
            self,
            "preservation_claim_hash",
            _hash64(self.preservation_claim_hash, "preservation_claim_hash"),
        )
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
            "schema": "TEV_SCRIPT_REGIME_EVALUATION_V0",
            "regime_hash": self.regime_hash,
            "binding_hash": self.binding_hash,
            "preservation_claim_hash": self.preservation_claim_hash,
            "status": self.status,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_regime_preservation(
    regime: RegimeContractV0,
    binding: TransformationRegimeBindingV0,
    claim: RegimePreservationClaimV0,
    *,
    transformation_semantic_hash: str,
    realization_semantic_claim_hash: str,
    semantic_relation: str,
) -> RegimeEvaluationV0:
    transformation_semantic_hash = _hash64(
        transformation_semantic_hash, "transformation_semantic_hash"
    )
    realization_semantic_claim_hash = _hash64(
        realization_semantic_claim_hash, "realization_semantic_claim_hash"
    )
    if semantic_relation not in _RELATIONS:
        raise RegimeSemanticsError("semantic_relation")

    issues: list[RegimeIssueV0] = []

    if binding.regime_hash != regime.regime_hash:
        issues.append(
            RegimeIssueV0(
                "regime.binding_mismatch",
                "REJECT",
                binding.binding_id,
                {"expected_regime_hash": regime.regime_hash, "observed_regime_hash": binding.regime_hash},
            )
        )
    if binding.transformation_semantic_hash != transformation_semantic_hash:
        issues.append(
            RegimeIssueV0(
                "regime.transformation_mismatch",
                "REJECT",
                binding.binding_id,
                {
                    "expected_transformation_semantic_hash": transformation_semantic_hash,
                    "observed_transformation_semantic_hash": binding.transformation_semantic_hash,
                },
            )
        )
    if claim.regime_hash != regime.regime_hash:
        issues.append(
            RegimeIssueV0(
                "regime.claim_regime_mismatch",
                "REJECT",
                claim.regime_hash,
                {"expected_regime_hash": regime.regime_hash},
            )
        )
    if claim.transformation_regime_binding_hash != binding.binding_hash:
        issues.append(
            RegimeIssueV0(
                "regime.claim_binding_mismatch",
                "REJECT",
                claim.transformation_regime_binding_hash,
                {"expected_binding_hash": binding.binding_hash},
            )
        )
    if claim.realization_semantic_claim_hash != realization_semantic_claim_hash:
        issues.append(
            RegimeIssueV0(
                "regime.realization_claim_mismatch",
                "REJECT",
                claim.realization_semantic_claim_hash,
                {"expected_realization_semantic_claim_hash": realization_semantic_claim_hash},
            )
        )
    if claim.semantic_relation != semantic_relation:
        issues.append(
            RegimeIssueV0(
                "regime.semantic_relation_mismatch",
                "REJECT",
                claim.semantic_relation,
                {"expected_semantic_relation": semantic_relation},
            )
        )

    required_constraints = set(regime.constraint_semantic_hashes)
    preserved_constraints = set(claim.preserved_constraint_hashes)
    violated_constraints = set(claim.violated_constraint_hashes)
    unknown_constraint_refs = (preserved_constraints | violated_constraints) - required_constraints
    for item in sorted(unknown_constraint_refs):
        issues.append(
            RegimeIssueV0(
                "regime.constraint_not_in_contract",
                "REJECT",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )
    for item in sorted(required_constraints & violated_constraints):
        issues.append(
            RegimeIssueV0(
                "regime.constraint_violated",
                "REJECT",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )
    for item in sorted(required_constraints - preserved_constraints - violated_constraints):
        issues.append(
            RegimeIssueV0(
                "regime.constraint_unresolved",
                "PROOF_REQUIRED",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )

    required_invariants = set(regime.invariant_claim_hashes)
    preserved_invariants = set(claim.preserved_invariant_hashes)
    violated_invariants = set(claim.violated_invariant_hashes)
    unknown_invariant_refs = (preserved_invariants | violated_invariants) - required_invariants
    for item in sorted(unknown_invariant_refs):
        issues.append(
            RegimeIssueV0(
                "regime.invariant_not_in_contract",
                "REJECT",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )
    for item in sorted(required_invariants & violated_invariants):
        issues.append(
            RegimeIssueV0(
                "regime.invariant_violated",
                "REJECT",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )
    for item in sorted(required_invariants - preserved_invariants - violated_invariants):
        issues.append(
            RegimeIssueV0(
                "regime.invariant_unresolved",
                "PROOF_REQUIRED",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )

    causal_required = bool(regime.causal_structure_hash)
    if causal_required:
        if claim.causal_preservation == "VIOLATED":
            issues.append(
                RegimeIssueV0(
                    "regime.causal_preservation_violated",
                    "REJECT",
                    regime.causal_structure_hash,
                    {},
                )
            )
        elif claim.causal_preservation != "PRESERVED":
            issues.append(
                RegimeIssueV0(
                    "regime.causal_preservation_required",
                    "PROOF_REQUIRED",
                    regime.causal_structure_hash,
                    {"observed": claim.causal_preservation},
                )
            )
    elif claim.causal_preservation != "NOT_REQUIRED":
        issues.append(
            RegimeIssueV0(
                "regime.causal_preservation_unscoped",
                "REJECT",
                claim.causal_preservation,
                {},
            )
        )

    equivalence_required = bool(regime.equivalence_relation_hash)
    if equivalence_required:
        if claim.equivalence_preservation == "VIOLATED":
            issues.append(
                RegimeIssueV0(
                    "regime.equivalence_preservation_violated",
                    "REJECT",
                    regime.equivalence_relation_hash,
                    {},
                )
            )
        elif claim.equivalence_preservation != "PRESERVED":
            issues.append(
                RegimeIssueV0(
                    "regime.equivalence_preservation_required",
                    "PROOF_REQUIRED",
                    regime.equivalence_relation_hash,
                    {"observed": claim.equivalence_preservation},
                )
            )
    elif claim.equivalence_preservation != "NOT_REQUIRED":
        issues.append(
            RegimeIssueV0(
                "regime.equivalence_preservation_unscoped",
                "REJECT",
                claim.equivalence_preservation,
                {},
            )
        )

    regime_assumptions = set(regime.assumption_hashes)
    claim_assumptions = set(claim.assumption_hashes)
    for item in sorted(claim_assumptions - regime_assumptions):
        issues.append(
            RegimeIssueV0(
                "regime.assumption_unaccepted",
                "REJECT",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )
    for item in sorted(regime_assumptions - claim_assumptions):
        issues.append(
            RegimeIssueV0(
                "regime.assumption_unacknowledged",
                "PROOF_REQUIRED",
                item,
                {"regime_hash": regime.regime_hash},
            )
        )

    return RegimeEvaluationV0(
        regime.regime_hash,
        binding.binding_hash,
        claim.preservation_claim_hash,
        tuple(issues),
    )


def realization_equivalence_class_claim_hash(
    *,
    transformation_semantic_hash: str,
    transformation_regime_binding_hash: str,
    semantic_relation: str,
    approximation_contract_hash: str = "",
) -> str:
    if semantic_relation not in _RELATIONS:
        raise RegimeSemanticsError("semantic_relation")
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_REALIZATION_EQUIVALENCE_CLASS_CLAIM_V0",
            "transformation_semantic_hash": _hash64(
                transformation_semantic_hash, "transformation_semantic_hash"
            ),
            "transformation_regime_binding_hash": _hash64(
                transformation_regime_binding_hash,
                "transformation_regime_binding_hash",
            ),
            "semantic_relation": semantic_relation,
            "approximation_contract_hash": _optional_hash(
                approximation_contract_hash, "approximation_contract_hash"
            ),
        }
    )


__all__ = [
    "REGIME_SCHEMA_V0",
    "REGIME_SEMANTIC_SCHEMA_V0",
    "REGIME_CONSTRAINT_SEMANTIC_SCHEMA_V0",
    "REGIME_BINDING_SCHEMA_V0",
    "REGIME_BINDING_SEMANTIC_SCHEMA_V0",
    "REGIME_PRESERVATION_SCHEMA_V0",
    "REGIME_PRESERVATION_RECORD_SCHEMA_V0",
    "RegimeSemanticsError",
    "RegimeConstraintV0",
    "RegimeContractV0",
    "TransformationRegimeBindingV0",
    "RegimePreservationClaimV0",
    "RegimeIssueV0",
    "RegimeEvaluationV0",
    "evaluate_regime_preservation",
    "realization_equivalence_class_claim_hash",
]
