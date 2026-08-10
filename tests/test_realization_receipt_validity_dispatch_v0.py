from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_dispatch_v0 import (
    ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
    AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
    PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0,
    ExecutionDispatchCandidateV0,
    dispatch_consumption_domain_hash,
    evaluate_execution_dispatch,
    residual_from_execution_dispatch,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_authority_v0 import (
    ExecutionAuthorityIssueV0,
    ExecutionAuthorityReceiptV0,
)
from tev_script.semantic_prepared_execution_v0 import (
    PreparedExecutionIssueV0,
    PreparedExecutionReceiptV0,
)
from tev_script.semantic_receipt_validity_v0 import (
    ReceiptValidityClaimV0,
    ReceiptValidityPolicyV0,
    ReceiptValidityRecordV0,
    evaluate_receipt_validity,
    residual_from_receipt_validity,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def activation(*, issues=()) -> ExecutionActivationReceiptV0:
    return ExecutionActivationReceiptV0(
        h("activation-candidate"),
        h("activation-record"),
        h("realization-receipt"),
        h("realization"),
        h("placement-evaluation"),
        h("machine-instance"),
        h("placement-context"),
        h("runtime-evaluation"),
        h("runtime-claim"),
        h("execution-context"),
        tuple(issues),
    )


def authority(
    a: ExecutionActivationReceiptV0,
    *,
    issues=(),
    realization_receipt=None,
    realization=None,
) -> ExecutionAuthorityReceiptV0:
    return ExecutionAuthorityReceiptV0(
        authority_claim_hash=h("authority-claim"),
        authority_record_hash=h("authority-record"),
        realization_receipt_hash=realization_receipt or a.realization_receipt_hash,
        realization_hash=realization or a.realization_hash,
        transformation_semantic_hash=h("transformation"),
        transformation_regime_binding_hash=h("regime-binding"),
        semantic_scope_hash=h("semantic-scope"),
        program_semantic_hash=h("program"),
        reaction_contract_hash=h("reaction-contract"),
        reaction_footprint_hash=h("reaction-footprint"),
        law_catalog_hash=h("law-catalog"),
        refinement_receipt_hash=h("refinement-receipt"),
        binding_evidence_evaluation_hash=h("binding-evidence-evaluation"),
        policy_hash=h("authority-policy"),
        issues=tuple(issues),
    )


def prepared(
    a: ExecutionActivationReceiptV0,
    auth: ExecutionAuthorityReceiptV0,
    *,
    issues=(),
    activation_hash=None,
    authority_hash=None,
) -> PreparedExecutionReceiptV0:
    return PreparedExecutionReceiptV0(
        prepared_execution_claim_hash=h("prepared-execution-claim"),
        activation_receipt_hash=activation_hash or a.receipt_hash,
        execution_authority_receipt_hash=authority_hash or auth.receipt_hash,
        realization_receipt_hash=a.realization_receipt_hash,
        realization_hash=a.realization_hash,
        execution_context_hash=a.execution_context_hash,
        invocation_workload_hash=h("invocation-workload"),
        prepared_reaction_hash=h("prepared-reaction"),
        prepared_refinement_receipt_hash=h("prepared-refinement"),
        before_checkpoint_hash=h("before-checkpoint"),
        after_checkpoint_hash=h("after-checkpoint"),
        program_semantic_hash=auth.program_semantic_hash,
        reaction_contract_hash=auth.reaction_contract_hash,
        reaction_footprint_hash=auth.reaction_footprint_hash,
        law_catalog_hash=auth.law_catalog_hash,
        issues=tuple(issues),
    )


class ReceiptValidityAndDispatchV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation()
        self.authority = authority(self.activation)
        self.prepared = prepared(self.activation, self.authority)
        self.epoch = h("dispatch-epoch")
        self.activation_state = h("activation-authority-state")
        self.authority_state = h("execution-authority-state")
        self.prepared_state = h("prepared-execution-authority-state")
        self.assumption = h("validity-assumption")
        self.scope = h("validity-scope")
        self.verifier = h("validity-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "current-validity",
                    ("ATTESTATION", "PROOF"),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = ReceiptValidityPolicyV0(
            self.evidence_policy.policy_hash,
            accepted_assumption_hashes=(self.assumption,),
        )

    def validity(
        self,
        *,
        subject_receipt_hash: str,
        subject_contract_hash: str,
        authority_state_hash: str,
        status: str = "VALID",
        epoch: str | None = None,
        evidence_status: str = "ACTIVE",
    ):
        claim = ReceiptValidityClaimV0(
            subject_receipt_hash,
            subject_contract_hash,
            epoch or self.epoch,
            authority_state_hash,
            status,
            assumption_hashes=(self.assumption,),
        )
        evidence = EvidenceItemV0(
            "e.validity." + subject_receipt_hash[:8],
            claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("validity-witness-" + subject_receipt_hash[:8]),
            assumption_hashes=(self.assumption,),
            status=evidence_status,
        )
        record = ReceiptValidityRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        evaluation = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=subject_receipt_hash,
            expected_subject_contract_hash=subject_contract_hash,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(evidence,),
        )
        return record, evidence, evaluation

    def activation_validity(self, **kwargs):
        return self.validity(
            subject_receipt_hash=self.activation.receipt_hash,
            subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.activation_state,
            **kwargs,
        )

    def authority_validity(self, *, authority_receipt=None, **kwargs):
        receipt = authority_receipt or self.authority
        return self.validity(
            subject_receipt_hash=receipt.receipt_hash,
            subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.authority_state,
            **kwargs,
        )

    def prepared_validity(self, *, prepared_receipt=None, **kwargs):
        receipt = prepared_receipt or self.prepared
        return self.validity(
            subject_receipt_hash=receipt.receipt_hash,
            subject_contract_hash=PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.prepared_state,
            **kwargs,
        )

    def dispatch(
        self,
        activation_validity,
        authority_validity,
        prepared_validity,
        *,
        authority_receipt=None,
        prepared_receipt=None,
        request="dispatch-request",
        epoch=None,
        provenance=None,
    ):
        authority_receipt = authority_receipt or self.authority
        prepared_receipt = prepared_receipt or self.prepared
        candidate = ExecutionDispatchCandidateV0(
            h(request),
            self.activation.receipt_hash,
            activation_validity.evaluation_hash,
            authority_receipt.receipt_hash,
            authority_validity.evaluation_hash,
            prepared_receipt.receipt_hash,
            prepared_validity.evaluation_hash,
            epoch or self.epoch,
            provenance={} if provenance is None else provenance,
        )
        result = evaluate_execution_dispatch(
            candidate,
            activation_receipt=self.activation,
            activation_validity=activation_validity,
            execution_authority_receipt=authority_receipt,
            execution_authority_validity=authority_validity,
            prepared_execution_receipt=prepared_receipt,
            prepared_execution_validity=prepared_validity,
        )
        return candidate, result

    def current_triplet(self):
        return (
            self.activation_validity()[2],
            self.authority_validity()[2],
            self.prepared_validity()[2],
        )

    def test_all_three_current_receipts_at_exact_epoch_are_required_for_pass(self):
        activation_record, _, av = self.activation_validity()
        authority_record, _, uv = self.authority_validity()
        prepared_record, _, pv = self.prepared_validity()
        self.assertEqual(av.status, "PASS")
        self.assertEqual(uv.status, "PASS")
        self.assertEqual(pv.status, "PASS")
        self.assertEqual(parse_residual(residual_from_receipt_validity(av)).status, "CLOSED")
        self.assertEqual(parse_residual(residual_from_receipt_validity(uv)).status, "CLOSED")
        self.assertEqual(parse_residual(residual_from_receipt_validity(pv)).status, "CLOSED")

        candidate, dispatch = self.dispatch(av, uv, pv)
        self.assertEqual(dispatch.status, "PASS")
        self.assertEqual(dispatch.dispatch_request_hash, candidate.dispatch_request_hash)
        self.assertEqual(dispatch.execution_authority_receipt_hash, self.authority.receipt_hash)
        self.assertEqual(dispatch.prepared_execution_receipt_hash, self.prepared.receipt_hash)
        self.assertEqual(dispatch.invocation_workload_hash, self.prepared.invocation_workload_hash)
        self.assertEqual(dispatch.before_checkpoint_hash, self.prepared.before_checkpoint_hash)
        self.assertEqual(dispatch.after_checkpoint_hash, self.prepared.after_checkpoint_hash)
        self.assertEqual(
            dispatch.dispatch_consumption_domain_hash,
            dispatch_consumption_domain_hash(dispatch.dispatch_request_hash),
        )
        self.assertEqual(parse_residual(residual_from_execution_dispatch(dispatch)).status, "CLOSED")
        self.assertEqual(activation_record.claim.subject_receipt_hash, self.activation.receipt_hash)
        self.assertEqual(authority_record.claim.subject_receipt_hash, self.authority.receipt_hash)
        self.assertEqual(prepared_record.claim.subject_receipt_hash, self.prepared.receipt_hash)

    def test_any_unknown_currentness_keeps_dispatch_open(self):
        _, _, av = self.activation_validity(status="UNKNOWN")
        _, _, uv = self.authority_validity()
        _, _, pv = self.prepared_validity()
        _, result = self.dispatch(av, uv, pv)
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.activation_not_current", {item.kind for item in result.issues})

        _, _, av = self.activation_validity()
        _, _, uv = self.authority_validity(status="UNKNOWN")
        _, result = self.dispatch(av, uv, pv)
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.execution_authority_not_current", {item.kind for item in result.issues})

        _, _, uv = self.authority_validity()
        _, _, pv = self.prepared_validity(status="UNKNOWN")
        _, result = self.dispatch(av, uv, pv)
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.prepared_execution_not_current", {item.kind for item in result.issues})

    def test_revoked_prepared_execution_blocks_new_dispatch_without_mutating_history(self):
        _, _, av = self.activation_validity()
        _, _, uv = self.authority_validity()
        _, _, pv = self.prepared_validity(status="REVOKED")
        self.assertEqual(self.activation.status, "PASS")
        self.assertEqual(self.authority.status, "PASS")
        self.assertEqual(self.prepared.status, "PASS")
        _, result = self.dispatch(av, uv, pv)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("dispatch.prepared_execution_not_current", {item.kind for item in result.issues})

    def test_non_pass_prepared_execution_cannot_dispatch(self):
        open_prepared = prepared(
            self.activation,
            self.authority,
            issues=(
                PreparedExecutionIssueV0(
                    "prepared_execution.workload_mismatch",
                    "PROOF_REQUIRED",
                    h("workload"),
                    {},
                ),
            ),
        )
        _, _, av = self.activation_validity()
        _, _, uv = self.authority_validity()
        _, _, pv = self.prepared_validity(prepared_receipt=open_prepared)
        _, result = self.dispatch(
            av,
            uv,
            pv,
            prepared_receipt=open_prepared,
        )
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.prepared_execution_not_admitted", {item.kind for item in result.issues})

    def test_prepared_execution_must_bind_same_activation_and_authority(self):
        foreign_prepared = prepared(
            self.activation,
            self.authority,
            activation_hash=h("other-activation"),
            authority_hash=h("other-authority"),
        )
        _, _, av = self.activation_validity()
        _, _, uv = self.authority_validity()
        _, _, pv = self.prepared_validity(prepared_receipt=foreign_prepared)
        _, result = self.dispatch(
            av,
            uv,
            pv,
            prepared_receipt=foreign_prepared,
        )
        self.assertEqual(result.status, "REJECT")
        kinds = {item.kind for item in result.issues}
        self.assertIn("dispatch.prepared_activation_mismatch", kinds)
        self.assertIn("dispatch.prepared_authority_mismatch", kinds)

    def test_foreign_execution_authority_realization_is_rejected(self):
        foreign = authority(
            self.activation,
            realization_receipt=h("foreign-realization-receipt"),
            realization=h("foreign-realization"),
        )
        foreign_prepared = prepared(self.activation, foreign)
        _, _, av = self.activation_validity()
        _, _, uv = self.authority_validity(authority_receipt=foreign)
        _, _, pv = self.prepared_validity(prepared_receipt=foreign_prepared)
        _, result = self.dispatch(
            av,
            uv,
            pv,
            authority_receipt=foreign,
            prepared_receipt=foreign_prepared,
        )
        self.assertEqual(result.status, "REJECT")
        kinds = {item.kind for item in result.issues}
        self.assertIn("dispatch.execution_authority_realization_receipt_mismatch", kinds)
        self.assertIn("dispatch.execution_authority_realization_mismatch", kinds)

    def test_validity_from_other_epoch_cannot_authorize_dispatch(self):
        _, _, av = self.activation_validity()
        _, _, uv = self.authority_validity()
        _, _, pv = self.prepared_validity(epoch=h("old-epoch"))
        self.assertEqual(pv.status, "REJECT")
        _, result = self.dispatch(av, uv, pv)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("dispatch.prepared_execution_not_current", {item.kind for item in result.issues})

    def test_dispatch_request_and_provenance_identity_rules_remain_explicit(self):
        av, uv, pv = self.current_triplet()
        first, _ = self.dispatch(av, uv, pv, request="dispatch-a")
        second, _ = self.dispatch(av, uv, pv, request="dispatch-b")
        self.assertNotEqual(first.dispatch_candidate_hash, second.dispatch_candidate_hash)

        left, _ = self.dispatch(av, uv, pv, provenance={"scheduler": "a"})
        right, _ = self.dispatch(av, uv, pv, provenance={"scheduler": "b"})
        self.assertEqual(left.dispatch_candidate_hash, right.dispatch_candidate_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_non_pass_activation_and_authority_still_propagate(self):
        rejected_activation = activation(
            issues=(ActivationIssueV0("activation.failure", "REJECT", h("failure"), {}),)
        )
        rejected_authority = authority(
            rejected_activation,
            issues=(
                ExecutionAuthorityIssueV0(
                    "authority.refinement_not_admitted",
                    "PROOF_REQUIRED",
                    h("refinement"),
                    {},
                ),
            ),
        )
        prepared_for_rejected = prepared(rejected_activation, rejected_authority)

        av_record, av_evidence, av = self.validity(
            subject_receipt_hash=rejected_activation.receipt_hash,
            subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.activation_state,
        )
        _, _, uv = self.validity(
            subject_receipt_hash=rejected_authority.receipt_hash,
            subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.authority_state,
        )
        _, _, pv = self.validity(
            subject_receipt_hash=prepared_for_rejected.receipt_hash,
            subject_contract_hash=PREPARED_EXECUTION_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.prepared_state,
        )
        candidate = ExecutionDispatchCandidateV0(
            h("dispatch-rejected-upstream"),
            rejected_activation.receipt_hash,
            av.evaluation_hash,
            rejected_authority.receipt_hash,
            uv.evaluation_hash,
            prepared_for_rejected.receipt_hash,
            pv.evaluation_hash,
            self.epoch,
        )
        result = evaluate_execution_dispatch(
            candidate,
            activation_receipt=rejected_activation,
            activation_validity=av,
            execution_authority_receipt=rejected_authority,
            execution_authority_validity=uv,
            prepared_execution_receipt=prepared_for_rejected,
            prepared_execution_validity=pv,
        )
        self.assertEqual(result.status, "REJECT")
        kinds = {item.kind for item in result.issues}
        self.assertIn("dispatch.activation_not_admitted", kinds)
        self.assertIn("dispatch.execution_authority_not_admitted", kinds)
        self.assertEqual(av_record.claim.subject_receipt_hash, rejected_activation.receipt_hash)
        self.assertTrue(av_evidence.evidence_hash)


if __name__ == "__main__":
    unittest.main()
