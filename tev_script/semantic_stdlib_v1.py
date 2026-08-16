from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .canonical import canonical_hash, canonical_json
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

RESIDUAL_PROFILE = "semantic_stdlib.residual"
DECISION_PROFILE = "semantic_stdlib.decision"
DISCOVERY_REALIZATION_PROFILE = "semantic_stdlib.discovery_realization"
_PROGRESS = frozenset({"CLOSED", "REDUCED", "UNCHANGED", "REGRESSED", "CHANGED", "INCOMPARABLE"})
_ADMISSION_STATUSES = frozenset({"PASS", "PROOF_REQUIRED", "REJECT"})
_DECISION_STATUSES = frozenset({"SELECTED", "INDETERMINATE", "NO_ADMISSIBLE_REALIZATION"})
_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True, slots=True)
class ResidualObstructionV1:
    kind: str
    subject: str
    expected: Any
    observed: Any
    obstruction_hash: str


@dataclass(frozen=True, slots=True)
class ResidualViewV1:
    status: str
    domain: str
    judgment_id: str
    boundary_hash: str
    judgment_hash: str
    source_hash: str
    obstructions: tuple[ResidualObstructionV1, ...]
    residual_hash: str


@dataclass(frozen=True, slots=True)
class ResidualProgressV1:
    classification: str
    before_residual_hash: str
    after_residual_hash: str
    boundary_hash: str
    resolved: tuple[str, ...]
    persistent: tuple[str, ...]
    introduced: tuple[str, ...]
    progress_hash: str


@dataclass(frozen=True, slots=True)
class DecisionCandidateV1:
    candidate_id: str
    candidate_hash: str
    rank: int
    candidate_record_hash: str


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
    considered_candidate_ids: tuple[str, ...]
    result_hash: str


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        _fail("TEVS_MAX_V3_STDLIB_HASH", f"{name} must be lowercase 64-hex")
    return value


def _stable(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("TEVS_MAX_V3_STDLIB_ID", f"{name} must be non-empty text")
    if any(ch.isspace() for ch in value):
        _fail("TEVS_MAX_V3_STDLIB_ID", f"{name} must not contain whitespace")
    return value


def residual_obstruction(
    kind: str,
    subject: str,
    *,
    expected: Any = None,
    observed: Any = None,
) -> ResidualObstructionV1:
    kind = _stable(kind, "obstruction kind")
    subject = _stable(subject, "obstruction subject")
    try:
        expected_json = canonical_json(expected)
        observed_json = canonical_json(observed)
    except (TypeError, ValueError) as error:
        _fail("TEVS_MAX_V3_STDLIB_CANONICAL", str(error))
    body = {
        "kind": kind,
        "subject": subject,
        "expected": expected_json,
        "observed": observed_json,
    }
    return ResidualObstructionV1(kind, subject, expected, observed, canonical_hash(body))


def _canonical_obstructions(values: Sequence[ResidualObstructionV1]) -> tuple[ResidualObstructionV1, ...]:
    if isinstance(values, (str, bytes)):
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL", "obstructions must be a sequence")
    checked: list[ResidualObstructionV1] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, ResidualObstructionV1):
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL", "ResidualObstructionV1 required")
        expected = residual_obstruction(value.kind, value.subject, expected=value.expected, observed=value.observed)
        if expected != value:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL", "obstruction identity mismatch")
        if value.obstruction_hash in seen:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL", "duplicate obstruction")
        seen.add(value.obstruction_hash)
        checked.append(value)
    return tuple(sorted(checked, key=lambda item: item.obstruction_hash))


def _residual_boundary(domain: str, judgment_id: str, judgment: Any, source: Any) -> tuple[str, str, str]:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    try:
        judgment_hash = canonical_hash({"schema": "TEV_SCRIPT_MAX_V3_STDLIB_JUDGMENT_V1", "judgment": judgment})
        source_hash = canonical_hash({"schema": "TEV_SCRIPT_MAX_V3_STDLIB_SOURCE_V1", "source": source})
    except (TypeError, ValueError) as error:
        _fail("TEVS_MAX_V3_STDLIB_CANONICAL", str(error))
    boundary_hash = canonical_hash(
        {
            "schema": "TEV_SCRIPT_MAX_V3_STDLIB_RESIDUAL_BOUNDARY_V1",
            "domain": domain,
            "judgment_id": judgment_id,
            "judgment_hash": judgment_hash,
            "source_hash": source_hash,
        }
    )
    return boundary_hash, judgment_hash, source_hash


def residual_field(
    *,
    domain: str,
    judgment_id: str,
    judgment: Any,
    source: Any,
    obstructions: Sequence[ResidualObstructionV1] = (),
) -> SemanticFieldV1:
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    rows = _canonical_obstructions(obstructions)
    boundary_hash, judgment_hash, source_hash = _residual_boundary(domain, judgment_id, judgment, source)
    status = "CLOSED" if not rows else "OPEN"
    root = field_fact(
        "tev.std.residual",
        (
            status,
            domain,
            judgment_id,
            boundary_hash,
            judgment_hash,
            source_hash,
            canonical_json(judgment),
            canonical_json(source),
            len(rows),
        ),
    )
    facts = [root]
    for row in rows:
        facts.append(
            field_fact(
                "tev.std.residual.obstruction",
                (
                    row.obstruction_hash,
                    row.kind,
                    row.subject,
                    canonical_json(row.expected),
                    canonical_json(row.observed),
                ),
            )
        )
    return semantic_field(tuple(facts), profile=RESIDUAL_PROFILE)


def parse_residual(field: SemanticFieldV1) -> ResidualViewV1:
    current = validate_semantic_field(field)
    if current.profile != RESIDUAL_PROFILE:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_PROFILE", "not a residual Field")
    roots = [fact for fact in current.facts if fact.relation == "tev.std.residual"]
    rows = [fact for fact in current.facts if fact.relation == "tev.std.residual.obstruction"]
    if len(roots) != 1 or len(roots[0].arguments) != 9:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_ROOT", "malformed residual root")
    root = roots[0]
    status, domain, judgment_id, boundary_hash, judgment_hash, source_hash, judgment_json, source_json, count = root.arguments
    if status not in {"OPEN", "CLOSED"}:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_STATUS", "invalid residual status")
    domain = _stable(domain, "domain")
    judgment_id = _stable(judgment_id, "judgment_id")
    boundary_hash = _sha(boundary_hash, "boundary_hash")
    judgment_hash = _sha(judgment_hash, "judgment_hash")
    source_hash = _sha(source_hash, "source_hash")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0 or len(rows) != count:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_COUNT", "residual obstruction count mismatch")
    import json
    try:
        judgment = json.loads(str(judgment_json))
        source = json.loads(str(source_json))
    except json.JSONDecodeError as error:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_JSON", str(error))
    expected_boundary, expected_judgment_hash, expected_source_hash = _residual_boundary(domain, judgment_id, judgment, source)
    if (expected_boundary, expected_judgment_hash, expected_source_hash) != (boundary_hash, judgment_hash, source_hash):
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_BOUNDARY", "residual boundary identity mismatch")
    obstructions: list[ResidualObstructionV1] = []
    for fact in rows:
        if len(fact.arguments) != 5:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_ROW", "malformed residual obstruction")
        obstruction_hash, kind, subject, expected_json, observed_json = fact.arguments
        try:
            expected_value = json.loads(str(expected_json))
            observed_value = json.loads(str(observed_json))
        except json.JSONDecodeError as error:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_JSON", str(error))
        obstruction = residual_obstruction(str(kind), str(subject), expected=expected_value, observed=observed_value)
        if _sha(obstruction_hash, "obstruction_hash") != obstruction.obstruction_hash:
            _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_OBSTRUCTION_HASH", "obstruction hash mismatch")
        obstructions.append(obstruction)
    ordered = _canonical_obstructions(tuple(obstructions))
    if status == "CLOSED" and ordered:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_STATUS", "CLOSED residual cannot carry obstructions")
    if status == "OPEN" and not ordered:
        _fail("TEVS_MAX_V3_STDLIB_RESIDUAL_STATUS", "OPEN residual requires obstruction")
    return ResidualViewV1(
        str(status), domain, judgment_id, boundary_hash, judgment_hash, source_hash,
        ordered, current.field_hash
    )


def compare_residuals(before: SemanticFieldV1, after: SemanticFieldV1) -> ResidualProgressV1:
    left, right = parse_residual(before), parse_residual(after)
    if left.boundary_hash != right.boundary_hash:
        classification = "INCOMPARABLE"
        resolved = persistent = introduced = ()
        boundary_hash = canonical_hash({"schema": "TEV_SCRIPT_MAX_V3_STDLIB_INCOMPARABLE_BOUNDARY_V1", "left": left.boundary_hash, "right": right.boundary_hash})
    else:
        boundary_hash = left.boundary_hash
        lset = set(item.obstruction_hash for item in left.obstructions)
        rset = set(item.obstruction_hash for item in right.obstructions)
        resolved = tuple(sorted(lset - rset))
        persistent = tuple(sorted(lset & rset))
        introduced = tuple(sorted(rset - lset))
        if not rset:
            classification = "CLOSED"
        elif lset == rset:
            classification = "UNCHANGED"
        elif rset < lset:
            classification = "REDUCED"
        elif lset < rset:
            classification = "REGRESSED"
        else:
            classification = "CHANGED"
    if classification not in _PROGRESS:
        _fail("TEVS_MAX_V3_STDLIB_PROGRESS", "invalid progress classification")
    body = {
        "schema": "TEV_SCRIPT_MAX_V3_STDLIB_RESIDUAL_PROGRESS_V1",
        "classification": classification,
        "before_residual_hash": left.residual_hash,
        "after_residual_hash": right.residual_hash,
        "boundary_hash": boundary_hash,
        "resolved": list(resolved),
        "persistent": list(persistent),
        "introduced": list(introduced),
    }
    return ResidualProgressV1(
        classification, left.residual_hash, right.residual_hash, boundary_hash,
        resolved, persistent, introduced, canonical_hash(body)
    )


def decision_candidate(candidate_id: str, candidate_hash: str, *, rank: int) -> DecisionCandidateV1:
    cid = _stable(candidate_id, "candidate_id")
    chash = _sha(candidate_hash, "candidate_hash")
    if isinstance(rank, bool) or not isinstance(rank, int):
        _fail("TEVS_MAX_V3_STDLIB_CANDIDATE_RANK", "rank must be integer")
    body = {"candidate_id": cid, "candidate_hash": chash, "rank": rank}
    return DecisionCandidateV1(cid, chash, rank, canonical_hash(body))


def admission(candidate_id: str, status: str, evidence_hashes: Sequence[str] = ()) -> AdmissionV1:
    cid = _stable(candidate_id, "candidate_id")
    if status not in _ADMISSION_STATUSES:
        _fail("TEVS_MAX_V3_STDLIB_ADMISSION_STATUS", "invalid admission status")
    if isinstance(evidence_hashes, (str, bytes)):
        _fail("TEVS_MAX_V3_STDLIB_ADMISSION_EVIDENCE", "evidence_hashes must be a sequence")
    evidence = tuple(sorted(_sha(value, "evidence_hash") for value in evidence_hashes))
    if len(set(evidence)) != len(evidence):
        _fail("TEVS_MAX_V3_STDLIB_ADMISSION_EVIDENCE", "duplicate admission evidence")
    body = {"candidate_id": cid, "status": status, "evidence_hashes": list(evidence)}
    return AdmissionV1(cid, status, evidence, canonical_hash(body))


def _validate_candidate(value: DecisionCandidateV1) -> DecisionCandidateV1:
    if not isinstance(value, DecisionCandidateV1):
        _fail("TEVS_MAX_V3_STDLIB_CANDIDATE", "DecisionCandidateV1 required")
    expected = decision_candidate(value.candidate_id, value.candidate_hash, rank=value.rank)
    if expected != value:
        _fail("TEVS_MAX_V3_STDLIB_CANDIDATE", "candidate identity mismatch")
    return value


def _validate_admission(value: AdmissionV1) -> AdmissionV1:
    if not isinstance(value, AdmissionV1):
        _fail("TEVS_MAX_V3_STDLIB_ADMISSION", "AdmissionV1 required")
    expected = admission(value.candidate_id, value.status, value.evidence_hashes)
    if expected != value:
        _fail("TEVS_MAX_V3_STDLIB_ADMISSION", "admission identity mismatch")
    return value


def resolve_candidates(
    candidates: Sequence[DecisionCandidateV1],
    admissions: Sequence[AdmissionV1],
) -> DecisionResultV1:
    if isinstance(candidates, (str, bytes)) or isinstance(admissions, (str, bytes)):
        _fail("TEVS_MAX_V3_STDLIB_DECISION", "candidate/admission inputs must be sequences")
    candidate_rows = tuple(_validate_candidate(value) for value in candidates)
    admission_rows = tuple(_validate_admission(value) for value in admissions)
    by_candidate = {row.candidate_id: row for row in candidate_rows}
    if len(by_candidate) != len(candidate_rows):
        _fail("TEVS_MAX_V3_STDLIB_DECISION", "duplicate candidate id")
    by_admission = {row.candidate_id: row for row in admission_rows}
    if set(by_admission) != set(by_candidate) or len(by_admission) != len(admission_rows):
        _fail("TEVS_MAX_V3_STDLIB_DECISION", "admission coverage must match candidates exactly")

    considered = tuple(sorted(by_candidate))
    statuses = {cid: by_admission[cid].status for cid in considered}
    if any(status == "PROOF_REQUIRED" for status in statuses.values()):
        status, selected = "INDETERMINATE", None
    else:
        admitted = [by_candidate[cid] for cid in considered if statuses[cid] == "PASS"]
        if not admitted:
            status, selected = "NO_ADMISSIBLE_REALIZATION", None
        else:
            best_rank = min(row.rank for row in admitted)
            best = [row for row in admitted if row.rank == best_rank]
            if len(best) != 1:
                status, selected = "INDETERMINATE", None
            else:
                status, selected = "SELECTED", best[0].candidate_id
    body = {
        "schema": "TEV_SCRIPT_MAX_V3_STDLIB_DECISION_RESULT_V1",
        "status": status,
        "selected_candidate_id": selected,
        "considered_candidate_ids": list(considered),
    }
    return DecisionResultV1(status, selected, considered, canonical_hash(body))


def decision_field(
    candidates: Sequence[DecisionCandidateV1],
    admissions: Sequence[AdmissionV1],
    result: DecisionResultV1,
) -> SemanticFieldV1:
    candidate_rows = tuple(sorted((_validate_candidate(value) for value in candidates), key=lambda row: row.candidate_id))
    admission_rows = tuple(sorted((_validate_admission(value) for value in admissions), key=lambda row: row.candidate_id))
    expected = resolve_candidates(candidate_rows, admission_rows)
    if result != expected:
        _fail("TEVS_MAX_V3_STDLIB_DECISION_RESULT", "decision result does not match governed resolution")
    facts = []
    for row in candidate_rows:
        facts.append(field_fact("tev.std.candidate", (row.candidate_id, row.candidate_hash, row.rank, row.candidate_record_hash)))
    for row in admission_rows:
        facts.append(field_fact("tev.std.admission", (row.candidate_id, row.status, list(row.evidence_hashes), row.admission_hash)))
    facts.append(field_fact("tev.std.selection", (result.status, result.selected_candidate_id, list(result.considered_candidate_ids), result.result_hash)))
    return semantic_field(tuple(facts), profile=DECISION_PROFILE)


def closure_residual(expected: SemanticFieldV1, recovered: SemanticFieldV1) -> SemanticFieldV1:
    expected = validate_semantic_field(expected)
    recovered = validate_semantic_field(recovered)
    expected_hashes = {fact.fact_hash: fact for fact in expected.facts}
    recovered_hashes = {fact.fact_hash: fact for fact in recovered.facts}
    obstructions: list[ResidualObstructionV1] = []
    for fact_hash in sorted(set(expected_hashes) - set(recovered_hashes)):
        obstructions.append(residual_obstruction("missing.fact", fact_hash, expected=fact_hash, observed=None))
    for fact_hash in sorted(set(recovered_hashes) - set(expected_hashes)):
        obstructions.append(residual_obstruction("unexpected.fact", fact_hash, expected=None, observed=fact_hash))
    return residual_field(
        domain="discovery_realization",
        judgment_id="exact_field_recovery",
        judgment={"expected_field_hash": expected.field_hash},
        source={"recovered_field_hash": recovered.field_hash},
        obstructions=tuple(obstructions),
    )


def discovery_realization_closure(
    theory: SemanticFieldV1,
    realization: FieldTransformationV1,
    discovery: FieldTransformationV1,
) -> tuple[SemanticFieldV1, SemanticFieldV1]:
    theory = validate_semantic_field(theory)
    realization = validate_field_transformation(realization)
    discovery = validate_field_transformation(discovery)
    world, realization_receipt = apply_field_transformation(theory, realization)
    if realization_receipt.status != "PASS":
        _fail("TEVS_MAX_V3_STDLIB_REALIZATION", "realization has unresolved proof requirements")
    recovered, discovery_receipt = apply_field_transformation(world, discovery)
    if discovery_receipt.status != "PASS":
        _fail("TEVS_MAX_V3_STDLIB_DISCOVERY", "discovery has unresolved proof requirements")
    cycle = semantic_field(
        (
            field_fact(
                "tev.std.discovery_realization",
                (
                    theory.field_hash,
                    realization.transformation_hash,
                    world.field_hash,
                    discovery.transformation_hash,
                    recovered.field_hash,
                    realization_receipt.receipt_hash,
                    discovery_receipt.receipt_hash,
                ),
            ),
        ),
        profile=DISCOVERY_REALIZATION_PROFILE,
    )
    return cycle, closure_residual(theory, recovered)


__all__ = [
    "AdmissionV1",
    "DecisionCandidateV1",
    "DecisionResultV1",
    "ResidualObstructionV1",
    "ResidualProgressV1",
    "ResidualViewV1",
    "admission",
    "closure_residual",
    "compare_residuals",
    "decision_candidate",
    "decision_field",
    "discovery_realization_closure",
    "parse_residual",
    "residual_field",
    "residual_obstruction",
    "resolve_candidates",
]
