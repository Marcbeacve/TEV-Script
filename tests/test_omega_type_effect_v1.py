from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_semantic_basis_v1 import FieldFactV1, SemanticFieldV1
from tev_script.omega_type_effect_v1 import (
    EPISTEMIC_QUALIFIERS,
    can_implicitly_assign_epistemic,
    effect_row,
    effect_row_substitutable,
    epistemic_type,
    lower_type_effect_to_field,
    refine_epistemic_type,
    validate_effect_row,
    validate_epistemic_refinement,
    validate_epistemic_type,
)


class EpistemicTypeTests(unittest.TestCase):
    def test_qualifier_set_is_closed_and_exact_assignment_only(self) -> None:
        self.assertEqual(
            EPISTEMIC_QUALIFIERS,
            frozenset({"Observed", "Inferred", "Predicted", "Hypothesis", "Verified"}),
        )
        observed = epistemic_type("Rat", "Observed")
        observed2 = epistemic_type("Rat", "Observed")
        predicted = epistemic_type("Rat", "Predicted")
        self.assertTrue(can_implicitly_assign_epistemic(observed, observed2))
        self.assertFalse(can_implicitly_assign_epistemic(observed, predicted))
        self.assertFalse(can_implicitly_assign_epistemic(observed, epistemic_type("Int", "Observed")))

    def test_unknown_qualifier_and_tampered_type_reject(self) -> None:
        with self.assertRaises(TevScriptError):
            epistemic_type("Rat", "Trusted")
        value = epistemic_type("Rat", "Observed")
        wire = {
            "schema": value.schema,
            "base_type": value.base_type,
            "qualifier": value.qualifier,
            "type_hash": "0" * 64,
        }
        with self.assertRaises(TevScriptError):
            validate_epistemic_type(wire)


class EpistemicRefinementTests(unittest.TestCase):
    T = "1" * 64

    def _types(self):
        return {
            name: epistemic_type("Rat", name)
            for name in EPISTEMIC_QUALIFIERS
        }

    def test_observed_requires_observation_evidence(self) -> None:
        types = self._types()
        rejected = refine_epistemic_type(types["Hypothesis"], types["Observed"], transformation_hash=self.T)
        self.assertEqual(rejected.status, "REJECT")
        passed = refine_epistemic_type(
            types["Hypothesis"], types["Observed"], transformation_hash=self.T,
            observation_evidence_hash="2" * 64,
        )
        self.assertEqual(passed.status, "PASS")

    def test_predicted_requires_model_evidence(self) -> None:
        types = self._types()
        rejected = refine_epistemic_type(types["Hypothesis"], types["Predicted"], transformation_hash=self.T)
        self.assertEqual(rejected.status, "REJECT")
        passed = refine_epistemic_type(
            types["Hypothesis"], types["Predicted"], transformation_hash=self.T,
            model_evidence_hash="3" * 64,
        )
        self.assertEqual(passed.status, "PASS")

    def test_verified_without_proof_is_proof_required_never_pass(self) -> None:
        types = self._types()
        pending = refine_epistemic_type(types["Inferred"], types["Verified"], transformation_hash=self.T)
        self.assertEqual(pending.status, "PROOF_REQUIRED")
        self.assertNotEqual(pending.status, "PASS")
        passed = refine_epistemic_type(
            types["Inferred"], types["Verified"], transformation_hash=self.T,
            proof_witness_hashes=("4" * 64,),
        )
        self.assertEqual(passed.status, "PASS")

    def test_inferred_and_hypothesis_are_explicit(self) -> None:
        types = self._types()
        inferred = refine_epistemic_type(types["Observed"], types["Inferred"], transformation_hash=self.T)
        self.assertEqual(inferred.status, "PASS")
        rejected = refine_epistemic_type(types["Observed"], types["Hypothesis"], transformation_hash=self.T)
        self.assertEqual(rejected.status, "REJECT")
        hypothesis = refine_epistemic_type(
            types["Observed"], types["Hypothesis"], transformation_hash=self.T,
            provenance_evidence_hash="5" * 64,
        )
        self.assertEqual(hypothesis.status, "PASS")

    def test_refinement_tamper_rejects(self) -> None:
        types = self._types()
        receipt = refine_epistemic_type(types["Observed"], types["Inferred"], transformation_hash=self.T)
        wire = {
            "schema": receipt.schema,
            "source_type_hash": receipt.source_type_hash,
            "target_type_hash": receipt.target_type_hash,
            "transformation_hash": receipt.transformation_hash,
            "observation_evidence_hash": receipt.observation_evidence_hash,
            "model_evidence_hash": receipt.model_evidence_hash,
            "provenance_evidence_hash": receipt.provenance_evidence_hash,
            "proof_witness_hashes": list(receipt.proof_witness_hashes),
            "status": receipt.status,
            "reason": receipt.reason,
            "receipt_hash": "0" * 64,
        }
        with self.assertRaises(TevScriptError):
            validate_epistemic_refinement(wire)


class EffectRowTests(unittest.TestCase):
    def test_effect_row_is_canonical_and_grants_no_authority(self) -> None:
        left = effect_row(
            effects=("observe:file.read", "command:file.replace"),
            capabilities=("file.read", "file.replace"),
        )
        right = effect_row(
            effects=("command:file.replace", "observe:file.read"),
            capabilities=("file.replace", "file.read"),
        )
        self.assertEqual(left, right)
        self.assertFalse(left.grants_authority)
        self.assertEqual(validate_effect_row(left), left)
        with self.assertRaises(TevScriptError):
            effect_row(effects=("observe:file.read", "observe:file.read"))

    def test_effect_subset_substitution(self) -> None:
        actual = effect_row(effects=("observe:file.read",), capabilities=("file.read",))
        allowed = effect_row(
            effects=("observe:file.read", "command:file.replace"),
            capabilities=("file.read", "file.replace"),
        )
        self.assertTrue(effect_row_substitutable(actual, allowed))
        self.assertFalse(effect_row_substitutable(allowed, actual))


class TypeEffectLoweringTests(unittest.TestCase):
    def test_all_objects_lower_to_existing_field_basis(self) -> None:
        observed = epistemic_type("Rat", "Observed")
        inferred = epistemic_type("Rat", "Inferred")
        refinement = refine_epistemic_type(observed, inferred, transformation_hash="1" * 64)
        effects = effect_row(effects=("observe:file.read",), capabilities=("file.read",))
        field = lower_type_effect_to_field(observed, effects, refinement)
        self.assertIsInstance(field, SemanticFieldV1)
        self.assertTrue(all(isinstance(fact, FieldFactV1) for fact in field.facts))
        self.assertEqual(
            {fact.relation for fact in field.facts},
            {"tev.type.epistemic", "tev.type.effect_row", "tev.type.epistemic_refinement"},
        )


if __name__ == "__main__":
    unittest.main()
