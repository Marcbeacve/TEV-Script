from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_selection_v0 import (
    RealizationSelectionDecisionV0,
    RealizationSelectionError,
    RealizationSelectionIssueV0,
    RealizationSelectionPolicyV0,
    RealizationSelectionProblemV0,
    RealizationSelectionReceiptV0,
    evaluate_realization_selection,
)
from .semantic_realization_v0 import RealizationAdmissionReceiptV0, RealizationCandidateV0
from .semantic_resource_algebra_v0 import ResourceCatalogV0

SELECTION_RESOLUTION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SELECTION_RESOLUTION_V0"
_RESOLUTION_STATES = frozenset({"SELECTED", "INDETERMINATE", "NO_ADMISSIBLE_REALIZATION"})
_CONTEXT_ISSUES = frozenset(
    {
        "selection.policy_mismatch",
        "selection.resource_catalog_mismatch",
        "selection.dimension_outside_catalog",
        "selection.candidate_receipt_set_mismatch",
        "selection.receipt_realization_problem_mismatch",
    }
)
_HEX = frozenset("0123456789abcdef")


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RealizationSelectionError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def _issues(values: Iterable[RealizationSelectionIssueV0]) -> tuple[RealizationSelectionIssueV0, ...]:
    unique: dict[str, RealizationSelectionIssueV0] = {}
    for item in values:
        unique[canonical_json(item.to_object())] = item
    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True, slots=True)
class RealizationSelectionResolutionV0:
    selection_problem_hash: str
    policy_hash: str
    state: str
    selected_candidate_hash: str = ""
    selected_realization_hash: str = ""
    decision_hash: str = ""
    selection_receipt_hash: str = ""
    pareto_candidate_hashes: tuple[str, ...] = ()
    issues: tuple[RealizationSelectionIssueV0, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection_problem_hash", _hash64(self.selection_problem_hash, "selection_problem_hash"))
        object.__setattr__(self, "policy_hash", _hash64(self.policy_hash, "policy_hash"))
        if self.state not in _RESOLUTION_STATES:
            raise RealizationSelectionError("unsupported selection resolution state")
        for name in (
            "selected_candidate_hash",
            "selected_realization_hash",
            "decision_hash",
            "selection_receipt_hash",
        ):
            object.__setattr__(self, name, _optional_hash(getattr(self, name), name))
        object.__setattr__(self, "pareto_candidate_hashes", _hashes(self.pareto_candidate_hashes, "pareto candidate hash"))
        object.__setattr__(self, "issues", _issues(self.issues))

        selected_values = (
            self.selected_candidate_hash,
            self.selected_realization_hash,
            self.decision_hash,
            self.selection_receipt_hash,
        )
        if self.state == "SELECTED":
            if any(not value for value in selected_values):
                raise RealizationSelectionError("SELECTED resolution requires candidate, realization, decision and receipt hashes")
        elif any(selected_values):
            raise RealizationSelectionError("non-selected resolution must not carry selected identities")

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SELECTION_RESOLUTION_SCHEMA_V0,
            "status": self.status,
            "state": self.state,
            "selection_problem_hash": self.selection_problem_hash,
            "policy_hash": self.policy_hash,
            "selected_candidate_hash": self.selected_candidate_hash,
            "selected_realization_hash": self.selected_realization_hash,
            "decision_hash": self.decision_hash,
            "selection_receipt_hash": self.selection_receipt_hash,
            "pareto_candidate_hashes": list(self.pareto_candidate_hashes),
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def resolution_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.selection_resolution.v0", self.to_object())


def _validate_pairs(
    entries: Iterable[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0]],
) -> tuple[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0], ...]:
    rows = tuple(entries)
    if not rows:
        raise RealizationSelectionError("selection resolution requires candidate entries")
    seen: set[str] = set()
    for candidate, receipt in rows:
        if receipt.candidate_hash != candidate.candidate_hash:
            raise RealizationSelectionError("candidate/receipt mismatch")
        if candidate.candidate_hash in seen:
            raise RealizationSelectionError("duplicate selection candidate")
        seen.add(candidate.candidate_hash)
    return rows


def _audit_candidate(
    problem: RealizationSelectionProblemV0,
    candidate: RealizationCandidateV0,
    *,
    policy: RealizationSelectionPolicyV0,
    resource_catalog: ResourceCatalogV0,
    entries: tuple[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0], ...],
) -> tuple[RealizationSelectionDecisionV0, RealizationSelectionReceiptV0]:
    decision = RealizationSelectionDecisionV0(problem.problem_hash, candidate.candidate_hash)
    receipt = evaluate_realization_selection(
        problem,
        decision,
        policy=policy,
        resource_catalog=resource_catalog,
        entries=entries,
    )
    return decision, receipt


def resolve_realization_selection(
    problem: RealizationSelectionProblemV0,
    *,
    policy: RealizationSelectionPolicyV0,
    resource_catalog: ResourceCatalogV0,
    entries: Iterable[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0]],
) -> RealizationSelectionResolutionV0:
    rows = _validate_pairs(entries)
    ordered_rows = tuple(sorted(rows, key=lambda item: item[0].candidate_hash))

    _, context_probe = _audit_candidate(
        problem,
        ordered_rows[0][0],
        policy=policy,
        resource_catalog=resource_catalog,
        entries=ordered_rows,
    )
    context_issues = _issues(item for item in context_probe.issues if item.kind in _CONTEXT_ISSUES)
    if context_issues:
        return RealizationSelectionResolutionV0(
            problem.problem_hash,
            policy.policy_hash,
            "INDETERMINATE",
            pareto_candidate_hashes=context_probe.pareto_candidate_hashes,
            issues=context_issues,
        )

    admitted = tuple((candidate, receipt) for candidate, receipt in ordered_rows if receipt.status == "PASS")
    if not admitted:
        open_receipts = tuple(receipt.receipt_hash for _, receipt in ordered_rows if receipt.status == "PROOF_REQUIRED")
        if open_receipts:
            issue = RealizationSelectionIssueV0(
                "selection.admission_open",
                "PROOF_REQUIRED",
                problem.problem_hash,
                {"candidate_receipt_hashes": list(sorted(open_receipts))},
            )
            return RealizationSelectionResolutionV0(
                problem.problem_hash,
                policy.policy_hash,
                "INDETERMINATE",
                issues=(issue,),
            )
        return RealizationSelectionResolutionV0(
            problem.problem_hash,
            policy.policy_hash,
            "NO_ADMISSIBLE_REALIZATION",
        )

    audits: list[tuple[RealizationCandidateV0, RealizationSelectionDecisionV0, RealizationSelectionReceiptV0]] = []
    for candidate, _ in admitted:
        decision, receipt = _audit_candidate(
            problem,
            candidate,
            policy=policy,
            resource_catalog=resource_catalog,
            entries=ordered_rows,
        )
        audits.append((candidate, decision, receipt))

    pareto_hashes = _hashes(
        (
            candidate_hash
            for _, _, receipt in audits
            for candidate_hash in receipt.pareto_candidate_hashes
        ),
        "pareto candidate hash",
    )
    passing = tuple(item for item in audits if item[2].status == "PASS")
    if len(passing) == 1:
        candidate, decision, receipt = passing[0]
        return RealizationSelectionResolutionV0(
            problem.problem_hash,
            policy.policy_hash,
            "SELECTED",
            selected_candidate_hash=candidate.candidate_hash,
            selected_realization_hash=candidate.realization_hash,
            decision_hash=decision.decision_hash,
            selection_receipt_hash=receipt.receipt_hash,
            pareto_candidate_hashes=pareto_hashes,
        )

    if len(passing) > 1:
        kind = "selection.preference_required" if policy.rule == "PARETO_MEMBER" else "selection.lexicographic_tie"
        issue = RealizationSelectionIssueV0(
            kind,
            "PROOF_REQUIRED",
            problem.problem_hash,
            {"candidate_hashes": [candidate.candidate_hash for candidate, _, _ in passing]},
        )
        return RealizationSelectionResolutionV0(
            problem.problem_hash,
            policy.policy_hash,
            "INDETERMINATE",
            pareto_candidate_hashes=pareto_hashes,
            issues=(issue,),
        )

    proof_issues = _issues(
        item
        for _, _, receipt in audits
        if receipt.status == "PROOF_REQUIRED"
        for item in receipt.issues
        if item.severity == "PROOF_REQUIRED"
    )
    if proof_issues:
        return RealizationSelectionResolutionV0(
            problem.problem_hash,
            policy.policy_hash,
            "INDETERMINATE",
            pareto_candidate_hashes=pareto_hashes,
            issues=proof_issues,
        )

    reject_issues = _issues(
        item
        for _, _, receipt in audits
        for item in receipt.issues
        if item.severity == "REJECT"
    )
    if not reject_issues:
        reject_issues = (
            RealizationSelectionIssueV0(
                "selection.no_verified_decision",
                "REJECT",
                problem.problem_hash,
                {},
            ),
        )
    return RealizationSelectionResolutionV0(
        problem.problem_hash,
        policy.policy_hash,
        "INDETERMINATE",
        pareto_candidate_hashes=pareto_hashes,
        issues=reject_issues,
    )


__all__ = [
    "SELECTION_RESOLUTION_SCHEMA_V0",
    "RealizationSelectionResolutionV0",
    "resolve_realization_selection",
]
