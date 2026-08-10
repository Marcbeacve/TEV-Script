from __future__ import annotations

from fractions import Fraction
import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
    EvidenceSemanticsError,
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
    realization_identity_hash,
    realization_semantic_claim_hash,
    residual_from_realization_admission,
    semantic_memoization_key,
)
from tev_script.semantic_resource_evidence_v0 import ResourceEstimateClaimV0
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
            tuple(bounds), complete=complete, catalog_hash=self.catalog.catalog_hash
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

    def test_empty_composition_is_explicit_zero_identity_over_catalog(self):
        result = compose_resource_vectors((), self.catalog, mode="SEQUENTIAL")
        self.assertTrue(result.complete)
        self.assertEqual(tuple(x.dimension_id for x in result.bounds), self.catalog.dimension_ids)
        self.assertTrue(all(x.exact_value == 0 for x in result.bounds))

    def test_complete_vector_must_cover_exact_catalog(self):
        vector = self.vector((ResourceBoundV0.exact("energy", 4),), complete=True)
        with self.assertRaises(ResourceAlgebraError):
            vector.validate_against(self.catalog)

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
            {(x.kind, x.dimension_id) for x in issues},
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
                        "opaque.compute", h("compute"), "compute", ("missing.numeric",)
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
        claim, scope, verifier = h("claim"), h("scope"), h("verifier")
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
        self.assertEqual({x.kind for x in evaluation.issues}, {"evidence.inactive"})

    def test_proof_like_evidence_requires_witness_and_verifier(self):
        with self.assertRaises(EvidenceSemanticsError):
            EvidenceItemV0("e.bad", h("claim"), h("scope"), "PROOF")
        with self.assertRaises(EvidenceSemanticsError):
            EvidenceItemV0(
                "e.bad2", h("claim"), h("scope"), "TRANSLATION_VALIDATION",
                witness_hash=h("witness"),
            )

    def test_falsified_evidence_on_exact_claim_is_never_silently_ignored(self):
        claim = h("claim")
        falsified = EvidenceItemV0(
            "e.false",
            claim,
            h("scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        evaluation = evaluate_evidence(claim, EvidencePolicyV0(()), (falsified,))
        self.assertTrue(evaluation.falsified)

    def test_existing_proof_boundary_projects_without_redefining_it(self):
        witness = ProofBoundaryWitnessV0(h("proof"), h("verifier"), h("scope"), "proved")
        projected = evidence_from_proof_boundary(
            witness, evidence_id="proof.projected", claim_hash=h("claim")
        )
        self.assertEqual(projected.method, "PROOF")
        self.assertEqual(projected.witness_hash, witness.witness_hash)


class RegimeIdentityV0Tests(unittest.TestCase):
    def _regime(self, regime_id="regime.a", constraint_id="c.a", provenance=None):
        return RegimeContractV0(
            regime_id,
            h("possibility"),
            h("history"),
            constraints=(
                RegimeConstraintV0(constraint_id, "safety", h("constraint"), h("scope")),
            ),
            causal_structure_hash=h("causal"),
            equivalence_relation_hash=h("equivalence"),
            observable_profile_hash=h("observables"),
            invariant_claim_hashes=(h("invariant"),),
            assumption_hashes=(h("assumption"),),
            provenance=provenance or {},
        )

    def test_regime_names_and_provenance_do_not_define_semantic_identity(self):
        left = self._regime("regime.alpha", "constraint.alpha", {"source": "a"})
        right = self._regime("regime.beta", "constraint.beta", {"source": "b"})
        self.assertEqual(left.regime_hash, right.regime_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)
        self.assertEqual(
            left.constraints[0].constraint_semantic_hash,
            right.constraints[0].constraint_semantic_hash,
        )

    def test_structural_regime_change_changes_semantic_identity(self):
        base = self._regime()
        changed = RegimeContractV0(
            "regime.other",
            h("different-possibility"),
            h("history"),
            constraints=base.constraints,
            causal_structure_hash=base.causal_structure_hash,
            equivalence_relation_hash=base.equivalence_relation_hash,
            observable_profile_hash=base.observable_profile_hash,
            invariant_claim_hashes=base.invariant_claim_hashes,
            assumption_hashes=base.assumption_hashes,
        )
        self.assertNotEqual(base.regime_hash, changed.regime_hash)

    def test_binding_id_is_record_metadata_not_semantic_binding_identity(self):
        regime = self._regime()
        a = TransformationRegimeBindingV0(h("t"), regime.regime_hash, h("scope"), "a")
        b = TransformationRegimeBindingV0(h("t"), regime.regime_hash, h("scope"), "b")
        self.assertEqual(a.binding_hash, b.binding_hash)
        self.assertNotEqual(a.record_hash, b.record_hash)

    def test_preservation_detail_is_audit_metadata(self):
        regime = self._regime()
        binding = TransformationRegimeBindingV0(h("t"), regime.regime_hash, h("scope"))
        kwargs = dict(
            realization_semantic_claim_hash=h("realization-claim"),
            transformation_regime_binding_hash=binding.binding_hash,
            regime_hash=regime.regime_hash,
            semantic_relation="EXACT_EQUIVALENT",
            preserved_constraint_hashes=regime.constraint_semantic_hashes,
            preserved_invariant_hashes=regime.invariant_claim_hashes,
            causal_preservation="PRESERVED",
            equivalence_preservation="PRESERVED",
            assumption_hashes=regime.assumption_hashes,
        )
        a = RegimePreservationClaimV0(**kwargs, detail={"tool": "a"})
        b = RegimePreservationClaimV0(**kwargs, detail={"tool": "b"})
        self.assertEqual(a.preservation_claim_hash, b.preservation_claim_hash)
        self.assertNotEqual(a.record_hash, b.record_hash)


class RegimeAndRealizationAdmissionV0Tests(unittest.TestCase):
    def _fixture(
        self,
        *,
        latency_upper=5,
        relation="EXACT_EQUIVALENT",
        approximation=None,
        resource_assumptions=None,
        resource_detail=None,
    ):
        transformation, scope, context = h("transformation"), h("semantic-scope"), h("context")
        assumption = h("assumption")
        regime = RegimeContractV0(
            "regime.test",
            h("possibility-space"),
            h("history-space"),
            constraints=(RegimeConstraintV0("c.safe", "safety", h("constraint"), scope),),
            equivalence_relation_hash=h("regime-equivalence"),
            observable_profile_hash=h("observables"),
            invariant_claim_hashes=(h("invariant"),),
            assumption_hashes=(assumption,),
        )
        binding = TransformationRegimeBindingV0(transformation, regime.regime_hash, scope)
        verifier = h("verifier")
        realization_policy = EvidencePolicyV0(
            (EvidenceRequirementV0(
                "semantic-preservation", ("TRANSLATION_VALIDATION",),
                scope_hash=scope, trusted_verifier_hashes=(verifier,),
            ),)
        )
        regime_policy = EvidencePolicyV0(
            (EvidenceRequirementV0(
                "regime-preservation", ("PROOF",),
                scope_hash=scope, trusted_verifier_hashes=(verifier,),
            ),)
        )
        resource_scope = h("resource-scope")
        resource_policy = EvidencePolicyV0(
            (EvidenceRequirementV0(
                "resource-bound", ("PROOF", "EXHAUSTIVE"),
                scope_hash=resource_scope, trusted_verifier_hashes=(verifier,),
            ),)
        )
        resource_catalog = ResourceCatalogV0(
            (ResourceDimensionV0("latency", "ms", "SUM", "MAX"),)
        )
        approximation_policy = None
        if relation == "APPROXIMATION":
            approximation_policy = ApproximationPolicyV0(
                h("metric"), h("approx-domain"), Fraction(1, 100),
                ("DETERMINISTIC_BOUND",),
            )
        policy = RealizationPolicyV0(
            (relation,), realization_policy.policy_hash, regime_policy.policy_hash,
            resource_policy.policy_hash, resource_catalog.catalog_hash,
            accepted_assumption_hashes=(assumption,),
            resource_ceilings=(ResourceCeilingV0(
                "latency", 10, resource_catalog.catalog_hash
            ),),
            approximation_policy=approximation_policy,
        )
        operation_hash = h("machine-operation")
        machine = MachineFieldV0(
            "machine.test",
            capabilities=(MachineCapabilityV0("opaque.compute", operation_hash, "compute"),),
            executable_formats=("tev.binary",),
        )
        requirement = MachineRequirementV0((operation_hash,), (), ("tev.binary",))
        artifact_hash = h("artifact")
        problem = RealizationProblemV0(
            transformation, binding.binding_hash, context, policy.policy_hash,
            (machine.machine_hash,),
        )
        claim_hash = realization_semantic_claim_hash(
            transformation_semantic_hash=transformation,
            transformation_regime_binding_hash=binding.binding_hash,
            machine_hash=machine.machine_hash,
            artifact_hashes=(artifact_hash,),
            machine_requirement=requirement,
            semantic_relation=relation,
            approximation_contract=approximation,
            assumption_hashes=(assumption,),
        )
        realization_hash = realization_identity_hash(
            realization_kind="tev.realization.test",
            transformation_semantic_hash=transformation,
            transformation_regime_binding_hash=binding.binding_hash,
            machine_hash=machine.machine_hash,
            artifact_hashes=(artifact_hash,),
            machine_requirement=requirement,
            semantic_relation=relation,
            approximation_contract=approximation,
            assumption_hashes=(assumption,),
        )
        predicted = ResourceVectorV0(
            (ResourceBoundV0("latency", 1, latency_upper),),
            complete=True,
            catalog_hash=resource_catalog.catalog_hash,
        )
        estimate = ResourceEstimateClaimV0(
            realization_hash,
            context,
            predicted.vector_hash,
            resource_catalog.catalog_hash,
            "ANALYTIC_BOUND",
            h("resource-estimator"),
            resource_scope,
            assumption_hashes=(assumption,) if resource_assumptions is None else resource_assumptions,
            detail=resource_detail,
        )
        preservation = RegimePreservationClaimV0(
            claim_hash,
            binding.binding_hash,
            regime.regime_hash,
            relation,
            preserved_constraint_hashes=regime.constraint_semantic_hashes,
            preserved_invariant_hashes=regime.invariant_claim_hashes,
            equivalence_preservation="PRESERVED",
            assumption_hashes=(assumption,),
        )
        semantic_evidence = EvidenceItemV0(
            "e.semantic", claim_hash, scope, "TRANSLATION_VALIDATION",
            verifier_hash=verifier, witness_hash=h("translation-witness"),
            assumption_hashes=(assumption,),
        )
        regime_evidence = EvidenceItemV0(
            "e.regime", preservation.preservation_claim_hash, scope, "PROOF",
            verifier_hash=verifier, witness_hash=h("regime-witness"),
            assumption_hashes=(assumption,),
        )
        resource_evidence = EvidenceItemV0(
            "e.resource", estimate.estimate_claim_hash, resource_scope, "PROOF",
            verifier_hash=verifier, witness_hash=h("resource-bound-witness"),
            assumption_hashes=(assumption,),
        )
        candidate = RealizationCandidateV0(
            transformation,
            binding.binding_hash,
            "tev.realization.test",
            machine.machine_hash,
            (artifact_hash,),
            requirement,
            relation,
            approximation_contract=approximation,
            assumption_hashes=(assumption,),
            predicted_resources=predicted,
            resource_estimate_claim_hash=estimate.estimate_claim_hash,
            evidence_hashes=(
                semantic_evidence.evidence_hash,
                regime_evidence.evidence_hash,
                resource_evidence.evidence_hash,
            ),
            regime_preservation_claim_hash=preservation.preservation_claim_hash,
        )
        return {
            "problem": problem,
            "candidate": candidate,
            "machine": machine,
            "policy": policy,
            "resource_catalog": resource_catalog,
            "resource_estimate_claim": estimate,
            "regime": regime,
            "binding": binding,
            "preservation": preservation,
            "realization_evidence_policy": realization_policy,
            "regime_evidence_policy": regime_policy,
            "resource_evidence_policy": resource_policy,
            "evidence": (semantic_evidence, regime_evidence, resource_evidence),
        }

    def _admit(self, fixture, **overrides):
        args = dict(fixture)
        args.update(overrides)
        evidence = args.pop("evidence")
        preservation = args.pop("preservation")
        return admit_realization(
            args.pop("problem"), args.pop("candidate"),
            preservation_claim=preservation, evidence=evidence, **args
        )

    def test_regime_unresolved_invariant_is_proof_required_not_pass(self):
        f = self._fixture()
        claim = RegimePreservationClaimV0(
            f["candidate"].semantic_claim_hash,
            f["binding"].binding_hash,
            f["regime"].regime_hash,
            "EXACT_EQUIVALENT",
            preserved_constraint_hashes=f["regime"].constraint_semantic_hashes,
            equivalence_preservation="PRESERVED",
            assumption_hashes=f["regime"].assumption_hashes,
        )
        evaluation = evaluate_regime_preservation(
            f["regime"], f["binding"], claim,
            transformation_semantic_hash=f["problem"].transformation_semantic_hash,
            realization_semantic_claim_hash=f["candidate"].semantic_claim_hash,
            semantic_relation="EXACT_EQUIVALENT",
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("regime.invariant_unresolved", {x.kind for x in evaluation.issues})

    def test_exact_realization_passes_only_after_all_boundaries_close(self):
        f = self._fixture()
        receipt = self._admit(f)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.regime_hash, f["regime"].regime_hash)
        self.assertEqual(receipt.resource_catalog_hash, f["resource_catalog"].catalog_hash)
        self.assertEqual(
            parse_residual(residual_from_realization_admission(receipt)).status,
            "CLOSED",
        )

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
        self.assertIn("machine.operation_missing", {x.kind for x in receipt.issues})

    def test_unknown_resource_bound_is_proof_required(self):
        receipt = self._admit(self._fixture(latency_upper=None))
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("resource.bound_unknown", {x.kind for x in receipt.issues})

    def test_resource_ceiling_violation_rejects(self):
        receipt = self._admit(self._fixture(latency_upper=11))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("resource.ceiling_exceeded", {x.kind for x in receipt.issues})

    def test_resource_bound_without_accepted_evidence_remains_open(self):
        f = self._fixture()
        receipt = self._admit(f, evidence=f["evidence"][:2])
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("resource.evidence.required", {x.kind for x in receipt.issues})

    def test_resource_estimate_assumption_requires_policy_acceptance(self):
        f = self._fixture(resource_assumptions=(h("zero-contention"),))
        receipt = self._admit(f)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn(
            "resource.estimate_assumption_not_accepted",
            {x.kind for x in receipt.issues},
        )

    def test_evidence_assumption_requires_policy_acceptance(self):
        f = self._fixture()
        bad = EvidenceItemV0(
            "e.semantic.bad-assumption",
            f["candidate"].semantic_claim_hash,
            h("semantic-scope"),
            "TRANSLATION_VALIDATION",
            verifier_hash=h("verifier"),
            witness_hash=h("translation-witness-2"),
            assumption_hashes=(h("hidden-assumption"),),
        )
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
            resource_estimate_claim_hash=f["candidate"].resource_estimate_claim_hash,
            evidence_hashes=(
                bad.evidence_hash,
                f["evidence"][1].evidence_hash,
                f["evidence"][2].evidence_hash,
            ),
            regime_preservation_claim_hash=f["candidate"].regime_preservation_claim_hash,
        )
        receipt = self._admit(
            f, candidate=candidate, evidence=(bad, f["evidence"][1], f["evidence"][2])
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("evidence.assumption_not_accepted", {x.kind for x in receipt.issues})

    def test_resource_estimate_detail_is_not_claim_identity(self):
        f = self._fixture(resource_detail={"note": "a"})
        base = f["resource_estimate_claim"]
        other = ResourceEstimateClaimV0(
            base.realization_hash,
            base.execution_context_hash,
            base.resource_vector_hash,
            base.resource_catalog_hash,
            base.estimate_kind,
            base.estimator_hash,
            base.scope_hash,
            assumption_hashes=base.assumption_hashes,
            detail={"note": "b"},
        )
        self.assertEqual(base.estimate_claim_hash, other.estimate_claim_hash)
        self.assertNotEqual(base.record_hash, other.record_hash)

    def test_resource_estimate_must_bind_realization_context_and_vector(self):
        f = self._fixture()
        base = f["resource_estimate_claim"]
        bad = ResourceEstimateClaimV0(
            f["candidate"].realization_hash,
            h("wrong-context"),
            f["candidate"].predicted_resources.vector_hash,
            f["resource_catalog"].catalog_hash,
            base.estimate_kind,
            base.estimator_hash,
            base.scope_hash,
            assumption_hashes=base.assumption_hashes,
        )
        receipt = self._admit(f, resource_estimate_claim=bad)
        self.assertEqual(receipt.status, "REJECT")

    def test_resource_catalog_mismatch_rejects(self):
        f = self._fixture()
        other = ResourceCatalogV0((ResourceDimensionV0("latency", "cycle", "SUM", "MAX"),))
        receipt = self._admit(f, resource_catalog=other)
        self.assertEqual(receipt.status, "REJECT")

    def test_missing_realization_evidence_remains_open(self):
        f = self._fixture()
        receipt = self._admit(f, evidence=f["evidence"][1:])
        self.assertEqual(receipt.status, "PROOF_REQUIRED")

    def test_positive_support_must_be_candidate_bound(self):
        f = self._fixture()
        base = f["candidate"]
        candidate = RealizationCandidateV0(
            base.transformation_semantic_hash,
            base.transformation_regime_binding_hash,
            base.realization_kind,
            base.machine_hash,
            base.artifact_hashes,
            base.machine_requirement,
            base.semantic_relation,
            assumption_hashes=base.assumption_hashes,
            predicted_resources=base.predicted_resources,
            resource_estimate_claim_hash=base.resource_estimate_claim_hash,
            evidence_hashes=(),
            regime_preservation_claim_hash=base.regime_preservation_claim_hash,
        )
        receipt = self._admit(f, candidate=candidate)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("evidence.unbound_support", {x.kind for x in receipt.issues})

    def test_falsified_realization_claim_rejects_even_with_good_evidence(self):
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
        self.assertIn("realization.evidence.falsified", {x.kind for x in receipt.issues})

    def test_approximation_is_explicit_and_policy_bounded(self):
        contract = ApproximationContractV0(
            h("metric"), h("approx-domain"), Fraction(1, 200), "DETERMINISTIC_BOUND"
        )
        self.assertEqual(
            self._admit(self._fixture(relation="APPROXIMATION", approximation=contract)).status,
            "PASS",
        )
        bad_contract = ApproximationContractV0(
            h("metric"), h("approx-domain"), Fraction(1, 20), "DETERMINISTIC_BOUND"
        )
        receipt = self._admit(self._fixture(relation="APPROXIMATION", approximation=bad_contract))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("approximation.bound_exceeded", {x.kind for x in receipt.issues})

    def test_cost_changes_do_not_change_semantic_or_realization_identity(self):
        low = self._fixture(latency_upper=2)["candidate"]
        high = self._fixture(latency_upper=9)["candidate"]
        self.assertEqual(low.semantic_claim_hash, high.semantic_claim_hash)
        self.assertEqual(low.realization_hash, high.realization_hash)
        self.assertNotEqual(low.resource_estimate_claim_hash, high.resource_estimate_claim_hash)
        self.assertNotEqual(low.candidate_hash, high.candidate_hash)

    def test_provenance_changes_candidate_not_realization_identity(self):
        f = self._fixture()
        base = f["candidate"]
        changed = RealizationCandidateV0(
            base.transformation_semantic_hash,
            base.transformation_regime_binding_hash,
            base.realization_kind,
            base.machine_hash,
            base.artifact_hashes,
            base.machine_requirement,
            base.semantic_relation,
            assumption_hashes=base.assumption_hashes,
            provenance_hashes=(h("compiler-provenance"),),
            predicted_resources=base.predicted_resources,
            resource_estimate_claim_hash=base.resource_estimate_claim_hash,
            evidence_hashes=base.evidence_hashes,
            regime_preservation_claim_hash=base.regime_preservation_claim_hash,
        )
        self.assertEqual(base.realization_hash, changed.realization_hash)
        self.assertEqual(base.semantic_claim_hash, changed.semantic_claim_hash)
        self.assertNotEqual(base.candidate_hash, changed.candidate_hash)

    def test_pareto_front_uses_only_admitted_candidates(self):
        fast, slow = self._fixture(latency_upper=2), self._fixture(latency_upper=8)
        front = pareto_front(
            (
                (fast["candidate"], self._admit(fast)),
                (slow["candidate"], self._admit(slow)),
            ),
            dimensions=("latency",),
        )
        self.assertEqual(tuple(x.candidate_hash for x in front), (fast["candidate"].candidate_hash,))

    def test_semantic_memoization_key_is_realization_independent(self):
        kwargs = dict(
            transformation_semantic_hash=h("t"),
            canonical_input_hash=h("input"),
            semantic_environment_hash=h("environment"),
        )
        self.assertEqual(semantic_memoization_key(**kwargs), semantic_memoization_key(**kwargs))


if __name__ == "__main__":
    unittest.main()
