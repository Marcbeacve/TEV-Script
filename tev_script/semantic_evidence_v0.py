from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_proof_boundary_v0 import ProofBoundaryWitnessV0

EVIDENCE_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_EVIDENCE_V0"
EVIDENCE_POLICY_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_EVIDENCE_POLICY_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_METHODS = frozenset(
    {
        "PROOF",
        "EXHAUSTIVE",
        "TRANSLATION_VALIDATION",
        "DIFFERENTIAL_TEST",
        "STATISTICAL_VALIDATION",
        "EMPIRICAL_OBSERVATION",
        "ATTESTATION",
        "ASSUMPTION",
    }
)
_STATUSES = frozenset({"ACTIVE", "REVOKED", "FALSIFIED"})
_PROOF_METHOD_MAP = {
    "proved": "PROOF",
    "exhaustive": "EXHAUSTIVE",
    "attested": "ATTESTATION",
    "sampled": "STATISTICAL_VALIDATION",
    "assumed": "ASSUMPTION",
}
_STATUS_MAP = {"active": "ACTIVE", "revoked": "REVOKED", "falsified": "FALSIFIED"}


class EvidenceSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise EvidenceSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise EvidenceSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class EvidenceItemV0:
    evidence_id: str
    claim_hash: str
    scope_hash: str
    method: str
    verifier_hash: str = ""
    witness_hash: str = ""
    assumption_hashes: tuple[str, ...] = ()
    coverage: Mapping[str, Any] | None = None
    status: str = "ACTIVE"

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _stable(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "claim_hash", _hash64(self.claim_hash, "claim_hash"))
        object.__setattr__(self, "scope_hash", _hash64(self.scope_hash, "scope_hash"))
        if self.method not in _METHODS:
            raise EvidenceSemanticsError("unsupported evidence method")
        if self.status not in _STATUSES:
            raise EvidenceSemanticsError("unsupported evidence status")
        object.__setattr__(self, "verifier_hash", _optional_hash(self.verifier_hash, "verifier_hash"))
        object.__setattr__(self, "witness_hash", _optional_hash(self.witness_hash, "witness_hash"))
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "assumption_hash"),
        )
        coverage = {} if self.coverage is None else dict(self.coverage)
        canonical_json(coverage)
        object.__setattr__(self, "coverage", coverage)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EVIDENCE_SCHEMA_V0,
            "evidence_id": self.evidence_id,
            "claim_hash": self.claim_hash,
            "scope_hash": self.scope_hash,
            "method": self.method,
            "verifier_hash": self.verifier_hash,
            "witness_hash": self.witness_hash,
            "assumption_hashes": list(self.assumption_hashes),
            "coverage": dict(self.coverage or {}),
            "status": self.status,
        }

    @property
    def evidence_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.evidence.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class EvidenceRequirementV0:
    requirement_id: str
    accepted_methods: tuple[str, ...]
    scope_hash: str = ""
    trusted_verifier_hashes: tuple[str, ...] = ()
    minimum_count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", _stable(self.requirement_id, "requirement_id"))
        methods = tuple(sorted(set(str(value) for value in self.accepted_methods)))
        if not methods or any(method not in _METHODS for method in methods):
            raise EvidenceSemanticsError("accepted_methods")
        object.__setattr__(self, "accepted_methods", methods)
        object.__setattr__(self, "scope_hash", _optional_hash(self.scope_hash, "scope_hash"))
        object.__setattr__(
            self,
            "trusted_verifier_hashes",
            _hashes(self.trusted_verifier_hashes, "trusted_verifier_hash"),
        )
        if (
            not isinstance(self.minimum_count, int)
            or isinstance(self.minimum_count, bool)
            or self.minimum_count <= 0
        ):
            raise EvidenceSemanticsError("minimum_count must be a positive integer")

    def to_object(self) -> dict[str, object]:
        return {
            "requirement_id": self.requirement_id,
            "accepted_methods": list(self.accepted_methods),
            "scope_hash": self.scope_hash,
            "trusted_verifier_hashes": list(self.trusted_verifier_hashes),
            "minimum_count": self.minimum_count,
        }


@dataclass(frozen=True, slots=True)
class EvidencePolicyV0:
    requirements: tuple[EvidenceRequirementV0, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.requirements, key=lambda item: item.requirement_id))
        if len({item.requirement_id for item in ordered}) != len(ordered):
            raise EvidenceSemanticsError("duplicate evidence requirement")
        object.__setattr__(self, "requirements", ordered)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": EVIDENCE_POLICY_SCHEMA_V0,
            "requirements": [item.to_object() for item in self.requirements],
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.evidence_policy.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class EvidenceIssueV0:
    kind: str
    requirement_id: str
    detail: Mapping[str, Any]
    evidence_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "evidence issue kind"))
        object.__setattr__(self, "requirement_id", _stable(self.requirement_id, "requirement_id"))
        object.__setattr__(self, "evidence_hash", _optional_hash(self.evidence_hash, "evidence_hash"))
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "requirement_id": self.requirement_id,
            "evidence_hash": self.evidence_hash,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class EvidenceEvaluationV0:
    claim_hash: str
    policy_hash: str
    accepted_evidence_hashes: tuple[str, ...]
    issues: tuple[EvidenceIssueV0, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_hash", _hash64(self.claim_hash, "claim_hash"))
        object.__setattr__(self, "policy_hash", _hash64(self.policy_hash, "policy_hash"))
        object.__setattr__(
            self,
            "accepted_evidence_hashes",
            _hashes(self.accepted_evidence_hashes, "accepted_evidence_hash"),
        )
        issues = tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object())))
        object.__setattr__(self, "issues", issues)

    @property
    def falsified(self) -> bool:
        return any(item.kind == "evidence.falsified" for item in self.issues)

    @property
    def complete(self) -> bool:
        return not self.issues

    def to_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_REALIZATION_EVIDENCE_EVALUATION_V0",
            "claim_hash": self.claim_hash,
            "policy_hash": self.policy_hash,
            "accepted_evidence_hashes": list(self.accepted_evidence_hashes),
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def _requirement_accepts(requirement: EvidenceRequirementV0, item: EvidenceItemV0) -> bool:
    if item.status != "ACTIVE":
        return False
    if item.method not in requirement.accepted_methods:
        return False
    if requirement.scope_hash and item.scope_hash != requirement.scope_hash:
        return False
    if (
        requirement.trusted_verifier_hashes
        and item.verifier_hash not in requirement.trusted_verifier_hashes
    ):
        return False
    return True


def evaluate_evidence(
    claim_hash: str,
    policy: EvidencePolicyV0,
    evidence: Iterable[EvidenceItemV0],
) -> EvidenceEvaluationV0:
    claim_hash = _hash64(claim_hash, "claim_hash")
    items = tuple(evidence)
    if len({item.evidence_hash for item in items}) != len(items):
        raise EvidenceSemanticsError("duplicate evidence item")

    issues: list[EvidenceIssueV0] = []
    accepted: set[str] = set()

    for item in items:
        if item.claim_hash == claim_hash and item.status == "FALSIFIED":
            issues.append(
                EvidenceIssueV0(
                    "evidence.falsified",
                    "global_claim_integrity",
                    {"evidence_id": item.evidence_id, "method": item.method},
                    item.evidence_hash,
                )
            )

    for requirement in policy.requirements:
        matching_claim = tuple(item for item in items if item.claim_hash == claim_hash)
        valid = tuple(item for item in matching_claim if _requirement_accepts(requirement, item))
        if len(valid) >= requirement.minimum_count:
            accepted.update(item.evidence_hash for item in valid)
            continue

        if not matching_claim:
            issues.append(
                EvidenceIssueV0(
                    "evidence.required",
                    requirement.requirement_id,
                    {
                        "minimum_count": requirement.minimum_count,
                        "accepted_methods": list(requirement.accepted_methods),
                    },
                )
            )
            continue

        active = tuple(item for item in matching_claim if item.status == "ACTIVE")
        if not active:
            issues.append(
                EvidenceIssueV0(
                    "evidence.inactive",
                    requirement.requirement_id,
                    {"observed_statuses": sorted(set(item.status for item in matching_claim))},
                )
            )
            continue

        method_matches = tuple(item for item in active if item.method in requirement.accepted_methods)
        if not method_matches:
            issues.append(
                EvidenceIssueV0(
                    "evidence.method_unaccepted",
                    requirement.requirement_id,
                    {
                        "accepted_methods": list(requirement.accepted_methods),
                        "observed_methods": sorted(set(item.method for item in active)),
                    },
                )
            )
            continue

        if requirement.scope_hash:
            scope_matches = tuple(item for item in method_matches if item.scope_hash == requirement.scope_hash)
            if not scope_matches:
                issues.append(
                    EvidenceIssueV0(
                        "evidence.scope_mismatch",
                        requirement.requirement_id,
                        {
                            "expected_scope_hash": requirement.scope_hash,
                            "observed_scope_hashes": sorted(set(item.scope_hash for item in method_matches)),
                        },
                    )
                )
                continue
        else:
            scope_matches = method_matches

        if requirement.trusted_verifier_hashes:
            trusted = tuple(
                item
                for item in scope_matches
                if item.verifier_hash in requirement.trusted_verifier_hashes
            )
            if not trusted:
                issues.append(
                    EvidenceIssueV0(
                        "evidence.verifier_untrusted",
                        requirement.requirement_id,
                        {
                            "trusted_verifier_hashes": list(requirement.trusted_verifier_hashes),
                            "observed_verifier_hashes": sorted(
                                set(item.verifier_hash for item in scope_matches)
                            ),
                        },
                    )
                )
                continue
        else:
            trusted = scope_matches

        issues.append(
            EvidenceIssueV0(
                "evidence.required",
                requirement.requirement_id,
                {
                    "minimum_count": requirement.minimum_count,
                    "accepted_count": len(trusted),
                },
            )
        )

    return EvidenceEvaluationV0(
        claim_hash,
        policy.policy_hash,
        tuple(sorted(accepted)),
        tuple(issues),
    )


def evidence_from_proof_boundary(
    witness: ProofBoundaryWitnessV0,
    *,
    evidence_id: str,
    claim_hash: str,
    assumption_hashes: Iterable[str] = (),
    coverage: Mapping[str, Any] | None = None,
) -> EvidenceItemV0:
    return EvidenceItemV0(
        evidence_id=evidence_id,
        claim_hash=claim_hash,
        scope_hash=witness.scope_hash,
        method=_PROOF_METHOD_MAP[witness.method],
        verifier_hash=witness.verifier_hash,
        witness_hash=witness.witness_hash,
        assumption_hashes=tuple(assumption_hashes),
        coverage=coverage,
        status=_STATUS_MAP[witness.status],
    )


__all__ = [
    "EVIDENCE_SCHEMA_V0",
    "EVIDENCE_POLICY_SCHEMA_V0",
    "EvidenceSemanticsError",
    "EvidenceItemV0",
    "EvidenceRequirementV0",
    "EvidencePolicyV0",
    "EvidenceIssueV0",
    "EvidenceEvaluationV0",
    "evaluate_evidence",
    "evidence_from_proof_boundary",
]
