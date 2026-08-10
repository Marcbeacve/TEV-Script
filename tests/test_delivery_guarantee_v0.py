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


def dispatch() -> ExecutionDispatchReceiptV0:
    request = h("dispatch-request")
    return ExecutionDispatchReceiptV0(
        dispatch_candidate_hash=h("dispatch-candidate"),
        dispatch_record_hash=h("dispatch-record"),
        dispatch_request_hash=request,
        dispatch_epoch_hash=h("dispatch-epoch"),
        activation_receipt_hash=h("activation"),
        activation_validity_evaluation_hash=h("activation-validity"),
        activation_authority_state_hash=h("activation-state"),
        execution_authority_receipt_hash=h("execution-authority"),
        execution_authority_claim_hash=h("execution-authority-claim"),
        execution_authority_validity_evaluation_hash=h("execution-authority-validity"),
        execution_authority_state_hash=h("execution-authority-state"),
        prepared_execution_receipt_hash=h("prepared-execution"),
        prepared_execution_claim_hash=h("prepared-execution-claim"),
        prepared_execution_validity_evaluation_hash=h("prepared-execution-validity"),
        prepared_execution_authority_state_hash=h("prepared-state"),
        invocation_workload_hash=h("workload"),
        before_checkpoint_hash=h("before"),
        after_checkpoint_hash=h("after"),
        dispatch_consumption_domain_hash=dispatch_consumption_domain_hash(request),
        realization_receipt_hash=h("realization-receipt"),
        realization_hash=h("realization"),
        execution_context_hash=h("context"),
        machine_instance_hash=h("machine-instance"),
        placement_context_hash=h("placement"),
        runtime_state_claim_hash=h("runtime"),
        issues=(),
    )


def prepared_execution(d: ExecutionDispatchReceiptV0) -> PreparedExecutionReceiptV0:
    return PreparedExecutionReceiptV0(
        prepared_execution_claim_hash=d.prepared_execution_claim_hash,
        activation_receipt_hash=d.activation_receipt_hash,
        execution_authority_receipt_hash=d.execution_authority_receipt_hash,
        realization_receipt_hash=d.realization_receipt_hash,
        realization_hash=d.realization_hash,
        execution_context_hash=d.execution_context_hash,
        invocation_workload_hash=d.invocation_workload_hash,
        prepared_reaction_hash=h("prepared-reaction"),
        prepared_refinement_receipt_hash=h("prepared-refinement"),
        before_checkpoint_hash=d.before_checkpoint_hash,
        after_checkpoint_hash=d.after_checkpoint_hash,
        program_semantic_hash=h("program"),
        reaction_contract_hash=h("contract"),
        reaction_footprint_hash=h("footprint"),
        law_catalog_hash=h("catalog-placeholder"),
        issues=(),
    )


def consumption(d: ExecutionDispatchReceiptV0) -> DispatchConsumptionCommitReceiptV0:
    return DispatchConsumptionCommitReceiptV0(
        h("commit-claim"),
        h("commit-record"),
        h("transition"),
        d.receipt_hash,
        d.dispatch_request_hash,
        h("before-ledger"),
        h("after-ledger"),
        h("storage-authority"),
        h("commit-epoch"),
        h("commit-evidence"),
        h("commit-policy"),
        (),
    )


class DeliveryGuaranteeV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatch = dispatch()
        self.prepared_execution = prepared_execution(self.dispatch)
        self.consumption = consumption(self.dispatch)
        self.coordinator = h("delivery-coordinator")
        self.verifier = h("delivery-verifier")
        self.scope = h("delivery-scope")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "atomic-delivery",
                    ("ATTESTATION", "PROOF"),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
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
            capabilities=(
                CapabilityLawV1(
                    "motor.set",
                    "effect",
                    (ResourceAccessV1("drive", "write"),),
                    effect_protocol="prepare_commit_abort",
                    commit_total_after_prepare=commit_total,
                    durable_recovery=durable,
                ),
            ),
        )

    def prepared_reaction(self, catalog, *, atomicity="transactional"):
        before = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "marker": "before"}
        after = {"schema": "TEST_CHECKPOINT_V0", "entities": [], "marker": "after"}
        return PreparedReactionV1(
            h("program"),
            h("source"),
            h("contract"),
            catalog.catalog_hash,
            h("prepared-refinement"),
            h("footprint"),
            "entity.main",
            "start",
            (),
            before,
            canonical_hash(before),
            after,
            canonical_hash(after),
            (),
            ({"index": 0, "capability_id": "motor.set", "arguments": []},),
            (),
            atomicity,
            ("test-prepared",),
        )

    def align_prepared_execution(self, reaction):
        return PreparedExecutionReceiptV0(
            prepared_execution_claim_hash=self.dispatch.prepared_execution_claim_hash,
            activation_receipt_hash=self.dispatch.activation_receipt_hash,
            execution_authority_receipt_hash=self.dispatch.execution_authority_receipt_hash,
            realization_receipt_hash=self.dispatch.realization_receipt_hash,
            realization_hash=self.dispatch.realization_hash,
            execution_context_hash=self.dispatch.execution_context_hash,
            invocation_workload_hash=self.dispatch.invocation_workload_hash,
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

    def atomic_claim(self, prepared_receipt, *, durable=False, coordinator=None):
        return AtomicDeliveryCommitClaimV0(
            self.consumption.receipt_hash,
            prepared_receipt.receipt_hash,
            h("atomic-domain"),
            h("participant-manifest"),
            coordinator or self.coordinator,
            durable,
        )

    def evidence(self, atomic_claim):
        return EvidenceItemV0(
            "e.atomic-delivery",
            atomic_claim.claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("atomic-delivery-witness"),
        )

    def evaluate(self, guarantee, reaction, catalog, *, atomic=None, evidence=()):
        prepared_receipt = self.align_prepared_execution(reaction)
        claim = DeliveryGuaranteeClaimV0(
            self.dispatch.receipt_hash,
            self.consumption.receipt_hash,
            prepared_receipt.receipt_hash,
            guarantee,
            "" if atomic is None else atomic.claim_hash,
        )
        return evaluate_delivery_guarantee(
            claim,
            dispatch_receipt=self.dispatch,
            consumption_commit_receipt=self.consumption,
            prepared_execution_receipt=prepared_receipt,
            prepared_reaction=reaction,
            law_catalog=catalog,
            policy=self.policy,
            atomic_delivery_claim=atomic,
            atomic_evidence_policy=None if atomic is None else self.evidence_policy,
            evidence=tuple(evidence),
        )

    def test_cas_proves_at_most_once_dispatch_only(self):
        catalog = self.law_catalog()
        reaction = self.prepared_reaction(catalog)
        receipt = self.evaluate("AT_MOST_ONCE_DISPATCH", reaction, catalog)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.requested_guarantee, "AT_MOST_ONCE_DISPATCH")
        self.assertEqual(parse_residual(residual_from_delivery_guarantee(receipt)).status, "CLOSED")

    def test_exactly_once_without_atomic_commit_witness_stays_open(self):
        catalog = self.law_catalog()
        reaction = self.prepared_reaction(catalog)
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", reaction, catalog)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("delivery.atomic_commit_witness_required", {item.kind for item in receipt.issues})

    def test_non_transactional_reaction_cannot_claim_exactly_once(self):
        catalog = self.law_catalog()
        reaction = self.prepared_reaction(catalog, atomicity="state_atomic")
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", reaction, catalog)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.atomicity_insufficient", {item.kind for item in receipt.issues})

    def test_effect_without_commit_total_after_prepare_cannot_claim_exactly_once(self):
        catalog = self.law_catalog(commit_total=False)
        reaction = self.prepared_reaction(catalog)
        prepared_receipt = self.align_prepared_execution(reaction)
        atomic = self.atomic_claim(prepared_receipt)
        witness = self.evidence(atomic)
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", reaction, catalog, atomic=atomic, evidence=(witness,))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("delivery.effect_not_exactly_once_capable", {item.kind for item in receipt.issues})

    def test_trusted_atomic_commit_witness_can_close_exactly_once(self):
        catalog = self.law_catalog()
        reaction = self.prepared_reaction(catalog)
        prepared_receipt = self.align_prepared_execution(reaction)
        atomic = self.atomic_claim(prepared_receipt)
        witness = self.evidence(atomic)
        receipt = self.evaluate("EXACTLY_ONCE_COMMIT", reaction, catalog, atomic=atomic, evidence=(witness,))
        self.assertEqual(receipt.status, "PASS")
        self.assertTrue(receipt.atomic_delivery_claim_hash)
        self.assertEqual(parse_residual(residual_from_delivery_guarantee(receipt)).status, "CLOSED")

    def test_durable_exactly_once_requires_durable_reaction_effect_and_atomic_commit(self):
        catalog = self.law_catalog(durable=False)
        reaction = self.prepared_reaction(catalog, atomicity="transactional")
        prepared_receipt = self.align_prepared_execution(reaction)
        atomic = self.atomic_claim(prepared_receipt, durable=False)
        witness = self.evidence(atomic)
        receipt = self.evaluate("DURABLE_EXACTLY_ONCE_COMMIT", reaction, catalog, atomic=atomic, evidence=(witness,))
        self.assertEqual(receipt.status, "REJECT")
        kinds = {item.kind for item in receipt.issues}
        self.assertIn("delivery.durable_atomicity_required", kinds)
        self.assertIn("delivery.effect_not_durably_recoverable", kinds)
        self.assertIn("delivery.atomic_commit_not_durable", kinds)


if __name__ == "__main__":
    unittest.main()
