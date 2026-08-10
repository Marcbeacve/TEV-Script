from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0
from tev_script.semantic_resource_algebra_v0 import (
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceDimensionV0,
    ResourceVectorV0,
)
from tev_script.semantic_resource_calibration_v0 import (
    ResourceCalibrationV0,
    evaluate_resource_calibration,
    residual_from_resource_calibration,
)
from tev_script.semantic_resource_evidence_v0 import ResourceEstimateClaimV0
from tev_script.semantic_resource_measurement_v0 import (
    ResourceMeasurementClaimV0,
    ResourceMeasurementEvaluationV0,
    ResourceMeasurementIssueV0,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def realization_receipt(estimate_hash: str, *, issues=()) -> RealizationAdmissionReceiptV0:
    return RealizationAdmissionReceiptV0(
        problem_hash=h("problem"),
        candidate_hash=h("candidate"),
        realization_hash=h("realization"),
        semantic_claim_hash=h("semantic-claim"),
        artifact_manifest_hash=h("manifest"),
        transformation_semantic_hash=h("transformation"),
        transformation_regime_binding_hash=h("binding"),
        semantic_relation="EXACT_EQUIVALENT",
        regime_preservation_claim_hash=h("preservation"),
        resource_estimate_claim_hash=estimate_hash,
        machine_hash=h("machine"),
        policy_hash=h("policy"),
        regime_hash=h("regime"),
        resource_catalog_hash=h("placeholder-catalog"),
        machine_compatibility_hash=h("machine-evaluation"),
        regime_evaluation_hash=h("regime-evaluation"),
        realization_evidence_evaluation_hash=h("semantic-evidence"),
        regime_evidence_evaluation_hash=h("regime-evidence"),
        resource_evidence_evaluation_hash=h("resource-evidence"),
        issues=tuple(issues),
    )


class ResourceCalibrationV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
            )
        )
        self.context = h("execution-context")
        self.realization = h("realization")
        self.predicted = ResourceVectorV0(
            (
                ResourceBoundV0("latency", 0, 10),
                ResourceBoundV0("energy", 0, 5),
            ),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        self.estimate = ResourceEstimateClaimV0(
            self.realization,
            self.context,
            self.predicted.vector_hash,
            self.catalog.catalog_hash,
            "ANALYTIC_BOUND",
            h("estimator"),
            h("estimate-scope"),
        )
        self.receipt = realization_receipt(self.estimate.estimate_claim_hash)
        # Synthetic receipt helper uses a placeholder catalog in unrelated
        # admission fields; calibration binds the exact catalog independently.
        object.__setattr__(self.receipt, "realization_hash", self.realization)
        object.__setattr__(self.receipt, "resource_catalog_hash", self.catalog.catalog_hash)

    def measurement(self, vector: ResourceVectorV0, *, context=None):
        claim = ResourceMeasurementClaimV0(
            h("activation"),
            self.realization,
            context or self.context,
            self.catalog.catalog_hash,
            vector.vector_hash,
            h("epoch"),
        )
        evaluation = ResourceMeasurementEvaluationV0(
            claim.measurement_claim_hash,
            h("measurement-record"),
            h("activation"),
            self.realization,
            context or self.context,
            self.catalog.catalog_hash,
            h("measurement-evidence-evaluation"),
            (),
        )
        return claim, evaluation

    def calibration(self, claim):
        return ResourceCalibrationV0(
            self.receipt.receipt_hash,
            self.estimate.estimate_claim_hash,
            claim.measurement_claim_hash,
            self.catalog.catalog_hash,
        )

    def evaluate(self, observed, *, context=None, measurement_issues=()):
        claim = ResourceMeasurementClaimV0(
            h("activation"),
            self.realization,
            context or self.context,
            self.catalog.catalog_hash,
            observed.vector_hash,
            h("epoch"),
        )
        evaluation = ResourceMeasurementEvaluationV0(
            claim.measurement_claim_hash,
            h("measurement-record"),
            h("activation"),
            self.realization,
            context or self.context,
            self.catalog.catalog_hash,
            h("measurement-evidence-evaluation"),
            tuple(measurement_issues),
        )
        return evaluate_resource_calibration(
            self.calibration(claim),
            realization_receipt=self.receipt,
            estimate_claim=self.estimate,
            predicted_resources=self.predicted,
            measurement_claim=claim,
            measurement_evaluation=evaluation,
            observed_resources=observed,
            resource_catalog=self.catalog,
        )

    def vector(self, latency, energy, *, complete=True):
        return ResourceVectorV0(
            (
                latency,
                energy,
            ),
            complete=complete,
            catalog_hash=self.catalog.catalog_hash,
        )

    def test_observation_inside_predicted_bounds_supports_prediction(self):
        observed = self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3))
        evaluation = self.evaluate(observed)
        self.assertEqual(evaluation.verdict, "SUPPORTED")
        self.assertTrue(all(item.verdict == "WITHIN_BOUND" for item in evaluation.dimension_results))
        self.assertEqual(parse_residual(residual_from_resource_calibration(evaluation)).status, "CLOSED")

    def test_measurement_above_predicted_upper_falsifies(self):
        observed = self.vector(ResourceBoundV0.exact("latency", 11), ResourceBoundV0.exact("energy", 3))
        evaluation = self.evaluate(observed)
        self.assertEqual(evaluation.verdict, "FALSIFIED")
        by_dimension = {item.dimension_id: item.verdict for item in evaluation.dimension_results}
        self.assertEqual(by_dimension["latency"], "BOUND_VIOLATED")
        self.assertEqual(parse_residual(residual_from_resource_calibration(evaluation)).status, "OPEN")

    def test_uncertain_measurement_overlapping_boundary_is_inconclusive(self):
        observed = self.vector(ResourceBoundV0("latency", 9, 12), ResourceBoundV0.exact("energy", 3))
        evaluation = self.evaluate(observed)
        self.assertEqual(evaluation.verdict, "INCONCLUSIVE")
        by_dimension = {item.dimension_id: item.verdict for item in evaluation.dimension_results}
        self.assertEqual(by_dimension["latency"], "INCONCLUSIVE")

    def test_unknown_predicted_upper_can_still_support_observed_value_above_lower(self):
        predicted = ResourceVectorV0(
            (
                ResourceBoundV0("latency", 0, None),
                ResourceBoundV0("energy", 0, 5),
            ),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        estimate = ResourceEstimateClaimV0(
            self.realization,
            self.context,
            predicted.vector_hash,
            self.catalog.catalog_hash,
            "ANALYTIC_BOUND",
            h("estimator-unknown"),
            h("estimate-scope"),
        )
        receipt = realization_receipt(estimate.estimate_claim_hash)
        object.__setattr__(receipt, "realization_hash", self.realization)
        object.__setattr__(receipt, "resource_catalog_hash", self.catalog.catalog_hash)
        observed = self.vector(ResourceBoundV0.exact("latency", 100), ResourceBoundV0.exact("energy", 3))
        claim, measurement_eval = self.measurement(observed)
        calibration = ResourceCalibrationV0(
            receipt.receipt_hash,
            estimate.estimate_claim_hash,
            claim.measurement_claim_hash,
            self.catalog.catalog_hash,
        )
        evaluation = evaluate_resource_calibration(
            calibration,
            realization_receipt=receipt,
            estimate_claim=estimate,
            predicted_resources=predicted,
            measurement_claim=claim,
            measurement_evaluation=measurement_eval,
            observed_resources=observed,
            resource_catalog=self.catalog,
        )
        self.assertEqual(evaluation.verdict, "SUPPORTED")

    def test_measurement_from_different_execution_context_cannot_calibrate(self):
        observed = self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3))
        evaluation = self.evaluate(observed, context=h("other-context"))
        self.assertEqual(evaluation.verdict, "FALSIFIED")
        self.assertIn("calibration.execution_context_mismatch", {item.kind for item in evaluation.issues})

    def test_non_admitted_measurement_does_not_calibrate_as_support(self):
        observed = self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3))
        evaluation = self.evaluate(
            observed,
            measurement_issues=(
                ResourceMeasurementIssueV0(
                    "measurement.evidence.required",
                    "PROOF_REQUIRED",
                    h("measurement"),
                    {},
                ),
            ),
        )
        self.assertEqual(evaluation.verdict, "INCONCLUSIVE")
        self.assertIn("calibration.measurement_not_admitted", {item.kind for item in evaluation.issues})

    def test_selecting_non_catalog_dimension_is_rejected(self):
        observed = self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3))
        claim, measurement_eval = self.measurement(observed)
        with self.assertRaises(Exception):
            evaluate_resource_calibration(
                self.calibration(claim),
                realization_receipt=self.receipt,
                estimate_claim=self.estimate,
                predicted_resources=self.predicted,
                measurement_claim=claim,
                measurement_evaluation=measurement_eval,
                observed_resources=observed,
                resource_catalog=self.catalog,
                dimensions=("money",),
            )


if __name__ == "__main__":
    unittest.main()
