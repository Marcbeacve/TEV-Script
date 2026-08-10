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
from tev_script.semantic_dispatch_v0 import DispatchIssueV0, ExecutionDispatchReceiptV0
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


def dispatch(request="request", *, issues=()) -> ExecutionDispatchReceiptV0:
    return ExecutionDispatchReceiptV0(
        h("dispatch-candidate-" + request),
        h("dispatch-record-" + request),
        h(request),
        h("dispatch-epoch"),
        h("activation"),
        h("activation-validity"),
        h("activation-authority-state"),
        h("execution-authority"),
        h("execution-authority-validity"),
        h("execution-authority-state"),
        h("realization-receipt"),
        h("realization"),
        h("execution-context"),
        h("machine-instance"),
        h("placement-context"),
        h("runtime-state"),
        tuple(issues),
    )


class DispatchConsumptionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.domain = h("dispatch-domain")
        self.before = DispatchConsumptionStateV0(self.domain)
        self.dispatch = dispatch()
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
        record = DispatchConsumptionCommitRecordV0(
            transition.transition_hash,
            storage_authority or self.storage_authority,
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
                storage_authority or self.storage_authority,
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
        self.assertEqual(parse_residual(residual_from_dispatch_consumption_transition(transition)).status, "CLOSED")

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
                    "dispatch.execution_authority_not_current",
                    "PROOF_REQUIRED",
                    h("authority"),
                    {},
                ),
            )
        )
        attempt = DispatchConsumptionAttemptV0(
            open_dispatch.receipt_hash,
            open_dispatch.dispatch_request_hash,
            self.domain,
            self.before.state_hash,
        )
        transition, after = self.transition(attempt, dispatch_receipt=open_dispatch)
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

    def test_concurrent_distinct_requests_share_before_state_but_produce_distinct_after_states(self):
        other_dispatch = dispatch("other-request")
        other_attempt = DispatchConsumptionAttemptV0(
            other_dispatch.receipt_hash,
            other_dispatch.dispatch_request_hash,
            self.domain,
            self.before.state_hash,
        )
        first_transition, first_after = self.transition()
        second_transition, second_after = self.transition(
            other_attempt,
            dispatch_receipt=other_dispatch,
        )
        self.assertEqual(first_transition.status, "PASS")
        self.assertEqual(second_transition.status, "PASS")
        self.assertNotEqual(first_after.state_hash, second_after.state_hash)
        self.assertEqual(first_transition.before_state_hash, second_transition.before_state_hash)
        # R0 intentionally requires a physical CAS attestation before either
        # transition may authorize effects; the pure transition itself does not
        # claim that both concurrent updates can be committed.


if __name__ == "__main__":
    unittest.main()
