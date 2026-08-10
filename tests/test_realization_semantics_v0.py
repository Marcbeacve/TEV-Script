from __future__ import annotations

from fractions import Fraction
import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
    evaluate_evidence,
    evidence_from_proof_boundary,
)
from tev_script.semantic_machine_v0 import (
    MachineCapabilityV0,
    MachineFieldV0,
    MachineRequirementV0,
    MachineSemanticsError,
    NumericModelV0,
    evaluate_machine_compatibility,
)
from tev_script.semantic_proof_boundary_v0 import ProofBoundaryWitnessV0
from tev_script.semantic_regime_v0 import (
    RegimeConstraintV0,
    RegimeContractV0,
    RegimePreservationClaimV0,
    TransformationRegimeBindingV0,
    evaluate_regime_preservation,
)
from tev_script.semantic_realization_v0 import (
    ApproximationContractV0,
    ApproximationPolicyV0,
    RealizationCandidateV0,
    RealizationPolicyV0,
    RealizationProblemV0,
    admit_realization,
    pareto_front,
    realization_semantic_claim_hash,
    residual_from_realization_admission,
    semantic_memoization_key,
)
from tev_script.semantic_residual_v0 import parse_residual
from tev_script.semantic_resource_algebra_v0 import (
    ResourceAlgebraError,
    ResourceBoundV0,
    ResourceCatalogV0,
    ResourceCeilingV0,
    ResourceDimensionV0,
    ResourceVectorV0,
    compose_resource_vectors,
    evaluate_resource_ceilings,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


class ResourceAlgebraV0Tests(unittest.TestCase):
    def setUp(self):
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("peak_memory", "byte", "MAX", "SUM"),
            )
        )

    def vector(self, bounds, *, complete):
        return ResourceVectorV0(
            tuple(bounds),
            complete=complete,
            catalog_hash=self.catalog.catalog_hash,
        )

    def test_exact_rational_sequential_and_parallel_composition(self):
        left = self.vector(
            (
                ResourceBoundV0.exact("latency", Fraction(3, 2)),
                ResourceBoundV0.exact("energy", 2),
                ResourceBoundV0.exact("peak_memory", 8),
            ),
            complete=True,
        )
        right = self.vector(
            (
                ResourceBoundV0.exact("latency", Fraction(5, 2)),
                ResourceBoundV0.exact("energy", 3),
                ResourceBoundV0.exact("peak_memory", 13),
            ),
            complete=True,
        )
        sequential = compose_resource_vectors((left, right), self.catalog, mode="SEQUENTIAL")
        parallel = compose_resource_vectors((left, right), self.catalog, mode="PARALLEL")
        self.assertEqual(sequential.bound("latency").exact_value, Fraction(4, 1))
        self.assertEqual(parallel.bound("latency").exact_value, Fraction(5, 2))
        self.assertEqual(sequential.bound("energy").exact_value, 5)
        self.assertEqual(parallel.bound("energy").exact_value, 5)
        self.assertEqual(sequential.bound("peak_memory").exact_value, 13)
        self.assertEqual(parallel.bound("peak_memory").exact_value, 21)
        self.assertEqual(sequential.catalog_hash, self.catalog.catalog_hash)

    def test_unknown_bound_propagates_instead_of_becoming_zero(self):
        left = self.vector((ResourceBoundV0.exact("energy", 1),), complete=False)
        right = self.vector((ResourceBoundV0.exact("latency", 2),), complete=False)
        combined = compose_resource_vectors((left, right), self.catalog, mode="SEQUENTIAL")
        self.assertIsNone(combined.bound("latency").upper)
        self.assertIsNone(combined.bound("energy").upper)
        self.assertIsNone(combined.bound("peak_memory").upper)

    def test_complete_vector_must_cover_exact_catalog(self):
        incomplete_surface = self.vector((ResourceBoundV0.exact("energy", 4),), complete=True)
        with self.assertRaises(ResourceAlgebraError):
            incomplete_surface.validate_against(self.catalog)

    def test_vector_dimension_outside_catalog_rejects(self):
        vector = self.vector((ResourceBoundV0.exact("unknown_dimension", 1),), complete=False)
        with self.assertRaises(ResourceAlgebraError):
            vector.validate_against(self.catalog)

    def test_catalog_identity_is_part_of_resource_meaning(self):
        other = ResourceCatalogV0((ResourceDimensionV0("latency", "cycle", "SUM", "MAX"),))
        vector = ResourceVectorV0(
            (ResourceBoundV0.exact("latency", 1),),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        with self.assertRaises(ResourceAlgebraError):
            vector.validate_against(other)

    def test_resource_ceilings_distinguish_unknown_and_exceeded(self):
        vector = self.vector(
            (
                ResourceBoundV0("latency", 2, None),
                ResourceBoundV0.exact("energy", 11),
                ResourceBoundV0.exact("peak_memory", 1),
            ),
            complete=True,
        )
        issues = evaluate_resource_ceilings(
            vector,
            (
                ResourceCeilingV0("latency", 10, self.catalog.catalog_hash),
                ResourceCeilingV0("energy", 10, self.catalog.catalog_hash),
            ),
        )
        self.assertEqual(
            {(item.kind, item.dimension_id) for item in issues},
            {("UNKNOWN", "latency"), ("EXCEEDED", "energy")},
        )


class MachineAndEvidenceV0Tests(unittest.TestCase):
    def test_machine_identity_is_order_independent_and_semantic_capability_based(self):
        op_a = MachineCapabilityV0("host.alpha", h("op-a"), "compute")
        op_b = MachineCapabilityV0("host.beta", h("op-b"), "compute", ("exact.int",))
        numeric = NumericModelV0("exact.int", h("exact-int"), True)
        first = MachineFieldV0(
            "machine.test",
            capabilities=(op_a, op_b),
            numeric_models=(numeric,),
            executable_formats=("format.z", "format.a"),
        )
        second = MachineFieldV0(
            "machine.test",
            capabilities=(op_b, op_a),
            numeric_models=(numeric,),
            executable_formats=("format.a", "format.z"),
        )
        self.assertEqual(first.machine_hash, second.machine_hash)
        self.assertTrue(first.supports_semantic_capability(h("op-a")))
        requirement = MachineRequirementV0((h("op-a"),), ("exact.int",), ("format.a",))
        self.assertTrue(evaluate_machine_compatibility(first, requirement).compatible)

    def test_capability_cannot_reference_undefined_numeric_model(self):
        with self.assertRaises(MachineSemanticsError):
            MachineFieldV0(
                "machine.bad",
                capabilities=(
                    MachineCapabilityV0(
                        "opaque.compute",
                        h("compute"),
                        "compute",
                        ("missing.numeric",),
                    ),
                ),
            )

    def test_machine_missing_semantic_operation_is_explicit(self):
        machine = MachineFieldV0("machine.test")
        requirement = MachineRequirementV0((h("missing-op"),), (), ())
        evaluation = evaluate_machine_compatibility(machine, requirement)
        self.assertFalse(evaluation.compatible)
        self.assertEqual(evaluation.missing_capability_semantic_hashes, (h("missing-op"),))

    def test_evidence_policy_checks_method_scope_verifier_and_status(self):
        claim = h("claim")
        scope = h("scope")
        verifier = h("verifier")
        policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "translation",
                    ("TRANSLATION_VALIDATION",),
                    scope_hash=scope,
                    trusted_verifier_hashes=(verifier,),
                ),
            )
        )
        valid = EvidenceItemV0(
            "e.valid",
            claim,
            scope,
            "TRANSLATION_VALIDATION",
            verifier_hash=verifier,
            witness_hash=h("witness"),
        )
        self.assertTrue(evaluate_evidence(claim, policy, (valid,)).complete)

        revoked = EvidenceItemV0(
            "e.revoked",
            claim,
            scope,
            "TRANSLATION_VALIDATION",
            verifier_hash=verifier,
            witness_hash=h("revoked-witness"),
            status="REVOKED",
        )
        evaluation = evaluate_evidence(claim, policy, (revoked,))
        self.assertFalse(evaluation.complete)
        self.assertEqual({item.kind for item in evaluation.issues}, {"evidence.inactive"})

    def test_falsified_evidence_on_exact_claim_is_never_silently_ignored(self):
        claim = h("claim")
        policy = EvidencePolicyV0(())
        falsified = EvidenceItemV0(
            "e.false",
            claim,
            h("scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        evaluation = evaluate_evidence(claim, policy, (falsified,))
        self.assertTrue(evaluation.falsified)
        self.assertIn("evidence.falsified", {item.kind for item in evaluation.issues})

    def test_existing_proof_boundary_projects_without_redefining_it(self):
        witness = ProofBoundaryWitnessV0(
            h("proof"), h("verifier"), h("scope"), "proved", "active"
        )
        projected = evidence_from_proof_boundary(
            witness,
            evidence_id="proof.projected",
            claim_hash=h("claim"),
        )
        self.assertEqual(projected.method, "PROOF")
        self.assertEqual(projected.verifier_hash, witness.verifier_hash)
        self.assertEqual(projected.witness_hash, witness.witness_hash)


class RegimeAndRealizationAdmissionV0Tests(unittest.TestCase):
    def _fixture(self, *, latency_upper=5, relation="EXACT_EQUIVALENT", approximation=None):
        transformation = h("transformation")
        scope = h("semantic-scope")
        assumption = h("assumption")
        constraint_hash = h("constraint")
        invariant_hash = h("invariant")
        regime = RegimeContractV0(
            "regime.test",
            h("possibility-space"),
            h("history-space"),
            constraints=(RegimeConstraintV0("c.safe", "safety", constraint_hash, scope),),
            equivalence_relation_hash=h("regime-equivalence"),
            observable_profile_hash=h("observables"),
            invariant_claim_hashes=(invariant_hash,),
            assumption_hashes=(assumption,),
        )
        binding = TransformationRegimeBindingV0(
            transformation,
            regime.regime_hash,
            scope,
        )
        verifier = h("verifier")
        realization_evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "semantic-preservation",
                    ("TRANSLATION_VALIDATION",),
                    scope_hash=scope,
                    trusted_verifier_hashes=(verifier,),
                ),
            )
        )
        regime_evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "regime-preservation",
                    ("PROOF",),
                    scope_hash=scope,
                    trusted_verifier_hashes=(verifier,),
                ),
            )
        )
        resource_catalog = ResourceCatalogV0(
            (ResourceDimensionV0("latency", "ms", "SUM", "MAX"),)
        )
        approximation_policy = None
        if relation == "APPROXIMATION":
            approximation_policy = ApproximationPolicyV0(
                h("metric"),
                h("approx-domain"),
                Fraction(1, 100),
                ("DETERMINISTIC_BOUND",),
            )
        policy = RealizationPolicyV0(
            (relation,),
            realization_evidence_policy.policy_hash,
            regime_evidence_policy.policy_hash,
            resource_catalog.catalog_hash,
            accepted_assumption_hashes=(assumption,),
            resource_ceilings=(
                ResourceCeilingV0("latency", 10, resource_catalog.catalog_hash),
            ),
            approximation_policy=approximation_policy,
        )
        operation_hash = h("machine-operation")
        machine = MachineFieldV0(
            "machine.test",
            capabilities=(MachineCapabilityV0("opaque.compute", operation_hash, "compute"),),
            executable_formats=("tev.binary",),
        )
        requirement = MachineRequirementV0((operation_hash,), (), ("tev.binary",))
        problem = RealizationProblemV0(
            transformation,
            binding.binding_hash,
            h("context"),
            policy.policy_hash,
            (machine.machine_hash,),
        )
        claim_hash = realization_semantic_claim_hash(
            transformation_semantic_hash=transformation,
            transformation_regime_binding_hash=binding.binding_hash,
            machine_hash=machine.machine_hash,
            artifact_hashes=(h("artifact"),),
            machine_requirement=requirement,
            semantic_relation=relation,
            approximation_contract=approximation,
            assumption_hashes=(assumption,),
        )
        preservation = RegimePreservationClaimV0(
            claim_hash,
            binding.binding_hash,
            regime.regime_hash,
            relation,
            preserved_constraint_hashes=(constraint_hash,),
            preserved_invariant_hashes=(invariant_hash,),
            equivalence_preservation="PRESERVED",
            assumption_hashes=(assumption,),
        )
        semantic_evidence = EvidenceItemV0(
            "e.semantic",
            claim_hash,
            scope,
            "TRANSLATION_VALIDATION",
            verifier_hash=verifier,
            witness_hash=h("translation-witness"),
        )
        regime_evidence = EvidenceItemV0(
            "e.regime",
            preservation.preservation_claim_hash,
            scope,
            "PROOF",
            verifier_hash=verifier,
            witness_hash=h("regime-witness"),
        )
        candidate = RealizationCandidateV0(
            transformation,
            binding.binding_hash,
            "tev.realization.test",
            machine.machine_hash,
            (h("artifact"),),
            requirement,
            relation,
            approximation_contract=approximation,
            assumption_hashes=(assumption,),
            predicted_resources=ResourceVectorV0(
                (ResourceBoundV0("latency", 1, latency_upper),),
                complete=True,
                catalog_hash=resource_catalog.catalog_hash,
            ),
            evidence_hashes=(semantic_evidence.evidence_hash, regime_evidence.evidence_hash),
            regime_preservation_claim_hash=preservation.preservation_claim_hash,
        )
        self.assertEqual(candidate.semantic_claim_hash, claim_hash)
        return {
            "problem": problem,
            "candidate": candidate,
            "machine": machine,
            "policy": policy,
            "resource_catalog": resource_catalog,
            "regime": regime,
            "binding": binding,
            "preservation": preservation,
            "realization_evidence_policy": realization_evidence_policy,
            "regime_evidence_policy": regime_evidence_policy,
            "evidence": (semantic_evidence, regime_evidence),
        }

    def _admit(self, fixture, **overrides):
        args = dict(fixture)
        args.update(overrides)
        evidence = args.pop("evidence")
        preservation = args.pop("preservation")
        return admit_realization(
            args.pop("problem"),
            args.pop("candidate"),
            preservation_claim=preservation,
            evidence=evidence,
            **args,
        )

    def test_regime_unresolved_invariant_is_proof_required_not_pass(self):
        f = self._fixture()
        claim = RegimePreservationClaimV0(
            f["candidate"].semantic_claim_hash,
            f["binding"].binding_hash,
            f["regime"].regime_hash,
            "EXACT_EQUIVALENT",
            preserved_constraint_hashes=f["regime"].constraint_claim_hashes,
            equivalence_preservation="PRESERVED",
            assumption_hashes=f["regime"].assumption_hashes,
        )
        evaluation = evaluate_regime_preservation(
            f["regime"],
            f["binding"],
            claim,
            transformation_semantic_hash=f["problem"].transformation_semantic_hash,
            realization_semantic_claim_hash=f["candidate"].semantic_claim_hash,
            semantic_relation="EXACT_EQUIVALENT",
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("regime.invariant_unresolved", {item.kind for item in evaluation.issues})

    def test_exact_realization_passes_only_after_all_boundaries_close(self):
        f = self._fixture()
        receipt = self._admit(f)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.resource_catalog_hash, f["resource_catalog"].catalog_hash)
        residual = parse_residual(residual_from_realization_admission(receipt))
        self.assertEqual(residual.status, "CLOSED")

    def test_missing_machine_operation_rejects_candidate(self):
        f = self._fixture()
        incompatible = MachineFieldV0("machine.test", executable_formats=("tev.binary",))
        problem = RealizationProblemV0(
            f["problem"].transformation_semantic_hash,
            f["problem"].transformation_regime_binding_hash,
            f["problem"].context_hash,
            f["problem"].policy_hash,
            (incompatible.machine_hash,),
        )
        receipt = self._admit(f, problem=problem, machine=incompatible)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("machine.operation_missing", {item.kind for item in receipt.issues})

    def test_unknown_resource_bound_is_proof_required(self):
        f = self._fixture(latency_upper=None)
        receipt = self._admit(f)
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("resource.bound_unknown", {item.kind for item in receipt.issues})

    def test_resource_ceiling_violation_rejects(self):
        f = self._fixture(latency_upper=11)
        receipt = self._admit(f)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("resource.ceiling_exceeded", {item.kind for item in receipt.issues})

    def test_resource_catalog_mismatch_rejects(self):
        f = self._fixture()
        other_catalog = ResourceCatalogV0(
            (ResourceDimensionV0("latency", "cycle", "SUM", "MAX"),)
        )
        receipt = self._admit(f, resource_catalog=other_catalog)
        self.assertEqual(receipt.status, "REJECT")
        kinds = {item.kind for item in receipt.issues}
        self.assertTrue(
            "resource.catalog_policy_mismatch" in kinds
            or "resource.vector_invalid" in kinds
        )

    def test_missing_realization_evidence_remains_open(self):
        f = self._fixture()
        receipt = self._admit(f, evidence=(f["evidence"][1],))
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        kinds = {item.kind for item in receipt.issues}
        self.assertTrue(
            "evidence.reference_missing" in kinds
            or "realization.evidence.required" in kinds
        )

    def test_positive_support_must_be_candidate_bound(self):
        f = self._fixture()
        candidate = RealizationCandidateV0(
            f["candidate"].transformation_semantic_hash,
            f["candidate"].transformation_regime_binding_hash,
            f["candidate"].realization_kind,
            f["candidate"].machine_hash,
            f["candidate"].artifact_hashes,
            f["candidate"].machine_requirement,
            f["candidate"].semantic_relation,
            assumption_hashes=f["candidate"].assumption_hashes,
            predicted_resources=f["candidate"].predicted_resources,
            evidence_hashes=(),
            regime_preservation_claim_hash=f["candidate"].regime_preservation_claim_hash,
        )
        receipt = self._admit(f, candidate=candidate)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("evidence.unbound_support", {item.kind for item in receipt.issues})

    def test_falsified_realization_claim_rejects_even_with_other_good_evidence(self):
        f = self._fixture()
        counterexample = EvidenceItemV0(
            "e.counterexample",
            f["candidate"].semantic_claim_hash,
            h("counterexample-scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample-witness"),
            status="FALSIFIED",
        )
        receipt = self._admit(f, evidence=(*f["evidence"], counterexample))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("realization.evidence.falsified", {item.kind for item in receipt.issues})

    def test_approximation_is_explicit_and_policy_bounded(self):
        contract = ApproximationContractV0(
            h("metric"), h("approx-domain"), Fraction(1, 200), "DETERMINISTIC_BOUND"
        )
        f = self._fixture(relation="APPROXIMATION", approximation=contract)
        self.assertEqual(self._admit(f).status, "PASS")

        bad_contract = ApproximationContractV0(
            h("metric"), h("approx-domain"), Fraction(1, 20), "DETERMINISTIC_BOUND"
        )
        bad = self._fixture(relation="APPROXIMATION", approximation=bad_contract)
        receipt = self._admit(bad)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("approximation.bound_exceeded", {item.kind for item in receipt.issues})

    def test_cost_changes_do_not_change_semantic_or_realization_identity(self):
        low = self._fixture(latency_upper=2)["candidate"]
        high = self._fixture(latency_upper=9)["candidate"]
        self.assertEqual(low.transformation_semantic_hash, high.transformation_semantic_hash)
        self.assertEqual(low.semantic_claim_hash, high.semantic_claim_hash)
        self.assertEqual(low.realization_hash, high.realization_hash)
        self.assertNotEqual(low.candidate_hash, high.candidate_hash)

    def test_pareto_front_uses_only_admitted_candidates(self):
        fast = self._fixture(latency_upper=2)
        slow = self._fixture(latency_upper=8)
        fast_receipt = self._admit(fast)
        slow_receipt = self._admit(slow)
        front = pareto_front(
            ((fast["candidate"], fast_receipt), (slow["candidate"], slow_receipt)),
            dimensions=("latency",),
        )
        self.assertEqual(
            tuple(item.candidate_hash for item in front),
            (fast["candidate"].candidate_hash,),
        )

    def test_semantic_memoization_key_ignores_realization_identity(self):
        key = semantic_memoization_key(
            transformation_semantic_hash=h("t"),
            canonical_input_hash=h("input"),
            semantic_environment_hash=h("environment"),
        )
        self.assertEqual(
            key,
            semantic_memoization_key(
                transformation_semantic_hash=h("t"),
                canonical_input_hash=h("input"),
                semantic_environment_hash=h("environment"),
            ),
        )


if __name__ == "__main__":
    unittest.main()
