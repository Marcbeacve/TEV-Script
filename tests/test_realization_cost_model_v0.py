from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_cost_model_v0 import (
    CostContextEnvelopeV0,
    CostModelPolicyV0,
    EmpiricalCostModelV0,
    empirical_envelope,
    evaluate_empirical_cost_model,
    residual_from_cost_model_admission,
)
from tev_script.semantic_resource_algebra_v0 import (
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceDimensionV0,
    ResourceVectorV0,
)
from tev_script.semantic_resource_measurement_v0 import (
    ResourceMeasurementClaimV0,
    ResourceMeasurementEvaluationV0,
    ResourceMeasurementIssueV0,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class EmpiricalCostModelV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
            )
        )
        self.realization = h("realization")
        self.context = h("execution-context")
        self.policy = CostModelPolicyV0(minimum_measurements_per_context=2)

    def vector(self, latency, energy, *, complete=True):
        return ResourceVectorV0(
            (latency, energy),
            complete=complete,
            catalog_hash=self.catalog.catalog_hash,
        )

    def measurement(self, label: str, vector: ResourceVectorV0, *, context=None, realization=None, issues=()):
        claim = ResourceMeasurementClaimV0(
            h("activation-" + label),
            realization or self.realization,
            context or self.context,
            self.catalog.catalog_hash,
            vector.vector_hash,
            h("epoch-" + label),
        )
        evaluation = ResourceMeasurementEvaluationV0(
            claim.measurement_claim_hash,
            h("record-" + label),
            claim.activation_receipt_hash,
            claim.realization_hash,
            claim.execution_context_hash,
            claim.resource_catalog_hash,
            h("evidence-eval-" + label),
            tuple(issues),
        )
        return claim, evaluation, vector

    def model_from(self, entries, *, model_id="cost.model", provenance=None, assumptions=()):
        envelope = empirical_envelope((vector for _, _, vector in entries), self.catalog)
        return EmpiricalCostModelV0(
            model_id,
            self.realization,
            self.catalog.catalog_hash,
            (
                CostContextEnvelopeV0(
                    self.context,
                    envelope,
                    tuple(claim.measurement_claim_hash for claim, _, _ in entries),
                ),
            ),
            assumption_hashes=tuple(assumptions),
            provenance=provenance or {},
        )

    def baseline(self):
        first = self.measurement(
            "a",
            self.vector(ResourceBoundV0.exact("latency", 4), ResourceBoundV0.exact("energy", 2)),
        )
        second = self.measurement(
            "b",
            self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3)),
        )
        return first, second

    def test_empirical_envelope_model_matches_admitted_measurements(self):
        entries = self.baseline()
        model = self.model_from(entries)
        receipt = evaluate_empirical_cost_model(
            model,
            policy=self.policy,
            resource_catalog=self.catalog,
            measurements=entries,
        )
        self.assertEqual(receipt.status, "PASS")
        envelope = model.envelope_for(self.context)
        self.assertIsNotNone(envelope)
        self.assertEqual(envelope.resource_vector.bound("latency").lower, 4)
        self.assertEqual(envelope.resource_vector.bound("latency").upper, 7)
        self.assertEqual(parse_residual(residual_from_cost_model_admission(receipt)).status, "CLOSED")

    def test_model_label_and_provenance_do_not_change_model_identity(self):
        entries = self.baseline()
        left = self.model_from(entries, model_id="model.left", provenance={"builder": "a"})
        right = self.model_from(entries, model_id="model.right", provenance={"builder": "b"})
        self.assertEqual(left.model_hash, right.model_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_same_function_different_measurement_basis_keeps_model_identity_but_changes_record(self):
        first = self.measurement(
            "a",
            self.vector(ResourceBoundV0.exact("latency", 4), ResourceBoundV0.exact("energy", 2)),
        )
        second = self.measurement(
            "b",
            self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3)),
        )
        alternate_first = self.measurement(
            "c",
            self.vector(ResourceBoundV0.exact("latency", 4), ResourceBoundV0.exact("energy", 2)),
        )
        alternate_second = self.measurement(
            "d",
            self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3)),
        )
        left = self.model_from((first, second))
        right = self.model_from((alternate_first, alternate_second))
        self.assertEqual(left.model_hash, right.model_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_wrong_envelope_is_rejected(self):
        entries = self.baseline()
        wrong_vector = self.vector(
            ResourceBoundV0("latency", 0, 5),
            ResourceBoundV0("energy", 0, 3),
        )
        model = EmpiricalCostModelV0(
            "bad.model",
            self.realization,
            self.catalog.catalog_hash,
            (
                CostContextEnvelopeV0(
                    self.context,
                    wrong_vector,
                    tuple(claim.measurement_claim_hash for claim, _, _ in entries),
                ),
            ),
        )
        receipt = evaluate_empirical_cost_model(
            model,
            policy=self.policy,
            resource_catalog=self.catalog,
            measurements=entries,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("cost_model.envelope_mismatch", {item.kind for item in receipt.issues})

    def test_non_admitted_measurement_keeps_model_open(self):
        first, second = self.baseline()
        open_eval = ResourceMeasurementEvaluationV0(
            second[0].measurement_claim_hash,
            second[1].measurement_record_hash,
            second[1].activation_receipt_hash,
            second[1].realization_hash,
            second[1].execution_context_hash,
            second[1].resource_catalog_hash,
            second[1].evidence_evaluation_hash,
            (
                ResourceMeasurementIssueV0(
                    "measurement.evidence.required",
                    "PROOF_REQUIRED",
                    second[0].measurement_claim_hash,
                    {},
                ),
            ),
        )
        entries = (first, (second[0], open_eval, second[2]))
        model = self.model_from(entries)
        receipt = evaluate_empirical_cost_model(
            model,
            policy=self.policy,
            resource_catalog=self.catalog,
            measurements=entries,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("cost_model.measurement_not_admitted", {item.kind for item in receipt.issues})

    def test_measurement_for_other_realization_is_rejected(self):
        first = self.measurement(
            "a",
            self.vector(ResourceBoundV0.exact("latency", 4), ResourceBoundV0.exact("energy", 2)),
        )
        foreign = self.measurement(
            "foreign",
            self.vector(ResourceBoundV0.exact("latency", 7), ResourceBoundV0.exact("energy", 3)),
            realization=h("other-realization"),
        )
        model = self.model_from((first, foreign))
        receipt = evaluate_empirical_cost_model(
            model,
            policy=self.policy,
            resource_catalog=self.catalog,
            measurements=(first, foreign),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("cost_model.measurement_realization_mismatch", {item.kind for item in receipt.issues})

    def test_unmodeled_context_is_rejected(self):
        first, second = self.baseline()
        foreign = self.measurement(
            "other-context",
            self.vector(ResourceBoundV0.exact("latency", 5), ResourceBoundV0.exact("energy", 2)),
            context=h("other-context"),
        )
        model = self.model_from((first, second))
        receipt = evaluate_empirical_cost_model(
            model,
            policy=self.policy,
            resource_catalog=self.catalog,
            measurements=(first, second, foreign),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("cost_model.measurement_context_unmodeled", {item.kind for item in receipt.issues})

    def test_minimum_measurement_policy_remains_open_until_satisfied(self):
        entry = self.measurement(
            "one",
            self.vector(ResourceBoundV0.exact("latency", 4), ResourceBoundV0.exact("energy", 2)),
        )
        model = self.model_from((entry,))
        receipt = evaluate_empirical_cost_model(
            model,
            policy=self.policy,
            resource_catalog=self.catalog,
            measurements=(entry,),
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("cost_model.insufficient_measurements", {item.kind for item in receipt.issues})


if __name__ == "__main__":
    unittest.main()
