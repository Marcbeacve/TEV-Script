from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_cost_model_v0 import (
    CostContextEnvelopeV0,
    CostModelAdmissionReceiptV0,
    CostModelIssueV0,
    EmpiricalCostModelV0,
)
from tev_script.semantic_cost_prediction_v0 import (
    CostPredictionRequestV0,
    evaluate_empirical_cost_prediction,
    residual_from_cost_prediction,
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


class CostPredictionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (ResourceDimensionV0("latency", "ms", "SUM", "MAX"),)
        )
        self.context = h("context")
        self.model_assumption = h("stationarity-assumption")
        self.vector = ResourceVectorV0(
            (ResourceBoundV0("latency", 4, 7),),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        self.model = EmpiricalCostModelV0(
            "model.test",
            h("realization"),
            self.catalog.catalog_hash,
            (
                CostContextEnvelopeV0(
                    self.context,
                    self.vector,
                    (h("measurement-a"), h("measurement-b")),
                ),
            ),
            assumption_hashes=(self.model_assumption,),
        )
        self.admission = CostModelAdmissionReceiptV0(
            self.model.model_hash,
            self.model.record_hash,
            self.model.realization_hash,
            self.catalog.catalog_hash,
            h("model-policy"),
            (h("measurement-eval-a"), h("measurement-eval-b")),
            (),
        )

    def request(self, *, context=None, model_hash=None, admission_hash=None, assumptions=()):
        return CostPredictionRequestV0(
            model_hash or self.model.model_hash,
            admission_hash or self.admission.receipt_hash,
            context or self.context,
            h("resource-scope"),
            tuple(assumptions),
        )

    def test_seen_context_projects_empirical_estimate_and_evidence(self):
        request = self.request()
        evaluation, estimate, vector, evidence = evaluate_empirical_cost_prediction(
            request,
            model=self.model,
            model_admission=self.admission,
            evidence_id="e.cost-model",
        )
        self.assertEqual(evaluation.status, "PASS")
        self.assertIsNotNone(estimate)
        self.assertIsNotNone(vector)
        self.assertIsNotNone(evidence)
        self.assertEqual(vector.vector_hash, self.vector.vector_hash)
        self.assertEqual(estimate.estimator_hash, self.model.model_hash)
        self.assertEqual(estimate.estimate_kind, "EMPIRICAL_ENVELOPE")
        self.assertEqual(evidence.claim_hash, estimate.estimate_claim_hash)
        self.assertEqual(evidence.method, "EMPIRICAL_OBSERVATION")
        self.assertEqual(evidence.witness_hash, self.admission.receipt_hash)
        self.assertEqual(parse_residual(residual_from_cost_prediction(evaluation)).status, "CLOSED")

    def test_model_and_request_assumptions_propagate_to_estimate_and_evidence(self):
        extra = h("prediction-assumption")
        evaluation, estimate, _, evidence = evaluate_empirical_cost_prediction(
            self.request(assumptions=(extra,)),
            model=self.model,
            model_admission=self.admission,
            evidence_id="e.cost-model",
        )
        self.assertEqual(evaluation.status, "PASS")
        expected = tuple(sorted((self.model_assumption, extra)))
        self.assertEqual(estimate.assumption_hashes, expected)
        self.assertEqual(evidence.assumption_hashes, expected)

    def test_unseen_context_remains_open_and_emits_no_estimate(self):
        evaluation, estimate, vector, evidence = evaluate_empirical_cost_prediction(
            self.request(context=h("unseen-context")),
            model=self.model,
            model_admission=self.admission,
            evidence_id="e.cost-model",
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIsNone(estimate)
        self.assertIsNone(vector)
        self.assertIsNone(evidence)
        self.assertIn("cost_prediction.context_unseen", {item.kind for item in evaluation.issues})

    def test_non_admitted_model_cannot_emit_prediction(self):
        open_admission = CostModelAdmissionReceiptV0(
            self.model.model_hash,
            self.model.record_hash,
            self.model.realization_hash,
            self.catalog.catalog_hash,
            h("model-policy"),
            (h("measurement-eval-a"),),
            (
                CostModelIssueV0(
                    "cost_model.insufficient_measurements",
                    "PROOF_REQUIRED",
                    self.context,
                    {},
                ),
            ),
        )
        request = self.request(admission_hash=open_admission.receipt_hash)
        evaluation, estimate, vector, evidence = evaluate_empirical_cost_prediction(
            request,
            model=self.model,
            model_admission=open_admission,
            evidence_id="e.cost-model",
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIsNone(estimate)
        self.assertIsNone(vector)
        self.assertIsNone(evidence)
        self.assertIn("cost_prediction.model_not_admitted", {item.kind for item in evaluation.issues})

    def test_request_for_different_model_is_rejected(self):
        evaluation, estimate, vector, evidence = evaluate_empirical_cost_prediction(
            self.request(model_hash=h("other-model")),
            model=self.model,
            model_admission=self.admission,
            evidence_id="e.cost-model",
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIsNone(estimate)
        self.assertIsNone(vector)
        self.assertIsNone(evidence)
        self.assertIn("cost_prediction.model_mismatch", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
