from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_resource_algebra_v0 import ResourceVectorV0

RESOURCE_ESTIMATE_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_BOUND_CLAIM_V0"
RESOURCE_ESTIMATE_RECORD_SCHEMA_V0 = "TEV_SCRIPT_RESOURCE_ESTIMATE_RECORD_V0"
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


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class ResourceEstimateClaimV0:
    """A resource-bound claim plus estimator provenance.

    The claim identity says that one realization, in one execution context and
    under explicit assumptions, has the stated ResourceVector in the stated
    catalog/scope. The estimator/method that proposed that claim is provenance
    and therefore belongs to the record, not to the claim hash. Evidence is what
    decides whether the claim is acceptable.
    """

    realization_hash: str
    execution_context_hash: str
    resource_vector_hash: str
    resource_catalog_hash: str
    estimate_kind: str
    estimator_hash: str
    scope_hash: str
    assumption_hashes: tuple[str, ...] = ()
    detail: Mapping[str, Any] | None = None

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
        object.__setattr__(
            self,
            "assumption_hashes",
            _hashes(self.assumption_hashes, "resource estimate assumption hash"),
        )
        detail = {} if self.detail is None else dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def claim_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_ESTIMATE_CLAIM_SCHEMA_V0,
            "realization_hash": self.realization_hash,
            "execution_context_hash": self.execution_context_hash,
            "resource_vector_hash": self.resource_vector_hash,
            "resource_catalog_hash": self.resource_catalog_hash,
            "scope_hash": self.scope_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def estimate_claim_hash(self) -> str:
        return canonical_hash(self.claim_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": RESOURCE_ESTIMATE_RECORD_SCHEMA_V0,
            "estimate_claim_hash": self.estimate_claim_hash,
            **{key: value for key, value in self.claim_object().items() if key != "schema"},
            "estimate_kind": self.estimate_kind,
            "estimator_hash": self.estimator_hash,
            "detail": dict(self.detail or {}),
        }

    @property
    def record_hash(self) -> str:
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
    "RESOURCE_ESTIMATE_RECORD_SCHEMA_V0",
    "ResourceEvidenceError",
    "ResourceEstimateClaimV0",
]
