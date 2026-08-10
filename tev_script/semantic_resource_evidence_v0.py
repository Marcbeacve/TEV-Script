from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_resource_algebra_v0 import ResourceVectorV0

RESOURCE_ESTIMATE_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_ESTIMATE_CLAIM_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_ESTIMATE_KINDS = frozenset(
    {
        "ANALYTIC_BOUND",
        "STATIC_ESTIMATE",
        "PROFILE_PREDICTION",
        "EMPIRICAL_ENVELOPE",
    }
)


class ResourceEvidenceError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ResourceEvidenceError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ResourceEvidenceError(what)
    return text


@dataclass(frozen=True, slots=True)
class ResourceEstimateClaimV0:
    realization_hash: str
    execution_context_hash: str
    resource_vector_hash: str
    resource_catalog_hash: str
    estimate_kind: str
    estimator_hash: str
    scope_hash: str
    assumptions: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in (
            "realization_hash",
            "execution_context_hash",
            "resource_vector_hash",
            "resource_catalog_hash",
            "estimator_hash",
            "scope_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.estimate_kind not in _ESTIMATE_KINDS:
            raise ResourceEvidenceError("unsupported estimate kind")
        assumptions = {} if self.assumptions is None else dict(self.assumptions)
        canonical_json(assumptions)
        object.__setattr__(self, "assumptions", assumptions)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_ESTIMATE_CLAIM_SCHEMA_V0,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "resource_vector_hash": self.resource_vector_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "estimate_kind": self.estimate_kind,
            "estimator_hash": self.estimator_hash,
            "scope_hash": self.scope_hash,
            "assumptions": dict(self.assumptions or {}),
        }

    @property
    def estimate_claim_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.resource_estimate.v0", self.to_object())

    def validates_vector(
        self,
        *,
        realization_hash: str,
        execution_context_hash: str,
        vector: ResourceVectorV0,
    ) -> bool:
        return (
            self.realization_hash == _hash64(realization_hash, "realization_hash")
            and self.execution_context_hash
            == _hash64(execution_context_hash, "execution_context_hash")
            and self.resource_vector_hash == vector.vector_hash
            and self.resource_catalog_hash == vector.catalog_hash
        )


__all__ = [
    "RESOURCE_ESTIMATE_CLAIM_SCHEMA_V0",
    "ResourceEvidenceError",
    "ResourceEstimateClaimV0",
]
