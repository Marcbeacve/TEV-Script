from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_request_v0 import (
    ExecutionIntentV0,
    ExecutionRequestError,
    ExecutionRequestPolicyV0,
    ExecutionRequestRecordV0,
    ExecutionRequestV0,
    evaluate_execution_request,
    residual_from_execution_request,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class ExecutionRequestV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.principal = h("requester")
        self.purpose = h("purpose")
        self.policy_context = h("policy-context")
        self.workload = h("workload")
        self.scope = h("request-evidence-scope")
        self.verifier = h("request-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "request-authorship",
                    ("ATTESTATION", "PROOF"),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = ExecutionRequestPolicyV0(
            self.evidence_policy.policy_hash,
            (self.principal,),
            allowed_purpose_hashes=(self.purpose,),
        )

    def intent(self, *, idempotency="OCCURRENCE_SCOPED", principal=None, purpose=None, guarantee="AT_MOST_ONCE_DISPATCH"):
        return ExecutionIntentV0(
            self.workload,
            principal or self.principal,
            purpose or self.purpose,
            self.policy_context,
            guarantee,
            idempotency,
        )

    def request(self, *, idempotency="OCCURRENCE_SCOPED", occurrence=None, principal=None, purpose=None, guarantee="AT_MOST_ONCE_DISPATCH"):
        intent = self.intent(
            idempotency=idempotency,
            principal=principal,
            purpose=purpose,
            guarantee=guarantee,
        )
        return ExecutionRequestV0(
            intent,
            "" if idempotency == "INTENT_SINGLETON" else (occurrence or h("occurrence-1")),
        )

    def evidence(self, request, *, status="ACTIVE"):
        return EvidenceItemV0(
            "e.request." + status.lower(),
            request.request_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("request-witness"),
            status=status,
        )

    def evaluate(self, request, *, policy=None, include_evidence=True, evidence_status="ACTIVE"):
        witness = self.evidence(request, status=evidence_status)
        record = ExecutionRequestRecordV0(
            request,
            self.evidence_policy.policy_hash,
            (witness.evidence_hash,) if include_evidence else (),
        )
        result = evaluate_execution_request(
            record,
            policy=policy or self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(witness,) if include_evidence else (),
        )
        return record, witness, result

    def test_occurrence_scoped_retry_keeps_request_identity(self):
        first = self.request(occurrence=h("occurrence-a"))
        retry = self.request(occurrence=h("occurrence-a"))
        second_occurrence = self.request(occurrence=h("occurrence-b"))
        self.assertEqual(first.request_hash, retry.request_hash)
        self.assertNotEqual(first.request_hash, second_occurrence.request_hash)
        self.assertEqual(first.intent.intent_hash, second_occurrence.intent.intent_hash)

    def test_singleton_intent_has_one_deterministic_request(self):
        first = self.request(idempotency="INTENT_SINGLETON")
        second = self.request(idempotency="INTENT_SINGLETON")
        self.assertEqual(first.request_hash, second.request_hash)
        with self.assertRaises(ExecutionRequestError):
            ExecutionRequestV0(first.intent, h("forbidden-occurrence"))

    def test_occurrence_scoped_requires_explicit_occurrence_key(self):
        with self.assertRaises(ExecutionRequestError):
            ExecutionRequestV0(self.intent(idempotency="OCCURRENCE_SCOPED"), "")

    def test_requester_purpose_delivery_and_idempotency_are_intent_semantics(self):
        base = self.request()
        foreign_requester = self.request(principal=h("other-requester"))
        other_purpose = self.request(purpose=h("other-purpose"))
        exactly_once = self.request(guarantee="EXACTLY_ONCE_COMMIT")
        singleton = self.request(idempotency="INTENT_SINGLETON")
        hashes = {
            base.intent.intent_hash,
            foreign_requester.intent.intent_hash,
            other_purpose.intent.intent_hash,
            exactly_once.intent.intent_hash,
            singleton.intent.intent_hash,
        }
        self.assertEqual(len(hashes), 5)

    def test_trusted_request_with_bound_evidence_passes(self):
        request = self.request()
        record, _, result = self.evaluate(request)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.request_hash, request.request_hash)
        self.assertEqual(result.request_record_hash, record.record_hash)
        self.assertEqual(result.invocation_workload_hash, self.workload)
        self.assertEqual(parse_residual(residual_from_execution_request(result)).status, "CLOSED")

    def test_untrusted_requester_rejects_even_with_valid_witness(self):
        request = self.request(principal=h("untrusted-requester"))
        _, _, result = self.evaluate(request)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("request.requester_untrusted", {item.kind for item in result.issues})

    def test_missing_request_evidence_remains_open(self):
        request = self.request()
        _, _, result = self.evaluate(request, include_evidence=False)
        self.assertEqual(result.status, "PROOF_REQUIRED")
        self.assertIn("request.evidence.required", {item.kind for item in result.issues})

    def test_revoked_same_witness_reopens_without_changing_evidence_identity(self):
        request = self.request()
        active = self.evidence(request, status="ACTIVE")
        revoked = self.evidence(request, status="REVOKED")
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        record = ExecutionRequestRecordV0(
            request,
            self.evidence_policy.policy_hash,
            (active.evidence_hash,),
        )
        active_eval = evaluate_execution_request(
            record,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(active,),
        )
        revoked_eval = evaluate_execution_request(
            record,
            policy=self.policy,
            evidence_policy=self.evidence_policy,
            evidence=(revoked,),
        )
        self.assertEqual(active_eval.status, "PASS")
        self.assertEqual(revoked_eval.status, "PROOF_REQUIRED")

    def test_policy_can_forbid_delivery_guarantee_or_idempotency_scope(self):
        strict = ExecutionRequestPolicyV0(
            self.evidence_policy.policy_hash,
            (self.principal,),
            allowed_delivery_guarantees=("AT_MOST_ONCE_DISPATCH",),
            allowed_idempotency_scopes=("INTENT_SINGLETON",),
            allowed_purpose_hashes=(self.purpose,),
        )
        exactly_once = self.request(guarantee="EXACTLY_ONCE_COMMIT")
        _, _, result = self.evaluate(exactly_once, policy=strict)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("request.delivery_guarantee_not_allowed", {item.kind for item in result.issues})

        repeatable = self.request(idempotency="OCCURRENCE_SCOPED")
        _, _, result = self.evaluate(repeatable, policy=strict)
        self.assertEqual(result.status, "REJECT")
        self.assertIn("request.idempotency_scope_not_allowed", {item.kind for item in result.issues})


if __name__ == "__main__":
    unittest.main()
