from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import FactV0, META_RELATION, SemanticFieldV0

RESIDUAL_PROFILE_V0 = "TEV_SCRIPT_SEMANTIC_RESIDUAL_V0"
RESIDUAL_JUDGMENT_SCHEMA_V0 = "TEV_SCRIPT_RESIDUAL_JUDGMENT_V0"
RESIDUAL_SOURCE_SCHEMA_V0 = "TEV_SCRIPT_RESIDUAL_SOURCE_V0"
RESIDUAL_PROGRESS_SCHEMA_V0 = "TEV_SCRIPT_RESIDUAL_PROGRESS_V0"
RESIDUAL_DECLS_V0 = (("tev.residual", 11), ("tev.residual.obstruction", 9))
DEFAULT_RESIDUAL_CONTEXT_HASH = canonical_hash(
    {"schema": "TEV_SCRIPT_SEMANTIC_CONTEXT_V0", "center": "none"}
)
DEFAULT_RESIDUAL_LAW_HASH = canonical_hash(
    {"schema": "TEV_SCRIPT_SEMANTIC_LAW_CONTEXT_V0", "laws": []}
)
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_PROGRESS = frozenset({"CLOSED", "REDUCED", "UNCHANGED", "REGRESSED", "CHANGED", "INCOMPARABLE"})


class SemanticResidualError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise SemanticResidualError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(ch not in _HEX for ch in text):
        raise SemanticResidualError(what)
    return text


def _refs(values: Iterable[str]) -> tuple[str, ...]:
    out = tuple(sorted(set(str(value) for value in values)))
    if any(not value for value in out):
        raise SemanticResidualError("dependency reference")
    return out


@dataclass(frozen=True, slots=True)
class ResidualObstructionV0:
    """One judgment-relevant obstruction. DTO only; canonical authority is the Residual Field."""

    kind: str
    subject: str
    expected: Any = None
    observed: Any = None
    detail: Mapping[str, Any] | None = None
    evidence_hash: str = ""
    dependency_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "obstruction kind"))
        subject = str(self.subject)
        if not subject:
            raise SemanticResidualError("obstruction subject")
        object.__setattr__(self, "subject", subject)
        canonical_json(self.expected)
        canonical_json(self.observed)
        detail = {} if self.detail is None else dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)
        evidence_hash = str(self.evidence_hash)
        if evidence_hash:
            _hash64(evidence_hash, "evidence_hash")
        object.__setattr__(self, "evidence_hash", evidence_hash)
        object.__setattr__(self, "dependency_refs", _refs(self.dependency_refs))

    def to_object(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "expected": self.expected,
            "observed": self.observed,
            "detail": dict(self.detail or {}),
            "evidence_hash": self.evidence_hash,
            "dependency_refs": list(self.dependency_refs),
        }

    @property
    def obstruction_hash(self) -> str:
        return canonical_hash({"schema": "TEV_SCRIPT_RESIDUAL_OBSTRUCTION_V0", **self.to_object()})


@dataclass(frozen=True, slots=True)
class ResidualViewV0:
    status: str
    domain: str
    judgment_id: str
    judgment_hash: str
    judgment: Any
    source_hash: str
    source: Any
    context_hash: str
    law_hash: str
    obstructions: tuple[ResidualObstructionV0, ...]

    @property
    def closed(self) -> bool:
        return self.status == "CLOSED"

    @property
    def obstruction_hashes(self) -> tuple[str, ...]:
        return tuple(item.obstruction_hash for item in self.obstructions)

    @property
    def boundary_hash(self) -> str:
        return canonical_hash(
            {
                "schema": "TEV_SCRIPT_RESIDUAL_BOUNDARY_V0",
                "domain": self.domain,
                "judgment_hash": self.judgment_hash,
                "context_hash": self.context_hash,
                "law_hash": self.law_hash,
            }
        )


@dataclass(frozen=True, slots=True)
class ResidualProgressV0:
    classification: str
    before_residual_hash: str
    after_residual_hash: str
    boundary_hash: str
    resolved: tuple[str, ...]
    persistent: tuple[str, ...]
    introduced: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.classification not in _PROGRESS:
            raise SemanticResidualError("progress classification")
        _hash64(self.before_residual_hash, "before_residual_hash")
        _hash64(self.after_residual_hash, "after_residual_hash")
        _hash64(self.boundary_hash, "boundary_hash")
        for name, values in (("resolved", self.resolved), ("persistent", self.persistent), ("introduced", self.introduced)):
            canonical = tuple(sorted(set(_hash64(value, name) for value in values)))
            object.__setattr__(self, name, canonical)

    def to_object(self) -> dict[str, Any]:
        return {
            "schema": RESIDUAL_PROGRESS_SCHEMA_V0,
            "classification": self.classification,
            "before_residual_hash": self.before_residual_hash,
            "after_residual_hash": self.after_residual_hash,
            "boundary_hash": self.boundary_hash,
            "resolved": list(self.resolved),
            "persistent": list(self.persistent),
            "introduced": list(self.introduced),
        }

    @property
    def progress_hash(self) -> str:
        return canonical_hash(self.to_object())


def residual_judgment_hash(domain: str, judgment_id: str, judgment: Any) -> str:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    canonical_json(judgment)
    return canonical_hash(
        {
            "schema": RESIDUAL_JUDGMENT_SCHEMA_V0,
            "domain": domain,
            "judgment_id": judgment_id,
            "judgment": judgment,
        }
    )


def residual_source_hash(source: Any) -> str:
    canonical_json(source)
    return canonical_hash({"schema": RESIDUAL_SOURCE_SCHEMA_V0, "source": source})


def _canonical_obstructions(obstructions: Iterable[ResidualObstructionV0]) -> tuple[ResidualObstructionV0, ...]:
    unique: dict[str, ResidualObstructionV0] = {}
    for obstruction in obstructions:
        if not isinstance(obstruction, ResidualObstructionV0):
            raise TypeError("ResidualObstructionV0 required")
        unique[obstruction.obstruction_hash] = obstruction
    return tuple(unique[key] for key in sorted(unique))


def residual_from_obstructions(
    *,
    domain: str,
    judgment_id: str,
    judgment: Any,
    source: Any,
    obstructions: Iterable[ResidualObstructionV0] = (),
    context_hash: str = DEFAULT_RESIDUAL_CONTEXT_HASH,
    law_hash: str = DEFAULT_RESIDUAL_LAW_HASH,
) -> SemanticFieldV0:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    context_hash = _hash64(context_hash, "context_hash")
    law_hash = _hash64(law_hash, "law_hash")
    canonical_json(judgment)
    canonical_json(source)
    rows = _canonical_obstructions(obstructions)
    status = "CLOSED" if not rows else "OPEN"
    judgment_hash = residual_judgment_hash(domain, judgment_id, judgment)
    source_hash = residual_source_hash(source)
    facts: list[FactV0] = [
        FactV0(
            "tev.residual",
            (
                RESIDUAL_PROFILE_V0,
                status,
                domain,
                judgment_id,
                judgment_hash,
                canonical_json(judgment),
                source_hash,
                canonical_json(source),
                context_hash,
                law_hash,
                len(rows),
            ),
        )
    ]
    for index, row in enumerate(rows):
        facts.append(
            FactV0(
                "tev.residual.obstruction",
                (
                    index,
                    row.obstruction_hash,
                    row.kind,
                    row.subject,
                    canonical_json(row.expected),
                    canonical_json(row.observed),
                    canonical_json(dict(row.detail or {})),
                    row.evidence_hash,
                    canonical_json(list(row.dependency_refs)),
                ),
            )
        )
    return SemanticFieldV0.build(RESIDUAL_DECLS_V0, facts)


def parse_residual(field: SemanticFieldV0) -> ResidualViewV0:
    if set(field.declarations) != set(RESIDUAL_DECLS_V0):
        raise SemanticResidualError("residual declaration surface")
    if any(
        f.relation not in {META_RELATION, "tev.residual", "tev.residual.obstruction"}
        for f in field.facts
    ):
        raise SemanticResidualError("residual relation surface")
    roots = field.facts_for("tev.residual")
    if len(roots) != 1:
        raise SemanticResidualError("exactly one tev.residual required")
    (
        profile,
        status,
        domain,
        judgment_id,
        judgment_hash,
        judgment_json,
        source_hash,
        source_json,
        context_hash,
        law_hash,
        count,
    ) = roots[0].arguments
    if str(profile) != RESIDUAL_PROFILE_V0:
        raise SemanticResidualError("residual profile")
    if str(status) not in {"OPEN", "CLOSED"}:
        raise SemanticResidualError("residual status")
    domain = _stable(str(domain), "domain")
    judgment_id = _stable(str(judgment_id), "judgment_id")
    judgment_hash = _hash64(str(judgment_hash), "judgment_hash")
    source_hash = _hash64(str(source_hash), "source_hash")
    context_hash = _hash64(str(context_hash), "context_hash")
    law_hash = _hash64(str(law_hash), "law_hash")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise SemanticResidualError("obstruction count")
    judgment = json.loads(str(judgment_json))
    source = json.loads(str(source_json))
    if canonical_json(judgment) != str(judgment_json):
        raise SemanticResidualError("judgment JSON not canonical")
    if canonical_json(source) != str(source_json):
        raise SemanticResidualError("source JSON not canonical")
    if residual_judgment_hash(domain, judgment_id, judgment) != judgment_hash:
        raise SemanticResidualError("judgment hash mismatch")
    if residual_source_hash(source) != source_hash:
        raise SemanticResidualError("source hash mismatch")
    rows = sorted(field.facts_for("tev.residual.obstruction"), key=lambda fact: int(fact.arguments[0]))
    if len(rows) != count or [int(row.arguments[0]) for row in rows] != list(range(count)):
        raise SemanticResidualError("obstruction index/count mismatch")
    obstructions: list[ResidualObstructionV0] = []
    previous_hash = ""
    for row in rows:
        (
            _, obstruction_hash, kind, subject, expected_json, observed_json,
            detail_json, evidence_hash, dependency_json,
        ) = row.arguments
        expected = json.loads(str(expected_json))
        observed = json.loads(str(observed_json))
        detail = json.loads(str(detail_json))
        dependencies = tuple(json.loads(str(dependency_json)))
        if canonical_json(expected) != str(expected_json):
            raise SemanticResidualError("expected JSON not canonical")
        if canonical_json(observed) != str(observed_json):
            raise SemanticResidualError("observed JSON not canonical")
        if canonical_json(detail) != str(detail_json):
            raise SemanticResidualError("detail JSON not canonical")
        if canonical_json(list(_refs(dependencies))) != str(dependency_json):
            raise SemanticResidualError("dependency refs not canonical")
        obstruction = ResidualObstructionV0(
            str(kind), str(subject), expected, observed, detail, str(evidence_hash), dependencies
        )
        observed_hash = _hash64(str(obstruction_hash), "obstruction_hash")
        if obstruction.obstruction_hash != observed_hash:
            raise SemanticResidualError("obstruction hash mismatch")
        if previous_hash and observed_hash <= previous_hash:
            raise SemanticResidualError("obstruction order not canonical")
        previous_hash = observed_hash
        obstructions.append(obstruction)
    if (str(status) == "CLOSED") != (count == 0):
        raise SemanticResidualError("status/count mismatch")
    return ResidualViewV0(
        str(status), domain, judgment_id, judgment_hash, judgment,
        source_hash, source, context_hash, law_hash, tuple(obstructions)
    )


def is_residual_field(field: SemanticFieldV0) -> bool:
    try:
        parse_residual(field)
        return True
    except (SemanticResidualError, ValueError, TypeError, json.JSONDecodeError):
        return False


def residual_closed(field: SemanticFieldV0) -> bool:
    return parse_residual(field).closed


def residualize_fields(
    observed: SemanticFieldV0,
    required: SemanticFieldV0,
    *,
    judgment_id: str,
    domain: str = "semantic",
    context_hash: str = DEFAULT_RESIDUAL_CONTEXT_HASH,
    law_hash: str = DEFAULT_RESIDUAL_LAW_HASH,
) -> SemanticFieldV0:
    obstructions: list[ResidualObstructionV0] = []
    for expected_fact in required.facts:
        if expected_fact.relation == META_RELATION:
            continue
        if observed.has(expected_fact.relation, expected_fact.arguments):
            continue
        candidates = observed.facts_for(expected_fact.relation)
        if candidates:
            kind = "semantic.value_mismatch"
            observed_value: Any = [list(candidate.arguments) for candidate in candidates]
        else:
            kind = "semantic.missing_fact"
            observed_value = None
        obstructions.append(
            ResidualObstructionV0(
                kind=kind,
                subject=expected_fact.relation,
                expected=list(expected_fact.arguments),
                observed=observed_value,
                detail={"required_fact_hash": expected_fact.fact_hash},
                dependency_refs=(required.field_hash,),
            )
        )
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={"kind": "field_requirement", "required_field_hash": required.field_hash},
        source={"kind": "semantic_field", "field_hash": observed.field_hash},
        obstructions=obstructions,
        context_hash=context_hash,
        law_hash=law_hash,
    )


def join_residuals(
    residuals: Iterable[SemanticFieldV0],
    *,
    source_kind: str = "residual_join",
) -> SemanticFieldV0:
    values = tuple(residuals)
    if not values:
        raise SemanticResidualError("join requires residuals")
    views = tuple(parse_residual(value) for value in values)
    first = views[0]
    if any(view.boundary_hash != first.boundary_hash for view in views[1:]):
        raise SemanticResidualError("join boundary mismatch")
    rows = tuple(item for view in views for item in view.obstructions)
    return residual_from_obstructions(
        domain=first.domain,
        judgment_id=first.judgment_id,
        judgment=first.judgment,
        source={"kind": source_kind, "child_residual_hashes": sorted(value.field_hash for value in values)},
        obstructions=rows,
        context_hash=first.context_hash,
        law_hash=first.law_hash,
    )


def aggregate_residuals(
    residuals: Iterable[SemanticFieldV0],
    *,
    judgment_id: str,
    domain: str = "aggregate",
    context_hash: str = DEFAULT_RESIDUAL_CONTEXT_HASH,
    law_hash: str = DEFAULT_RESIDUAL_LAW_HASH,
) -> SemanticFieldV0:
    values = tuple(residuals)
    views = tuple(parse_residual(field) for field in values)
    obstructions: list[ResidualObstructionV0] = []
    for view, field in sorted(zip(views, values), key=lambda item: item[1].field_hash):
        if view.closed:
            continue
        obstructions.append(
            ResidualObstructionV0(
                kind="aggregate.child_residual_open",
                subject=view.domain,
                expected="CLOSED",
                observed=view.status,
                detail={
                    "child_residual_hash": field.field_hash,
                    "child_judgment_hash": view.judgment_hash,
                    "child_boundary_hash": view.boundary_hash,
                    "obstruction_count": len(view.obstructions),
                },
                dependency_refs=(field.field_hash,),
            )
        )
    children = sorted(field.field_hash for field in values)
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={"kind": "aggregate_closure", "children": children},
        source={"kind": "residual_aggregate", "child_residual_hashes": children},
        obstructions=obstructions,
        context_hash=context_hash,
        law_hash=law_hash,
    )


def residual_progress(before: SemanticFieldV0, after: SemanticFieldV0) -> ResidualProgressV0:
    b = parse_residual(before)
    a = parse_residual(after)
    if a.boundary_hash != b.boundary_hash:
        return ResidualProgressV0(
            "INCOMPARABLE", before.field_hash, after.field_hash,
            canonical_hash({"schema": "TEV_SCRIPT_RESIDUAL_INCOMPARABLE_V0", "before": b.boundary_hash, "after": a.boundary_hash}),
            (), (), (),
        )
    before_set = set(b.obstruction_hashes)
    after_set = set(a.obstruction_hashes)
    resolved = tuple(sorted(before_set - after_set))
    persistent = tuple(sorted(before_set & after_set))
    introduced = tuple(sorted(after_set - before_set))
    if before_set and not after_set:
        classification = "CLOSED"
    elif before_set == after_set:
        classification = "UNCHANGED"
    elif after_set < before_set:
        classification = "REDUCED"
    elif before_set < after_set:
        classification = "REGRESSED"
    else:
        classification = "CHANGED"
    return ResidualProgressV0(
        classification, before.field_hash, after.field_hash, b.boundary_hash,
        resolved, persistent, introduced,
    )


def residual_strictly_refines(after: SemanticFieldV0, before: SemanticFieldV0) -> bool:
    progress = residual_progress(before, after)
    return progress.classification in {"REDUCED", "CLOSED"}


def residual_obstructions(
    field: SemanticFieldV0,
    *,
    kinds: Iterable[str] | None = None,
    subjects: Iterable[str] | None = None,
    dependency_refs: Iterable[str] | None = None,
) -> tuple[ResidualObstructionV0, ...]:
    view = parse_residual(field)
    kind_set = None if kinds is None else set(str(value) for value in kinds)
    subject_set = None if subjects is None else set(str(value) for value in subjects)
    dependency_set = None if dependency_refs is None else set(str(value) for value in dependency_refs)
    return tuple(
        item
        for item in view.obstructions
        if (kind_set is None or item.kind in kind_set)
        and (subject_set is None or item.subject in subject_set)
        and (dependency_set is None or dependency_set.intersection(item.dependency_refs))
    )


def residual_dependency_refs(field: SemanticFieldV0) -> tuple[str, ...]:
    return tuple(sorted({ref for item in parse_residual(field).obstructions for ref in item.dependency_refs}))


__all__ = [
    "RESIDUAL_PROFILE_V0", "RESIDUAL_JUDGMENT_SCHEMA_V0", "RESIDUAL_SOURCE_SCHEMA_V0",
    "RESIDUAL_PROGRESS_SCHEMA_V0", "RESIDUAL_DECLS_V0",
    "DEFAULT_RESIDUAL_CONTEXT_HASH", "DEFAULT_RESIDUAL_LAW_HASH",
    "SemanticResidualError", "ResidualObstructionV0", "ResidualViewV0", "ResidualProgressV0",
    "residual_judgment_hash", "residual_source_hash", "residual_from_obstructions",
    "parse_residual", "is_residual_field", "residual_closed", "residualize_fields",
    "join_residuals", "aggregate_residuals", "residual_progress", "residual_strictly_refines",
    "residual_obstructions", "residual_dependency_refs",
]
