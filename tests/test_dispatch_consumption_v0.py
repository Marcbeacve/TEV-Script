from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_dispatch_consumption_v0 import (
    DispatchConsumptionAttemptV0,
    DispatchConsumptionCommitPolicyV0,
    DispatchConsumptionCommitRecordV0,
    DispatchConsumptionStateV0,
    evaluate_dispatch_consumption_commit,
    evaluate_dispatch_consumption_transition,
    residual_from_dispatch_consumption_commit,
    residual_from_dispatch_consumption_transition,
)
from tev_script.semantic_dispatch_v0 import (
    DispatchIssueV0,
    ExecutionDispatchReceiptV0,
    dispatch_consumption_domain_hash,
)
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def dispatch(request="request", *, issues=(), authority_claim=None) -> ExecutionDispatchReceiptV0:
    request_hash = h(request)
    return ExecutionDispatchReceiptV0(
        dispatch_candidate_hash=h("dispatch-candidate-" + request),
        dispatch_record_hash=h("dispatch-record-" + request),
        dispatch_request_hash=request_hash,
        dispatch_epoch_hash=h("dispatch-epoch"),
        execution_request_receipt_hash=h("execution-request-receipt-" + request),
        execution_request_intent_hash=h("execution-intent-" + request),
        execution_request_validity_evaluation_hash=h("execution-request-validity-" + request),
        execution_request_authority_state_hash=h("execution-request-state-" + request),
        requester_principal_hash=h("requester"),
        purpose_hash=h("purpose"),
        requested_delivery_guarantee="AT_MOST_ONCE_DISPATCH",
        idempotency_scope="OCCURRENCE_SCOPED",
        activation_receipt_hash=h("activation"),
        activation_validity_evaluation_hash=h("activation-validity"),
        activation_authority_state_hash=h("activation-authority-state"),
        execution_authority_receipt_hash=h("execution-authority"),
        execution_authority_claim_hash=authority_claim or h("execution-authority-claim"),
        execution_authority_validity_evaluation_hash=h("execution-authority-validity"),
        execution_authority_state_hash=h("execution-authority-state"),
        prepared_execution_receipt_hash=h("prepared-execution"),
        prepared_execution_claim_hash=h("prepared-execution-claim"),
        prepared_execution_validity_evaluation_hash=h("prepared-execution-validity"),
        prepared_execution_authority_state_hash=h("prepared-execution-authority-state"),
        invocation_workload_hash=h("invocation-workload"),
        before_checkpoint_hash=h("before-checkpoint"),
        after_checkpoint_hash=h("after-checkpoint"),
        dispatch_consumption_domain_hash=dispatch_consumption_domain_hash(request_hash),
        realization_receipt_hash=h("realization-receipt"),
        realization_hash=h("realization"),
        execution_context_hash=h("execution-context"),
        machine_instance_hash=h("machine-instance"),
        placement_context_hash=h("placement-context"),
        runtime_state_claim_hash=h("runtime-state"),
        issues=tuple(issues),
    )


class DispatchConsumptionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.dispatch = dispatch()
        self.domain = self.dispatch.dispatch_consumption_domain_hash
        self.before = DispatchConsumptionStateV0(self.domain)
        self.attempt = DispatchConsumptionAttemptV0(
            self.dispatch.receipt_hash,
            self.dispatch.dispatch_request_hash,
            self.domain,
            self.before.state_hash,
        )
        self.storage_authority = h("storage-authority")
        self.scope = h("cas-scope")
        self.verifier = h("cas-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "atomic-cas",
                    ("ATTESTATION",),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = DispatchConsumptionCommitPolicyV0(
            self.evidence_policy.policy_hash,
            (self.storage_authority,),
        )

    def transition(self, attempt=None, before=None, dispatch_receipt=None):
        return evaluate_dispatch_consumption_transition(
            attempt or self.attempt,
            before_state=before or self.before,
            dispatch_receipt=dispatch_receipt or self.dispatch,
        )

    def commit(self, transition, *, evidence=True, storage_authority=None):
        authority = storage_authority or self.storage_authority
        record = DispatchConsumptionCommitRecordV0(
            transition.transition_hash,
            authority,
            h("cas-commit-epoch"),
            self.evidence_policy.policy_hash,
        )
        witness = EvidenceItemV0(
            "e.cas",
            record.commit_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("cas-witness"),
        )
        if evidence:
            record = DispatchConsumptionCommitRecordV0(
                transition.transition_hash,
                authority,
                h("cas-commit-epoch"),
                self.evidence_policy.policy_hash,
                (witness.evidence_hash,),
            )
            evidence_items = (witness,)
        else:
            evidence_items = ()
        receipt = evaluate_dispatch_consumption_commit(
            record,
            transition=transition,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=evidence_items,
        )
        return record, receipt

    def test_fresh_dispatch_produces_deterministic_transition(self):
        transition, after = self.transition()
        self.assertEqual(transition.status, "PASS")
        self.assertIsNotNone(after)
        self.assertTrue(after.contains(self.dispatch.dispatch_request_hash))
        self.assertEqual(after.state_hash, transition.after_state_hash)
        self.assertEqual(transition.dispatch_domain_hash, self.dispatch.dispatch_consumption_domain_hash)
        self.assertEqual(parse_residual(residual_from_dispatch_consumption_transition(transition)).status, "CLOSED")

    def test_caller_cannot_switch_ledger_domain_to_bypass_request_replay_scope(self):
        wrong_domain = h("caller-chosen-domain")
        wrong_state = DispatchConsumptionStateV0(wrong_domain)
        wrong_attempt = DispatchConsumptionAttemptV0(
            self.dispatch.receipt_hash,
            self.dispatch.dispatch_request_hash,
            wrong_domain,
            wrong_state.state_hash,
        )
        transition, after = self.transition(wrong_attempt, before=wrong_state)
        self.assertEqual(transition.status, "REJECT")
        self.assertIsNone(after)
        kinds = {item.kind for item in transition.issues}
        self.assertIn("dispatch_consumption.request_domain_mismatch", kinds)
        self.assertIn("dispatch_consumption.ledger_domain_mismatch", kinds)

    def test_same_request_keeps_same_domain_when_authority_changes(self):
        reauthorized = dispatch(authority_claim=h("new-execution-authority-claim"))
        self.assertEqual(reauthorized.dispatch_request_hash, self.dispatch.dispatch_request_hash)
        self.assertNotEqual(reauthorized.execution_authority_claim_hash, self.dispatch.execution_authority_claim_hash)
        self.assertEqual(reauthorized.dispatch_consumption_domain_hash, self.dispatch.dispatch_consumption_domain_hash)

        first, after = self.transition()
        self.assertEqual(first.status, "PASS")
        retry_attempt = DispatchConsumptionAttemptV0(
            reauthorized.receipt_hash,
            reauthorized.dispatch_request_hash,
            reauthorized.dispatch_consumption_domain_hash,
            after.state_hash,
        )
        retry, retry_after = evaluate_dispatch_consumption_transition(
            retry_attempt,
            before_state=after,
            dispatch_receipt=reauthorized,
        )
        self.assertEqual(retry.status, "REJECT")
        self.assertIsNone(retry_after)
        self.assertIn("dispatch_consumption.replay", {item.kind for item in retry.issues})

    def test_replaying_consumed_request_is_rejected(self):
        first, after = self.transition()
        self.assertEqual(first.status, "PASS")
        replay_attempt = DispatchConsumptionAttemptV0(
            self.dispatch.receipt_hash,
            self.dispatch.dispatch_request_hash,
            self.domain,
            after.state_hash,
        )
        replay, replay_after = self.transition(replay_attempt, before=after)
        self.assertEqual(replay.status, "REJECT")
        self.assertIsNone(replay_after)
        self.assertIn("dispatch_consumption.replay", {item.kind for item in replay.issues})

    def test_non_pass_dispatch_cannot_enter_consumption(self):
        open_dispatch = dispatch(
            issues=(
                DispatchIssueV0(
                    "dispatch.execution_request_not_current",
                    "PROOF_REQUIRED",
                    h("request-validity"),
                    {},
                ),
            )
        )
        before = DispatchConsumptionStateV0(open_dispatch.dispatch_consumption_domain_hash)
        attempt = DispatchConsumptionAttemptV0(
            open_dispatch.receipt_hash,
            open_dispatch.dispatch_request_hash,
            open_dispatch.dispatch_consumption_domain_hash,
            before.state_hash,
        )
        transition, after = evaluate_dispatch_consumption_transition(
            attempt,
            before_state=before,
            dispatch_receipt=open_dispatch,
        )
        self.assertEqual(transition.status, "PROOF_REQUIRED")
        self.assertIsNone(after)
        self.assertIn("dispatch_consumption.dispatch_not_admitted", {item.kind for item in transition.issues})

    def test_transition_is_not_physical_commit_without_cas_evidence(self):
        transition, _ = self.transition()
        _, receipt = self.commit(transition, evidence=False)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("dispatch_consumption.evidence.required", {item.kind for item in receipt.issues})

    def test_trusted_cas_attestation_closes_consumption_commit(self):
        transition, after = self.transition()
        _, receipt = self.commit(transition)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.before_state_hash, self.before.state_hash)
        self.assertEqual(receipt.after_state_hash, after.state_hash)
        self.assertEqual(receipt.dispatch_request_hash, self.dispatch.dispatch_request_hash)
        self.assertEqual(parse_residual(residual_from_dispatch_consumption_commit(receipt)).status, "CLOSED")

    def test_untrusted_storage_authority_rejects_commit(self):
        transition, _ = self.transition()
        _, receipt = self.commit(transition, storage_authority=h("untrusted-store"))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("dispatch_consumption.storage_authority_untrusted", {item.kind for item in receipt.issues})

    def test_distinct_requests_have_distinct_consumption_domains(self):
        other = dispatch("other-request")
        self.assertNotEqual(other.dispatch_request_hash, self.dispatch.dispatch_request_hash)
        self.assertNotEqual(other.dispatch_consumption_domain_hash, self.dispatch.dispatch_consumption_domain_hash)


if __name__ == "__main__":
    unittest.main()
