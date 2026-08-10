from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_realization_v0 import (
    ParetoEntryV0,
    RealizationAdmissionReceiptV0,
    RealizationCandidateV0,
    pareto_front,
)
from .semantic_resource_algebra_v0 import ResourceCatalogV0
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions

SELECTION_POLICY_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SELECTION_POLICY_V0"
SELECTION_PROBLEM_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SELECTION_PROBLEM_V0"
SELECTION_DECISION_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SELECTION_DECISION_V0"
SELECTION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_SELECTION_RECEIPT_V0"
_RULES = frozenset({"PARETO_MEMBER", "LEXICOGRAPHIC_MIN"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class RealizationSelectionError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise RealizationSelectionError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise RealizationSelectionError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def _dimensions(values: Iterable[str]) -> tuple[str, ...]:
    rows = tuple(_stable(value, "selection resource dimension") for value in values)
    if not rows:
        raise RealizationSelectionError("selection requires at least one resource dimension")
    if len(set(rows)) != len(rows):
        raise RealizationSelectionError("duplicate selection resource dimension")
    return rows


@dataclass(frozen=True, slots=True)
class RealizationSelectionPolicyV0:
    resource_catalog_hash: str
    rule: str
    dimensions: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_catalog_hash", _hash64(self.resource_catalog_hash, "resource_catalog_hash"))
        if self.rule not in _RULES:
            raise RealizationSelectionError("unsupported selection rule")
        object.__setattr__(self, "dimensions", _dimensions(self.dimensions))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SELECTION_POLICY_SCHEMA_V0,
            "resource_catalog_hash": self.resource_catalog_hash,
            "rule": self.rule,
            "dimensions": list(self.dimensions),
        }

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationSelectionProblemV0:
    realization_problem_hash: str
    policy_hash: str
    candidate_receipt_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "realization_problem_hash", _hash64(self.realization_problem_hash, "realization_problem_hash"))
        object.__setattr__(self, "policy_hash", _hash64(self.policy_hash, "policy_hash"))
        receipts = _hashes(self.candidate_receipt_hashes, "candidate receipt hash")
        if not receipts:
            raise RealizationSelectionError("selection problem requires candidate receipts")
        object.__setattr__(self, "candidate_receipt_hashes", receipts)

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SELECTION_PROBLEM_SCHEMA_V0,
            "realization_problem_hash": self.realization_problem_hash,
            "policy_hash": self.policy_hash,
            "candidate_receipt_hashes": list(self.candidate_receipt_hashes),
        }

    @property
    def problem_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationSelectionDecisionV0:
    selection_problem_hash: str
    selected_candidate_hash: str
    provenance_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "selection_problem_hash", _hash64(self.selection_problem_hash, "selection_problem_hash"))
        object.__setattr__(self, "selected_candidate_hash", _hash64(self.selected_candidate_hash, "selected_candidate_hash"))
        object.__setattr__(self, "provenance_hashes", _hashes(self.provenance_hashes, "selection provenance hash"))

    def identity_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_REALIZATION_SELECTION_DECISION_IDENTITY_V0",
            "selection_problem_hash": self.selection_problem_hash,
            "selected_candidate_hash": self.selected_candidate_hash,
        }

    @property
    def decision_hash(self) -> str:
        return canonical_hash(self.identity_object())

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SELECTION_DECISION_SCHEMA_V0,
            "decision_hash": self.decision_hash,
            **{key: value for key, value in self.identity_object().items() if key != "schema"},
            "provenance_hashes": list(self.provenance_hashes),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class RealizationSelectionIssueV0:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _stable(self.kind, "selection issue kind"))
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise RealizationSelectionError("selection issue severity")
        subject = str(self.subject)
        if not subject:
            raise RealizationSelectionError("selection issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {"kind": self.kind, "severity": self.severity, "subject": self.subject, "detail": dict(self.detail)}


@dataclass(frozen=True, slots=True)
class RealizationSelectionReceiptV0:
    selection_problem_hash: str
    decision_hash: str
    decision_record_hash: str
    selected_candidate_hash: str
    selected_realization_hash: str
    policy_hash: str
    pareto_candidate_hashes: tuple[str, ...]
    issues: tuple[RealizationSelectionIssueV0, ...]

    def __post_init__(self) -> None:
        for name in (
            "selection_problem_hash",
            "decision_hash",
            "decision_record_hash",
            "selected_candidate_hash",
            "selected_realization_hash",
            "policy_hash",
        ):
            object.__setattr__(self, name, _hash64(getattr(self, name), name))
        object.__setattr__(self, "pareto_candidate_hashes", _hashes(self.pareto_candidate_hashes, "pareto candidate hash"))
        object.__setattr__(self, "issues", tuple(sorted(self.issues, key=lambda item: canonical_json(item.to_object()))))

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": SELECTION_RECEIPT_SCHEMA_V0,
            "status": self.status,
            "selection_problem_hash": self.selection_problem_hash,
            "decision_hash": self.decision_hash,
            "decision_record_hash": self.decision_record_hash,
            "selected_candidate_hash": self.selected_candidate_hash,
            "selected_realization_hash": self.selected_realization_hash,
            "policy_hash": self.policy_hash,
            "pareto_candidate_hashes": list(self.pareto_candidate_hashes),
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def receipt_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.selection_receipt.v0", self.to_object())


def _candidate_map(entries: Iterable[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0]]):
    rows = tuple(entries)
    if not rows:
        raise RealizationSelectionError("selection requires candidate entries")
    result: dict[str, tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0]] = {}
    for candidate, receipt in rows:
        if receipt.candidate_hash != candidate.candidate_hash:
            raise RealizationSelectionError("candidate/receipt mismatch")
        if candidate.candidate_hash in result:
            raise RealizationSelectionError("duplicate selection candidate")
        result[candidate.candidate_hash] = (candidate, receipt)
    return result


def evaluate_realization_selection(
    problem: RealizationSelectionProblemV0,
    decision: RealizationSelectionDecisionV0,
    *,
    policy: RealizationSelectionPolicyV0,
    resource_catalog: ResourceCatalogV0,
    entries: Iterable[tuple[RealizationCandidateV0, RealizationAdmissionReceiptV0]],
) -> RealizationSelectionReceiptV0:
    issues: list[RealizationSelectionIssueV0] = []
    candidates = _candidate_map(entries)

    if problem.policy_hash != policy.policy_hash:
        issues.append(RealizationSelectionIssueV0("selection.policy_mismatch", "REJECT", problem.policy_hash, {"observed": policy.policy_hash}))
    if decision.selection_problem_hash != problem.problem_hash:
        issues.append(RealizationSelectionIssueV0("selection.problem_mismatch", "REJECT", decision.selection_problem_hash, {"observed": problem.problem_hash}))
    if policy.resource_catalog_hash != resource_catalog.catalog_hash:
        issues.append(RealizationSelectionIssueV0("selection.resource_catalog_mismatch", "REJECT", policy.resource_catalog_hash, {"observed": resource_catalog.catalog_hash}))
    outside_dimensions = set(policy.dimensions) - set(resource_catalog.dimension_ids)
    if outside_dimensions:
        issues.append(RealizationSelectionIssueV0("selection.dimension_outside_catalog", "REJECT", sorted(outside_dimensions)[0], {"outside": sorted(outside_dimensions)}))

    observed_receipts = tuple(sorted(receipt.receipt_hash for _, receipt in candidates.values()))
    if observed_receipts != problem.candidate_receipt_hashes:
        issues.append(RealizationSelectionIssueV0("selection.candidate_receipt_set_mismatch", "REJECT", problem.problem_hash, {"expected": list(problem.candidate_receipt_hashes), "observed": list(observed_receipts)}))

    for _, receipt in candidates.values():
        if receipt.problem_hash != problem.realization_problem_hash:
            issues.append(
                RealizationSelectionIssueV0(
                    "selection.receipt_realization_problem_mismatch",
                    "REJECT",
                    receipt.receipt_hash,
                    {
                        "expected_realization_problem_hash": problem.realization_problem_hash,
                        "observed_realization_problem_hash": receipt.problem_hash,
                    },
                )
            )

    selected_pair = candidates.get(decision.selected_candidate_hash)
    if selected_pair is None:
        selected_realization_hash = canonical_hash({"schema": "TEV_SCRIPT_MISSING_SELECTED_REALIZATION_V0", "candidate_hash": decision.selected_candidate_hash})
        issues.append(RealizationSelectionIssueV0("selection.selected_candidate_missing", "REJECT", decision.selected_candidate_hash, {}))
    else:
        selected_candidate, selected_receipt = selected_pair
        selected_realization_hash = selected_candidate.realization_hash
        if selected_receipt.status != "PASS":
            issues.append(RealizationSelectionIssueV0("selection.selected_candidate_not_admitted", "REJECT" if selected_receipt.status == "REJECT" else "PROOF_REQUIRED", selected_receipt.receipt_hash, {"status": selected_receipt.status}))

    admitted_entries = tuple((candidate, receipt) for candidate, receipt in candidates.values() if receipt.status == "PASS")
    pareto: tuple[ParetoEntryV0, ...] = ()
    if not outside_dimensions:
        pareto = pareto_front(
            admitted_entries,
            resource_catalog=resource_catalog,
            dimensions=policy.dimensions,
        ) if admitted_entries else ()
    pareto_hashes = tuple(item.candidate_hash for item in pareto)

    if selected_pair is not None and selected_pair[1].status == "PASS" and not outside_dimensions:
        selected_candidate = selected_pair[0]
        if policy.rule == "PARETO_MEMBER":
            if selected_candidate.candidate_hash not in pareto_hashes:
                issues.append(RealizationSelectionIssueV0("selection.not_pareto_member", "REJECT", selected_candidate.candidate_hash, {"pareto": list(pareto_hashes)}))
        else:
            unknown: list[tuple[str, str]] = []
            scores: dict[str, tuple[object, ...]] = {}
            for candidate, receipt in admitted_entries:
                values: list[object] = []
                for dimension in policy.dimensions:
                    bound = candidate.predicted_resources.bound(dimension)
                    if bound is None or bound.upper is None:
                        unknown.append((candidate.candidate_hash, dimension))
                        break
                    values.append(bound.upper)
                else:
                    scores[candidate.candidate_hash] = tuple(values)
            if unknown:
                for candidate_hash, dimension in sorted(unknown):
                    issues.append(RealizationSelectionIssueV0("selection.lexicographic_bound_unknown", "PROOF_REQUIRED", candidate_hash, {"dimension": dimension}))
            elif scores:
                best_score = min(scores.values())
                best = tuple(sorted(candidate_hash for candidate_hash, score in scores.items() if score == best_score))
                if selected_candidate.candidate_hash not in best:
                    issues.append(RealizationSelectionIssueV0("selection.not_lexicographic_minimum", "REJECT", selected_candidate.candidate_hash, {"best_candidates": list(best)}))

    return RealizationSelectionReceiptV0(
        problem.problem_hash,
        decision.decision_hash,
        decision.record_hash,
        decision.selected_candidate_hash,
        selected_realization_hash,
        policy.policy_hash,
        pareto_hashes,
        tuple(issues),
    )


def residual_from_realization_selection(receipt: RealizationSelectionReceiptV0) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="realization_selection",
        judgment_id="realization_selection",
        judgment={"kind": "selected_realization_satisfies_selection_policy", "selected_candidate_hash": receipt.selected_candidate_hash, "status": receipt.status},
        source={"kind": "realization_selection_receipt", "receipt_hash": receipt.receipt_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(receipt.selection_problem_hash, receipt.decision_hash, receipt.selected_candidate_hash, receipt.policy_hash),
            )
            for item in receipt.issues
        ),
    )


__all__ = [
    "SELECTION_POLICY_SCHEMA_V0",
    "SELECTION_PROBLEM_SCHEMA_V0",
    "SELECTION_DECISION_SCHEMA_V0",
    "SELECTION_RECEIPT_SCHEMA_V0",
    "RealizationSelectionError",
    "RealizationSelectionPolicyV0",
    "RealizationSelectionProblemV0",
    "RealizationSelectionDecisionV0",
    "RealizationSelectionIssueV0",
    "RealizationSelectionReceiptV0",
    "evaluate_realization_selection",
    "residual_from_realization_selection",
]
