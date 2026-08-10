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
from tev_script.semantic_delivery_guarantee_v0 import (
    AtomicDeliveryCommitClaimV0,
    DeliveryGuaranteeClaimV0,
    DeliveryGuaranteePolicyV0,
    evaluate_delivery_guarantee,
    residual_from_delivery_guarantee,
)
from tev_script.semantic_dispatch_consumption_v0 import DispatchConsumptionCommitReceiptV0
from tev_script.semantic_dispatch_v0 import ExecutionDispatchReceiptV0, dispatch_consumption_domain_hash
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_prepared_execution_v0 import PreparedExecutionReceiptV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class DeliveryGuaranteeV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation_receipt_hash = h("activation")
        self.execution_authority_receipt_hash = h("execution-authority")
        self.realization_receipt_hash = h("realization-receipt")
        self.realization_hash = h("realization")
        self.execution_context_hash = h("context")
        self.coordinator = h("delivery-coordinator")
        self.atomic_domain = h("atomic-domain")
        self.participant_manifest = h("participant-manifest")
        self.verifier = h("delivery-verifier")
        self.scope = h("delivery-scope")
        self.evidence_policy = EvidencePolicyV0(
            (EvidenceRequirementV0(
                "atomic-delivery",
                ("ATTESTATION", "PROOF"),
                scope_hash=self.scope,
                trusted_verifier_hashes=(self.verifier,),
            ),)
        )
        self.policy = DeliveryGuaranteePolicyV0(
            self.evidence_policy.policy_hash,
            trusted_coordinator_hashes=(self.coordinator,),
        )

    def law_catalog(self, *, durable=False, commit_total=True):
        return CapabilityLawCatalogV1(
            "delivery.catalog",
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

    def prepared_reaction(self, catalog, *, atomicity="transactional"):
        before = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "marker": "before"}
        after = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "marker": "after"}
        return PreparedReactionV1(
            h("program"), h("source"), h("contract"), catalog.catalog_hash,
            h("prepared-refinement"), h("footprint"), "entity.main", "start", (),
            before, canonical_hash(before), after, canonical_hash(after), (),
            ({"index": 0, "capability_id": "motor.set", "arguments": []},), (),
            atomicity, ("test-prepared",),
        )

    def prepared_execution(self, reaction):
        return PreparedExecutionReceiptV0(
            prepared_execution_claim_hash=h("prepared-execution-claim"),
            activation_receipt_hash=self.activation_receipt_hash,
            execution_authority_receipt_hash=self.execution_authority_receipt_hash,
            realization_receipt_hash=self.realization_receipt_hash,
            realization_hash=self.realization_hash,
            execution_context_hash=self.execution_context_hash,
            invocation_workload_hash=h("workload"),
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

    def dispatch(self, prepared_receipt, requested_guarantee):
        request = h("dispatch-request")
        exact = requested_guarantee != "AT_MOST_ONCE_DISPATCH"
        return ExecutionDispatchReceiptV0(
            dispatch_candidate_hash=h("dispatch-candidate"),
            dispatch_record_hash=h("dispatch-record"),
            dispatch_request_hash=request,
            dispatch_epoch_hash=h("dispatch-epoch"),
            execution_request_receipt_hash=h("execution-request-receipt"),
            execution_request_intent_hash=h("execution-intent"),
            execution_request_validity_evaluation_hash=h("execution-request-validity"),
            execution_request_authority_state_hash=h("execution-request-state"),
            requester_principal_hash=h("requester"),
            purpose_hash=h("purpose"),
            requested_delivery_guarantee=requested_guarantee,
            idempotency_scope="OCCURRENCE_SCOPED",
            activation_receipt_hash=self.activation_receipt_hash,
            activation_validity_evaluation_hash=h("activation-validity"),
            activation_authority_state_hash=h("activation-state"),
            execution_authority_receipt_hash=self.execution_authority_receipt_hash,
            execution_authority_claim_hash=h("execution-authority-claim"),
            execution_authority_validity_evaluation_hash=h("execution-authority-validity"),
            execution_authority_state_hash=h("execution-authority-state"),
            prepared_execution_receipt_hash=prepared_receipt.receipt_hash,
            prepared_execution_claim_hash=prepared_receipt.prepared_execution_claim_hash,
            prepared_execution_validity_evaluation_hash=h("prepared-execution-validity"),
            prepared_execution_authority_state_hash=h("prepared-state"),
            delivery_plan_receipt_hash=h("delivery-plan-receipt"),
            delivery_plan_claim_hash=h("delivery-plan-claim"),
            delivery_plan_validity_evaluation_hash=h("delivery-plan-validity"),
            delivery_plan_authority_state_hash=h("delivery-plan-state"),
            delivery_participant_manifest_hash=self.participant_manifest,
            delivery_coordinator_hash=self.coordinator if exact else "",
            delivery_atomic_commit_domain_hash=self.atomic_domain if exact else "",
            invocation_workload_hash=prepared_receipt.invocation_workload_hash,
            before_checkpoint_hash=prepared_receipt.before_checkpoint_hash,
            after_checkpoint_hash=prepared_receipt.after_checkpoint_hash,
            dispatch_consumption_domain_hash=dispatch_consumption_domain_hash(request),
            realization_receipt_hash=self.realization_receipt_hash,
            realization_hash=self.realization_hash,
            execution_context_hash=self.execution_context_hash,
            machine_instance_hash=h("machine-instance"),
            placement_context_hash=h("placement"),
            runtime_state_claim_hash=h("runtime"),
            issues=(),
        )

    def consumption(self, dispatch_receipt):
        return DispatchConsumptionCommitReceiptV0(
            h("commit-claim"), h("commit-record"), h("transition"),
            dispatch_receipt.receipt_hash, dispatch_receipt.dispatch_request_hash,
            h("before-ledger"), h("after-ledger"), h("storage-authority"),
            h("commit-epoch"), h("commit-evidence"), h("commit-policy"), (),
        )

    def atomic_claim(
        self,
        dispatch_receipt,
        consumption_receipt,
        prepared_receipt,
        *,
        durable=False,
        coordinator=None,
        participant_manifest=None,
        atomic_domain=None,
        delivery_plan_receipt=None,
    ):
        return AtomicDeliveryCommitClaimV0(
            delivery_plan_receipt or dispatch_receipt.delivery_plan_receipt_hash,
            consumption_receipt.receipt_hash,
            prepared_receipt.receipt_hash,
            atomic_domain or dispatch_receipt.delivery_atomic_commit_domain_hash,
            participant_manifest or dispatch_receipt.delivery_participant_manifest_hash,
            coordinator or dispatch_receipt.delivery_coordinator_hash,
            durable,
        )

    def evidence(self, atomic_claim):
        return EvidenceItemV0(
            "e.atomic-delivery", atomic_claim.claim_hash, self.scope, "ATTESTATION",
            verifier_hash=self.verifier, witness_hash=h("atomic-delivery-witness"),
        )

    def evaluate(
        self,
        guarantee,
        reaction,
        catalog,
        *,
        dispatch_guarantee=None,
        with_atomic=False,
        durable_atomic=False,
        coordinator=None,
        participant_manifest=None,
        atomic_domain=None,
        delivery_plan_receipt=None,
    ):
        prepared_receipt = self.prepared_execution(reaction)
        dispatch_receipt = self.dispatch(prepared_receipt, dispatch_guarantee or guarantee)
        consumption_receipt = self.consumption(dispatch_receipt)
        atomic = None
        evidence = ()
        if with_atomic:
            atomic = self.atomic_claim(
                dispatch_receipt,
                consumption_receipt,
                prepared_receipt,
                durable=durable_atomic,
                coordinator=coordinator,
                participant_manifest=participant_manifest,
                atomic_domain=atomic_domain,
                delivery_plan_receipt=delivery_plan_receipt,
            )
            evidence = (self.evidence(atomic),)
        claim = DeliveryGuaranteeClaimV0(
            dispatch_receipt.receipt_hash,
            consumption_receipt.receipt_hash,
            prepared_receipt.receipt_hash,
            guarantee,
            "" if atomic is None else atomic.claim_hash,
        )
        return evaluate_delivery_guarantee(
            claim,
            dispatch_receipt=dispatch_receipt,
            consumption_commit_receipt=consumption_receipt,
            prepared_execution_receipt=prepared_receipt,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            atomic_delivery_claim=atomic,
            atomic_evidence_policy=None if atomic is None else self.evidence_policy,
            evidence=evidence,
        )

    def test_cas_proves_at_most_once_dispatch_only(self):
        catalog = self.law_catalog()
        receipt = self.evaluate("AT_MOST_ONCE_DISPATCH", self.prepared_reaction(catalog), catalog)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(parse_residual(residual_from_delivery_guarantee(receipt)).status, "CLOSED")

    def test_delivery_verdict_must_match_execution_intent_requirement(self):
        catalog = self.law_catalog()
        receipt = self.evaluate(
            "AT_MOST_ONCE_DISPATCH",
            self.prepared_reaction(catalog),
            catalog,
            dispatch_guarantee="EXACTLY_ONCE_COMMIT",
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.requested_guarantee_mismatch", {item.kind for item in receipt.issues})

    def test_exactly_once_without_atomic_commit_witness_stays_open(self):
        catalog = self.law_catalog()
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", self.prepared_reaction(catalog), catalog)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("delivery.atomic_commit_witness_required", {item.kind for item in receipt.issues})

    def test_non_transactional_reaction_cannot_claim_exactly_once(self):
        catalog = self.law_catalog()
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", self.prepared_reaction(catalog, atomicity="state_atomic"), catalog)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.atomicity_insufficient", {item.kind for item in receipt.issues})

    def test_effect_without_commit_total_after_prepare_cannot_claim_exactly_once(self):
        catalog = self.law_catalog(commit_total=False)
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", self.prepared_reaction(catalog), catalog, with_atomic=True)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.effect_not_exactly_once_capable", {item.kind for item in receipt.issues})

    def test_trusted_atomic_commit_witness_can_close_exactly_once(self):
        catalog = self.law_catalog()
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", self.prepared_reaction(catalog), catalog, with_atomic=True)
        self.assertEqual(receipt.status, "PASS")
        self.assertTrue(receipt.atomic_delivery_claim_hash)
        self.assertEqual(parse_residual(residual_from_delivery_guarantee(receipt)).status, "CLOSED")

    def test_atomic_claim_cannot_replace_pre_dispatch_plan_identity(self):
        catalog = self.law_catalog()
        receipt = self.evaluate(
            "EXACTLY_ONCE_COMMIT",
            self.prepared_reaction(catalog),
            catalog,
            with_atomic=True,
            delivery_plan_receipt=h("other-plan"),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.atomic_claim_plan_mismatch", {item.kind for item in receipt.issues})

    def test_atomic_claim_cannot_replace_pre_dispatch_participant_manifest(self):
        catalog = self.law_catalog()
        receipt = self.evaluate(
            "EXACTLY_ONCE_COMMIT",
            self.prepared_reaction(catalog),
            catalog,
            with_atomic=True,
            participant_manifest=h("other-manifest"),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.atomic_claim_participant_manifest_mismatch", {item.kind for item in receipt.issues})

    def test_untrusted_atomic_coordinator_rejects_exactly_once(self):
        catalog = self.law_catalog()
        receipt = self.evaluate(
            "EXACTLY_ONCE_COMMIT",
            self.prepared_reaction(catalog),
            catalog,
            with_atomic=True,
            coordinator=h("untrusted-coordinator"),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.coordinator_untrusted", {item.kind for item in receipt.issues})

    def test_atomic_claim_cannot_replace_pre_dispatch_atomic_domain(self):
        catalog = self.law_catalog()
        receipt = self.evaluate(
            "EXACTLY_ONCE_COMMIT",
            self.prepared_reaction(catalog),
            catalog,
            with_atomic=True,
            atomic_domain=h("other-atomic-domain"),
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.atomic_claim_domain_mismatch", {item.kind for item in receipt.issues})

    def test_durable_exactly_once_requires_all_three_durability_surfaces(self):
        catalog = self.law_catalog(durable=False)
        receipt = self.evaluate(
            "DURABLE_EXACTLY_ONCE_COMMIT",
            self.prepared_reaction(catalog, atomicity="transactional"),
            catalog,
            with_atomic=True,
            durable_atomic=False,
        )
        self.assertEqual(receipt.status, "REJECT")
        kinds = {item.kind for item in receipt.issues}
        self.assertIn("delivery.durable_atomicity_required", kinds)
        self.assertIn("delivery.effect_not_durably_recoverable", kinds)
        self.assertIn("delivery.atomic_commit_not_durable", kinds)


if __name__ == "__main__":
    unittest.main()
