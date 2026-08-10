from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    CapabilityLawV1,
    PreparedReactionV1,
    ResourceAccessV1,
    ResourceLawV1,
)
from tev_script.semantic_delivery_plan_v0 import (
    DeliveryParticipantManifestV0,
    DeliveryParticipantV0,
    DeliveryPlanClaimV0,
    DeliveryPlanPolicyV0,
    derive_delivery_participant_manifest,
    evaluate_delivery_plan,
    residual_from_delivery_plan,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_request_v0 import ExecutionRequestAdmissionReceiptV0
from tev_script.semantic_prepared_execution_v0 import PreparedExecutionReceiptV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class DeliveryPlanV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.request_hash = h("request")
        self.workload = h("workload")
        self.prepared_reaction_hash_placeholder = h("prepared")
        self.request = self.request_receipt("AT_MOST_ONCE_DISPATCH")
        self.coordinator = h("coordinator")
        self.scope = h("delivery-plan-scope")
        self.verifier = h("delivery-plan-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (EvidenceRequirementV0(
                "atomic-plan",
                ("PROOF", "ATTESTATION"),
                scope_hash=self.scope,
                trusted_verifier_hashes=(self.verifier,),
            ),)
        )
        self.policy = DeliveryPlanPolicyV0(
            self.evidence_policy.policy_hash,
            (self.coordinator,),
        )

    def request_receipt(self, guarantee):
        return ExecutionRequestAdmissionReceiptV0(
            request_hash=self.request_hash,
            request_record_hash=h("request-record-" + guarantee),
            intent_hash=h("intent-" + guarantee),
            invocation_workload_hash=self.workload,
            requester_principal_hash=h("requester"),
            purpose_hash=h("purpose"),
            policy_context_hash=h("policy-context"),
            requested_delivery_guarantee=guarantee,
            idempotency_scope="OCCURRENCE_SCOPED",
            evidence_evaluation_hash=h("request-evidence-" + guarantee),
            policy_hash=h("request-policy"),
            issues=(),
        )

    def catalog(self, *, commit_total=True, durable=False):
        return CapabilityLawCatalogV1(
            "delivery.plan.catalog",
            True,
            resources=(ResourceLawV1("drive"),),
            capabilities=(CapabilityLawV1(
                "motor.set",
                "effect",
                (ResourceAccessV1("drive", "write"),),
                effect_protocol="prepare_commit_abort",
                commit_total_after_prepare=commit_total,
                durable_recovery=durable,
            ),),
        )

    def reaction(self, catalog, *, atomicity="transactional"):
        before = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "state": 0}
        after = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "state": 1}
        return PreparedReactionV1(
            h("program"), h("source"), h("contract"), catalog.catalog_hash,
            h("prepared-refinement"), h("footprint"), "entity.main", "start", (),
            before, canonical_hash(before), after, canonical_hash(after), (),
            ({"index": 0, "capability_id": "motor.set", "arguments": []},),
            (), atomicity, ("test-prepared",),
        )

    def prepared_receipt(self, reaction):
        return PreparedExecutionReceiptV0(
            prepared_execution_claim_hash=h("prepared-claim"),
            activation_receipt_hash=h("activation"),
            execution_authority_receipt_hash=h("authority"),
            realization_receipt_hash=h("realization-receipt"),
            realization_hash=h("realization"),
            execution_context_hash=h("context"),
            invocation_workload_hash=self.workload,
            prepared_reaction_hash=reaction.prepared_reaction_hash,
            prepared_refinement_receipt_hash=reaction.refinement_receipt_hash,
            before_checkpoint_hash=reaction.before_checkpoint_hash,
            after_checkpoint_hash=reaction.after_checkpoint_hash,
            program_semantic_hash=reaction.program_semantic_hash,
            reaction_contract_hash=reaction.contract_hash,
            reaction_footprint_hash=reaction.footprint_hash,
            law_catalog_hash=reaction.law_catalog_hash,
            issues=(),
        )

    def claim(self, request, prepared, manifest, *, coordinator="", atomic_domain=""):
        return DeliveryPlanClaimV0(
            request.receipt_hash,
            prepared.receipt_hash,
            manifest.manifest_hash,
            request.requested_delivery_guarantee,
            coordinator,
            atomic_domain,
        )

    def evidence(self, claim):
        return EvidenceItemV0(
            "e.delivery-plan",
            claim.claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("delivery-plan-witness"),
        )

    def test_manifest_is_derived_and_complete_for_ledger_state_and_effects(self):
        catalog = self.catalog()
        reaction = self.reaction(catalog)
        manifest = derive_delivery_participant_manifest(self.request_hash, reaction)
        kinds = [item.kind for item in manifest.participants]
        self.assertIn("DISPATCH_LEDGER", kinds)
        self.assertIn("RUNTIME_STATE_COMMIT", kinds)
        self.assertIn("EXTERNAL_EFFECT", kinds)
        self.assertEqual(kinds.count("EXTERNAL_EFFECT"), len(reaction.effect_intents))

    def test_at_most_once_plan_closes_without_atomic_coordinator(self):
        catalog = self.catalog()
        reaction = self.reaction(catalog)
        prepared = self.prepared_receipt(reaction)
        manifest = derive_delivery_participant_manifest(self.request_hash, reaction)
        claim = self.claim(self.request, prepared, manifest)
        receipt = evaluate_delivery_plan(
            claim,
            execution_request_receipt=self.request,
            prepared_execution_receipt=prepared,
            participant_manifest=manifest,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
        )
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(parse_residual(residual_from_delivery_plan(receipt)).status, "CLOSED")

    def test_exactly_once_plan_requires_evidence_even_if_hardware_path_looks_capable(self):
        request = self.request_receipt("EXACTLY_ONCE_COMMIT")
        catalog = self.catalog()
        reaction = self.reaction(catalog)
        prepared = self.prepared_receipt(reaction)
        manifest = derive_delivery_participant_manifest(request.request_hash, reaction)
        claim = self.claim(request, prepared, manifest, coordinator=self.coordinator, atomic_domain=h("atomic-domain"))
        receipt = evaluate_delivery_plan(
            claim,
            execution_request_receipt=request,
            prepared_execution_receipt=prepared,
            participant_manifest=manifest,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(),
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("delivery_plan.evidence.required", {item.kind for item in receipt.issues})

    def test_trusted_evidenced_exactly_once_plan_can_close(self):
        request = self.request_receipt("EXACTLY_ONCE_COMMIT")
        catalog = self.catalog()
        reaction = self.reaction(catalog)
        prepared = self.prepared_receipt(reaction)
        manifest = derive_delivery_participant_manifest(request.request_hash, reaction)
        claim = self.claim(request, prepared, manifest, coordinator=self.coordinator, atomic_domain=h("atomic-domain"))
        witness = self.evidence(claim)
        receipt = evaluate_delivery_plan(
            claim,
            execution_request_receipt=request,
            prepared_execution_receipt=prepared,
            participant_manifest=manifest,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(witness,),
        )
        self.assertEqual(receipt.status, "PASS")

    def test_tampered_participant_manifest_is_rejected(self):
        catalog = self.catalog()
        reaction = self.reaction(catalog)
        prepared = self.prepared_receipt(reaction)
        derived = derive_delivery_participant_manifest(self.request_hash, reaction)
        tampered = DeliveryParticipantManifestV0(
            self.request_hash,
            reaction.prepared_reaction_hash,
            tuple(item for item in derived.participants if item.kind != "EXTERNAL_EFFECT"),
        )
        claim = self.claim(self.request, prepared, tampered)
        receipt = evaluate_delivery_plan(
            claim,
            execution_request_receipt=self.request,
            prepared_execution_receipt=prepared,
            participant_manifest=tampered,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery_plan.participant_manifest_not_derived", {item.kind for item in receipt.issues})

    def test_nontransactional_or_non_total_effect_cannot_plan_exactly_once(self):
        request = self.request_receipt("EXACTLY_ONCE_COMMIT")
        catalog = self.catalog(commit_total=False)
        reaction = self.reaction(catalog, atomicity="state_atomic")
        prepared = self.prepared_receipt(reaction)
        manifest = derive_delivery_participant_manifest(request.request_hash, reaction)
        claim = self.claim(request, prepared, manifest, coordinator=self.coordinator, atomic_domain=h("atomic-domain"))
        witness = self.evidence(claim)
        receipt = evaluate_delivery_plan(
            claim,
            execution_request_receipt=request,
            prepared_execution_receipt=prepared,
            participant_manifest=manifest,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(witness,),
        )
        self.assertEqual(receipt.status, "REJECT")
        kinds = {item.kind for item in receipt.issues}
        self.assertIn("delivery_plan.atomicity_insufficient", kinds)
        self.assertIn("delivery_plan.effect_not_exactly_once_capable", kinds)

    def test_request_guarantee_cannot_be_silently_downgraded_in_plan(self):
        request = self.request_receipt("EXACTLY_ONCE_COMMIT")
        catalog = self.catalog()
        reaction = self.reaction(catalog)
        prepared = self.prepared_receipt(reaction)
        manifest = derive_delivery_participant_manifest(request.request_hash, reaction)
        downgrade = DeliveryPlanClaimV0(
            request.receipt_hash,
            prepared.receipt_hash,
            manifest.manifest_hash,
            "AT_MOST_ONCE_DISPATCH",
        )
        receipt = evaluate_delivery_plan(
            downgrade,
            execution_request_receipt=request,
            prepared_execution_receipt=prepared,
            participant_manifest=manifest,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery_plan.requested_guarantee_mismatch", {item.kind for item in receipt.issues})


if __name__ == "__main__":
    unittest.main()
