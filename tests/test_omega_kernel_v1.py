from __future__ import annotations

import unittest

from tev_script.omega_kernel_v1 import (
    AuthorityGrantV1,
    AuthorityUseV1,
    ContinuationReceiptV1,
    EffectSetV1,
    EpochIdentityV1,
    KernelComputationIdentityV1,
    ObservationEvidenceV1,
    ProofEnvelopeV1,
    ResourceBoundV1,
    ResourceVectorV1,
    authority_grant,
    authority_use,
    compose_resource_sequence,
    continuation_receipt,
    effect_set,
    epoch_identity,
    kernel_computation_identity,
    observation_evidence,
    omega_hash,
    omega_wire,
    proof_envelope,
    resource_exact,
    resource_unknown,
    resource_upper,
    resource_vector,
    validate_continuation_receipt,
    verify_continuation_link,
)


class OmegaKernelIdentityTests(unittest.TestCase):
    def test_kernel_identity_is_canonical_and_self_hashed(self) -> None:
        identity = kernel_computation_identity(
            language_id="TEV-Script",
            language_version="2.0.0",
            semantic_profile="program-ir-v4-pure",
            program_hash="1" * 64,
            source_semantic_hash="2" * 64,
        )
        self.assertIsInstance(identity, KernelComputationIdentityV1)
        wire = omega_wire(identity)
        declared = wire.pop("identity_hash")
        self.assertEqual(declared, omega_hash(wire))
        self.assertEqual(identity.program_hash, "1" * 64)

    def test_proof_envelope_is_evidence_not_authority(self) -> None:
        envelope = proof_envelope(
            claim_kind="translation_validation",
            subject_hash="1" * 64,
            proof_system="external:test",
            proof_artifact_hash="2" * 64,
        )
        self.assertIsInstance(envelope, ProofEnvelopeV1)
        self.assertFalse(envelope.admission_authority)
        wire = omega_wire(envelope)
        declared = wire.pop("envelope_hash")
        self.assertEqual(declared, omega_hash(wire))


class OmegaAuthorityResourceTests(unittest.TestCase):
    def test_unknown_resource_never_collapses_to_zero(self) -> None:
        left = resource_vector(cpu=resource_upper(10), memory=resource_unknown())
        right = resource_vector(cpu=resource_exact(5), memory=resource_upper(1024))
        combined = compose_resource_sequence(left, right)
        self.assertIsInstance(combined, ResourceVectorV1)
        self.assertEqual(combined.cpu.kind, "upper")
        self.assertEqual(combined.cpu.value, 15)
        self.assertEqual(combined.memory.kind, "unknown")
        self.assertIsNone(combined.memory.value)

    def test_effect_set_is_sorted_unique_and_hashed(self) -> None:
        effects = effect_set(
            (
                "command:file.replace",
                "observe:file.read",
                "observe:file.read",
            )
        )
        self.assertIsInstance(effects, EffectSetV1)
        self.assertEqual(
            effects.effects,
            ("command:file.replace", "observe:file.read"),
        )
        wire = omega_wire(effects)
        declared = wire.pop("effect_set_hash")
        self.assertEqual(declared, omega_hash(wire))

    def test_linear_authority_use_consumes_exact_grant(self) -> None:
        grant = authority_grant(
            principal_hash="1" * 64,
            capability_id="file.replace",
            scope_hash="2" * 64,
            duplication_policy="linear",
            resources=resource_vector(effects=resource_upper(1)),
        )
        self.assertIsInstance(grant, AuthorityGrantV1)
        use = authority_use(
            grant=grant,
            operation="commit",
            subject_hash="3" * 64,
            resources=resource_vector(effects=resource_exact(1)),
            consume=True,
        )
        self.assertIsInstance(use, AuthorityUseV1)
        self.assertEqual(use.grant_hash, grant.grant_hash)
        self.assertTrue(use.consumes_grant)

    def test_resource_bound_kinds_are_closed(self) -> None:
        for value in (
            resource_exact(0),
            resource_upper(3),
            resource_unknown(),
        ):
            self.assertIsInstance(value, ResourceBoundV1)
        with self.assertRaises(Exception):
            resource_upper(-1)


class OmegaEpochTests(unittest.TestCase):
    def test_observation_turns_nondeterminism_into_explicit_evidence(self) -> None:
        evidence = observation_evidence(
            capability_id="clock.now",
            contract_hash="1" * 64,
            request_hash="2" * 64,
            result_hash="3" * 64,
            transcript_hash="4" * 64,
        )
        self.assertIsInstance(evidence, ObservationEvidenceV1)
        self.assertEqual(evidence.capability_id, "clock.now")
        wire = omega_wire(evidence)
        declared = wire.pop("evidence_hash")
        self.assertEqual(declared, omega_hash(wire))

    def test_epoch_chain_consumes_exact_previous_continuation(self) -> None:
        first_epoch = epoch_identity(
            epoch_index=0,
            computation_hash="1" * 64,
            input_state_hash="2" * 64,
            authority_hash="3" * 64,
            previous_continuation_hash=None,
        )
        self.assertIsInstance(first_epoch, EpochIdentityV1)
        first = continuation_receipt(
            epoch=first_epoch,
            result_hash="4" * 64,
            state_hash="5" * 64,
            observations_hash="6" * 64,
            effects_hash="7" * 64,
            resources_hash="8" * 64,
        )
        self.assertIsInstance(first, ContinuationReceiptV1)
        second_epoch = epoch_identity(
            epoch_index=1,
            computation_hash="9" * 64,
            input_state_hash="5" * 64,
            authority_hash="a" * 64,
            previous_continuation_hash=first.continuation_hash,
        )
        second = continuation_receipt(
            epoch=second_epoch,
            result_hash="b" * 64,
            state_hash="c" * 64,
            observations_hash="d" * 64,
            effects_hash="e" * 64,
            resources_hash="f" * 64,
        )
        self.assertTrue(verify_continuation_link(first, second))

    def test_continuation_tamper_is_rejected(self) -> None:
        epoch = epoch_identity(
            epoch_index=0,
            computation_hash="1" * 64,
            input_state_hash="2" * 64,
            authority_hash="3" * 64,
            previous_continuation_hash=None,
        )
        receipt = continuation_receipt(
            epoch=epoch,
            result_hash="4" * 64,
            state_hash="5" * 64,
            observations_hash="6" * 64,
            effects_hash="7" * 64,
            resources_hash="8" * 64,
        )
        wire = omega_wire(receipt)
        wire["state_hash"] = "9" * 64
        with self.assertRaises(Exception):
            validate_continuation_receipt(wire)


if __name__ == "__main__":
    unittest.main()
