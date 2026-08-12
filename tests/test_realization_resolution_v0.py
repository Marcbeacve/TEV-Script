from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_realization_resolution_v0 import resolve_realization_selection
from tev_script.semantic_realization_selection_v0 import (
    RealizationSelectionPolicyV0,
    RealizationSelectionProblemV0,
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


def h(label: str) -> str:
    return canonical_hash({"test": label})


class RealizationResolutionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
            )
        )
        self.realization_problem_hash = h("realization-problem")

    def candidate(self, label: str, latency, energy) -> RealizationCandidateV0:
        return RealizationCandidateV0(
            h("transformation"),
            h("binding"),
            "tev.realization.test",
            h("machine-" + label),
            h("manifest-" + label),
            "EXACT_EQUIVALENT",
            predicted_resources=ResourceVectorV0(
                (latency, energy),
                complete=True,
                catalog_hash=self.catalog.catalog_hash,
            ),
            resource_estimate_claim_hash=h("estimate-" + label),
            regime_preservation_claim_hash=h("preservation-" + label),
        )

    def admission(self, candidate: RealizationCandidateV0, *, status: str = "PASS") -> RealizationAdmissionReceiptV0:
        issues = ()
        if status == "PROOF_REQUIRED":
            issues = (RealizationIssueV0("resource.bound_unknown", "PROOF_REQUIRED", "latency", {}),)
        elif status == "REJECT":
            issues = (RealizationIssueV0("machine.operation_missing", "REJECT", h("operation"), {}),)
        return RealizationAdmissionReceiptV0(
            problem_hash=self.realization_problem_hash,
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

    def resolve(self, rows, *, rule="PARETO_MEMBER", dimensions=("latency",)):
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, rule, tuple(dimensions))
        problem = RealizationSelectionProblemV0(
            self.realization_problem_hash,
            policy.policy_hash,
            tuple(receipt.receipt_hash for _, receipt in rows),
        )
        return resolve_realization_selection(
            problem,
            policy=policy,
            resource_catalog=self.catalog,
            entries=rows,
        )

    def test_unique_pareto_member_is_selected(self):
        fast = self.candidate("fast", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 5))
        slow = self.candidate("slow", ResourceBoundV0.exact("latency", 8), ResourceBoundV0.exact("energy", 5))
        result = self.resolve(((fast, self.admission(fast)), (slow, self.admission(slow))))
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.state, "SELECTED")
        self.assertEqual(result.selected_candidate_hash, fast.candidate_hash)
        self.assertTrue(result.selection_receipt_hash)
        self.assertTrue(result.decision_hash)

    def test_pareto_tradeoff_is_indeterminate_without_preference(self):
        low_latency = self.candidate("latency", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 10))
        low_energy = self.candidate("energy", ResourceBoundV0.exact("latency", 5), ResourceBoundV0.exact("energy", 2))
        rows = ((low_latency, self.admission(low_latency)), (low_energy, self.admission(low_energy)))
        result = self.resolve(rows, dimensions=("latency", "energy"))
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertEqual(result.state, "INDETERMINATE")
        self.assertIn("selection.preference_required", {item.kind for item in result.issues})
        self.assertEqual(result.selected_candidate_hash, "")

    def test_lexicographic_tie_is_indeterminate(self):
        left = self.candidate("left", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        right = self.candidate("right", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        rows = ((left, self.admission(left)), (right, self.admission(right)))
        result = self.resolve(rows, rule="LEXICOGRAPHIC_MIN", dimensions=("latency", "energy"))
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertEqual(result.state, "INDETERMINATE")
        self.assertIn("selection.lexicographic_tie", {item.kind for item in result.issues})

    def test_unknown_lexicographic_bound_preserves_proof_required(self):
        known = self.candidate("known", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        unknown = self.candidate("unknown", ResourceBoundV0("latency", 0, None), ResourceBoundV0.exact("energy", 1))
        rows = ((known, self.admission(known)), (unknown, self.admission(unknown)))
        result = self.resolve(rows, rule="LEXICOGRAPHIC_MIN", dimensions=("latency",))
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertEqual(result.state, "INDETERMINATE")
        self.assertIn("selection.lexicographic_bound_unknown", {item.kind for item in result.issues})

    def test_all_rejected_is_no_admissible_realization(self):
        candidate = self.candidate("rejected", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        result = self.resolve(((candidate, self.admission(candidate, status="REJECT")),))
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.state, "NO_ADMISSIBLE_REALIZATION")
        self.assertEqual(result.selected_candidate_hash, "")

    def test_open_admission_is_indeterminate_not_no_admissible(self):
        candidate = self.candidate("open", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        result = self.resolve(((candidate, self.admission(candidate, status="PROOF_REQUIRED")),))
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertEqual(result.state, "INDETERMINATE")
        self.assertIn("selection.admission_open", {item.kind for item in result.issues})

    def test_input_permutation_does_not_change_resolution_identity(self):
        fast = self.candidate("fast", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 5))
        slow = self.candidate("slow", ResourceBoundV0.exact("latency", 8), ResourceBoundV0.exact("energy", 5))
        first = (fast, self.admission(fast))
        second = (slow, self.admission(slow))
        left = self.resolve((first, second))
        right = self.resolve((second, first))
        self.assertEqual(left.resolution_hash, right.resolution_hash)

    def test_candidate_receipt_set_mismatch_fails_closed(self):
        candidate = self.candidate("one", ResourceBoundV0.exact("latency", 2), ResourceBoundV0.exact("energy", 3))
        admission = self.admission(candidate)
        policy = RealizationSelectionPolicyV0(self.catalog.catalog_hash, "PARETO_MEMBER", ("latency",))
        problem = RealizationSelectionProblemV0(
            self.realization_problem_hash,
            policy.policy_hash,
            (h("foreign-receipt"),),
        )
        result = resolve_realization_selection(
            problem,
            policy=policy,
            resource_catalog=self.catalog,
            entries=((candidate, admission),),
        )
        self.assertEqual(result.status, "REJECT")
        self.assertEqual(result.state, "INDETERMINATE")
        self.assertIn("selection.candidate_receipt_set_mismatch", {item.kind for item in result.issues})


if __name__ == "__main__":
    unittest.main()
