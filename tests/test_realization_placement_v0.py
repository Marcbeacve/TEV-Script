from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_placement_v0 import (
    MachineInstanceV0,
    PlacementCandidateV0,
    PlacementContextV0,
    PlacementPolicyV0,
    evaluate_placement,
    execution_context_hash,
    residual_from_placement,
)
from tev_script.semantic_realization_v0 import RealizationAdmissionReceiptV0, RealizationIssueV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def admitted_receipt(machine_profile_hash: str, *, rejected: bool = False) -> RealizationAdmissionReceiptV0:
    issues = (
        (RealizationIssueV0("realization.invalid", "REJECT", h("invalid"), {}),)
        if rejected
        else ()
    )
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
        resource_estimate_claim_hash=h("resource-estimate"),
        machine_hash=machine_profile_hash,
        policy_hash=h("realization-policy"),
        regime_hash=h("regime"),
        resource_catalog_hash=h("resource-catalog"),
        machine_compatibility_hash=h("machine-compatibility"),
        regime_evaluation_hash=h("regime-evaluation"),
        realization_evidence_evaluation_hash=h("realization-evidence"),
        regime_evidence_evaluation_hash=h("regime-evidence"),
        resource_evidence_evaluation_hash=h("resource-evidence"),
        issues=issues,
    )


class MachineInstanceAndPlacementV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = h("machine-profile")
        self.attribute = h("trusted-boot-attribute")
        self.instance = MachineInstanceV0(
            "inventory.node.a",
            self.profile,
            h("instance-principal"),
            immutable_attribute_claim_hashes=(self.attribute,),
            provenance={"inventory": "a"},
        )
        self.location = h("location-a")
        self.authority = h("authority-a")
        self.fault_domain = h("fault-a")
        self.communication = h("network-a")
        self.assumption = h("placement-assumption")
        self.context = PlacementContextV0(
            self.instance.machine_instance_hash,
            location_hash=self.location,
            authority_domain_hash=self.authority,
            fault_domain_hash=self.fault_domain,
            communication_domain_hash=self.communication,
            policy_context_hash=h("policy-context"),
            assumption_hashes=(self.assumption,),
        )
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "instance-attestation",
                    ("ATTESTATION",),
                    scope_hash=h("instance-attestation-scope"),
                    trusted_verifier_hashes=(h("attestation-verifier"),),
                ),
            )
        )
        self.policy = PlacementPolicyV0(
            self.evidence_policy.policy_hash,
            accepted_assumption_hashes=(self.assumption,),
            allowed_location_hashes=(self.location,),
            allowed_authority_domain_hashes=(self.authority,),
            allowed_fault_domain_hashes=(self.fault_domain,),
            allowed_communication_domain_hashes=(self.communication,),
            required_instance_attribute_claim_hashes=(self.attribute,),
        )
        self.receipt = admitted_receipt(self.profile)

    def evidence(self, *, evidence_id="e.instance", status="ACTIVE") -> EvidenceItemV0:
        return EvidenceItemV0(
            evidence_id,
            self.instance.machine_instance_hash,
            h("instance-attestation-scope"),
            "ATTESTATION",
            verifier_hash=h("attestation-verifier"),
            witness_hash=h("attestation-witness"),
            assumption_hashes=(self.assumption,),
            status=status,
        )

    def candidate(self, evidence_hashes=()) -> PlacementCandidateV0:
        return PlacementCandidateV0(
            self.receipt.receipt_hash,
            self.context.placement_context_hash,
            assumption_hashes=(self.assumption,),
            evidence_hashes=tuple(evidence_hashes),
            provenance={"planner": "test"},
        )

    def evaluate(self, candidate, evidence=(), **overrides):
        args = {
            "realization_receipt": self.receipt,
            "machine_instance": self.instance,
            "placement_context": self.context,
            "policy": self.policy,
            "instance_evidence_policy": self.evidence_policy,
            "evidence": tuple(evidence),
        }
        args.update(overrides)
        return evaluate_placement(candidate, **args)

    def test_instance_alias_and_provenance_do_not_change_instance_identity(self):
        other = MachineInstanceV0(
            "inventory.node.renamed",
            self.profile,
            self.instance.instance_principal_hash,
            immutable_attribute_claim_hashes=self.instance.immutable_attribute_claim_hashes,
            provenance={"inventory": "other"},
        )
        self.assertEqual(self.instance.machine_instance_hash, other.machine_instance_hash)
        self.assertNotEqual(self.instance.record_hash, other.record_hash)

    def test_admitted_realization_attested_instance_and_allowed_domains_pass(self):
        evidence = self.evidence()
        candidate = self.candidate((evidence.evidence_hash,))
        evaluation = self.evaluate(candidate, (evidence,))
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(parse_residual(residual_from_placement(evaluation)).status, "CLOSED")

    def test_missing_instance_attestation_is_proof_required(self):
        evaluation = self.evaluate(self.candidate())
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("placement.evidence.required", {item.kind for item in evaluation.issues})

    def test_revocation_keeps_evidence_identity_but_reopens_placement(self):
        active = self.evidence(evidence_id="e.active", status="ACTIVE")
        revoked = self.evidence(evidence_id="e.revoked", status="REVOKED")
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        candidate = self.candidate((active.evidence_hash,))
        self.assertEqual(self.evaluate(candidate, (active,)).status, "PASS")
        reopened = self.evaluate(candidate, (revoked,))
        self.assertEqual(reopened.status, "PROOF_REQUIRED")
        kinds = {item.kind for item in reopened.issues}
        self.assertIn("placement.evidence.inactive", kinds)
        self.assertNotIn("placement.evidence_reference_missing", kinds)

    def test_positive_attestation_must_be_candidate_bound(self):
        evidence = self.evidence()
        evaluation = self.evaluate(self.candidate(), (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("placement.evidence_unbound_support", {item.kind for item in evaluation.issues})

    def test_profile_mismatch_rejects_instance_even_when_attested(self):
        evidence = self.evidence()
        candidate = self.candidate((evidence.evidence_hash,))
        wrong = MachineInstanceV0(
            "wrong.profile.instance",
            h("other-profile"),
            self.instance.instance_principal_hash,
            immutable_attribute_claim_hashes=(self.attribute,),
        )
        wrong_context = PlacementContextV0(
            wrong.machine_instance_hash,
            location_hash=self.location,
            authority_domain_hash=self.authority,
            fault_domain_hash=self.fault_domain,
            communication_domain_hash=self.communication,
            policy_context_hash=h("policy-context"),
            assumption_hashes=(self.assumption,),
        )
        wrong_candidate = PlacementCandidateV0(
            self.receipt.receipt_hash,
            wrong_context.placement_context_hash,
            assumption_hashes=(self.assumption,),
        )
        evaluation = self.evaluate(
            wrong_candidate,
            machine_instance=wrong,
            placement_context=wrong_context,
            evidence=(),
        )
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("placement.machine_profile_mismatch", {item.kind for item in evaluation.issues})

    def test_location_or_authority_change_does_not_change_realization_identity_but_changes_placement(self):
        moved = PlacementContextV0(
            self.instance.machine_instance_hash,
            location_hash=h("location-b"),
            authority_domain_hash=self.authority,
            fault_domain_hash=self.fault_domain,
            communication_domain_hash=self.communication,
            policy_context_hash=h("policy-context"),
            assumption_hashes=(self.assumption,),
        )
        self.assertNotEqual(self.context.placement_context_hash, moved.placement_context_hash)
        self.assertEqual(self.receipt.realization_hash, h("realization"))
        candidate = PlacementCandidateV0(
            self.receipt.receipt_hash,
            moved.placement_context_hash,
            assumption_hashes=(self.assumption,),
        )
        evaluation = self.evaluate(candidate, placement_context=moved)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("placement.location_not_allowed", {item.kind for item in evaluation.issues})

    def test_execution_context_changes_with_workload_or_placement_not_realization(self):
        first = execution_context_hash(
            realization_hash=self.receipt.realization_hash,
            machine_instance_hash=self.instance.machine_instance_hash,
            placement_context_hash=self.context.placement_context_hash,
            workload_hash=h("workload-a"),
        )
        second = execution_context_hash(
            realization_hash=self.receipt.realization_hash,
            machine_instance_hash=self.instance.machine_instance_hash,
            placement_context_hash=self.context.placement_context_hash,
            workload_hash=h("workload-b"),
        )
        self.assertNotEqual(first, second)
        self.assertEqual(self.receipt.realization_hash, h("realization"))

    def test_non_admitted_realization_cannot_be_placed(self):
        rejected = admitted_receipt(self.profile, rejected=True)
        candidate = PlacementCandidateV0(
            rejected.receipt_hash,
            self.context.placement_context_hash,
            assumption_hashes=(self.assumption,),
        )
        evaluation = self.evaluate(candidate, realization_receipt=rejected)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("placement.realization_not_admitted", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
