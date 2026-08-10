from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_authority_v0 import (
    ExecutionAuthorityPolicyV0,
    ExecutionAuthorityRecordV0,
    TransformationProgramBindingClaimV0,
    evaluate_execution_authority,
    residual_from_execution_authority,
)
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0
from tev_script.semantic_regime_v0 import TransformationRegimeBindingV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class ExecutionAuthorityV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.transformation_hash = h("transformation")
        self.program_hash = h("program")
        self.scope = h("authority-scope")
        self.regime_hash = h("regime")
        self.regime_binding = TransformationRegimeBindingV0(
            self.transformation_hash,
            self.regime_hash,
            self.scope,
        )
        self.verifier = h("authority-verifier")
        self.realization = RealizationAdmissionReceiptV0(
            problem_hash=h("problem"),
            candidate_hash=h("candidate"),
            realization_hash=h("realization"),
            semantic_claim_hash=h("semantic-claim"),
            artifact_manifest_hash=h("manifest"),
            transformation_semantic_hash=self.transformation_hash,
            transformation_regime_binding_hash=self.regime_binding.binding_hash,
            semantic_relation="EXACT_EQUIVALENT",
            regime_preservation_claim_hash=h("regime-preservation"),
            resource_estimate_claim_hash=h("resource-estimate"),
            machine_hash=h("machine"),
            policy_hash=h("realization-policy"),
            regime_hash=self.regime_hash,
            resource_catalog_hash=h("resource-catalog"),
            machine_compatibility_hash=h("machine-evaluation"),
            regime_evaluation_hash=h("regime-evaluation"),
            realization_evidence_evaluation_hash=h("realization-evidence"),
            regime_evidence_evaluation_hash=h("regime-evidence"),
            resource_evidence_evaluation_hash=h("resource-evidence"),
            issues=(),
        )
        self.footprint = ReactionFootprintV1(
            self.program_hash,
            h("source"),
            "entity.main",
            "start",
            ("start",),
            (),
            (),
            (),
            (),
            (),
            (),
            1,
            1,
            1,
            False,
        )
        self.contract = ReactionContractV1(
            "contract.main",
            "entity.main",
            "start",
            maximum_reachable_events=1,
            maximum_instruction_ceiling=1,
        )
        self.catalog = CapabilityLawCatalogV1("deployment.main", True)
        self.refinement = RefinementReceiptV1(
            self.contract.contract_hash,
            self.program_hash,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            "PASS",
        )
        self.binding = TransformationProgramBindingClaimV0(
            self.transformation_hash,
            self.program_hash,
            "EXACT_EQUIVALENT",
            self.scope,
        )
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "transformation-program-binding",
                    ("PROOF",),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = ExecutionAuthorityPolicyV0(
            self.evidence_policy.policy_hash,
            ("EXACT_EQUIVALENT",),
            (),
            True,
        )

    def evidence(self, binding=None, *, status="ACTIVE"):
        claim = binding or self.binding
        return EvidenceItemV0(
            "e.authority." + status.lower(),
            claim.binding_claim_hash,
            claim.scope_hash,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("authority-witness-" + status.lower()),
            status=status,
        )

    def record(self, binding=None, *, evidence_hashes=()):
        return ExecutionAuthorityRecordV0(
            self.realization.receipt_hash,
            binding or self.binding,
            self.contract.contract_hash,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            self.refinement.receipt_hash,
            self.evidence_policy.policy_hash,
            tuple(evidence_hashes),
        )

    def evaluate(
        self,
        record,
        *,
        evidence=(),
        catalog=None,
        refinement=None,
        footprint=None,
        regime_binding=None,
    ):
        return evaluate_execution_authority(
            record,
            realization_receipt=self.realization,
            transformation_regime_binding=regime_binding or self.regime_binding,
            reaction_contract=self.contract,
            reaction_footprint=footprint or self.footprint,
            law_catalog=catalog or self.catalog,
            refinement_receipt=refinement or self.refinement,
            policy=self.policy,
            binding_evidence_policy=self.evidence_policy,
            evidence=tuple(evidence),
        )

    def test_exact_binding_plus_causal_refinement_closes_authority(self):
        evidence = self.evidence()
        receipt = self.evaluate(
            self.record(evidence_hashes=(evidence.evidence_hash,)),
            evidence=(evidence,),
        )
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.realization_receipt_hash, self.realization.receipt_hash)
        self.assertEqual(receipt.transformation_semantic_hash, self.transformation_hash)
        self.assertEqual(receipt.transformation_regime_binding_hash, self.regime_binding.binding_hash)
        self.assertEqual(receipt.semantic_scope_hash, self.scope)
        self.assertEqual(receipt.program_semantic_hash, self.program_hash)
        self.assertEqual(parse_residual(residual_from_execution_authority(receipt)).status, "CLOSED")

    def test_mapping_without_evidence_remains_open(self):
        receipt = self.evaluate(self.record())
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("authority.evidence.required", {item.kind for item in receipt.issues})

    def test_refinement_proof_required_propagates_without_reinterpreting_it(self):
        evidence = self.evidence()
        open_refinement = RefinementReceiptV1(
            self.contract.contract_hash,
            self.program_hash,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            "PROOF_REQUIRED",
            pending_obligations=("proof.remaining",),
        )
        record = ExecutionAuthorityRecordV0(
            self.realization.receipt_hash,
            self.binding,
            self.contract.contract_hash,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            open_refinement.receipt_hash,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        receipt = self.evaluate(record, evidence=(evidence,), refinement=open_refinement)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("authority.refinement_not_admitted", {item.kind for item in receipt.issues})

    def test_incomplete_capability_law_catalog_cannot_close_under_strict_policy(self):
        incomplete = CapabilityLawCatalogV1("deployment.unknown", False)
        refinement = RefinementReceiptV1(
            self.contract.contract_hash,
            self.program_hash,
            self.footprint.footprint_hash,
            incomplete.catalog_hash,
            "PASS",
        )
        evidence = self.evidence()
        record = ExecutionAuthorityRecordV0(
            self.realization.receipt_hash,
            self.binding,
            self.contract.contract_hash,
            self.footprint.footprint_hash,
            incomplete.catalog_hash,
            refinement.receipt_hash,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        receipt = self.evaluate(
            record,
            evidence=(evidence,),
            catalog=incomplete,
            refinement=refinement,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("authority.law_catalog_incomplete", {item.kind for item in receipt.issues})

    def test_transformation_program_binding_cannot_point_at_different_footprint_program(self):
        wrong_binding = TransformationProgramBindingClaimV0(
            self.transformation_hash,
            h("other-program"),
            "EXACT_EQUIVALENT",
            self.scope,
        )
        evidence = self.evidence(wrong_binding)
        record = self.record(wrong_binding, evidence_hashes=(evidence.evidence_hash,))
        receipt = self.evaluate(record, evidence=(evidence,))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("authority.program_footprint_mismatch", {item.kind for item in receipt.issues})

    def test_binding_scope_cannot_be_narrower_or_different_than_realization_regime_scope(self):
        wrong_scope = h("different-scope")
        wrong_binding = TransformationProgramBindingClaimV0(
            self.transformation_hash,
            self.program_hash,
            "EXACT_EQUIVALENT",
            wrong_scope,
        )
        wrong_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "transformation-program-binding",
                    ("PROOF",),
                    scope_hash=wrong_scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        wrong_execution_policy = ExecutionAuthorityPolicyV0(wrong_policy.policy_hash)
        evidence = EvidenceItemV0(
            "e.wrong-scope",
            wrong_binding.binding_claim_hash,
            wrong_scope,
            "PROOF",
            verifier_hash=self.verifier,
            witness_hash=h("wrong-scope-witness"),
        )
        record = ExecutionAuthorityRecordV0(
            self.realization.receipt_hash,
            wrong_binding,
            self.contract.contract_hash,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            self.refinement.receipt_hash,
            wrong_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        receipt = evaluate_execution_authority(
            record,
            realization_receipt=self.realization,
            transformation_regime_binding=self.regime_binding,
            reaction_contract=self.contract,
            reaction_footprint=self.footprint,
            law_catalog=self.catalog,
            refinement_receipt=self.refinement,
            policy=wrong_execution_policy,
            binding_evidence_policy=wrong_policy,
            evidence=(evidence,),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("authority.binding_scope_mismatch", {item.kind for item in receipt.issues})

    def test_falsified_binding_evidence_rejects_authority(self):
        good = self.evidence()
        falsified = EvidenceItemV0(
            "e.authority.counterexample",
            self.binding.binding_claim_hash,
            h("counterexample-scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        record = self.record(evidence_hashes=(good.evidence_hash,))
        receipt = self.evaluate(record, evidence=(good, falsified))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("authority.evidence.falsified", {item.kind for item in receipt.issues})


if __name__ == "__main__":
    unittest.main()
