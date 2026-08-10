from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_delivery_plan_v0 import DeliveryPlanIssueV0, DeliveryPlanReceiptV0
from tev_script.semantic_dispatch_v0 import (
    ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
    AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
    DELIVERY_PLAN_RECEIPT_CONTRACT_HASH_V0,
    EXECUTION_REQUEST_RECEIPT_CONTRACT_HASH_V0,
    PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0,
    ExecutionDispatchCandidateV0,
    dispatch_consumption_domain_hash,
    evaluate_execution_dispatch,
    residual_from_execution_dispatch,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_authority_v0 import ExecutionAuthorityIssueV0, ExecutionAuthorityReceiptV0
from tev_script.semantic_execution_request_v0 import ExecutionRequestAdmissionReceiptV0, ExecutionRequestIssueV0
from tev_script.semantic_prepared_execution_v0 import PreparedExecutionIssueV0, PreparedExecutionReceiptV0
from tev_script.semantic_receipt_validity_v0 import (
    ReceiptValidityClaimV0,
    ReceiptValidityPolicyV0,
    ReceiptValidityRecordV0,
    evaluate_receipt_validity,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def activation(*, issues=()) -> ExecutionActivationReceiptV0:
    return ExecutionActivationReceiptV0(
        h("activation-candidate"), h("activation-record"), h("realization-receipt"),
        h("realization"), h("placement-evaluation"), h("machine-instance"),
        h("placement-context"), h("runtime-evaluation"), h("runtime-claim"),
        h("execution-context"), tuple(issues),
    )


def authority(a: ExecutionActivationReceiptV0, *, issues=()) -> ExecutionAuthorityReceiptV0:
    return ExecutionAuthorityReceiptV0(
        authority_claim_hash=h("authority-claim"),
        authority_record_hash=h("authority-record"),
        realization_receipt_hash=a.realization_receipt_hash,
        realization_hash=a.realization_hash,
        transformation_semantic_hash=h("transformation"),
        transformation_regime_binding_hash=h("regime-binding"),
        semantic_scope_hash=h("semantic-scope"),
        program_semantic_hash=h("program"),
        reaction_contract_hash=h("reaction-contract"),
        reaction_footprint_hash=h("reaction-footprint"),
        law_catalog_hash=h("law-catalog"),
        refinement_receipt_hash=h("refinement"),
        binding_evidence_evaluation_hash=h("binding-evidence"),
        policy_hash=h("authority-policy"),
        issues=tuple(issues),
    )


def prepared(a: ExecutionActivationReceiptV0, auth: ExecutionAuthorityReceiptV0, *, workload=None, issues=()) -> PreparedExecutionReceiptV0:
    return PreparedExecutionReceiptV0(
        prepared_execution_claim_hash=h("prepared-claim"),
        activation_receipt_hash=a.receipt_hash,
        execution_authority_receipt_hash=auth.receipt_hash,
        realization_receipt_hash=a.realization_receipt_hash,
        realization_hash=a.realization_hash,
        execution_context_hash=a.execution_context_hash,
        invocation_workload_hash=workload or h("workload"),
        prepared_reaction_hash=h("prepared-reaction"),
        prepared_refinement_receipt_hash=h("prepared-refinement"),
        before_checkpoint_hash=h("before"),
        after_checkpoint_hash=h("after"),
        program_semantic_hash=auth.program_semantic_hash,
        reaction_contract_hash=auth.reaction_contract_hash,
        reaction_footprint_hash=auth.reaction_footprint_hash,
        law_catalog_hash=auth.law_catalog_hash,
        issues=tuple(issues),
    )


def request(workload: str, *, issues=(), guarantee="AT_MOST_ONCE_DISPATCH") -> ExecutionRequestAdmissionReceiptV0:
    return ExecutionRequestAdmissionReceiptV0(
        request_hash=h("execution-request"),
        request_record_hash=h("execution-request-record"),
        intent_hash=h("execution-intent"),
        invocation_workload_hash=workload,
        requester_principal_hash=h("requester"),
        purpose_hash=h("purpose"),
        policy_context_hash=h("request-policy-context"),
        requested_delivery_guarantee=guarantee,
        idempotency_scope="OCCURRENCE_SCOPED",
        evidence_evaluation_hash=h("request-evidence"),
        policy_hash=h("request-policy"),
        issues=tuple(issues),
    )


def delivery_plan(
    request_receipt: ExecutionRequestAdmissionReceiptV0,
    prepared_receipt: PreparedExecutionReceiptV0,
    *,
    issues=(),
) -> DeliveryPlanReceiptV0:
    exact = request_receipt.requested_delivery_guarantee != "AT_MOST_ONCE_DISPATCH"
    return DeliveryPlanReceiptV0(
        plan_claim_hash=h("delivery-plan-claim"),
        execution_request_receipt_hash=request_receipt.receipt_hash,
        prepared_execution_receipt_hash=prepared_receipt.receipt_hash,
        participant_manifest_hash=h("delivery-participant-manifest"),
        requested_guarantee=request_receipt.requested_delivery_guarantee,
        coordinator_hash=h("delivery-coordinator") if exact else "",
        atomic_commit_domain_hash=h("delivery-atomic-domain") if exact else "",
        evidence_evaluation_hash=h("delivery-plan-evidence") if exact else "",
        policy_hash=h("delivery-plan-policy"),
        issues=tuple(issues),
    )


class CurrentRequestDispatchV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation()
        self.authority = authority(self.activation)
        self.prepared = prepared(self.activation, self.authority)
        self.request = request(self.prepared.invocation_workload_hash)
        self.delivery_plan = delivery_plan(self.request, self.prepared)
        self.epoch = h("dispatch-epoch")
        self.scope = h("validity-scope")
        self.verifier = h("validity-verifier")
        self.assumption = h("validity-assumption")
        self.evidence_policy = EvidencePolicyV0(
            (EvidenceRequirementV0(
                "current",
                ("ATTESTATION",),
                scope_hash=self.scope,
                trusted_verifier_hashes=(self.verifier,),
            ),)
        )
        self.validity_policy = ReceiptValidityPolicyV0(
            self.evidence_policy.policy_hash,
            (self.assumption,),
        )

    def validity(self, subject, contract, state, *, status="VALID"):
        claim = ReceiptValidityClaimV0(subject, contract, self.epoch, state, status, (self.assumption,))
        witness = EvidenceItemV0(
            "e." + subject[:8],
            claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("witness-" + subject[:8]),
            assumption_hashes=(self.assumption,),
        )
        record = ReceiptValidityRecordV0(claim, self.evidence_policy.policy_hash, (witness.evidence_hash,))
        return evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=subject,
            expected_subject_contract_hash=contract,
            expected_validation_epoch_hash=self.epoch,
            policy=self.validity_policy,
            evidence_policy=self.evidence_policy,
            evidence=(witness,),
        )

    def closures(
        self,
        *,
        request_status="VALID",
        activation_status="VALID",
        authority_status="VALID",
        prepared_status="VALID",
        delivery_plan_status="VALID",
        request_receipt=None,
        prepared_receipt=None,
        delivery_plan_receipt=None,
    ):
        request_receipt = request_receipt or self.request
        prepared_receipt = prepared_receipt or self.prepared
        delivery_plan_receipt = delivery_plan_receipt or self.delivery_plan
        return (
            self.validity(request_receipt.receipt_hash, EXECUTION_REQUEST_RECEIPT_CONTRACT_HASH_V0, h("request-state"), status=request_status),
            self.validity(self.activation.receipt_hash, ACTIVATION_RECEIPT_CONTRACT_HASH_V0, h("activation-state"), status=activation_status),
            self.validity(self.authority.receipt_hash, AUTHORITY_RECEIPT_CONTRACT_HASH_V0, h("authority-state"), status=authority_status),
            self.validity(prepared_receipt.receipt_hash, PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0, h("prepared-state"), status=prepared_status),
            self.validity(delivery_plan_receipt.receipt_hash, DELIVERY_PLAN_RECEIPT_CONTRACT_HASH_V0, h("delivery-plan-state"), status=delivery_plan_status),
        )

    def evaluate(
        self,
        rv,
        av,
        uv,
        pv,
        dv,
        *,
        request_receipt=None,
        prepared_receipt=None,
        delivery_plan_receipt=None,
        request_hash=None,
    ):
        request_receipt = request_receipt or self.request
        prepared_receipt = prepared_receipt or self.prepared
        delivery_plan_receipt = delivery_plan_receipt or self.delivery_plan
        candidate = ExecutionDispatchCandidateV0(
            dispatch_request_hash=request_hash or request_receipt.request_hash,
            execution_request_receipt_hash=request_receipt.receipt_hash,
            execution_request_validity_evaluation_hash=rv.evaluation_hash,
            activation_receipt_hash=self.activation.receipt_hash,
            activation_validity_evaluation_hash=av.evaluation_hash,
            execution_authority_receipt_hash=self.authority.receipt_hash,
            execution_authority_validity_evaluation_hash=uv.evaluation_hash,
            prepared_execution_receipt_hash=prepared_receipt.receipt_hash,
            prepared_execution_validity_evaluation_hash=pv.evaluation_hash,
            delivery_plan_receipt_hash=delivery_plan_receipt.receipt_hash,
            delivery_plan_validity_evaluation_hash=dv.evaluation_hash,
            dispatch_epoch_hash=self.epoch,
        )
        return evaluate_execution_dispatch(
            candidate,
            execution_request_receipt=request_receipt,
            execution_request_validity=rv,
            activation_receipt=self.activation,
            activation_validity=av,
            execution_authority_receipt=self.authority,
            execution_authority_validity=uv,
            prepared_execution_receipt=prepared_receipt,
            prepared_execution_validity=pv,
            delivery_plan_receipt=delivery_plan_receipt,
            delivery_plan_validity=dv,
        )

    def test_five_current_closures_are_required_for_dispatch_pass(self):
        rv, av, uv, pv, dv = self.closures()
        receipt = self.evaluate(rv, av, uv, pv, dv)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.dispatch_request_hash, self.request.request_hash)
        self.assertEqual(receipt.execution_request_receipt_hash, self.request.receipt_hash)
        self.assertEqual(receipt.delivery_plan_receipt_hash, self.delivery_plan.receipt_hash)
        self.assertEqual(receipt.delivery_participant_manifest_hash, self.delivery_plan.participant_manifest_hash)
        self.assertEqual(receipt.invocation_workload_hash, self.prepared.invocation_workload_hash)
        self.assertEqual(receipt.requested_delivery_guarantee, "AT_MOST_ONCE_DISPATCH")
        self.assertEqual(receipt.dispatch_consumption_domain_hash, dispatch_consumption_domain_hash(self.request.request_hash))
        self.assertEqual(parse_residual(residual_from_execution_dispatch(receipt)).status, "CLOSED")

    def test_request_hash_is_not_free_nonce_anymore(self):
        rv, av, uv, pv, dv = self.closures()
        receipt = self.evaluate(rv, av, uv, pv, dv, request_hash=h("invented-request"))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch.request_hash_mismatch", {item.kind for item in receipt.issues})

    def test_request_workload_must_equal_prepared_invocation(self):
        foreign_request = request(h("different-workload"))
        foreign_plan = delivery_plan(foreign_request, self.prepared)
        rv, av, uv, pv, dv = self.closures(request_receipt=foreign_request, delivery_plan_receipt=foreign_plan)
        receipt = self.evaluate(
            rv,
            av,
            uv,
            pv,
            dv,
            request_receipt=foreign_request,
            delivery_plan_receipt=foreign_plan,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch.request_workload_mismatch", {item.kind for item in receipt.issues})

    def test_delivery_plan_must_bind_exact_request_prepared_and_guarantee(self):
        foreign_plan = DeliveryPlanReceiptV0(
            plan_claim_hash=h("foreign-plan-claim"),
            execution_request_receipt_hash=h("foreign-request-receipt"),
            prepared_execution_receipt_hash=h("foreign-prepared-receipt"),
            participant_manifest_hash=h("manifest"),
            requested_guarantee="EXACTLY_ONCE_COMMIT",
            coordinator_hash=h("coordinator"),
            atomic_commit_domain_hash=h("atomic-domain"),
            evidence_evaluation_hash=h("plan-evidence"),
            policy_hash=h("plan-policy"),
            issues=(),
        )
        rv, av, uv, pv, dv = self.closures(delivery_plan_receipt=foreign_plan)
        receipt = self.evaluate(rv, av, uv, pv, dv, delivery_plan_receipt=foreign_plan)
        self.assertEqual(receipt.status, "REJECT")
        kinds = {item.kind for item in receipt.issues}
        self.assertIn("dispatch.delivery_plan_request_mismatch", kinds)
        self.assertIn("dispatch.delivery_plan_prepared_mismatch", kinds)
        self.assertIn("dispatch.delivery_plan_guarantee_mismatch", kinds)

    def test_request_and_delivery_plan_must_be_current_at_same_epoch(self):
        rv, av, uv, pv, dv = self.closures(request_status="UNKNOWN")
        receipt = self.evaluate(rv, av, uv, pv, dv)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.execution_request_not_current", {item.kind for item in receipt.issues})

        rv, av, uv, pv, dv = self.closures(delivery_plan_status="UNKNOWN")
        receipt = self.evaluate(rv, av, uv, pv, dv)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.delivery_plan_not_current", {item.kind for item in receipt.issues})

    def test_revoked_delivery_plan_blocks_new_dispatch_without_mutating_history(self):
        rv, av, uv, pv, dv = self.closures(delivery_plan_status="REVOKED")
        self.assertEqual(self.request.status, "PASS")
        self.assertEqual(self.activation.status, "PASS")
        self.assertEqual(self.authority.status, "PASS")
        self.assertEqual(self.prepared.status, "PASS")
        self.assertEqual(self.delivery_plan.status, "PASS")
        receipt = self.evaluate(rv, av, uv, pv, dv)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch.delivery_plan_not_current", {item.kind for item in receipt.issues})

    def test_non_admitted_request_or_plan_cannot_dispatch(self):
        open_request = request(
            self.prepared.invocation_workload_hash,
            issues=(ExecutionRequestIssueV0("request.evidence.required", "PROOF_REQUIRED", h("request"), {}),),
        )
        open_plan = delivery_plan(
            open_request,
            self.prepared,
            issues=(DeliveryPlanIssueV0("delivery_plan.evidence.required", "PROOF_REQUIRED", h("plan"), {}),),
        )
        rv, av, uv, pv, dv = self.closures(
            request_receipt=open_request,
            delivery_plan_receipt=open_plan,
        )
        receipt = self.evaluate(
            rv,
            av,
            uv,
            pv,
            dv,
            request_receipt=open_request,
            delivery_plan_receipt=open_plan,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        kinds = {item.kind for item in receipt.issues}
        self.assertIn("dispatch.execution_request_not_admitted", kinds)
        self.assertIn("dispatch.delivery_plan_not_admitted", kinds)

    def test_existing_activation_authority_and_prepared_failures_remain_explicit(self):
        open_activation = activation(issues=(ActivationIssueV0("activation.open", "PROOF_REQUIRED", h("a"), {}),))
        open_authority = authority(self.activation, issues=(ExecutionAuthorityIssueV0("authority.open", "PROOF_REQUIRED", h("u"), {}),))
        open_prepared = prepared(self.activation, self.authority, issues=(PreparedExecutionIssueV0("prepared_execution.open", "PROOF_REQUIRED", h("p"), {}),))
        self.assertEqual(open_activation.status, "PROOF_REQUIRED")
        self.assertEqual(open_authority.status, "PROOF_REQUIRED")
        self.assertEqual(open_prepared.status, "PROOF_REQUIRED")


if __name__ == "__main__":
    unittest.main()
