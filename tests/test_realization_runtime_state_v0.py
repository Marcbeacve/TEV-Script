from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import EvidenceItemV0, EvidencePolicyV0, EvidenceRequirementV0
from tev_script.semantic_runtime_state_v0 import (
    RuntimeStateObservationV0,
    RuntimeStatePolicyV0,
    RuntimeStateSemanticsError,
    evaluate_runtime_state,
    residual_from_runtime_state,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class RuntimeStateV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.instance = h("machine-instance")
        self.assumption = h("runtime-assumption")
        self.scope = h("runtime-observation-scope")
        self.verifier = h("runtime-verifier")
        self.evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "runtime-observation",
                    ("ATTESTATION", "EMPIRICAL_OBSERVATION"),
                    scope_hash=self.scope,
                    trusted_verifier_hashes=(self.verifier,),
                ),
            )
        )
        self.policy = RuntimeStatePolicyV0(
            self.evidence_policy.policy_hash,
            accepted_availability_statuses=("AVAILABLE", "DEGRADED"),
            accepted_assumption_hashes=(self.assumption,),
        )

    def observation(
        self,
        *,
        status="AVAILABLE",
        epoch="epoch-a",
        state="state-a",
        evidence_hashes=(),
        source="source-a",
        detail=None,
    ) -> RuntimeStateObservationV0:
        return RuntimeStateObservationV0(
            self.instance,
            h(epoch),
            status,
            h(state),
            assumption_hashes=(self.assumption,),
            evidence_hashes=tuple(evidence_hashes),
            observation_source_hash=h(source),
            detail={} if detail is None else detail,
        )

    def evidence(self, observation, *, evidence_id="e.runtime", status="ACTIVE") -> EvidenceItemV0:
        return EvidenceItemV0(
            evidence_id,
            observation.runtime_state_claim_hash,
            self.scope,
            "ATTESTATION",
            verifier_hash=self.verifier,
            witness_hash=h("runtime-witness"),
            assumption_hashes=(self.assumption,),
            status=status,
        )

    def evaluate(self, observation, evidence=(), policy=None, evidence_policy=None):
        return evaluate_runtime_state(
            observation,
            policy=policy or self.policy,
            evidence_policy=evidence_policy or self.evidence_policy,
            evidence=tuple(evidence),
        )

    def test_source_detail_and_evidence_refs_are_record_not_state_claim_identity(self):
        base = self.observation(source="source-a", detail={"sensor": "a"})
        changed = self.observation(source="source-b", detail={"sensor": "b"}, evidence_hashes=(h("some-evidence"),))
        self.assertEqual(base.runtime_state_claim_hash, changed.runtime_state_claim_hash)
        self.assertNotEqual(base.record_hash, changed.record_hash)

    def test_epoch_status_or_runtime_state_change_changes_claim(self):
        base = self.observation()
        self.assertNotEqual(base.runtime_state_claim_hash, self.observation(epoch="epoch-b").runtime_state_claim_hash)
        self.assertNotEqual(base.runtime_state_claim_hash, self.observation(status="DEGRADED").runtime_state_claim_hash)
        self.assertNotEqual(base.runtime_state_claim_hash, self.observation(state="state-b").runtime_state_claim_hash)

    def test_available_state_with_bound_evidence_passes(self):
        raw = self.observation()
        evidence = self.evidence(raw)
        observation = self.observation(evidence_hashes=(evidence.evidence_hash,))
        evaluation = self.evaluate(observation, (evidence,))
        self.assertEqual(evaluation.status, "PASS")
        self.assertEqual(parse_residual(residual_from_runtime_state(evaluation)).status, "CLOSED")

    def test_unknown_is_proof_required_never_pass(self):
        raw = self.observation(status="UNKNOWN")
        evidence = self.evidence(raw)
        observation = self.observation(status="UNKNOWN", evidence_hashes=(evidence.evidence_hash,))
        evaluation = self.evaluate(observation, (evidence,))
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("runtime.availability_unknown", {item.kind for item in evaluation.issues})

    def test_policy_cannot_explicitly_admit_unknown(self):
        with self.assertRaises(RuntimeStateSemanticsError):
            RuntimeStatePolicyV0(
                self.evidence_policy.policy_hash,
                accepted_availability_statuses=("UNKNOWN",),
            )

    def test_unavailable_rejects_under_available_degraded_policy(self):
        raw = self.observation(status="UNAVAILABLE")
        evidence = self.evidence(raw)
        observation = self.observation(status="UNAVAILABLE", evidence_hashes=(evidence.evidence_hash,))
        evaluation = self.evaluate(observation, (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("runtime.availability_not_accepted", {item.kind for item in evaluation.issues})

    def test_degraded_can_pass_only_when_policy_explicitly_accepts_it(self):
        raw = self.observation(status="DEGRADED")
        evidence = self.evidence(raw)
        observation = self.observation(status="DEGRADED", evidence_hashes=(evidence.evidence_hash,))
        self.assertEqual(self.evaluate(observation, (evidence,)).status, "PASS")
        strict = RuntimeStatePolicyV0(
            self.evidence_policy.policy_hash,
            accepted_availability_statuses=("AVAILABLE",),
            accepted_assumption_hashes=(self.assumption,),
        )
        self.assertEqual(self.evaluate(observation, (evidence,), policy=strict).status, "REJECT")

    def test_revocation_preserves_evidence_identity_but_reopens_runtime_state(self):
        raw = self.observation()
        active = self.evidence(raw, evidence_id="e.active", status="ACTIVE")
        revoked = self.evidence(raw, evidence_id="e.revoked", status="REVOKED")
        self.assertEqual(active.evidence_hash, revoked.evidence_hash)
        observation = self.observation(evidence_hashes=(active.evidence_hash,))
        self.assertEqual(self.evaluate(observation, (active,)).status, "PASS")
        reopened = self.evaluate(observation, (revoked,))
        self.assertEqual(reopened.status, "PROOF_REQUIRED")
        self.assertIn("runtime.evidence.inactive", {item.kind for item in reopened.issues})

    def test_positive_runtime_support_must_be_record_bound(self):
        observation = self.observation()
        evidence = self.evidence(observation)
        evaluation = self.evaluate(observation, (evidence,))
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("runtime.evidence_unbound_support", {item.kind for item in evaluation.issues})

    def test_empty_evidence_policy_rejects(self):
        empty = EvidencePolicyV0(())
        policy = RuntimeStatePolicyV0(empty.policy_hash)
        evaluation = self.evaluate(self.observation(), policy=policy, evidence_policy=empty)
        self.assertEqual(evaluation.status, "REJECT")
        self.assertIn("runtime.evidence_policy_empty", {item.kind for item in evaluation.issues})


if __name__ == "__main__":
    unittest.main()
