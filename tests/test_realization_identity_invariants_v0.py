from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_discovery_realization_v0 import StructuralLawClaimV0
from tev_script.semantic_evidence_v0 import EvidencePolicyV0
from tev_script.semantic_machine_v0 import (
    ExecutableFormatV0,
    MachineCapabilityV0,
    MachineFieldV0,
    MemorySpaceV0,
    NumericModelV0,
)
from tev_script.semantic_regime_v0 import (
    RegimeContractV0,
    RegimePreservationClaimV0,
    TransformationRegimeBindingV0,
    evaluate_regime_preservation,
)
from tev_script.semantic_resource_evidence_v0 import ResourceEstimateClaimV0


def h(label: str) -> str:
    return canonical_hash({"test": label})


class MachineProfileIdentityV0Tests(unittest.TestCase):
    def _profile(
        self,
        machine_id: str,
        *,
        capability_id: str = "opaque.compute",
        numeric_id: str = "exact.int",
        format_id: str = "tev.binary",
        memory_id: str = "memory.local",
        operation_hash: str | None = None,
        numeric_semantics: str | None = None,
        format_semantics: str | None = None,
    ) -> MachineFieldV0:
        numeric = NumericModelV0(
            numeric_id,
            numeric_semantics or h("exact-int"),
            True,
        )
        fmt = ExecutableFormatV0(
            format_id,
            format_semantics or h("binary-abi"),
        )
        capability = MachineCapabilityV0(
            capability_id,
            operation_hash or h("operation"),
            "compute",
            (numeric.numeric_model_hash,),
        )
        return MachineFieldV0(
            machine_id,
            capabilities=(capability,),
            numeric_models=(numeric,),
            memory_spaces=(MemorySpaceV0(memory_id, "byte", 4096),),
            executable_formats=(fmt,),
            topology_hash=h("topology"),
            properties={"parallelism_profile": "bounded"},
        )

    def test_all_local_aliases_are_record_metadata_not_profile_identity(self):
        left = self._profile(
            "machine.alpha",
            capability_id="adapter.compute.a",
            numeric_id="adapter.int.a",
            format_id="adapter.format.a",
            memory_id="adapter.memory.a",
        )
        right = self._profile(
            "machine.beta",
            capability_id="adapter.compute.b",
            numeric_id="adapter.int.b",
            format_id="adapter.format.b",
            memory_id="adapter.memory.b",
        )
        self.assertEqual(left.machine_hash, right.machine_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_numeric_semantics_change_changes_profile(self):
        left = self._profile("machine.a", numeric_semantics=h("numeric-a"))
        right = self._profile("machine.a", numeric_semantics=h("numeric-b"))
        self.assertNotEqual(left.machine_hash, right.machine_hash)

    def test_executable_format_semantics_change_changes_profile(self):
        left = self._profile("machine.a", format_semantics=h("format-a"))
        right = self._profile("machine.a", format_semantics=h("format-b"))
        self.assertNotEqual(left.machine_hash, right.machine_hash)

    def test_operation_semantics_change_changes_profile(self):
        left = self._profile("machine.a", operation_hash=h("operation-a"))
        right = self._profile("machine.a", operation_hash=h("operation-b"))
        self.assertNotEqual(left.machine_hash, right.machine_hash)

    def test_numeric_and_format_records_keep_alias_auditability(self):
        numeric_a = NumericModelV0("int.a", h("int-semantics"), True)
        numeric_b = NumericModelV0("int.b", h("int-semantics"), True)
        self.assertEqual(numeric_a.numeric_model_hash, numeric_b.numeric_model_hash)
        self.assertNotEqual(numeric_a.record_hash, numeric_b.record_hash)

        format_a = ExecutableFormatV0("format.a", h("format-semantics"))
        format_b = ExecutableFormatV0("format.b", h("format-semantics"))
        self.assertEqual(format_a.format_hash, format_b.format_hash)
        self.assertNotEqual(format_a.record_hash, format_b.record_hash)


class StructuralLawIdentityBoundaryV0Tests(unittest.TestCase):
    def _law(self, *, falsifier: str, law_id: str = "law.test") -> StructuralLawClaimV0:
        return StructuralLawClaimV0(
            law_id,
            h("regime"),
            h("transformation"),
            h("boundary"),
            falsifier,
            EvidencePolicyV0(()).policy_hash,
            assumption_hashes=(h("assumption"),),
            formulation_hash=h("formulation"),
            provenance={"source": law_id},
        )

    def test_falsification_protocol_is_epistemic_not_law_identity(self):
        left = self._law(falsifier=h("falsifier-a"), law_id="law.a")
        right = self._law(falsifier=h("falsifier-b"), law_id="law.b")
        self.assertEqual(left.law_semantic_hash, right.law_semantic_hash)
        self.assertNotEqual(left.law_claim_hash, right.law_claim_hash)

    def test_validity_boundary_remains_semantic(self):
        policy = EvidencePolicyV0(()).policy_hash
        left = StructuralLawClaimV0(
            "law.a",
            h("regime"),
            h("transformation"),
            h("boundary-a"),
            h("falsifier"),
            policy,
            assumption_hashes=(h("assumption"),),
        )
        right = StructuralLawClaimV0(
            "law.b",
            h("regime"),
            h("transformation"),
            h("boundary-b"),
            h("falsifier"),
            policy,
            assumption_hashes=(h("assumption"),),
        )
        self.assertNotEqual(left.law_semantic_hash, right.law_semantic_hash)

    def test_assumptions_remain_semantic_to_law(self):
        policy = EvidencePolicyV0(()).policy_hash
        left = StructuralLawClaimV0(
            "law.a",
            h("regime"),
            h("transformation"),
            h("boundary"),
            h("falsifier"),
            policy,
            assumption_hashes=(h("assumption-a"),),
        )
        right = StructuralLawClaimV0(
            "law.b",
            h("regime"),
            h("transformation"),
            h("boundary"),
            h("falsifier"),
            policy,
            assumption_hashes=(h("assumption-b"),),
        )
        self.assertNotEqual(left.law_semantic_hash, right.law_semantic_hash)


class RegimeAssumptionBoundaryV0Tests(unittest.TestCase):
    def test_constitutive_regime_assumption_cannot_be_omitted(self):
        assumption = h("regime-assumption")
        transformation = h("transformation")
        regime = RegimeContractV0(
            "regime.test",
            h("possibility"),
            h("history"),
            assumption_hashes=(assumption,),
        )
        binding = TransformationRegimeBindingV0(
            transformation,
            regime.regime_hash,
            h("scope"),
        )
        claim = RegimePreservationClaimV0(
            h("realization-claim"),
            binding.binding_hash,
            regime.regime_hash,
            "EXACT_EQUIVALENT",
        )
        evaluation = evaluate_regime_preservation(
            regime,
            binding,
            claim,
            transformation_semantic_hash=transformation,
            realization_semantic_claim_hash=h("realization-claim"),
            semantic_relation="EXACT_EQUIVALENT",
        )
        self.assertEqual(evaluation.status, "PROOF_REQUIRED")
        self.assertIn("regime.assumption_unresolved", {issue.kind for issue in evaluation.issues})


class ResourceBoundClaimIdentityV0Tests(unittest.TestCase):
    def _claim(
        self,
        *,
        estimate_kind: str = "ANALYTIC_BOUND",
        estimator: str = "estimator-a",
        assumptions=("assumption",),
        detail=None,
    ) -> ResourceEstimateClaimV0:
        return ResourceEstimateClaimV0(
            h("realization"),
            h("context"),
            h("vector"),
            h("catalog"),
            estimate_kind,
            h(estimator),
            h("scope"),
            assumption_hashes=tuple(h(item) for item in assumptions),
            detail=detail or {},
        )

    def test_estimator_method_and_detail_are_record_not_bound_identity(self):
        analytic = self._claim(
            estimate_kind="ANALYTIC_BOUND",
            estimator="estimator-a",
            detail={"path": "a"},
        )
        empirical = self._claim(
            estimate_kind="EMPIRICAL_ENVELOPE",
            estimator="estimator-b",
            detail={"path": "b"},
        )
        self.assertEqual(analytic.estimate_claim_hash, empirical.estimate_claim_hash)
        self.assertNotEqual(analytic.record_hash, empirical.record_hash)

    def test_resource_claim_assumptions_are_semantic_to_bound_claim(self):
        base = self._claim(assumptions=("assumption",))
        changed = self._claim(assumptions=("different-assumption",))
        self.assertNotEqual(base.estimate_claim_hash, changed.estimate_claim_hash)


if __name__ == "__main__":
    unittest.main()
