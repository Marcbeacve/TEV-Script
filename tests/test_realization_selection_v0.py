from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_realization_selection_v0 import (
    RealizationSelectionDecisionV0,
    RealizationSelectionPolicyV0,
    RealizationSelectionProblemV0,
    evaluate_realization_selection,
    residual_from_realization_selection,
)
from tev_script.semantic_realization_v0 import (
    RealizationAdmissionReceiptV0,
    RealizationCandidateV0,
    RealizationIssueV0,
)
from tev_script.semantic_resource_algebra_v0 import (
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceDimensionV0,
    ResourceVectorV0,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class RealizationSelectionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
            )
        )
        self.realization_problem_hash = h("realization-problem")

    def candidate(self, label: str, latency, energy) -> RealizationCandidateV0:
        vector = ResourceVectorV0(
            (latency, energy),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        return RealizationCandidateV0(
            h("transformation"),
            h("binding"),
            "tev.realization.test",
            h("machine-" + label),
            h("manifest-" + label),
            "EXACT_EQUIVALENT",
            predicted_resources=vector,
            resource_estimate_claim_hash=h("estimate-" + label),
            regime_preservation_claim_hash=h("preservation-" + label),
        )

    def receipt(self, candidate, *, status="PASS", problem_hash=None):
        issues = ()
        if status == "PROOF_REQUIRED":
            issues = (RealizationIssueV0("resource.bound_unknown", "PROOF_REQUIRED", "latency", {}),)
        elif status == "REJECT":
            issues = (RealizationIssueV0("machine.operation_missing", "REJECT", h("op"), {}),)
        return RealizationAdmissionReceiptV0(
            problem_hash=problem_hash or self.realization_problem_hash,
            candidate_hash=candidate.candidate_hash,
            realization_hash=candidate.realization_hash,
            semantic_claim_hash=candidate.semantic_claim_hash,
            artifact_manifest_hash=candidate.artifact_manifest_hash,
            transformation_semantic_hash=candidate.transformation_semantic_hash,
            transformation_regime_binding_hash=candidate.transformation_regime_binding_hash,
            semantic_relation=candidate.semantic_relation,
            regime_preservation_claim_hash=candidate.regime_preservation_claim_hash,
            resource_estimate_claim_hash=candidate.resource_estimate_claim_hash,
            machine_hash=candidate.machine_hash,
            policy_hash=h("admission-policy"),
            regime_hash=h("regime"),
            resource_catalog_hash=self.catalog.catalog_hash,
            machine_compatibility_hash=h("machine-eval-" + candidate.machine_hash[:8]),
            regime_evaluation_hash=h("regime-eval-" + candidate.machine_hash[:8]),
            realization_evidence_evaluation_hash=h("realization-evidence-" + candidate.machine_hash[:8]),
            regime_evidence_evaluation_hash=h("regime-evidence-" + candidate.machine_hash[:8]),
            resource_evidence_evaluation_hash=h("resource-evidence-" + candidate.machine_hash[:8]),
            issues=issues,
        )

    def evaluate(self, candidates, selected, *, rule="PARETO_MEMBER", dimensions=("latency",)):
        entries = tuple((candidate, self.receipt(candidate)) for candidate in candidates)
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, rule, tuple(dimensions))
        problem = RealizationSelectionProblemV0(
            self.realization_problem_hash,
            policy.policy_hash,
            tuple(receipt.receipt_hash for _, receipt in entries),
        )
        decision = RealizationSelectionDecisionV0(problem.problem_hash, selected.candidate_hash)
        return evaluate_realization_selection(
            problem,
            decision,
            policy=policy,
            resource_catalog=self.catalog,
            entries=entries,
        )

    def test_pareto_policy_accepts_nondominated_candidate(self):
        fast = self.candidate("fast", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 5))
        slow = self.candidate("slow", ResourceBoundV0.exact("latency", 8), ResourceBoundV0.exact("energy", 5))
        receipt = self.evaluate((fast, slow), fast)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.pareto_candidate_hashes, (fast.candidate_hash,))
        self.assertEqual(parse_residual(residual_from_realization_selection(receipt)).status, "CLOSED")

    def test_pareto_policy_rejects_dominated_candidate(self):
        fast = self.candidate("fast", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 5))
        slow = self.candidate("slow", ResourceBoundV0.exact("latency", 8), ResourceBoundV0.exact("energy", 5))
        receipt = self.evaluate((fast, slow), slow)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("selection.not_pareto_member", {item.kind for item in receipt.issues})

    def test_multidimensional_tradeoff_keeps_both_on_pareto_front(self):
        low_latency = self.candidate("latency", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 10))
        low_energy = self.candidate("energy", ResourceBoundV0.exact("latency", 5), ResourceBoundV0.exact("energy", 2))
        receipt = self.evaluate((low_latency, low_energy), low_latency, dimensions=("latency", "energy"))
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(set(receipt.pareto_candidate_hashes), {low_latency.candidate_hash, low_energy.candidate_hash})

    def test_lexicographic_minimum_is_verified(self):
        first = self.candidate("first", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 9))
        second = self.candidate("second", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        receipt = self.evaluate((first, second), second, rule="LEXICOGRAPHIC_MIN", dimensions=("latency", "energy"))
        self.assertEqual(receipt.status, "PASS")
        bad = self.evaluate((first, second), first, rule="LEXICOGRAPHIC_MIN", dimensions=("latency", "energy"))
        self.assertEqual(bad.status, "REJECT")
        self.assertIn("selection.not_lexicographic_minimum", {item.kind for item in bad.issues})

    def test_unknown_alternative_bound_prevents_claim_of_lexicographic_optimality(self):
        known = self.candidate("known", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        unknown = self.candidate("unknown", ResourceBoundV0("latency", 0, None), ResourceBoundV0.exact("energy", 1))
        receipt = self.evaluate((known, unknown), known, rule="LEXICOGRAPHIC_MIN", dimensions=("latency",))
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("selection.lexicographic_bound_unknown", {item.kind for item in receipt.issues})

    def test_selection_decision_provenance_does_not_change_decision_identity(self):
        candidate = self.candidate("one", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        admission = self.receipt(candidate)
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, "PARETO_MEMBER", ("latency",))
        problem = RealizationSelectionProblemV0(self.realization_problem_hash, policy.policy_hash, (admission.receipt_hash,))
        left = RealizationSelectionDecisionV0(problem.problem_hash, candidate.candidate_hash, (h("planner-a"),))
        right = RealizationSelectionDecisionV0(problem.problem_hash, candidate.candidate_hash, (h("planner-b"),))
        self.assertEqual(left.decision_hash, right.decision_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_non_admitted_candidate_cannot_be_selected(self):
        candidate = self.candidate("open", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        admission = self.receipt(candidate, status="PROOF_REQUIRED")
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, "PARETO_MEMBER", ("latency",))
        problem = RealizationSelectionProblemV0(self.realization_problem_hash, policy.policy_hash, (admission.receipt_hash,))
        decision = RealizationSelectionDecisionV0(problem.problem_hash, candidate.candidate_hash)
        result = evaluate_realization_selection(
            problem,
            decision,
            policy=policy,
            resource_catalog=self.catalog,
            entries=((candidate, admission),),
        )
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("selection.selected_candidate_not_admitted", {item.kind for item in result.issues})

    def test_candidate_receipt_set_is_exactly_bound(self):
        first = self.candidate("first", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        second = self.candidate("second", ResourceBoundV0.exact("latency", 3), ResourceBoundV0.exact("energy", 3))
        first_receipt = self.receipt(first)
        second_receipt = self.receipt(second)
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, "PARETO_MEMBER", ("latency",))
        problem = RealizationSelectionProblemV0(self.realization_problem_hash, policy.policy_hash, (first_receipt.receipt_hash,))
        decision = RealizationSelectionDecisionV0(problem.problem_hash, first.candidate_hash)
        result = evaluate_realization_selection(
            problem,
            decision,
            policy=policy,
            resource_catalog=self.catalog,
            entries=((first, first_receipt), (second, second_receipt)),
        )
        self.assertEqual(result.status, "REJECT")
        self.assertIn("selection.candidate_receipt_set_mismatch", {item.kind for item in result.issues})

    def test_receipt_from_different_realization_problem_is_rejected(self):
        candidate = self.candidate("foreign", ResourceBoundV0.exact("latency", 1), ResourceBoundV0.exact("energy", 1))
        foreign_receipt = self.receipt(candidate, problem_hash=h("other-realization-problem"))
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, "PARETO_MEMBER", ("latency",))
        problem = RealizationSelectionProblemV0(
            self.realization_problem_hash,
            policy.policy_hash,
            (foreign_receipt.receipt_hash,),
        )
        decision = RealizationSelectionDecisionV0(problem.problem_hash, candidate.candidate_hash)
        result = evaluate_realization_selection(
            problem,
            decision,
            policy=policy,
            resource_catalog=self.catalog,
            entries=((candidate, foreign_receipt),),
        )
        self.assertEqual(result.status, "REJECT")
        self.assertIn(
            "selection.receipt_realization_problem_mismatch",
            {item.kind for item in result.issues},
        )


if __name__ == "__main__":
    unittest.main()
