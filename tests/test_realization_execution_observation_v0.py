from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_activation_v0 import ActivationIssueV0, ExecutionActivationReceiptV0
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_execution_observation_v0 import (
    ExecutionObservationClaimV0,
    ExecutionObservationPolicyV0,
    ExecutionObservationRecordV0,
    evaluate_execution_observation,
    residual_from_execution_observation,
)
from tev_script.semantic_kernel_v0 import field_from_mapping
from tev_script.semantic_residual_v0 import (
    ResidualObstructionV0,
    parse_residual,
    residual_from_obstructions,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


def activation_receipt(*, issues=()) -> ExecutionActivationReceiptV0:
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


class ExecutionObservationV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.activation = activation_receipt()
        self.causal_result = field_from_mapping(
            "tev.test.causal_result",
            {"status": "COMMITTED", "result": h("result")},
        )
        self.causal_residual = residual_from_obstructions(
            domain="causal",
            judgment_id="commit",
            judgment={"kind": "commit_completed"},
            source={"kind": "test"},
            obstructions=(),
        )
        self.history = field_from_mapping(
            "tev.test.observed_history",
            {"events_hash": h("events")},
        )
        self.assumption = h("observation-assumption")
        self.scope = h("observation-scope")
        self.verifier = h("observation-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "execution-observation",
                    ("ATTESTATION", "EMPIRICAL_OBSERVATION"),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = ExecutionObservationPolicyV0(
            self.evidence_policy.policy_hash,
            accepted_assumption_hashes=(self.assumption,),
        )

    def claim(self, *, trace_hash="") -> ExecutionObservationClaimV0:
        return ExecutionObservationClaimV0(
            self.activation.receipt_hash,
            self.activation.execution_context_hash,
            self.causal_result.field_hash,
            self.causal_residual.field_hash,
            self.history.field_hash,
            trace_hash=trace_hash,
            assumption_hashes=(self.assumption,),
        )

    def evidence(self, claim, *, evidence_id="e.observation", status="ACTIVE") -> EvidenceItemV0:
        return EvidenceItemV0(
            evidence_id,
            claim.observation_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("observation-witness"),
            assumption_hashes=(self.assumption,),
            status=status,
        )

    def record(self, claim, evidence_hashes=(), provenance=None):
        return ExecutionObservationRecordV0(
            claim,
            self.evidence_policy.policy_hash,
            tuple(evidence_hashes),
            provenance={} if provenance is None else provenance,
        )

    def evaluate(self, record, evidence=(), **overrides):
        args = {
            "activation_receipt": self.activation,
            "causal_result_field": self.causal_result,
            "causal_residual_field": self.causal_residual,
            "observed_history": self.history,
            "policy": self.policy,
            "evidence_policy": self.evidence_policy,
            "evidence": tuple(evidence),
        }
        args.update(overrides)
        return evaluate_execution_observation(record, **args)

    def test_bound_evidenced_observation_closes(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        receipt = self.evaluate(self.record(claim, (evidence.evidence_hash,)), (evidence,))
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(parse_residual(residual_from_execution_observation(receipt)).status, "CLOSED")

    def test_record_provenance_does_not_change_observation_claim(self):
        claim = self.claim()
        left = self.record(claim, provenance={"collector": "a"})
        right = self.record(claim, provenance={"collector": "b"})
        self.assertEqual(left.claim.observation_claim_hash, right.claim.observation_claim_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_abort_or_open_causal_residual_can_still_be_authentic_observation(self):
        causal_result = field_from_mapping(
            "tev.test.causal_result",
            {"status": "ABORTED", "reason": "precondition"},
        )
        causal_residual = residual_from_obstructions(
            domain="causal",
            judgment_id="commit",
            judgment={"kind": "commit_completed"},
            source={"kind": "test"},
            obstructions=(
                ResidualObstructionV0(
                    "operational.application_aborted",
                    "commit",
                    "committed",
                    "ABORTED",
                    {},
                ),
            ),
        )
        claim = ExecutionObservationClaimV0(
            self.activation.receipt_hash,
            self.activation.execution_context_hash,
            causal_result.field_hash,
            causal_residual.field_hash,
            self.history.field_hash,
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        receipt = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            causal_result_field=causal_result,
            causal_residual_field=causal_residual,
        )
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(parse_residual(causal_residual).status, "OPEN")

    def test_non_residual_causal_residual_field_rejects(self):
        fake = field_from_mapping("tev.test.fake_residual", {"x": 1})
        claim = ExecutionObservationClaimV0(
            self.activation.receipt_hash,
            self.activation.execution_context_hash,
            self.causal_result.field_hash,
            fake.field_hash,
            self.history.field_hash,
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        receipt = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            causal_residual_field=fake,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("observation.causal_residual_not_residual_field", {item.kind for item in receipt.issues})

    def test_activation_must_be_pass(self):
        open_activation = activation_receipt(
            issues=(ActivationIssueV0("activation.runtime_state_not_admitted", "PROOF_REQUIRED", h("runtime"), {}),)
        )
        claim = ExecutionObservationClaimV0(
            open_activation.receipt_hash,
            open_activation.execution_context_hash,
            self.causal_result.field_hash,
            self.causal_residual.field_hash,
            self.history.field_hash,
            assumption_hashes=(self.assumption,),
        )
        evidence = self.evidence(claim)
        receipt = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            activation_receipt=open_activation,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("observation.activation_not_admitted", {item.kind for item in receipt.issues})

    def test_history_or_result_hash_mismatch_rejects(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        wrong_history = field_from_mapping("tev.test.observed_history", {"events_hash": h("other")})
        receipt = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            observed_history=wrong_history,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("observation.history_mismatch", {item.kind for item in receipt.issues})

    def test_trace_requirement_stays_open_when_trace_absent(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        strict = ExecutionObservationPolicyV0(
            self.evidence_policy.policy_hash,
            accepted_assumption_hashes=(self.assumption,),
            require_trace=True,
        )
        receipt = self.evaluate(
            self.record(claim, (evidence.evidence_hash,)),
            (evidence,),
            policy=strict,
        )
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("observation.trace_required", {item.kind for item in receipt.issues})

    def test_revocation_keeps_support_identity_but_reopens_observation(self):
        claim = self.claim()
        active = self.evidence(claim, evidence_id="e.active", status="ACTIVE")
        revoked = self.evidence(claim, evidence_id="e.revoked", status="REVOKED")
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        record = self.record(claim, (active.evidence_hash,))
        self.assertEqual(self.evaluate(record, (active,)).status, "PASS")
        reopened = self.evaluate(record, (revoked,))
        self.assertEqual(reopened.status, "PROOF_REQUIRED")
        self.assertIn("observation.evidence.inactive", {item.kind for item in reopened.issues})

    def test_positive_support_must_be_record_bound(self):
        claim = self.claim()
        evidence = self.evidence(claim)
        receipt = self.evaluate(self.record(claim), (evidence,))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("observation.evidence_unbound_support", {item.kind for item in receipt.issues})


if __name__ == "__main__":
    unittest.main()
