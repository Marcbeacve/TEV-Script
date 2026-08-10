from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_dispatch_v0 import (
    ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
    ExecutionDispatchCandidateV0,
    evaluate_execution_dispatch,
    residual_from_execution_dispatch,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
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


class ReceiptValidityAndDispatchV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation()
        self.epoch = h("dispatch-epoch")
        self.authority_state = h("authority-state")
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

    def claim(self, *, status="VALID", epoch=None, receipt_hash=None):
        return ReceiptValidityClaimV0(
            receipt_hash or self.activation.receipt_hash,
            ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            epoch or self.epoch,
            self.authority_state,
            status,
            assumption_hashes=(self.assumption,),
        )

    def evidence(self, claim, *, evidence_id="e.validity", status="ACTIVE"):
        return EvidenceItemV0(
            evidence_id,
            claim.validity_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("validity-witness"),
            assumption_hashes=(self.assumption,),
            status=status,
        )

    def evaluate_validity(self, claim, *, evidence_status="ACTIVE"):
        evidence = self.evidence(claim, status=evidence_status)
        record = ReceiptValidityRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        evaluation = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=self.activation.receipt_hash,
            expected_subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(evidence,),
        )
        return record, evidence, evaluation

    def dispatch(self, validity, *, request="dispatch-request", epoch=None, provenance=None):
        candidate = ExecutionDispatchCandidateV0(
            h(request),
            self.activation.receipt_hash,
            validity.evaluation_hash,
            epoch or self.epoch,
            provenance={} if provenance is None else provenance,
        )
        return candidate, evaluate_execution_dispatch(
            candidate,
            activation_receipt=self.activation,
            activation_validity=validity,
        )

    def test_valid_receipt_at_exact_epoch_passes(self):
        record, _, validity = self.evaluate_validity(self.claim())
        self.assertEqual(validity.status, "PASS")
        self.assertEqual(parse_residual(residual_from_receipt_validity(validity)).status, "CLOSED")
        candidate, dispatch = self.dispatch(validity)
        self.assertEqual(dispatch.status, "PASS")
        self.assertEqual(dispatch.dispatch_request_hash, candidate.dispatch_request_hash)
        self.assertEqual(parse_residual(residual_from_execution_dispatch(dispatch)).status, "CLOSED")
        self.assertEqual(record.claim.subject_receipt_hash, self.activation.receipt_hash)

    def test_unknown_validity_stays_open_and_blocks_dispatch(self):
        _, _, validity = self.evaluate_validity(self.claim(status="UNKNOWN"))
        self.assertEqual(validity.status, "PROOF_REQUIRED")
        _, dispatch = self.dispatch(validity)
        self.assertEqual(dispatch.status, "PROOF_REQUIRED")
        self.assertIn("dispatch.activation_not_current", {item.kind for item in dispatch.issues})

    def test_revoked_or_superseded_historical_receipt_rejects_dispatch(self):
        for status in ("REVOKED", "SUPERSEDED"):
            _, _, validity = self.evaluate_validity(self.claim(status=status))
            self.assertEqual(validity.status, "REJECT")
            _, dispatch = self.dispatch(validity)
            self.assertEqual(dispatch.status, "REJECT")
            self.assertIn("dispatch.activation_not_current", {item.kind for item in dispatch.issues})

    def test_revoking_same_validity_witness_does_not_change_evidence_identity_but_reopens(self):
        claim = self.claim()
        active = self.evidence(claim, evidence_id="e.active", status="ACTIVE")
        revoked = self.evidence(claim, evidence_id="e.revoked", status="REVOKED")
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        record = ReceiptValidityRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (active.evidence_hash,),
        )
        active_eval = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=self.activation.receipt_hash,
            expected_subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(active,),
        )
        revoked_eval = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=self.activation.receipt_hash,
            expected_subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(revoked,),
        )
        self.assertEqual(active_eval.status, "PASS")
        self.assertEqual(revoked_eval.status, "PROOF_REQUIRED")
        _, dispatch = self.dispatch(revoked_eval)
        self.assertEqual(dispatch.status, "PROOF_REQUIRED")

    def test_validity_for_other_epoch_cannot_authorize_dispatch(self):
        claim = self.claim(epoch=h("old-epoch"))
        evidence = self.evidence(claim)
        record = ReceiptValidityRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            (evidence.evidence_hash,),
        )
        validity = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=self.activation.receipt_hash,
            expected_subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(evidence,),
        )
        self.assertEqual(validity.status, "REJECT")
        _, dispatch = self.dispatch(validity)
        self.assertEqual(dispatch.status, "REJECT")

    def test_dispatch_request_is_part_of_identity_and_prevents_accidental_replay_alias(self):
        _, _, validity = self.evaluate_validity(self.claim())
        first, _ = self.dispatch(validity, request="dispatch-a")
        second, _ = self.dispatch(validity, request="dispatch-b")
        self.assertNotEqual(first.dispatch_candidate_hash, second.dispatch_candidate_hash)

    def test_dispatch_provenance_is_record_not_dispatch_identity(self):
        _, _, validity = self.evaluate_validity(self.claim())
        left, _ = self.dispatch(validity, provenance={"scheduler": "a"})
        right, _ = self.dispatch(validity, provenance={"scheduler": "b"})
        self.assertEqual(left.dispatch_candidate_hash, right.dispatch_candidate_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_non_pass_activation_cannot_dispatch_even_if_validity_claim_says_valid(self):
        rejected_activation = activation(
            issues=(ActivationIssueV0("activation.failure", "REJECT", h("failure"), {}),)
        )
        claim = ReceiptValidityClaimV0(
            rejected_activation.receipt_hash,
            ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            self.epoch,
            self.authority_state,
            "VALID",
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        record = ReceiptValidityRecordV0(claim, self.evidence_policy.policy_hash, (evidence.evidence_hash,))
        validity = evaluate_receipt_validity(
            record,
            expected_subject_receipt_hash=rejected_activation.receipt_hash,
            expected_subject_contract_hash=ACTIVATION_RECEIPT_CONTRACT_HASH_V0,
            expected_validation_epoch_hash=self.epoch,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(evidence,),
        )
        candidate = ExecutionDispatchCandidateV0(
            h("dispatch-request"),
            rejected_activation.receipt_hash,
            validity.evaluation_hash,
            self.epoch,
        )
        dispatch = evaluate_execution_dispatch(
            candidate,
            activation_receipt=rejected_activation,
            activation_validity=validity,
        )
        self.assertEqual(dispatch.status, "REJECT")
        self.assertIn("dispatch.activation_not_admitted", {item.kind for item in dispatch.issues})


if __name__ == "__main__":
    unittest.main()
