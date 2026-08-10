from __future__ import annotations

from fractions import Fraction
import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_artifact_v0 import (
    ArtifactDescriptorV0,
    ArtifactManifestV0,
    ArtifactSemanticsError,
    manifest_from_single_artifact,
)
from tev_script.semantic_evidence_v0 import (
    EvidenceItemV0,
    EvidencePolicyV0,
    EvidenceRequirementV0,
    EvidenceSemanticsError,
    evaluate_evidence,
)
from tev_script.semantic_machine_v0 import (
    ExecutableFormatV0,
    MachineCapabilityV0,
    MachineFieldV0,
    MachineRequirementV0,
    MachineSemanticsError,
    MemorySpaceV0,
    NumericModelV0,
    evaluate_machine_compatibility,
)
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
from tev_script.semantic_resource_evidence_v0 import ResourceEstimateClaimV0
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class ResourceAlgebraV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = ResourceCatalogV0(
            (
                ResourceDimensionV0("energy", "J", "SUM", "SUM"),
                ResourceDimensionV0("latency", "ms", "SUM", "MAX"),
                ResourceDimensionV0("peak_memory", "byte", "MAX", "SUM"),
            )
        )

    def vector(self, bounds, *, complete: bool) -> ResourceVectorV0:
        return ResourceVectorV0(
            tuple(bounds),
            complete=complete,
            catalog_hash=self.catalog.catalog_hash,
        )

    def test_exact_rational_composition_uses_dimension_laws(self):
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
        self.assertEqual(sequential.bound("latency").exact_value, 4)
        self.assertEqual(parallel.bound("latency").exact_value, Fraction(5, 2))
        self.assertEqual(sequential.bound("energy").exact_value, 5)
        self.assertEqual(parallel.bound("energy").exact_value, 5)
        self.assertEqual(sequential.bound("peak_memory").exact_value, 13)
        self.assertEqual(parallel.bound("peak_memory").exact_value, 21)

    def test_unknown_bound_propagates_and_never_becomes_zero(self):
        left = self.vector((ResourceBoundV0.exact("energy", 1),), complete=False)
        right = self.vector((ResourceBoundV0.exact("latency", 2),), complete=False)
        combined = compose_resource_vectors((left, right), self.catalog, mode="SEQUENTIAL")
        self.assertIsNone(combined.bound("latency").upper)
        self.assertIsNone(combined.bound("energy").upper)
        self.assertIsNone(combined.bound("peak_memory").upper)

    def test_empty_composition_is_explicit_zero_identity_for_catalog(self):
        result = compose_resource_vectors((), self.catalog, mode="SEQUENTIAL")
        self.assertTrue(result.complete)
        self.assertEqual(tuple(x.dimension_id for x in result.bounds), self.catalog.dimension_ids)
        self.assertTrue(all(x.exact_value == 0 for x in result.bounds))

    def test_complete_vector_requires_exact_catalog_surface(self):
        vector = self.vector((ResourceBoundV0.exact("energy", 4),), complete=True)
        with self.assertRaises(ResourceAlgebraError):
            vector.validate_against(self.catalog)

    def test_catalog_identity_carries_units_and_semantics(self):
        other = ResourceCatalogV0((ResourceDimensionV0("latency", "cycle", "SUM", "MAX"),))
        vector = ResourceVectorV0(
            (ResourceBoundV0.exact("latency", 1),),
            complete=True,
            catalog_hash=self.catalog.catalog_hash,
        )
        with self.assertRaises(ResourceAlgebraError):
            vector.validate_against(other)

    def test_ceiling_distinguishes_unknown_from_exceeded(self):
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


class MachineSemanticIdentityV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.numeric = NumericModelV0("adapter.int", h("exact-int-semantics"), True)
        self.format = ExecutableFormatV0("adapter.exec", h("exec-abi-semantics"))

    def machine(self, *, machine_id="machine.a", capability_id="cap.a", numeric=None, fmt=None):
        numeric = numeric or self.numeric
        fmt = fmt or self.format
        capability = MachineCapabilityV0(
            capability_id,
            h("operation"),
            "compute",
            (numeric.numeric_model_hash,),
        )
        return MachineFieldV0(
            machine_id,
            capabilities=(capability,),
            numeric_models=(numeric,),
            memory_spaces=(MemorySpaceV0("mem.local", "byte", 1024),),
            executable_formats=(fmt,),
            topology_hash=h("topology"),
        )

    def test_machine_and_capability_aliases_do_not_change_profile_identity(self):
        left = self.machine(machine_id="machine.a", capability_id="adapter.op.a")
        right = self.machine(machine_id="machine.b", capability_id="adapter.op.b")
        self.assertEqual(left.machine_hash, right.machine_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_numeric_and_format_aliases_do_not_change_profile_identity(self):
        numeric_alias = NumericModelV0("another.int.name", self.numeric.semantics_hash, True)
        format_alias = ExecutableFormatV0("another.exec.name", self.format.semantics_hash)
        left = self.machine()
        right = self.machine(numeric=numeric_alias, fmt=format_alias)
        self.assertEqual(left.machine_hash, right.machine_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_numeric_semantics_change_changes_machine_profile(self):
        changed = NumericModelV0("adapter.int", h("different-int-semantics"), True)
        self.assertNotEqual(self.machine().machine_hash, self.machine(numeric=changed).machine_hash)

    def test_format_semantics_change_changes_machine_profile(self):
        changed = ExecutableFormatV0("adapter.exec", h("different-exec-abi"))
        self.assertNotEqual(self.machine().machine_hash, self.machine(fmt=changed).machine_hash)

    def test_capability_cannot_reference_undefined_numeric_semantics(self):
        missing = h("missing-numeric-profile")
        with self.assertRaises(MachineSemanticsError):
            MachineFieldV0(
                "machine.bad",
                capabilities=(MachineCapabilityV0("op", h("op"), "compute", (missing,)),),
            )

    def test_compatibility_is_semantic_hash_based(self):
        machine = self.machine()
        requirement = MachineRequirementV0(
            (h("operation"),),
            (self.numeric.numeric_model_hash,),
            (self.format.format_hash,),
        )
        self.assertTrue(evaluate_machine_compatibility(machine, requirement).compatible)
        missing = MachineRequirementV0((h("missing-operation"),), (), ())
        evaluation = evaluate_machine_compatibility(machine, missing)
        self.assertFalse(evaluation.compatible)
        self.assertEqual(evaluation.missing_capability_semantic_hashes, (h("missing-operation"),))


class ArtifactManifestV0Tests(unittest.TestCase):
    def test_manifest_derives_machine_requirement_from_artifact_semantics(self):
        numeric = NumericModelV0("int.alias", h("int-semantics"), True)
        fmt = ExecutableFormatV0("exec.alias", h("exec-semantics"))
        manifest = manifest_from_single_artifact(
            role_id="entry",
            format_hash=fmt.format_hash,
            content_hash=h("binary-bytes"),
            interface_hash=h("interface"),
            required_machine_capability_semantic_hashes=(h("op"),),
            required_numeric_model_hashes=(numeric.numeric_model_hash,),
        )
        requirement = manifest.machine_requirement
        self.assertEqual(requirement.required_capability_semantic_hashes, (h("op"),))
        self.assertEqual(requirement.required_numeric_model_hashes, (numeric.numeric_model_hash,))
        self.assertEqual(requirement.required_executable_format_hashes, (fmt.format_hash,))

    def test_manifest_requires_closed_dependency_graph(self):
        dependency = ArtifactDescriptorV0(
            role_id="library",
            format_hash=h("format"),
            content_hash=h("library"),
        )
        entry = ArtifactDescriptorV0(
            role_id="entry",
            format_hash=h("format"),
            content_hash=h("entry"),
            interface_hash=h("interface"),
            entrypoint=True,
            dependency_descriptor_hashes=(dependency.descriptor_hash,),
        )
        self.assertEqual(len(ArtifactManifestV0((entry, dependency)).descriptors), 2)
        outside = ArtifactDescriptorV0(
            role_id="bad.entry",
            format_hash=h("format"),
            content_hash=h("bad-entry"),
            interface_hash=h("interface"),
            entrypoint=True,
            dependency_descriptor_hashes=(h("outside-descriptor"),),
        )
        with self.assertRaises(ArtifactSemanticsError):
            ArtifactManifestV0((outside,))


class EvidenceV0Tests(unittest.TestCase):
    def test_policy_checks_method_scope_verifier_and_status(self):
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
            witness_hash=h("revoked"),
            status="REVOKED",
        )
        self.assertIn("evidence.inactive", {x.kind for x in evaluate_evidence(claim, policy, (revoked,)).issues})

    def test_proof_like_evidence_requires_real_witness_and_verifier(self):
        with self.assertRaises(EvidenceSemanticsError):
            EvidenceItemV0("e.bad", h("claim"), h("scope"), "PROOF")
        with self.assertRaises(EvidenceSemanticsError):
            EvidenceItemV0(
                "e.bad2",
                h("claim"),
                h("scope"),
                "TRANSLATION_VALIDATION",
                witness_hash=h("witness"),
            )

    def test_falsification_is_never_silently_ignored(self):
        claim = h("claim")
        falsified = EvidenceItemV0(
            "e.false",
            claim,
            h("scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        self.assertTrue(evaluate_evidence(claim, EvidencePolicyV0(()), (falsified,)).falsified)


class RegimeAndRealizationAdmissionV0Tests(unittest.TestCase):
    def _fixture(
        self,
        *,
        latency_upper=5,
        relation="EXACT_EQUIVALENT",
        approximation=None,
        resource_assumptions=None,
    ):
        transformation = h("transformation")
        scope = h("semantic-scope")
        context = h("context")
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
        resource_scope = h("resource-scope")
        resource_evidence_policy = EvidencePolicyV0(
            (
                EvidenceRequirementV0(
                    "resource-bound",
                    ("PROOF", "EXHAUSTIVE"),
                    scope_hash=resource_scope,
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
            resource_evidence_policy.policy_hash,
            resource_catalog.catalog_hash,
            accepted_assumption_hashes=(assumption,),
            resource_ceilings=(
                ResourceCeilingV0("latency", 10, resource_catalog.catalog_hash),
            ),
            approximation_policy=approximation_policy,
        )

        numeric = NumericModelV0("adapter.int", h("int-semantics"), True)
        fmt = ExecutableFormatV0("adapter.exec", h("exec-semantics"))
        operation_hash = h("machine-operation")
        capability = MachineCapabilityV0(
            "adapter.compute",
            operation_hash,
            "compute",
            (numeric.numeric_model_hash,),
        )
        machine = MachineFieldV0(
            "machine.test",
            capabilities=(capability,),
            numeric_models=(numeric,),
            executable_formats=(fmt,),
        )
        manifest = manifest_from_single_artifact(
            role_id="entry",
            format_hash=fmt.format_hash,
            content_hash=h("artifact-bytes"),
            interface_hash=h("interface"),
            required_machine_capability_semantic_hashes=(operation_hash,),
            required_numeric_model_hashes=(numeric.numeric_model_hash,),
        )
        requirement = manifest.machine_requirement
        problem = RealizationProblemV0(
            transformation,
            binding.binding_hash,
            context,
            policy.policy_hash,
            (machine.machine_hash,),
        )
        claim_hash = realization_semantic_claim_hash(
            transformation_semantic_hash=transformation,
            transformation_regime_binding_hash=binding.binding_hash,
            machine_hash=machine.machine_hash,
            artifact_manifest_hash=manifest.manifest_hash,
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
            artifact_manifest_hash=manifest.manifest_hash,
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
            assumption_hashes=(assumption,) if resource_assumptions is None else tuple(resource_assumptions),
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
            "e.semantic",
            claim_hash,
            scope,
            "TRANSLATION_VALIDATION",
            verifier_hash=verifier,
            witness_hash=h("translation-witness"),
            assumption_hashes=(assumption,),
        )
        regime_evidence = EvidenceItemV0(
            "e.regime",
            preservation.preservation_claim_hash,
            scope,
            "PROOF",
            verifier_hash=verifier,
            witness_hash=h("regime-witness"),
            assumption_hashes=(assumption,),
        )
        resource_evidence = EvidenceItemV0(
            "e.resource",
            estimate.estimate_claim_hash,
            resource_scope,
            "PROOF",
            verifier_hash=verifier,
            witness_hash=h("resource-witness"),
            assumption_hashes=(assumption,),
        )
        candidate = RealizationCandidateV0(
            transformation,
            binding.binding_hash,
            "tev.realization.test",
            machine.machine_hash,
            manifest.manifest_hash,
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
        self.assertEqual(candidate.semantic_claim_hash, claim_hash)
        self.assertEqual(candidate.realization_hash, realization_hash)
        return {
            "problem": problem,
            "candidate": candidate,
            "artifact_manifest": manifest,
            "machine": machine,
            "policy": policy,
            "resource_catalog": resource_catalog,
            "resource_estimate_claim": estimate,
            "regime": regime,
            "binding": binding,
            "preservation": preservation,
            "realization_evidence_policy": realization_evidence_policy,
            "regime_evidence_policy": regime_evidence_policy,
            "resource_evidence_policy": resource_evidence_policy,
            "evidence": (semantic_evidence, regime_evidence, resource_evidence),
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

    def test_regime_omitted_invariant_is_proof_required(self):
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
            f["regime"],
            f["binding"],
            claim,
            transformation_semantic_hash=f["problem"].transformation_semantic_hash,
            realization_semantic_claim_hash=f["candidate"].semantic_claim_hash,
            semantic_relation="EXACT_EQUIVALENT",
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("regime.invariant_unresolved", {x.kind for x in evaluation.issues})

    def test_regime_omitted_constitutive_assumption_is_proof_required(self):
        f = self._fixture()
        claim = RegimePreservationClaimV0(
            f["candidate"].semantic_claim_hash,
            f["binding"].binding_hash,
            f["regime"].regime_hash,
            "EXACT_EQUIVALENT",
            preserved_constraint_hashes=f["regime"].constraint_semantic_hashes,
            preserved_invariant_hashes=f["regime"].invariant_claim_hashes,
            equivalence_preservation="PRESERVED",
            assumption_hashes=(),
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
        self.assertIn("regime.assumption_unresolved", {x.kind for x in evaluation.issues})

    def test_exact_realization_passes_only_after_every_boundary_closes(self):
        f = self._fixture()
        receipt = self._admit(f)
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.artifact_manifest_hash, f["artifact_manifest"].manifest_hash)
        self.assertEqual(parse_residual(residual_from_realization_admission(receipt)).status, "CLOSED")

    def test_artifact_manifest_mismatch_rejects(self):
        f = self._fixture()
        other = manifest_from_single_artifact(
            role_id="entry",
            format_hash=f["machine"].executable_formats[0].format_hash,
            content_hash=h("different-bytes"),
            interface_hash=h("interface"),
            required_machine_capability_semantic_hashes=f["candidate"].machine_requirement.required_capability_semantic_hashes,
            required_numeric_model_hashes=f["candidate"].machine_requirement.required_numeric_model_hashes,
        )
        receipt = self._admit(f, artifact_manifest=other)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("artifact.manifest_mismatch", {x.kind for x in receipt.issues})

    def test_candidate_cannot_hide_artifact_machine_dependency(self):
        f = self._fixture()
        base = f["candidate"]
        hidden = RealizationCandidateV0(
            base.transformation_semantic_hash,
            base.transformation_regime_binding_hash,
            base.realization_kind,
            base.machine_hash,
            base.artifact_manifest_hash,
            MachineRequirementV0(),
            base.semantic_relation,
            assumption_hashes=base.assumption_hashes,
            predicted_resources=base.predicted_resources,
            resource_estimate_claim_hash=base.resource_estimate_claim_hash,
            evidence_hashes=base.evidence_hashes,
            regime_preservation_claim_hash=base.regime_preservation_claim_hash,
        )
        receipt = self._admit(f, candidate=hidden)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("artifact.machine_requirement_mismatch", {x.kind for x in receipt.issues})

    def test_missing_machine_operation_rejects(self):
        f = self._fixture()
        incompatible = MachineFieldV0(
            "machine.bad",
            numeric_models=f["machine"].numeric_models,
            executable_formats=f["machine"].executable_formats,
        )
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

    def test_unknown_resource_bound_remains_open(self):
        receipt = self._admit(self._fixture(latency_upper=None))
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("resource.bound_unknown", {x.kind for x in receipt.issues})

    def test_resource_ceiling_violation_rejects(self):
        receipt = self._admit(self._fixture(latency_upper=11))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("resource.ceiling_exceeded", {x.kind for x in receipt.issues})

    def test_resource_estimate_assumption_requires_policy_acceptance(self):
        receipt = self._admit(self._fixture(resource_assumptions=(h("zero-contention"),)))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("resource.estimate_assumption_not_accepted", {x.kind for x in receipt.issues})

    def test_missing_resource_evidence_is_proof_required(self):
        f = self._fixture()
        receipt = self._admit(f, evidence=f["evidence"][:2])
        self.assertEqual(receipt.status, "PROOF_REQUIRED")
        self.assertIn("resource.evidence.required", {x.kind for x in receipt.issues})

    def test_falsified_semantic_claim_rejects_even_with_positive_evidence(self):
        f = self._fixture()
        counterexample = EvidenceItemV0(
            "e.counterexample",
            f["candidate"].semantic_claim_hash,
            h("counterexample-scope"),
            "EMPIRICAL_OBSERVATION",
            witness_hash=h("counterexample"),
            status="FALSIFIED",
        )
        receipt = self._admit(f, evidence=(*f["evidence"], counterexample))
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("realization.evidence.falsified", {x.kind for x in receipt.issues})

    def test_approximation_is_explicit_and_policy_bounded(self):
        good = ApproximationContractV0(
            h("metric"), h("approx-domain"), Fraction(1, 200), "DETERMINISTIC_BOUND"
        )
        self.assertEqual(self._admit(self._fixture(relation="APPROXIMATION", approximation=good)).status, "PASS")
        bad = ApproximationContractV0(
            h("metric"), h("approx-domain"), Fraction(1, 20), "DETERMINISTIC_BOUND"
        )
        receipt = self._admit(self._fixture(relation="APPROXIMATION", approximation=bad))
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
            base.artifact_manifest_hash,
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
