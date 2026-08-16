from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Sequence

from .canonical import canonical_hash, to_json_value
from .diagnostics import TevScriptError
from .omega_semantic_basis_v1 import (
    FieldTransformationV1,
    SemanticFieldV1,
    apply_field_transformation,
    field_fact,
    semantic_field,
    validate_field_transformation,
    validate_semantic_field,
)

_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_ADMISSION = frozenset({"PASS", "REJECT", "PROOF_REQUIRED"})
_RESOLUTION = frozenset({"SELECTED", "INDETERMINATE", "NO_ADMISSIBLE_REALIZATION"})


@dataclass(frozen=True, slots=True)
class ResidualObstructionV1:
    kind: str
    subject: str
    expected: Any
    observed: Any
    evidence_hash: str | None
    obstruction_hash: str


@dataclass(frozen=True, slots=True)
class ResidualViewV1:
    status: str
    domain: str
    judgment_id: str
    judgment_hash: str
    source_hash: str
    boundary_hash: str
    obstructions: tuple[ResidualObstructionV1, ...]
    residual_hash: str


@dataclass(frozen=True, slots=True)
class ResidualProgressV1:
    classification: str
    boundary_hash: str | None
    resolved: tuple[str, ...]
    persistent: tuple[str, ...]
    introduced: tuple[str, ...]
    progress_hash: str


@dataclass(frozen=True, slots=True)
class DecisionCandidateV1:
    candidate_id: str
    semantic_hash: str
    rank: int
    candidate_hash: str


@dataclass(frozen=True, slots=True)
class AdmissionV1:
    candidate_id: str
    status: str
    evidence_hashes: tuple[str, ...]
    admission_hash: str


@dataclass(frozen=True, slots=True)
class DecisionResultV1:
    status: str
    selected_candidate_id: str | None
    admitted_candidate_ids: tuple[str, ...]
    rejected_candidate_ids: tuple[str, ...]
    open_candidate_ids: tuple[str, ...]
    result_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _stable(value: Any, name: str) -> str:
    if not isinstance(value, str) or _STABLE.fullmatch(value) is None:
        _fail("TEVS_MAX_V3_STDLIB_ID", f"invalid {name}")
    return value


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        _fail("TEVS_MAX_V3_STDLIB_HASH", f"{name} must be lowercase 64-hex")
    return value


def _optional_sha(value: Any, name: str) -> str | None:
    return None if value is None else _sha(value, name)


def _fact_rows(field: SemanticFieldV1, relation: str):
    field = validate_semantic_field(field)
    return tuple(f for f in field.facts if f.relation == relation)


def residual_obstruction(
    kind: str,
    subject: str,
    *,
    expected: Any = None,
    observed: Any = None,
    evidence_hash: str | None = None,
) -> ResidualObstructionV1:
    kind = _stable(kind, "obstruction kind")
    subject = _stable(subject, "obstruction subject")
    evidence = _optional_sha(evidence_hash, "evidence_hash")
    expected = to_json_value(expected)
    observed = to_json_value(observed)
    body = {
        "kind": kind,
        "subject": subject,
        "expected": expected,
        "observed": observed,
        "evidence_hash": evidence,
    }
    return ResidualObstructionV1(kind, subject, expected, observed, evidence, canonical_hash(body))


def residual_field(
    *,
    domain: str,
    judgment_id: str,
    judgment: Any,
    source: Any,
    obstructions: Sequence[ResidualObstructionV1] = (),
    context_hash: str | None = None,
    law_hash: str | None = None,
) -> SemanticFieldV1:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    judgment = to_json_value(judgment)
    source = to_json_value(source)
    context = canonical_hash({"context": "none"}) if context_hash is None else _sha(context_hash, "context_hash")
    law = canonical_hash({"laws": []}) if law_hash is None else _sha(law_hash, "law_hash")
    judgment_hash = canonical_hash({"domain": domain, "judgment_id": judgment_id, "judgment": judgment})
    source_hash = canonical_hash({"source": source})
    boundary_hash = canonical_hash({
        "domain": domain,
        "judgment_hash": judgment_hash,
        "source_hash": source_hash,
        "context_hash": context,
        "law_hash": law,
    })
    rows: dict[str, ResidualObstructionV1] = {}
    for item in obstructions:
        if not isinstance(item, ResidualObstructionV1):
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL", "ResidualObstructionV1 required")
        if item.obstruction_hash in rows:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_DUPLICATE", "duplicate residual obstruction")
        rows[item.obstruction_hash] = item
    status = "CLOSED" if not rows else "OPEN"
    facts = [
        field_fact(
            "tev.std.residual",
            (status, domain, judgment_id, judgment_hash, source_hash, context, law, boundary_hash, len(rows)),
        )
    ]
    for item in rows.values():
        facts.append(field_fact(
            "tev.std.residual.obstruction",
            (item.obstruction_hash, item.kind, item.subject, item.expected, item.observed, item.evidence_hash),
        ))
    return semantic_field(facts, profile="stdlib.residual")


def parse_residual(field: SemanticFieldV1) -> ResidualViewV1:
    field = validate_semantic_field(field)
    roots = _fact_rows(field, "tev.std.residual")
    rows = _fact_rows(field, "tev.std.residual.obstruction")
    if len(roots) != 1 or any(f.relation not in {"tev.std.residual", "tev.std.residual.obstruction"} for f in field.facts):
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_SHAPE", "invalid residual Field surface")
    args = roots[0].arguments
    if len(args) != 9:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_ROOT", "invalid residual root")
    status, domain, judgment_id, judgment_hash, source_hash, context, law, boundary_hash, count = args
    if status not in {"OPEN", "CLOSED"} or not isinstance(count, int) or isinstance(count, bool) or count < 0:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_ROOT", "invalid residual status/count")
    _stable(domain, "domain"); _stable(judgment_id, "judgment_id")
    for value, name in ((judgment_hash, "judgment_hash"), (source_hash, "source_hash"), (context, "context_hash"), (law, "law_hash"), (boundary_hash, "boundary_hash")):
        _sha(value, name)
    parsed: list[ResidualObstructionV1] = []
    for row in rows:
        if len(row.arguments) != 6:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_ROW", "invalid residual obstruction")
        obstruction_hash, kind, subject, expected, observed, evidence = row.arguments
        candidate = residual_obstruction(kind, subject, expected=expected, observed=observed, evidence_hash=evidence)
        if _sha(obstruction_hash, "obstruction_hash") != candidate.obstruction_hash:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_HASH", "obstruction hash mismatch")
        parsed.append(candidate)
    parsed = sorted(parsed, key=lambda item: item.obstruction_hash)
    if len(parsed) != count or (status == "CLOSED") != (count == 0):
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_STATUS", "residual CLOSED iff empty invariant failed")
    return ResidualViewV1(
        status, domain, judgment_id, judgment_hash, source_hash, boundary_hash,
        tuple(parsed), field.field_hash,
    )


def compare_residuals(before: SemanticFieldV1, after: SemanticFieldV1) -> ResidualProgressV1:
    left, right = parse_residual(before), parse_residual(after)
    if left.boundary_hash != right.boundary_hash:
        classification, boundary, resolved, persistent, introduced = "INCOMPARABLE", None, (), (), ()
    else:
        lset = {o.obstruction_hash for o in left.obstructions}
        rset = {o.obstruction_hash for o in right.obstructions}
        resolved = tuple(sorted(lset - rset)); persistent = tuple(sorted(lset & rset)); introduced = tuple(sorted(rset - lset))
        boundary = left.boundary_hash
        if not rset and lset:
            classification = "CLOSED"
        elif rset == lset:
            classification = "UNCHANGED"
        elif rset < lset:
            classification = "REDUCED"
        elif lset < rset:
            classification = "REGRESSED"
        else:
            classification = "CHANGED"
    body = {
        "classification": classification, "boundary_hash": boundary,
        "resolved": list(resolved), "persistent": list(persistent), "introduced": list(introduced),
    }
    return ResidualProgressV1(classification, boundary, resolved, persistent, introduced, canonical_hash(body))


def decision_candidate(candidate_id: str, semantic_hash: str, *, rank: int) -> DecisionCandidateV1:
    candidate_id = _stable(candidate_id, "candidate_id")
    semantic_hash = _sha(semantic_hash, "semantic_hash")
    if isinstance(rank, bool) or not isinstance(rank, int):
        _fail("TEVS_MAX_V3_STDLIB_RANK", "rank must be integer")
    body = {"candidate_id": candidate_id, "semantic_hash": semantic_hash, "rank": rank}
    return DecisionCandidateV1(candidate_id, semantic_hash, rank, canonical_hash(body))


def admission(candidate_id: str, status: str, *, evidence_hashes: Sequence[str] = ()) -> AdmissionV1:
    candidate_id = _stable(candidate_id, "candidate_id")
    if status not in _ADMISSION:
        _fail("TEVS_MAX_V3_STDLIB_ADMISSION", "invalid admission status")
    if isinstance(evidence_hashes, (str, bytes)):
        _fail("TEVS_MAX_V3_STDLIB_EVIDENCE", "evidence hashes must be sequence")
    hashes = tuple(sorted(_sha(v, "evidence_hash") for v in evidence_hashes))
    if len(set(hashes)) != len(hashes):
        _fail("TEVS_MAX_V3_STDLIB_EVIDENCE_DUP", "duplicate evidence hash")
    body = {"candidate_id": candidate_id, "status": status, "evidence_hashes": list(hashes)}
    return AdmissionV1(candidate_id, status, hashes, canonical_hash(body))


def resolve_candidates(
    candidates: Sequence[DecisionCandidateV1],
    admissions: Sequence[AdmissionV1],
) -> DecisionResultV1:
    if isinstance(candidates, (str, bytes)) or isinstance(admissions, (str, bytes)):
        _fail("TEVS_MAX_V3_STDLIB_DECISION", "decision inputs must be sequences")
    cmap: dict[str, DecisionCandidateV1] = {}
    for item in candidates:
        if not isinstance(item, DecisionCandidateV1) or item != decision_candidate(item.candidate_id, item.semantic_hash, rank=item.rank):
            _fail("TEVS_MAX_V3_STDLIB_CANDIDATE", "invalid candidate")
        if item.candidate_id in cmap:
            _fail("TEVS_MAX_V3_STDLIB_CANDIDATE_DUP", "duplicate candidate id")
        cmap[item.candidate_id] = item
    amap: dict[str, AdmissionV1] = {}
    for item in admissions:
        if not isinstance(item, AdmissionV1) or item != admission(item.candidate_id, item.status, evidence_hashes=item.evidence_hashes):
            _fail("TEVS_MAX_V3_STDLIB_ADMISSION", "invalid admission")
        if item.candidate_id in amap:
            _fail("TEVS_MAX_V3_STDLIB_ADMISSION_DUP", "duplicate admission")
        amap[item.candidate_id] = item
    if not cmap or set(cmap) != set(amap):
        _fail("TEVS_MAX_V3_STDLIB_DECISION_DOMAIN", "candidate/admission domains must match and be nonempty")
    passed = tuple(sorted(k for k, v in amap.items() if v.status == "PASS"))
    rejected = tuple(sorted(k for k, v in amap.items() if v.status == "REJECT"))
    opened = tuple(sorted(k for k, v in amap.items() if v.status == "PROOF_REQUIRED"))
    selected: str | None = None
    if opened:
        status = "INDETERMINATE"
    elif not passed:
        status = "NO_ADMISSIBLE_REALIZATION"
    else:
        best_rank = min(cmap[k].rank for k in passed)
        best = tuple(k for k in passed if cmap[k].rank == best_rank)
        if len(best) == 1:
            status, selected = "SELECTED", best[0]
        else:
            status = "INDETERMINATE"
    body = {
        "status": status, "selected_candidate_id": selected,
        "admitted_candidate_ids": list(passed), "rejected_candidate_ids": list(rejected),
        "open_candidate_ids": list(opened),
    }
    return DecisionResultV1(status, selected, passed, rejected, opened, canonical_hash(body))


def decision_field(
    candidates: Sequence[DecisionCandidateV1],
    admissions: Sequence[AdmissionV1],
    result: DecisionResultV1,
) -> SemanticFieldV1:
    expected = resolve_candidates(candidates, admissions)
    if result != expected:
        _fail("TEVS_MAX_V3_STDLIB_DECISION_RESULT", "decision result does not match inputs")
    facts = []
    for item in sorted(candidates, key=lambda x: x.candidate_id):
        facts.append(field_fact("tev.std.candidate", (item.candidate_id, item.semantic_hash, item.rank, item.candidate_hash)))
    for item in sorted(admissions, key=lambda x: x.candidate_id):
        facts.append(field_fact("tev.std.admission", (item.candidate_id, item.status, list(item.evidence_hashes), item.admission_hash)))
    facts.append(field_fact("tev.std.resolution", (result.status, result.selected_candidate_id, result.result_hash)))
    if result.status == "SELECTED":
        facts.append(field_fact("tev.std.selection", (result.selected_candidate_id, result.result_hash)))
    return semantic_field(facts, profile="stdlib.decision")


def closure_residual(expected: SemanticFieldV1, recovered: SemanticFieldV1) -> SemanticFieldV1:
    expected, recovered = validate_semantic_field(expected), validate_semantic_field(recovered)
    e = {f.fact_hash for f in expected.facts}; r = {f.fact_hash for f in recovered.facts}
    obstructions = [
        *(() if expected.profile == recovered.profile else (
            residual_obstruction(
                "profile.mismatch", "field.profile",
                expected=expected.profile, observed=recovered.profile,
            ),
        )),
        *(residual_obstruction("missing.fact", h, expected=True, observed=False) for h in sorted(e - r)),
        *(residual_obstruction("unexpected.fact", h, expected=False, observed=True) for h in sorted(r - e)),
    ]
    return residual_field(
        domain="discovery_realization", judgment_id="field_equivalence",
        judgment={"expected_field_hash": expected.field_hash, "recovered_field_hash": recovered.field_hash},
        source={"expected_profile": expected.profile, "recovered_profile": recovered.profile},
        obstructions=obstructions,
    )


def discovery_realization_closure(
    theory: SemanticFieldV1,
    realization: FieldTransformationV1,
    discovery: FieldTransformationV1,
) -> tuple[SemanticFieldV1, SemanticFieldV1]:
    theory = validate_semantic_field(theory)
    realization = validate_field_transformation(realization)
    discovery = validate_field_transformation(discovery)
    world, rr = apply_field_transformation(theory, realization)
    if rr.status != "PASS":
        _fail("TEVS_MAX_V3_STDLIB_REALIZATION_OPEN", "realization requires unresolved proof")
    recovered, dr = apply_field_transformation(world, discovery)
    if dr.status != "PASS":
        _fail("TEVS_MAX_V3_STDLIB_DISCOVERY_OPEN", "discovery requires unresolved proof")
    cycle = semantic_field((field_fact(
        "tev.std.discovery_realization",
        (theory.field_hash, realization.transformation_hash, world.field_hash,
         discovery.transformation_hash, recovered.field_hash, False),
    ),), profile="stdlib.discovery_realization")
    return cycle, closure_residual(theory, recovered)


__all__ = [
    "AdmissionV1", "DecisionCandidateV1", "DecisionResultV1",
    "ResidualObstructionV1", "ResidualProgressV1", "ResidualViewV1",
    "admission", "closure_residual", "compare_residuals", "decision_candidate",
    "decision_field", "discovery_realization_closure", "parse_residual",
    "residual_field", "residual_obstruction", "resolve_candidates",
]
