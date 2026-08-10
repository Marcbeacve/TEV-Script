from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Iterable

from .canonical import canonical_hash

_RESOURCE_SCHEMA = "TEV_SCRIPT_RESOURCE_VECTOR_V0"
_RESOURCE_CATALOG_SCHEMA = "TEV_SCRIPT_RESOURCE_CATALOG_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_AGGREGATIONS = frozenset({"SUM", "MAX"})
_MODES = frozenset({"SEQUENTIAL", "PARALLEL"})
_HEX = frozenset("0123456789abcdef")
EMPTY_RESOURCE_CATALOG_HASH = canonical_hash(
    {"schema": _RESOURCE_CATALOG_SCHEMA, "dimensions": []}
)


class ResourceAlgebraError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ResourceAlgebraError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ResourceAlgebraError(what)
    return text


def _nonnegative_fraction(value: Fraction | int, what: str) -> Fraction:
    result = value if isinstance(value, Fraction) else Fraction(value)
    if result < 0:
        raise ResourceAlgebraError(f"{what} must be non-negative")
    return result


def _fraction_object(value: Fraction) -> dict[str, list[str]]:
    return {"$rat": [str(value.numerator), str(value.denominator)]}


@dataclass(frozen=True, slots=True)
class ResourceDimensionV0:
    dimension_id: str
    unit: str
    sequential_aggregation: str
    parallel_aggregation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension_id", _stable(self.dimension_id, "dimension_id"))
        unit = str(self.unit)
        if not unit:
            raise ResourceAlgebraError("unit must be non-empty")
        object.__setattr__(self, "unit", unit)
        if self.sequential_aggregation not in _AGGREGATIONS:
            raise ResourceAlgebraError("unsupported sequential aggregation")
        if self.parallel_aggregation not in _AGGREGATIONS:
            raise ResourceAlgebraError("unsupported parallel aggregation")

    def aggregation_for(self, mode: str) -> str:
        if mode == "SEQUENTIAL":
            return self.sequential_aggregation
        if mode == "PARALLEL":
            return self.parallel_aggregation
        raise ResourceAlgebraError("unsupported composition mode")

    def to_object(self) -> dict[str, str]:
        return {
            "dimension_id": self.dimension_id,
            "unit": self.unit,
            "sequential_aggregation": self.sequential_aggregation,
            "parallel_aggregation": self.parallel_aggregation,
        }


@dataclass(frozen=True, slots=True)
class ResourceCatalogV0:
    dimensions: tuple[ResourceDimensionV0, ...]

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.dimensions, key=lambda item: item.dimension_id))
        if len({item.dimension_id for item in ordered}) != len(ordered):
            raise ResourceAlgebraError("duplicate resource dimension")
        object.__setattr__(self, "dimensions", ordered)

    @property
    def dimension_ids(self) -> tuple[str, ...]:
        return tuple(item.dimension_id for item in self.dimensions)

    def dimension(self, dimension_id: str) -> ResourceDimensionV0 | None:
        for item in self.dimensions:
            if item.dimension_id == dimension_id:
                return item
        return None

    def to_object(self) -> dict[str, object]:
        return {
            "schema": _RESOURCE_CATALOG_SCHEMA,
            "dimensions": [item.to_object() for item in self.dimensions],
        }

    @property
    def catalog_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceBoundV0:
    dimension_id: str
    lower: Fraction | int
    upper: Fraction | int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension_id", _stable(self.dimension_id, "dimension_id"))
        lower = _nonnegative_fraction(self.lower, "lower")
        upper = None if self.upper is None else _nonnegative_fraction(self.upper, "upper")
        if upper is not None and upper < lower:
            raise ResourceAlgebraError("upper bound must be >= lower bound")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    @classmethod
    def exact(cls, dimension_id: str, value: Fraction | int) -> "ResourceBoundV0":
        exact = _nonnegative_fraction(value, "exact resource value")
        return cls(dimension_id, exact, exact)

    @classmethod
    def unknown(cls, dimension_id: str, lower: Fraction | int = 0) -> "ResourceBoundV0":
        return cls(dimension_id, lower, None)

    @property
    def known_upper(self) -> bool:
        return self.upper is not None

    @property
    def exact_value(self) -> Fraction | None:
        return self.lower if self.upper == self.lower else None

    def to_object(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "lower": _fraction_object(self.lower),
            "upper": None if self.upper is None else _fraction_object(self.upper),
        }


@dataclass(frozen=True, slots=True)
class ResourceVectorV0:
    bounds: tuple[ResourceBoundV0, ...] = ()
    complete: bool = False
    catalog_hash: str = EMPTY_RESOURCE_CATALOG_HASH

    def __post_init__(self) -> None:
        if not isinstance(self.complete, bool):
            raise ResourceAlgebraError("complete must be bool")
        object.__setattr__(self, "catalog_hash", _hash64(self.catalog_hash, "catalog_hash"))
        ordered = tuple(sorted(self.bounds, key=lambda item: item.dimension_id))
        if len({item.dimension_id for item in ordered}) != len(ordered):
            raise ResourceAlgebraError("duplicate resource bound")
        object.__setattr__(self, "bounds", ordered)

    def validate_against(self, catalog: ResourceCatalogV0) -> None:
        if self.catalog_hash != catalog.catalog_hash:
            raise ResourceAlgebraError("resource vector/catalog identity mismatch")
        vector_dimensions = {item.dimension_id for item in self.bounds}
        catalog_dimensions = set(catalog.dimension_ids)
        extras = vector_dimensions - catalog_dimensions
        if extras:
            raise ResourceAlgebraError(
                "resource vector contains dimensions outside catalog: " + ",".join(sorted(extras))
            )
        if self.complete and vector_dimensions != catalog_dimensions:
            missing = catalog_dimensions - vector_dimensions
            raise ResourceAlgebraError(
                "complete resource vector missing catalog dimensions: " + ",".join(sorted(missing))
            )

    def bound(self, dimension_id: str) -> ResourceBoundV0 | None:
        for item in self.bounds:
            if item.dimension_id == dimension_id:
                return item
        return None

    def effective_bound(self, dimension_id: str) -> ResourceBoundV0:
        explicit = self.bound(dimension_id)
        return explicit if explicit is not None else ResourceBoundV0.unknown(dimension_id)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": _RESOURCE_SCHEMA,
            "catalog_hash": self.catalog_hash,
            "complete": self.complete,
            "bounds": [item.to_object() for item in self.bounds],
        }

    @property
    def vector_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ResourceCeilingV0:
    dimension_id: str
    maximum: Fraction | int
    catalog_hash: str = EMPTY_RESOURCE_CATALOG_HASH

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension_id", _stable(self.dimension_id, "dimension_id"))
        object.__setattr__(self, "maximum", _nonnegative_fraction(self.maximum, "maximum"))
        object.__setattr__(self, "catalog_hash", _hash64(self.catalog_hash, "catalog_hash"))

    def validate_against(self, catalog: ResourceCatalogV0) -> None:
        if self.catalog_hash != catalog.catalog_hash:
            raise ResourceAlgebraError("resource ceiling/catalog identity mismatch")
        if catalog.dimension(self.dimension_id) is None:
            raise ResourceAlgebraError(
                f"resource ceiling dimension {self.dimension_id!r} is outside catalog"
            )

    def to_object(self) -> dict[str, object]:
        return {
            "dimension_id": self.dimension_id,
            "maximum": _fraction_object(self.maximum),
            "catalog_hash": self.catalog_hash,
        }


@dataclass(frozen=True, slots=True)
class ResourceCeilingIssueV0:
    kind: str
    dimension_id: str
    maximum: Fraction
    observed_upper: Fraction | None

    def __post_init__(self) -> None:
        if self.kind not in {"UNKNOWN", "EXCEEDED"}:
            raise ResourceAlgebraError("resource ceiling issue kind")
        object.__setattr__(self, "dimension_id", _stable(self.dimension_id, "dimension_id"))
        object.__setattr__(self, "maximum", _nonnegative_fraction(self.maximum, "maximum"))
        if self.observed_upper is not None:
            object.__setattr__(
                self,
                "observed_upper",
                _nonnegative_fraction(self.observed_upper, "observed_upper"),
            )


def _combine_pair(left: ResourceBoundV0, right: ResourceBoundV0, aggregation: str) -> ResourceBoundV0:
    if left.dimension_id != right.dimension_id:
        raise ResourceAlgebraError("cannot combine different resource dimensions")
    if aggregation == "SUM":
        lower = left.lower + right.lower
        upper = None if left.upper is None or right.upper is None else left.upper + right.upper
        return ResourceBoundV0(left.dimension_id, lower, upper)
    if aggregation == "MAX":
        lower = max(left.lower, right.lower)
        upper = None if left.upper is None or right.upper is None else max(left.upper, right.upper)
        return ResourceBoundV0(left.dimension_id, lower, upper)
    raise ResourceAlgebraError("unsupported aggregation")


def compose_resource_vectors(
    vectors: Iterable[ResourceVectorV0],
    catalog: ResourceCatalogV0,
    *,
    mode: str,
) -> ResourceVectorV0:
    if mode not in _MODES:
        raise ResourceAlgebraError("unsupported composition mode")
    rows = tuple(vectors)
    for vector in rows:
        vector.validate_against(catalog)
    if not rows:
        return ResourceVectorV0(
            tuple(ResourceBoundV0.exact(item.dimension_id, 0) for item in catalog.dimensions),
            complete=True,
            catalog_hash=catalog.catalog_hash,
        )
    result: list[ResourceBoundV0] = []
    for dimension in catalog.dimensions:
        aggregation = dimension.aggregation_for(mode)
        current = rows[0].effective_bound(dimension.dimension_id)
        for vector in rows[1:]:
            current = _combine_pair(
                current,
                vector.effective_bound(dimension.dimension_id),
                aggregation,
            )
        result.append(current)
    return ResourceVectorV0(
        tuple(result),
        complete=True,
        catalog_hash=catalog.catalog_hash,
    )


def validate_resource_ceilings(
    ceilings: Iterable[ResourceCeilingV0],
    catalog: ResourceCatalogV0,
) -> tuple[ResourceCeilingV0, ...]:
    ordered = tuple(sorted(ceilings, key=lambda item: item.dimension_id))
    if len({item.dimension_id for item in ordered}) != len(ordered):
        raise ResourceAlgebraError("duplicate resource ceiling")
    for ceiling in ordered:
        ceiling.validate_against(catalog)
    return ordered


def evaluate_resource_ceilings(
    vector: ResourceVectorV0,
    ceilings: Iterable[ResourceCeilingV0],
) -> tuple[ResourceCeilingIssueV0, ...]:
    issues: list[ResourceCeilingIssueV0] = []
    seen: set[str] = set()
    for ceiling in sorted(ceilings, key=lambda item: item.dimension_id):
        if ceiling.dimension_id in seen:
            raise ResourceAlgebraError("duplicate resource ceiling")
        seen.add(ceiling.dimension_id)
        if ceiling.catalog_hash != vector.catalog_hash:
            raise ResourceAlgebraError("resource ceiling/vector catalog mismatch")
        bound = vector.effective_bound(ceiling.dimension_id)
        if bound.upper is None:
            issues.append(ResourceCeilingIssueV0("UNKNOWN", ceiling.dimension_id, ceiling.maximum, None))
        elif bound.upper > ceiling.maximum:
            issues.append(
                ResourceCeilingIssueV0(
                    "EXCEEDED",
                    ceiling.dimension_id,
                    ceiling.maximum,
                    bound.upper,
                )
            )
    return tuple(issues)


def resource_context_hash(*, machine_hash: str, workload_hash: str, placement_hash: str) -> str:
    return canonical_hash(
        {
            "schema": "TEV_SCRIPT_RESOURCE_CONTEXT_V0",
            "machine_hash": _hash64(machine_hash, "machine_hash"),
            "workload_hash": _hash64(workload_hash, "workload_hash"),
            "placement_hash": _hash64(placement_hash, "placement_hash"),
        }
    )


__all__ = [
    "EMPTY_RESOURCE_CATALOG_HASH",
    "ResourceAlgebraError",
    "ResourceDimensionV0",
    "ResourceCatalogV0",
    "ResourceBoundV0",
    "ResourceVectorV0",
    "ResourceCeilingV0",
    "ResourceCeilingIssueV0",
    "compose_resource_vectors",
    "validate_resource_ceilings",
    "evaluate_resource_ceilings",
    "resource_context_hash",
]
