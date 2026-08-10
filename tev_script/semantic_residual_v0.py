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
RESIDUAL_DECLS_V0 = (("tev.residual", 8), ("tev.residual.obstruction", 7))
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")

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

@dataclass(frozen=True, slots=True)
class ResidualObstructionV0:
    kind: str
    subject: str
    expected: Any = None
    observed: Any = None
    detail: Mapping[str, Any] | None = None
    evidence_hash: str = ""

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

    def to_object(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "expected": self.expected,
            "observed": self.observed,
            "detail": dict(self.detail or {}),
            "evidence_hash": self.evidence_hash,
        }

@dataclass(frozen=True, slots=True)
class ResidualViewV0:
    status: str
    domain: str
    judgment_id: str
    judgment_hash: str
    judgment: Any
    source_hash: str
    obstructions: tuple[ResidualObstructionV0, ...]

    @property
    def closed(self) -> bool:
        return self.status == "CLOSED"

def residual_judgment_hash(domain: str, judgment_id: str, judgment: Any) -> str:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    canonical_json(judgment)
    return canonical_hash({
        "schema": RESIDUAL_JUDGMENT_SCHEMA_V0,
        "domain": domain,
        "judgment_id": judgment_id,
        "judgment": judgment,
    })

def residual_source_hash(source: Any) -> str:
    canonical_json(source)
    return canonical_hash({"schema": RESIDUAL_SOURCE_SCHEMA_V0, "source": source})

def _canonical_obstructions(obstructions: Iterable[ResidualObstructionV0]) -> tuple[ResidualObstructionV0, ...]:
    unique: dict[str, ResidualObstructionV0] = {}
    for obstruction in obstructions:
        if not isinstance(obstruction, ResidualObstructionV0):
            raise TypeError("ResidualObstructionV0 required")
        unique[canonical_json(obstruction.to_object())] = obstruction
    return tuple(unique[key] for key in sorted(unique))

def residual_from_obstructions(
    *,
    domain: str,
    judgment_id: str,
    judgment: Any,
    source: Any,
    obstructions: Iterable[ResidualObstructionV0] = (),
) -> SemanticFieldV0:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    canonical_json(judgment)
    canonical_json(source)
    rows = _canonical_obstructions(obstructions)
    status = "CLOSED" if not rows else "OPEN"
    judgment_hash = residual_judgment_hash(domain, judgment_id, judgment)
    source_hash = residual_source_hash(source)
    facts: list[FactV0] = [
        FactV0("tev.residual", (
            RESIDUAL_PROFILE_V0,
            status,
            domain,
            judgment_id,
            judgment_hash,
            canonical_json(judgment),
            source_hash,
            len(rows),
        ))
    ]
    for index, row in enumerate(rows):
        facts.append(FactV0("tev.residual.obstruction", (
            index,
            row.kind,
            row.subject,
            canonical_json(row.expected),
            canonical_json(row.observed),
            canonical_json(dict(row.detail or {})),
            row.evidence_hash,
        )))
    return SemanticFieldV0.build(RESIDUAL_DECLS_V0, facts)

def parse_residual(field: SemanticFieldV0) -> ResidualViewV0:
    if set(field.declarations) != set(RESIDUAL_DECLS_V0):
        raise SemanticResidualError("residual declaration surface")
    if any(f.relation not in {META_RELATION, "tev.residual", "tev.residual.obstruction"} for f in field.facts):
        raise SemanticResidualError("residual relation surface")
    roots = field.facts_for("tev.residual")
    if len(roots) != 1:
        raise SemanticResidualError("exactly one tev.residual required")
    profile, status, domain, judgment_id, judgment_hash, judgment_json, source_hash, count = roots[0].arguments
    if str(profile) != RESIDUAL_PROFILE_V0:
        raise SemanticResidualError("residual profile")
    if str(status) not in {"OPEN", "CLOSED"}:
        raise SemanticResidualError("residual status")
    domain = _stable(str(domain), "domain")
    judgment_id = _stable(str(judgment_id), "judgment_id")
    judgment_hash = _hash64(str(judgment_hash), "judgment_hash")
    source_hash = _hash64(str(source_hash), "source_hash")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise SemanticResidualError("obstruction count")
    judgment = json.loads(str(judgment_json))
    if residual_judgment_hash(domain, judgment_id, judgment) != judgment_hash:
        raise SemanticResidualError("judgment hash mismatch")
    rows = sorted(field.facts_for("tev.residual.obstruction"), key=lambda fact: int(fact.arguments[0]))
    if len(rows) != count or [int(row.arguments[0]) for row in rows] != list(range(count)):
        raise SemanticResidualError("obstruction index/count mismatch")
    obstructions = []
    for row in rows:
        _, kind, subject, expected_json, observed_json, detail_json, evidence_hash = row.arguments
        obstructions.append(ResidualObstructionV0(
            str(kind),
            str(subject),
            json.loads(str(expected_json)),
            json.loads(str(observed_json)),
            json.loads(str(detail_json)),
            str(evidence_hash),
        ))
    if (str(status) == "CLOSED") != (count == 0):
        raise SemanticResidualError("status/count mismatch")
    return ResidualViewV0(str(status), domain, judgment_id, judgment_hash, judgment, source_hash, tuple(obstructions))

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
) -> SemanticFieldV0:
    obstructions: list[ResidualObstructionV0] = []
    for expected_fact in required.facts:
        if expected_fact.relation == META_RELATION:
            continue
        if observed.has(expected_fact.relation, expected_fact.arguments):
            continue
        candidates = observed.facts_for(expected_fact.relation)
        if candidates:
            kind = "value_mismatch"
            observed_value: Any = [list(candidate.arguments) for candidate in candidates]
        else:
            kind = "missing_fact"
            observed_value = None
        obstructions.append(ResidualObstructionV0(
            kind=kind,
            subject=expected_fact.relation,
            expected=list(expected_fact.arguments),
            observed=observed_value,
            detail={"required_fact_hash": expected_fact.fact_hash},
        ))
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={"kind": "field_requirement", "required_field_hash": required.field_hash},
        source={"kind": "semantic_field", "field_hash": observed.field_hash},
        obstructions=obstructions,
    )

def aggregate_residuals(
    residuals: Iterable[SemanticFieldV0],
    *,
    judgment_id: str,
    domain: str = "aggregate",
) -> SemanticFieldV0:
    residuals = tuple(residuals)
    views = tuple(parse_residual(field) for field in residuals)
    obstructions = []
    for view, field in sorted(zip(views, residuals), key=lambda item: item[1].field_hash):
        if view.closed:
            continue
        obstructions.append(ResidualObstructionV0(
            kind="child_residual_open",
            subject=view.domain,
            expected="CLOSED",
            observed=view.status,
            detail={
                "child_residual_hash": field.field_hash,
                "child_judgment_hash": view.judgment_hash,
                "obstruction_count": len(view.obstructions),
            },
        ))
    children = [field.field_hash for field in residuals]
    return residual_from_obstructions(
        domain=domain,
        judgment_id=judgment_id,
        judgment={"kind": "aggregate_closure", "children": sorted(children)},
        source={"child_residual_hashes": sorted(children)},
        obstructions=obstructions,
    )

__all__ = [
    "RESIDUAL_PROFILE_V0", "RESIDUAL_JUDGMENT_SCHEMA_V0", "RESIDUAL_SOURCE_SCHEMA_V0",
    "SemanticResidualError", "ResidualObstructionV0", "ResidualViewV0",
    "residual_judgment_hash", "residual_source_hash", "residual_from_obstructions",
    "parse_residual", "is_residual_field", "residual_closed", "residualize_fields",
    "aggregate_residuals",
]
