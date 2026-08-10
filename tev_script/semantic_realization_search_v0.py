from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, evaluate_evidence
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_selection_v0 import (
    RealizationSelectionProblemV0,
    RealizationSelectionReceiptV0,
)
from .semantic_realization_v0 import RealizationAdmissionReceiptV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

SEARCH_COVERAGE_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SEARCH_COVERAGE_CLAIM_V0"
SEARCH_COVERAGE_RECORD_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SEARCH_COVERAGE_RECORD_V0"
SEARCH_COVERAGE_POLICY_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SEARCH_COVERAGE_POLICY_V0"
SEARCH_COVERAGE_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SEARCH_COVERAGE_EVALUATION_V0"
PLANNING_CLAIM_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_PLANNING_CLAIM_V0"
PLANNING_EVALUATION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_PLANNING_EVALUATION_V0"
_METHODS = frozenset({"HEURISTIC", "BOUNDED", "EXHAUSTIVE"})
_SCOPES = frozenset({"CANDIDATE_SET", "BOUNDED_SEARCH_SPACE", "EXHAUSTIVE_SEARCH_SPACE"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class RealizationSearchError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise RealizationSearchError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RealizationSearchError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class SearchCoverageClaimV0:
    realization_problem_hash: str
    candidate_receipt_hashes: tuple[str, ...]
    search_space_hash: str
    method: str
    bound_hash: str = ""
    assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "realization_problem_hash", _hash64(self.realization_problem_hash, "realization_problem_hash"))
        receipts = _hashes(self.candidate_receipt_hashes, "candidate_receipt_hash")
        if not receipts:
            raise RealizationSearchError("search coverage requires candidate receipts")
        object.__setattr__(self, "candidate_receipt_hashes", receipts)
        object.__setattr__(self, "search_space_hash", _hash64(self.search_space_hash, "search_space_hash"))
        if self.method not in _METHODS:
            raise RealizationSearchError("unsupported search coverage method")
        object.__setattr__(self, "bound_hash", _optional_hash(self.bound_hash, "bound_hash"))
        if self.method == "BOUNDED" and not self.bound_hash:
            raise RealizationSearchError("BOUNDED search coverage requires bound_hash")
        if self.method == "EXHAUSTIVE" and self.bound_hash:
            raise RealizationSearchError("EXHAUSTIVE search coverage uses search_space_hash, not bound_hash")
        object.__setattr__(self, "assumption_hashes", _hashes(self.assumption_hashes, "search coverage assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SEARCH_COVERAGE_CLAIM_SCHEMA_V0,
            "realization_problem_hash": self.realization_problem_hash,
            "candidate_receipt_hashes": list(self.candidate_receipt_hashes),
            "search_space_hash": self.search_space_hash,
            "method": self.method,
            "bound_hash": self.bound_hash,
            "assumption_hashes": list(self.assumption_hashes),
        }

    @property
    def coverage_claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class SearchCoverageRecordV0:
    claim: SearchCoverageClaimV0
    evidence_policy_hash: str
    evidence_hashes: tuple[str, ...] = ()
    provenance_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        object.__setattr__(self, "evidence_hashes", _hashes(self.evidence_hashes, "coverage evidence hash"))
        object.__setattr__(self, "provenance_hashes", _hashes(self.provenance_hashes, "coverage provenance hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SEARCH_COVERAGE_RECORD_SCHEMA_V0,
            "coverage_claim_hash": self.claim.coverage_claim_hash,
            "claim": self.claim.to_object(),
            "evidence_policy_hash": self.evidence_policy_hash,
            "evidence_hashes": list(self.evidence_hashes),
            "provenance_hashes": list(self.provenance_hashes),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class SearchCoveragePolicyV0:
    evidence_policy_hash: str
    allowed_methods: tuple[str, ...] = ("HEURISTIC", "BOUNDED", "EXHAUSTIVE")
    accepted_assumption_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_policy_hash", _hash64(self.evidence_policy_hash, "evidence_policy_hash"))
        methods = tuple(sorted(set(str(item) for item in self.allowed_methods)))
        if not methods or any(item not in _METHODS for item in methods):
            raise RealizationSearchError("allowed_methods")
        object.__setattr__(self, "allowed_methods", methods)
        object.__setattr__(self, "accepted_assumption_hashes", _hashes(self.accepted_assumption_hashes, "accepted search assumption hash"))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SEARCH_COVERAGE_POLICY_SCHEMA_V0,
            "evidence_policy_hash": self.evidence_policy_hash,
            "allowed_methods": list(self.allowed_methods),
            "accepted_assumption_hashes": list(self.accepted_assumption_hashes),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class SearchCoverageIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "search coverage issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RealizationSearchError("search coverage issue severity")
        subject = str(self.subject)
        if not subject:
            raise RealizationSearchError("search coverage issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class SearchCoverageEvaluationV0:
    coverage_claim_hash: str
    coverage_record_hash: str
    policy_hash: str
    evidence_evaluation_hash: str
    method: str
    issues: tuple[SearchCoverageIssueV0, ...]

    def __post_init__(self) -> None:
        for name in ("coverage_claim_hash", "coverage_record_hash", "policy_hash", "evidence_evaluation_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.method not in _METHODS:
            raise RealizationSearchError("search coverage evaluation method")
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SEARCH_COVERAGE_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "coverage_claim_hash": self.coverage_claim_hash,
            "coverage_record_hash": self.coverage_record_hash,
            "policy_hash": self.policy_hash,
            "evidence_evaluation_hash": self.evidence_evaluation_hash,
            "method": self.method,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_search_coverage(
    record: SearchCoverageRecordV0,
    *,
    policy: SearchCoveragePolicyV0,
    evidence_policy: EvidencePolicyV0,
    candidate_receipts: Iterable[RealizationAdmissionReceiptV0],
    evidence: Iterable[EvidenceItemV0],
) -> SearchCoverageEvaluationV0:
    issues: list[SearchCoverageIssueV0] = []
    claim = record.claim
    receipts = tuple(candidate_receipts)
    observed_receipts = tuple(sorted(receipt.receipt_hash for receipt in receipts))

    if observed_receipts != claim.candidate_receipt_hashes:
        issues.append(SearchCoverageIssueV0("search.coverage_candidate_set_mismatch", "REJECT", claim.coverage_claim_hash, {"expected": list(claim.candidate_receipt_hashes), "observed": list(observed_receipts)}))
    for receipt in receipts:
        if receipt.problem_hash != claim.realization_problem_hash:
            issues.append(SearchCoverageIssueV0("search.receipt_realization_problem_mismatch", "REJECT", receipt.receipt_hash, {"expected": claim.realization_problem_hash, "observed": receipt.problem_hash}))
    if claim.method not in policy.allowed_methods:
        issues.append(SearchCoverageIssueV0("search.method_not_allowed", "REJECT", claim.method, {"allowed": list(policy.allowed_methods)}))
    if record.evidence_policy_hash != evidence_policy.policy_hash or policy.evidence_policy_hash != evidence_policy.policy_hash:
        issues.append(SearchCoverageIssueV0("search.evidence_policy_mismatch", "REJECT", evidence_policy.policy_hash, {"record": record.evidence_policy_hash, "policy": policy.evidence_policy_hash}))
    if not evidence_policy.requirements:
        issues.append(SearchCoverageIssueV0("search.evidence_policy_empty", "REJECT", evidence_policy.policy_hash, {}))

    accepted_assumptions = set(policy.accepted_assumption_hashes)
    for assumption_hash in sorted(set(claim.assumption_hashes) - accepted_assumptions):
        issues.append(SearchCoverageIssueV0("search.assumption_not_accepted", "REJECT", assumption_hash, {}))

    evidence_items = tuple(evidence)
    evidence_by_hash = {item.evidence_hash: item for item in evidence_items}
    for evidence_hash in record.evidence_hashes:
        if evidence_hash not in evidence_by_hash:
            issues.append(SearchCoverageIssueV0("search.evidence_reference_missing", "PROOF_REQUIRED", evidence_hash, {}))

    evidence_evaluation = evaluate_evidence(claim.coverage_claim_hash, evidence_policy, evidence_items)
    for item in evidence_evaluation.issues:
        issues.append(SearchCoverageIssueV0("search." + item.kind, "REJECT" if item.kind == "evidence.falsified" else "PROOF_REQUIRED", item.requirement_id, {"evidence_hash": item.evidence_hash, **dict(item.detail)}))
    for accepted_hash in evidence_evaluation.accepted_evidence_hashes:
        if accepted_hash not in record.evidence_hashes:
            issues.append(SearchCoverageIssueV0("search.evidence_unbound_support", "REJECT", accepted_hash, {}))
        item = evidence_by_hash.get(accepted_hash)
        if item is not None:
            for assumption_hash in sorted(set(item.assumption_hashes) - accepted_assumptions):
                issues.append(SearchCoverageIssueV0("search.evidence_assumption_not_accepted", "REJECT", assumption_hash, {"evidence_hash": accepted_hash}))

    return SearchCoverageEvaluationV0(
        claim.coverage_claim_hash,
        record.record_hash,
        policy.policy_hash,
        evidence_evaluation.evaluation_hash,
        claim.method,
        tuple(issues),
    )


@dataclass(frozen=True, slots=True)
class RealizationPlanningClaimV0:
    selection_problem_hash: str
    selection_receipt_hash: str
    coverage_evaluation_hash: str
    scope: str

    def __post_init__(self) -> None:
        for name in ("selection_problem_hash", "selection_receipt_hash", "coverage_evaluation_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.scope not in _SCOPES:
            raise RealizationSearchError("unsupported planning scope")

    def to_object(self) -> dict[str, object]:
        return {
            "schema": PLANNING_CLAIM_SCHEMA_V0,
            "selection_problem_hash": self.selection_problem_hash,
            "selection_receipt_hash": self.selection_receipt_hash,
            "coverage_evaluation_hash": self.coverage_evaluation_hash,
            "scope": self.scope,
        }

    @property
    def planning_claim_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationPlanningIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "planning issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RealizationSearchError("planning issue severity")
        subject = str(self.subject)
        if not subject:
            raise RealizationSearchError("planning issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class RealizationPlanningEvaluationV0:
    planning_claim_hash: str
    selected_candidate_hash: str
    selected_realization_hash: str
    coverage_method: str
    scope: str
    issues: tuple[RealizationPlanningIssueV0, ...]

    def __post_init__(self) -> None:
        for name in ("planning_claim_hash", "selected_candidate_hash", "selected_realization_hash"):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        if self.coverage_method not in _METHODS:
            raise RealizationSearchError("planning coverage method")
        if self.scope not in _SCOPES:
            raise RealizationSearchError("planning scope")
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": PLANNING_EVALUATION_SCHEMA_V0,
            "status": self.status,
            "planning_claim_hash": self.planning_claim_hash,
            "selected_candidate_hash": self.selected_candidate_hash,
            "selected_realization_hash": self.selected_realization_hash,
            "coverage_method": self.coverage_method,
            "scope": self.scope,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.planning_evaluation.v0", self.to_object())


def evaluate_realization_planning(
    claim: RealizationPlanningClaimV0,
    *,
    selection_problem: RealizationSelectionProblemV0,
    selection_receipt: RealizationSelectionReceiptV0,
    coverage_record: SearchCoverageRecordV0,
    coverage_evaluation: SearchCoverageEvaluationV0,
) -> RealizationPlanningEvaluationV0:
    issues: list[RealizationPlanningIssueV0] = []

    if claim.selection_problem_hash != selection_problem.problem_hash:
        issues.append(RealizationPlanningIssueV0("planning.selection_problem_mismatch", "REJECT", claim.selection_problem_hash, {"observed": selection_problem.problem_hash}))
    if claim.selection_receipt_hash != selection_receipt.receipt_hash:
        issues.append(RealizationPlanningIssueV0("planning.selection_receipt_mismatch", "REJECT", claim.selection_receipt_hash, {"observed": selection_receipt.receipt_hash}))
    if claim.coverage_evaluation_hash != coverage_evaluation.evaluation_hash:
        issues.append(RealizationPlanningIssueV0("planning.coverage_evaluation_mismatch", "REJECT", claim.coverage_evaluation_hash, {"observed": coverage_evaluation.evaluation_hash}))
    if selection_receipt.selection_problem_hash != selection_problem.problem_hash:
        issues.append(RealizationPlanningIssueV0("planning.selection_receipt_not_bound", "REJECT", selection_receipt.receipt_hash, {}))
    if selection_receipt.status != "PASS":
        issues.append(RealizationPlanningIssueV0("planning.selection_not_admitted", "REJECT" if selection_receipt.status == "REJECT" else "PROOF_REQUIRED", selection_receipt.receipt_hash, {"status": selection_receipt.status}))
    if coverage_evaluation.coverage_claim_hash != coverage_record.claim.coverage_claim_hash or coverage_evaluation.coverage_record_hash != coverage_record.record_hash:
        issues.append(RealizationPlanningIssueV0("planning.coverage_not_bound", "REJECT", coverage_evaluation.evaluation_hash, {}))
    if coverage_evaluation.status != "PASS":
        issues.append(RealizationPlanningIssueV0("planning.coverage_not_admitted", "REJECT" if coverage_evaluation.status == "REJECT" else "PROOF_REQUIRED", coverage_evaluation.evaluation_hash, {"status": coverage_evaluation.status}))
    if coverage_record.claim.realization_problem_hash != selection_problem.realization_problem_hash:
        issues.append(RealizationPlanningIssueV0("planning.realization_problem_mismatch", "REJECT", coverage_record.claim.realization_problem_hash, {"selection": selection_problem.realization_problem_hash}))
    if coverage_record.claim.candidate_receipt_hashes != selection_problem.candidate_receipt_hashes:
        issues.append(RealizationPlanningIssueV0("planning.candidate_universe_mismatch", "REJECT", coverage_record.claim.coverage_claim_hash, {"coverage": list(coverage_record.claim.candidate_receipt_hashes), "selection": list(selection_problem.candidate_receipt_hashes)}))

    if claim.scope == "BOUNDED_SEARCH_SPACE" and coverage_record.claim.method not in {"BOUNDED", "EXHAUSTIVE"}:
        issues.append(RealizationPlanningIssueV0("planning.coverage_insufficient_for_bounded_scope", "REJECT", coverage_record.claim.method, {}))
    if claim.scope == "EXHAUSTIVE_SEARCH_SPACE" and coverage_record.claim.method != "EXHAUSTIVE":
        issues.append(RealizationPlanningIssueV0("planning.coverage_insufficient_for_exhaustive_scope", "REJECT", coverage_record.claim.method, {}))

    return RealizationPlanningEvaluationV0(
        claim.planning_claim_hash,
        selection_receipt.selected_candidate_hash,
        selection_receipt.selected_realization_hash,
        coverage_record.claim.method,
        claim.scope,
        tuple(issues),
    )


def residual_from_search_coverage(evaluation: SearchCoverageEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_search_coverage",
        judgment_id="search_coverage",
        judgment={"kind": "candidate_set_search_coverage", "coverage_claim_hash": evaluation.coverage_claim_hash, "method": evaluation.method, "status": evaluation.status},
        source={"kind": "search_coverage_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(item.kind, item.subject, "resolved", item.severity, dict(item.detail), dependency_refs=(evaluation.coverage_claim_hash, evaluation.coverage_record_hash, evaluation.policy_hash))
            for item in evaluation.issues
        ),
    )


def residual_from_realization_planning(evaluation: RealizationPlanningEvaluationV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_planning",
        judgment_id="realization_planning_scope",
        judgment={"kind": "selected_realization_with_coverage_scope", "planning_claim_hash": evaluation.planning_claim_hash, "scope": evaluation.scope, "status": evaluation.status},
        source={"kind": "realization_planning_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(item.kind, item.subject, "resolved", item.severity, dict(item.detail), dependency_refs=(evaluation.planning_claim_hash, evaluation.selected_candidate_hash, evaluation.selected_realization_hash))
            for item in evaluation.issues
        ),
    )


__all__ = [
    "SEARCH_COVERAGE_CLAIM_SCHEMA_V0",
    "SEARCH_COVERAGE_RECORD_SCHEMA_V0",
    "SEARCH_COVERAGE_POLICY_SCHEMA_V0",
    "SEARCH_COVERAGE_EVALUATION_SCHEMA_V0",
    "PLANNING_CLAIM_SCHEMA_V0",
    "PLANNING_EVALUATION_SCHEMA_V0",
    "RealizationSearchError",
    "SearchCoverageClaimV0",
    "SearchCoverageRecordV0",
    "SearchCoveragePolicyV0",
    "SearchCoverageIssueV0",
    "SearchCoverageEvaluationV0",
    "RealizationPlanningClaimV0",
    "RealizationPlanningIssueV0",
    "RealizationPlanningEvaluationV0",
    "evaluate_search_coverage",
    "evaluate_realization_planning",
    "residual_from_search_coverage",
    "residual_from_realization_planning",
]
