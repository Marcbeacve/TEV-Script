from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_cost_model_update_v0 import (
    CostModelUpdateV0,
    evaluate_cost_model_update,
    residual_from_cost_model_update,
)
from tev_script.semantic_cost_model_v0 import (
    CostContextEnvelopeV0,
    CostModelAdmissionReceiptV0,
    EmpiricalCostModelV0,
    empirical_envelope,
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


class CostModelUpdateV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (ResourceDimensionV0("latency", "ms", "SUM", "MAX"),)
        )
        self.realization = h("realization")
        self.context = h("context")

    def vector(self, value):
        return ResourceVectorV0(
            (ResourceBoundV0.exact("latency", value),),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )

    def measurement(self, label: str, value, *, issues=()):
        vector = self.vector(value)
        claim = ResourceMeasurementClaimV0(
            h("activation-" + label),
            self.realization,
            self.context,
            self.catalog.catalog_hash,
            vector.vector_hash,
            h("epoch-" + label),
        )
        evaluation = ResourceMeasurementEvaluationV0(
            claim.measurement_claim_hash,
            h("record-" + label),
            claim.activation_receipt_hash,
            self.realization,
            self.context,
            self.catalog.catalog_hash,
            h("evidence-" + label),
            tuple(issues),
        )
        return claim, evaluation, vector

    def model(self, label: str, entries):
        envelope = empirical_envelope((row[2] for row in entries), self.catalog)
        return EmpiricalCostModelV0(
            label,
            self.realization,
            self.catalog.catalog_hash,
            (
                CostContextEnvelopeV0(
                    self.context,
                    envelope,
                    tuple(row[0].measurement_claim_hash for row in entries),
                ),
            ),
        )

    def admission(self, model, *, issues=()):
        return CostModelAdmissionReceiptV0(
            model.model_hash,
            model.record_hash,
            self.realization,
            self.catalog.catalog_hash,
            h("cost-policy"),
            (h("measurement-evaluation-set"),),
            tuple(issues),
        )

    def update(self, parent, parent_receipt, successor, successor_receipt, new_entries):
        return CostModelUpdateV0(
            parent.model_hash,
            parent.record_hash,
            parent_receipt.receipt_hash,
            successor.model_hash,
            successor.record_hash,
            successor_receipt.receipt_hash,
            tuple(row[0].measurement_claim_hash for row in new_entries),
        )

    def test_new_evidence_can_change_record_without_changing_model_function(self):
        a = self.measurement("a", 4)
        b = self.measurement("b", 7)
        c = self.measurement("c", 5)
        parent = self.model("parent", (a, b))
        successor = self.model("successor", (a, b, c))
        self.assertEqual(parent.model_hash, successor.model_hash)
        self.assertNotEqual(parent.record_hash, successor.record_hash)

        parent_receipt = self.admission(parent)
        successor_receipt = self.admission(successor)
        update = self.update(parent, parent_receipt, successor, successor_receipt, (c,))
        result = evaluate_cost_model_update(
            update,
            parent_model=parent,
            parent_admission=parent_receipt,
            successor_model=successor,
            successor_admission=successor_receipt,
            new_measurements=((c[0], c[1]),),
        )
        self.assertEqual(result.status, "PASS")
        self.assertEqual(parse_residual(residual_from_cost_model_update(result)).status, "CLOSED")

    def test_envelope_extension_changes_model_identity_and_can_still_be_valid_update(self):
        a = self.measurement("a", 4)
        b = self.measurement("b", 7)
        c = self.measurement("c", 11)
        parent = self.model("parent", (a, b))
        successor = self.model("successor", (a, b, c))
        self.assertNotEqual(parent.model_hash, successor.model_hash)

        parent_receipt = self.admission(parent)
        successor_receipt = self.admission(successor)
        update = self.update(parent, parent_receipt, successor, successor_receipt, (c,))
        result = evaluate_cost_model_update(
            update,
            parent_model=parent,
            parent_admission=parent_receipt,
            successor_model=successor,
            successor_admission=successor_receipt,
            new_measurements=((c[0], c[1]),),
        )
        self.assertEqual(result.status, "PASS")

    def test_successor_cannot_silently_drop_parent_measurements(self):
        a = self.measurement("a", 4)
        b = self.measurement("b", 7)
        c = self.measurement("c", 11)
        parent = self.model("parent", (a, b))
        successor = self.model("successor", (b, c))
        parent_receipt = self.admission(parent)
        successor_receipt = self.admission(successor)
        update = self.update(parent, parent_receipt, successor, successor_receipt, (c,))
        result = evaluate_cost_model_update(
            update,
            parent_model=parent,
            parent_admission=parent_receipt,
            successor_model=successor,
            successor_admission=successor_receipt,
            new_measurements=((c[0], c[1]),),
        )
        self.assertEqual(result.status, "REJECT")
        self.assertIn("cost_model_update.successor_basis_mismatch", {item.kind for item in result.issues})

    def test_existing_parent_measurement_cannot_be_presented_as_new(self):
        a = self.measurement("a", 4)
        b = self.measurement("b", 7)
        parent = self.model("parent", (a,))
        successor = self.model("successor", (a, b))
        parent_receipt = self.admission(parent)
        successor_receipt = self.admission(successor)
        update = self.update(parent, parent_receipt, successor, successor_receipt, (a, b))
        result = evaluate_cost_model_update(
            update,
            parent_model=parent,
            parent_admission=parent_receipt,
            successor_model=successor,
            successor_admission=successor_receipt,
            new_measurements=((a[0], a[1]), (b[0], b[1])),
        )
        self.assertEqual(result.status, "REJECT")
        self.assertIn("cost_model_update.measurement_already_in_parent", {item.kind for item in result.issues})

    def test_non_admitted_new_measurement_keeps_update_open(self):
        a = self.measurement("a", 4)
        issue = ResourceMeasurementIssueV0(
            "measurement.evidence.required",
            "PROOF_REQUIRED",
            h("measurement-b"),
            {},
        )
        b = self.measurement("b", 7, issues=(issue,))
        parent = self.model("parent", (a,))
        successor = self.model("successor", (a, b))
        parent_receipt = self.admission(parent)
        successor_receipt = self.admission(successor)
        update = self.update(parent, parent_receipt, successor, successor_receipt, (b,))
        result = evaluate_cost_model_update(
            update,
            parent_model=parent,
            parent_admission=parent_receipt,
            successor_model=successor,
            successor_admission=successor_receipt,
            new_measurements=((b[0], b[1]),),
        )
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("cost_model_update.measurement_not_admitted", {item.kind for item in result.issues})


if __name__ == "__main__":
    unittest.main()
