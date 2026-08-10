from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_realization_search_v0 import (
    RealizationPlanningClaimV0,
    SearchCoverageClaimV0,
    SearchCoveragePolicyV0,
    SearchCoverageRecordV0,
    evaluate_realization_planning,
    evaluate_search_coverage,
    residual_from_realization_planning,
    residual_from_search_coverage,
)
from tev_script.semantic_realization_selection_v0 import (
    RealizationSelectionProblemV0,
    RealizationSelectionReceiptV0,
)
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def admission(label: str, problem_hash: str) -> RealizationAdmissionReceiptV0:
    return RealizationAdmissionReceiptV0(
        problem_hash=problem_hash,
        candidate_hash=h(label + ".candidate"),
        realization_hash=h(label + ".realization"),
        semantic_claim_hash=h(label + ".semantic"),
        artifact_manifest_hash=h(label + ".manifest"),
        transformation_semantic_hash=h("transformation"),
        transformation_regime_binding_hash=h("binding"),
        semantic_relation="EXACT_EQUIVALENT",
        regime_preservation_claim_hash=h(label + ".preservation"),
        resource_estimate_claim_hash=h(label + ".estimate"),
        machine_hash=h(label + ".machine"),
        policy_hash=h("admission-policy"),
        regime_hash=h("regime"),
        resource_catalog_hash=h("catalog"),
        machine_compatibility_hash=h(label + ".machine-eval"),
        regime_evaluation_hash=h(label + ".regime-eval"),
        realization_evidence_evaluation_hash=h(label + ".semantic-eval"),
        regime_evidence_evaluation_hash=h(label + ".regime-evidence"),
        resource_evidence_evaluation_hash=h(label + ".resource-evidence"),
        issues=(),
    )


class RealizationSearchV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.realization_problem_hash = h("realization-problem")
        self.left = admission("left", self.realization_problem_hash)
        self.right = admission("right", self.realization_problem_hash)
        self.receipts = (self.left, self.right)
        self.scope = h("coverage-scope")
        self.verifier = h("coverage-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "coverage-proof",
                    ("PROOF",),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.coverage_policy = SearchCoveragePolicyV0(self.evidence_policy.policy_hash)

    def coverage(self, method: str, *, bound_hash=""):
        claim = SearchCoverageClaimV0(
            self.realization_problem_hash,
            tuple(receipt.receipt_hash for receipt in self.receipts),
            h("search-space"),
            method,
            bound_hash=bound_hash,
        )
        evidence = EvidenceItemV0(
            "e.coverage",
            claim.coverage_claim_hash,
            self.scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("coverage-witness-" + method.lower()),
        )
        record = SearchCoverageRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        evaluation = evaluate_search_coverage(
            record,
            policy=self.coverage_policy,
            evidence_policy=self.evidence_policy,
            candidate_receipts=self.receipts,
            evidence=(evidence,),
        )
        return claim, record, evaluation

    def selection(self):
        policy_hash = h("selection-policy")
        problem = RealizationSelectionProblemV0(
            self.realization_problem_hash,
            policy_hash,
            tuple(receipt.receipt_hash for receipt in self.receipts),
        )
        receipt = RealizationSelectionReceiptV0(
            problem.problem_hash,
            h("selection-decision"),
            h("selection-decision-record"),
            self.left.candidate_hash,
            self.left.realization_hash,
            policy_hash,
            (self.left.candidate_hash,),
            (),
        )
        return problem, receipt

    def planning(self, scope, record, coverage_eval):
        selection_problem, selection_receipt = self.selection()
        claim = RealizationPlanningClaimV0(
            selection_problem.problem_hash,
            selection_receipt.receipt_hash,
            coverage_eval.evaluation_hash,
            scope,
        )
        evaluation = evaluate_realization_planning(
            claim,
            selection_problem=selection_problem,
            selection_receipt=selection_receipt,
            coverage_record=record,
            coverage_evaluation=coverage_eval,
        )
        return claim, evaluation

    def test_heuristic_coverage_can_only_support_candidate_set_scope(self):
        _, record, coverage_eval = self.coverage("HEURISTIC")
        self.assertEqual(coverage_eval.status, "PASS")
        _, candidate_scope = self.planning("CANDIDATE_SET", record, coverage_eval)
        self.assertEqual(candidate_scope.status, "PASS")
        _, exhaustive_scope = self.planning("EXHAUSTIVE_SEARCH_SPACE", record, coverage_eval)
        self.assertEqual(exhaustive_scope.status, "REJECT")
        self.assertIn(
            "planning.coverage_insufficient_for_exhaustive_scope",
            {item.kind for item in exhaustive_scope.issues},
        )

    def test_bounded_coverage_supports_bounded_but_not_exhaustive_scope(self):
        _, record, coverage_eval = self.coverage("BOUNDED", bound_hash=h("search-bound"))
        self.assertEqual(coverage_eval.status, "PASS")
        _, bounded = self.planning("BOUNDED_SEARCH_SPACE", record, coverage_eval)
        self.assertEqual(bounded.status, "PASS")
        _, exhaustive = self.planning("EXHAUSTIVE_SEARCH_SPACE", record, coverage_eval)
        self.assertEqual(exhaustive.status, "REJECT")

    def test_exhaustive_coverage_can_support_exhaustive_planning_scope(self):
        _, record, coverage_eval = self.coverage("EXHAUSTIVE")
        self.assertEqual(coverage_eval.status, "PASS")
        self.assertEqual(parse_residual(residual_from_search_coverage(coverage_eval)).status, "CLOSED")
        _, planning_eval = self.planning("EXHAUSTIVE_SEARCH_SPACE", record, coverage_eval)
        self.assertEqual(planning_eval.status, "PASS")
        self.assertEqual(parse_residual(residual_from_realization_planning(planning_eval)).status, "CLOSED")

    def test_missing_coverage_evidence_keeps_claim_open(self):
        claim = SearchCoverageClaimV0(
            self.realization_problem_hash,
            tuple(receipt.receipt_hash for receipt in self.receipts),
            h("search-space"),
            "EXHAUSTIVE",
        )
        record = SearchCoverageRecordV0(claim, self.evidence_policy.policy_hash, ())
        evaluation = evaluate_search_coverage(
            record,
            policy=self.coverage_policy,
            evidence_policy=self.evidence_policy,
            candidate_receipts=self.receipts,
            evidence=(),
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("search.evidence.required", {item.kind for item in evaluation.issues})

    def test_receipt_from_another_realization_problem_rejects_coverage(self):
        foreign = admission("foreign", h("other-problem"))
        claim = SearchCoverageClaimV0(
            self.realization_problem_hash,
            (foreign.receipt_hash,),
            h("search-space"),
            "HEURISTIC",
        )
        evidence = EvidenceItemV0(
            "e.foreign",
            claim.coverage_claim_hash,
            self.scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("foreign-witness"),
        )
        record = SearchCoverageRecordV0(claim, self.evidence_policy.policy_hash, (evidence.evidence_hash,))
        evaluation = evaluate_search_coverage(
            record,
            policy=self.coverage_policy,
            evidence_policy=self.evidence_policy,
            candidate_receipts=(foreign,),
            evidence=(evidence,),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("search.receipt_realization_problem_mismatch", {item.kind for item in evaluation.issues})

    def test_planning_rejects_different_candidate_universe(self):
        _, record, coverage_eval = self.coverage("EXHAUSTIVE")
        selection_problem, selection_receipt = self.selection()
        altered_problem = RealizationSelectionProblemV0(
            self.realization_problem_hash,
            selection_problem.policy_hash,
            (self.left.receipt_hash,),
        )
        altered_receipt = RealizationSelectionReceiptV0(
            altered_problem.problem_hash,
            selection_receipt.decision_hash,
            selection_receipt.decision_record_hash,
            self.left.candidate_hash,
            self.left.realization_hash,
            selection_receipt.policy_hash,
            (self.left.candidate_hash,),
            (),
        )
        claim = RealizationPlanningClaimV0(
            altered_problem.problem_hash,
            altered_receipt.receipt_hash,
            coverage_eval.evaluation_hash,
            "EXHAUSTIVE_SEARCH_SPACE",
        )
        evaluation = evaluate_realization_planning(
            claim,
            selection_problem=altered_problem,
            selection_receipt=altered_receipt,
            coverage_record=record,
            coverage_evaluation=coverage_eval,
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("planning.candidate_universe_mismatch", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
