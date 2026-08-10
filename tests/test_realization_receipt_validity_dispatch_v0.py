from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_dispatch_v0 import (
    ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
    AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
    ExecutionDispatchCandidateV0,
    evaluate_execution_dispatch,
    residual_from_execution_dispatch,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_authority_v0 import (
    ExecutionAuthorityIssueV0,
    ExecutionAuthorityReceiptV0,
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


def authority(a: ExecutionActivationReceiptV0, *, issues=(), realization_receipt=None, realization=None):
    return ExecutionAuthorityReceiptV0(
        h("authority-claim"),
        h("authority-record"),
        realization_receipt or a.realization_receipt_hash,
        realization or a.realization_hash,
        h("transformation"),
        h("program"),
        h("reaction-contract"),
        h("reaction-footprint"),
        h("law-catalog"),
        h("refinement-receipt"),
        h("binding-evidence-evaluation"),
        h("authority-policy"),
        tuple(issues),
    )


class ReceiptValidityAndDispatchV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation()
        self.authority = authority(self.activation)
        self.epoch = h("dispatch-epoch")
        self.activation_authority_state = h("activation-authority-state")
        self.execution_authority_state = h("execution-authority-state")
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
        subject_receipt_hash,
        subject_contract_hash,
        authority_state_hash,
        status="VALID",
        epoch=None,
        evidence_status="ACTIVE",
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
            authority_state_hash=self.activation_authority_state,
            **kwargs,
        )

    def authority_validity(self, *, authority_receipt=None, **kwargs):
        receipt = authority_receipt or self.authority
        return self.validity(
            subject_receipt_hash=receipt.receipt_hash,
            subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            authority_state_hash=self.execution_authority_state,
            **kwargs,
        )

    def dispatch(
        self,
        activation_validity,
        authority_validity,
        *,
        authority_receipt=None,
        request="dispatch-request",
        epoch=None,
        provenance=None,
    ):
        authority_receipt = authority_receipt or self.authority
        candidate = ExecutionDispatchCandidateV0(
            h(request),
            self.activation.receipt_hash,
            activation_validity.evaluation_hash,
            authority_receipt.receipt_hash,
            authority_validity.evaluation_hash,
            epoch or self.epoch,
            provenance={} if provenance is None else provenance,
        )
        return candidate, evaluate_execution_dispatch(
            candidate,
            activation_receipt=self.activation,
            activation_validity=activation_validity,
            execution_authority_receipt=authority_receipt,
            execution_authority_validity=authority_validity,
        )

    def test_both_current_receipts_at_exact_epoch_are_required_for_pass(self):
        activation_record, _, activation_validity = self.activation_validity()
        authority_record, _, authority_validity = self.authority_validity()
        self.assertEqual(activation_validity.status, "PASS")
        self.assertEqual(authority_validity.status, "PASS")
        self.assertEqual(parse_residual(residual_from_receipt_validity(activation_validity)).status, "CLOSED")
        self.assertEqual(parse_residual(residual_from_receipt_validity(authority_validity)).status, "CLOSED")

        candidate, dispatch = self.dispatch(activation_validity, authority_validity)
        self.assertEqual(dispatch.status, "PASS")
        self.assertEqual(dispatch.dispatch_request_hash, candidate.dispatch_request_hash)
        self.assertEqual(dispatch.execution_authority_receipt_hash, self.authority.receipt_hash)
        self.assertEqual(dispatch.activation_authority_state_hash, self.activation_authority_state)
        self.assertEqual(dispatch.execution_authority_state_hash, self.execution_authority_state)
        self.assertEqual(parse_residual(residual_from_execution_dispatch(dispatch)).status, "CLOSED")
        self.assertEqual(activation_record.claim.subject_receipt_hash, self.activation.receipt_hash)
        self.assertEqual(authority_record.claim.subject_receipt_hash, self.authority.receipt_hash)

    def test_activation_unknown_blocks_dispatch_even_when_authority_is_current(self):
        _, _, activation_validity = self.activation_validity(status="UNKNOWN")
        _, _, authority_validity = self.authority_validity()
        _, dispatch = self.dispatch(activation_validity, authority_validity)
        self.assertEqual(dispatch.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.activation_not_current", {item.kind for item in dispatch.issues})

    def test_execution_authority_unknown_blocks_dispatch_even_when_activation_is_current(self):
        _, _, activation_validity = self.activation_validity()
        _, _, authority_validity = self.authority_validity(status="UNKNOWN")
        _, dispatch = self.dispatch(activation_validity, authority_validity)
        self.assertEqual(dispatch.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.execution_authority_not_current", {item.kind for item in dispatch.issues})

    def test_revoked_execution_authority_rejects_new_dispatch_without_mutating_activation(self):
        _, _, activation_validity = self.activation_validity()
        _, _, authority_validity = self.authority_validity(status="REVOKED")
        self.assertEqual(activation_validity.status, "PASS")
        self.assertEqual(authority_validity.status, "REJECT")
        _, dispatch = self.dispatch(activation_validity, authority_validity)
        self.assertEqual(dispatch.status, "REJECT")
        self.assertIn("dispatch.execution_authority_not_current", {item.kind for item in dispatch.issues})
        self.assertEqual(self.activation.status, "PASS")

    def test_non_pass_execution_authority_receipt_cannot_dispatch(self):
        open_authority = authority(
            self.activation,
            issues=(
                ExecutionAuthorityIssueV0(
                    "authority.refinement_not_admitted",
                    "PROOF_REQUIRED",
                    h("refinement"),
                    {},
                ),
            ),
        )
        _, _, activation_validity = self.activation_validity()
        _, _, authority_validity = self.authority_validity(authority_receipt=open_authority)
        _, dispatch = self.dispatch(
            activation_validity,
            authority_validity,
            authority_receipt=open_authority,
        )
        self.assertEqual(dispatch.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.execution_authority_not_admitted", {item.kind for item in dispatch.issues})

    def test_authority_for_different_realization_is_rejected(self):
        foreign = authority(
            self.activation,
            realization_receipt=h("foreign-realization-receipt"),
            realization=h("foreign-realization"),
        )
        _, _, activation_validity = self.activation_validity()
        _, _, authority_validity = self.authority_validity(authority_receipt=foreign)
        _, dispatch = self.dispatch(
            activation_validity,
            authority_validity,
            authority_receipt=foreign,
        )
        self.assertEqual(dispatch.status, "REJECT")
        kinds = {item.kind for item in dispatch.issues}
        self.assertIn("dispatch.execution_authority_realization_receipt_mismatch", kinds)
        self.assertIn("dispatch.execution_authority_realization_mismatch", kinds)

    def test_authority_validity_from_other_epoch_cannot_authorize_dispatch(self):
        _, _, activation_validity = self.activation_validity()
        _, _, authority_validity = self.authority_validity(epoch=h("old-epoch"))
        self.assertEqual(authority_validity.status, "REJECT")
        _, dispatch = self.dispatch(activation_validity, authority_validity)
        self.assertEqual(dispatch.status, "REJECT")
        self.assertIn("dispatch.execution_authority_not_current", {item.kind for item in dispatch.issues})

    def test_revoking_same_authority_validity_witness_reopens_without_changing_evidence_identity(self):
        claim = ReceiptValidityClaimV0(
            self.authority.receipt_hash,
            AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            self.epoch,
            self.execution_authority_state,
            "VALID",
            assumption_hashes=(self.assumption,),
        )
        active = EvidenceItemV0(
            "e.active",
            claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("same-authority-validity-witness"),
            assumption_hashes=(self.assumption,),
            status="ACTIVE",
        )
        revoked = EvidenceItemV0(
            "e.revoked",
            claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("same-authority-validity-witness"),
            assumption_hashes=(self.assumption,),
            status="REVOKED",
        )
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        record = ReceiptValidityRecordV0(claim, self.evidence_policy.policy_hash, (active.evidence_hash,))
        active_eval = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=self.authority.receipt_hash,
            expected_subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(active,),
        )
        revoked_eval = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=self.authority.receipt_hash,
            expected_subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(revoked,),
        )
        self.assertEqual(active_eval.status, "PASS")
        self.assertEqual(revoked_eval.status, "PROOF_REQUIRED")
        _, _, activation_validity = self.activation_validity()
        _, dispatch = self.dispatch(activation_validity, revoked_eval)
        self.assertEqual(dispatch.status, "PROOF_REQUIRED")

    def test_dispatch_request_and_provenance_identity_rules_remain_explicit(self):
        _, _, activation_validity = self.activation_validity()
        _, _, authority_validity = self.authority_validity()
        first, _ = self.dispatch(activation_validity, authority_validity, request="dispatch-a")
        second, _ = self.dispatch(activation_validity, authority_validity, request="dispatch-b")
        self.assertNotEqual(first.dispatch_candidate_hash, second.dispatch_candidate_hash)

        left, _ = self.dispatch(
            activation_validity,
            authority_validity,
            provenance={"scheduler": "a"},
        )
        right, _ = self.dispatch(
            activation_validity,
            authority_validity,
            provenance={"scheduler": "b"},
        )
        self.assertEqual(left.dispatch_candidate_hash, right.dispatch_candidate_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_non_pass_activation_cannot_dispatch_even_with_current_authority(self):
        rejected_activation = activation(
            issues=(ActivationIssueV0("activation.failure", "REJECT", h("failure"), {}),)
        )
        current_authority = authority(rejected_activation)

        activation_claim = ReceiptValidityClaimV0(
            rejected_activation.receipt_hash,
            ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            self.epoch,
            self.activation_authority_state,
            "VALID",
            assumption_hashes=(self.assumption,),
        )
        activation_evidence = EvidenceItemV0(
            "e.rejected-activation-validity",
            activation_claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("rejected-activation-validity"),
            assumption_hashes=(self.assumption,),
        )
        activation_record = ReceiptValidityRecordV0(
            activation_claim,
            self.evidence_policy.policy_hash,
            (activation_evidence.evidence_hash,),
        )
        activation_validity = evaluate_receipt_validity(
            activation_record,
            expected_subject_receipt_hash=rejected_activation.receipt_hash,
            expected_subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(activation_evidence,),
        )

        authority_claim = ReceiptValidityClaimV0(
            current_authority.receipt_hash,
            AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            self.epoch,
            self.execution_authority_state,
            "VALID",
            assumption_hashes=(self.assumption,),
        )
        authority_evidence = EvidenceItemV0(
            "e.current-authority-validity",
            authority_claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("current-authority-validity"),
            assumption_hashes=(self.assumption,),
        )
        authority_record = ReceiptValidityRecordV0(
            authority_claim,
            self.evidence_policy.policy_hash,
            (authority_evidence.evidence_hash,),
        )
        authority_validity = evaluate_receipt_validity(
            authority_record,
            expected_subject_receipt_hash=current_authority.receipt_hash,
            expected_subject_contract_hash=AUTHORITY_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(authority_evidence,),
        )

        candidate = ExecutionDispatchCandidateV0(
            h("dispatch-request"),
            rejected_activation.receipt_hash,
            activation_validity.evaluation_hash,
            current_authority.receipt_hash,
            authority_validity.evaluation_hash,
            self.epoch,
        )
        dispatch = evaluate_execution_dispatch(
            candidate,
            activation_receipt=rejected_activation,
            activation_validity=activation_validity,
            execution_authority_receipt=current_authority,
            execution_authority_validity=authority_validity,
        )
        self.assertEqual(dispatch.status, "REJECT")
        self.assertIn("dispatch.activation_not_admitted", {item.kind for item in dispatch.issues})


if __name__ == "__main__":
    unittest.main()
