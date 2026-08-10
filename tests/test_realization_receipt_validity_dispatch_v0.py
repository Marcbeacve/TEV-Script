from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_dispatch_v0 import (
    ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
    AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
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


class CurrentRequestDispatchV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation()
        self.authority = authority(self.activation)
        self.prepared = prepared(self.activation, self.authority)
        self.request = request(self.prepared.invocation_workload_hash)
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
        claim = ReceiptValidityClaimV0(
            subject,
            contract,
            self.epoch,
            state,
            status,
            (self.assumption,),
        )
        witness = EvidenceItemV0(
            "e." + subject[:8],
            claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("witness-" + subject[:8]),
            assumption_hashes=(self.assumption,),
        )
        record = ReceiptValidityRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (witness.evidence_hash,),
        )
        return evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=subject,
            expected_subject_contract_hash=contract,
            expected_validation_epoch_hash=self.epoch,
            policy=self.validity_policy,
            evidence_policy=self.evidence_policy,
            evidence=(witness,),
        )

    def quartet(self, *, request_status="VALID", activation_status="VALID", authority_status="VALID", prepared_status="VALID"):
        return (
            self.validity(self.request.receipt_hash, EXECUTION_REQUEST_RECEIPT_CONTRACT_HASH_V0, h("request-state"), status=request_status),
            self.validity(self.activation.receipt_hash, ACTIVATION_RECEIPT_CONTRACT_HASH_V0, h("activation-state"), status=activation_status),
            self.validity(self.authority.receipt_hash, AUTHORITY_RECEIPT_CONTRACT_HASH_V0, h("authority-state"), status=authority_status),
            self.validity(self.prepared.receipt_hash, PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0, h("prepared-state"), status=prepared_status),
        )

    def evaluate(self, rv, av, uv, pv, *, request_receipt=None, prepared_receipt=None, request_hash=None):
        request_receipt = request_receipt or self.request
        prepared_receipt = prepared_receipt or self.prepared
        candidate = ExecutionDispatchCandidateV0(
            request_hash or request_receipt.request_hash,
            request_receipt.receipt_hash,
            rv.evaluation_hash,
            self.activation.receipt_hash,
            av.evaluation_hash,
            self.authority.receipt_hash,
            uv.evaluation_hash,
            prepared_receipt.receipt_hash,
            pv.evaluation_hash,
            self.epoch,
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
        )

    def test_four_current_closures_are_required_for_dispatch_pass(self):
        rv, av, uv, pv = self.quartet()
        receipt = self.evaluate(rv, av, uv, pv)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.dispatch_request_hash, self.request.request_hash)
        self.assertEqual(receipt.execution_request_receipt_hash, self.request.receipt_hash)
        self.assertEqual(receipt.requester_principal_hash, self.request.requester_principal_hash)
        self.assertEqual(receipt.invocation_workload_hash, self.prepared.invocation_workload_hash)
        self.assertEqual(receipt.requested_delivery_guarantee, "AT_MOST_ONCE_DISPATCH")
        self.assertEqual(receipt.dispatch_consumption_domain_hash, dispatch_consumption_domain_hash(self.request.request_hash))
        self.assertEqual(parse_residual(residual_from_execution_dispatch(receipt)).status, "CLOSED")

    def test_request_hash_is_not_free_nonce_anymore(self):
        rv, av, uv, pv = self.quartet()
        receipt = self.evaluate(rv, av, uv, pv, request_hash=h("invented-request"))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch.request_hash_mismatch", {item.kind for item in receipt.issues})

    def test_request_workload_must_equal_prepared_invocation(self):
        foreign = request(h("different-workload"))
        rv = self.validity(foreign.receipt_hash, EXECUTION_REQUEST_RECEIPT_CONTRACT_HASH_V0, h("request-state"))
        _, av, uv, pv = self.quartet()
        receipt = self.evaluate(rv, av, uv, pv, request_receipt=foreign)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch.request_workload_mismatch", {item.kind for item in receipt.issues})

    def test_request_must_be_current_at_same_epoch(self):
        rv, av, uv, pv = self.quartet(request_status="UNKNOWN")
        receipt = self.evaluate(rv, av, uv, pv)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.execution_request_not_current", {item.kind for item in receipt.issues})

    def test_non_admitted_request_cannot_dispatch(self):
        open_request = request(
            self.prepared.invocation_workload_hash,
            issues=(ExecutionRequestIssueV0("request.evidence.required", "PROOF_REQUIRED", h("request"), {}),),
        )
        rv = self.validity(open_request.receipt_hash, EXECUTION_REQUEST_RECEIPT_CONTRACT_HASH_V0, h("request-state"))
        _, av, uv, pv = self.quartet()
        receipt = self.evaluate(rv, av, uv, pv, request_receipt=open_request)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.execution_request_not_admitted", {item.kind for item in receipt.issues})

    def test_existing_activation_authority_and_prepared_failures_still_propagate(self):
        open_activation = activation(issues=(ActivationIssueV0("activation.open", "PROOF_REQUIRED", h("a"), {}),))
        open_authority = authority(self.activation, issues=(ExecutionAuthorityIssueV0("authority.open", "PROOF_REQUIRED", h("u"), {}),))
        open_prepared = prepared(self.activation, self.authority, issues=(PreparedExecutionIssueV0("prepared_execution.open", "PROOF_REQUIRED", h("p"), {}),))
        self.assertEqual(open_activation.status, "PROOF_REQUIRED")
        self.assertEqual(open_authority.status, "PROOF_REQUIRED")
        self.assertEqual(open_prepared.status, "PROOF_REQUIRED")


if __name__ == "__main__":
    unittest.main()
