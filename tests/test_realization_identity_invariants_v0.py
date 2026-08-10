from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_discovery_realization_v0 import StructuralLawClaimV0
from tev_script.semantic_evidence_v0 import EvidencePolicyV0
from tev_script.semantic_machine_v0 import (
    MachineCapabilityV0,
    MachineFieldV0,
    NumericModelV0,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


class MachineProfileIdentityV0Tests(unittest.TestCase):
    def _profile(
        self,
        machine_id: str,
        *,
        capability_id: str = "opaque.compute",
        operation_hash: str | None = None,
    ):
        numeric = NumericModelV0("exact.int", h("exact-int"), True)
        capability = MachineCapabilityV0(
            capability_id,
            operation_hash or h("operation"),
            "compute",
            ("exact.int",),
        )
        return MachineFieldV0(
            machine_id,
            capabilities=(capability,),
            numeric_models=(numeric,),
            executable_formats=("tev.binary",),
            topology_hash=h("topology"),
            properties={"parallelism_profile": "bounded"},
        )

    def test_machine_record_id_does_not_change_profile_identity(self):
        left = self._profile("machine.alpha")
        right = self._profile("machine.beta")
        self.assertEqual(left.machine_hash, right.machine_hash)
        self.assertEqual(left.machine_profile_hash, right.machine_profile_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_local_capability_alias_does_not_change_profile_identity(self):
        left = self._profile("machine.alpha", capability_id="adapter.compute.a")
        right = self._profile("machine.alpha", capability_id="adapter.compute.b")
        self.assertEqual(left.machine_hash, right.machine_hash)
        self.assertNotEqual(left.record_hash, right.record_hash)

    def test_semantic_operation_change_changes_machine_profile(self):
        left = self._profile("machine.alpha", operation_hash=h("operation-a"))
        right = self._profile("machine.alpha", operation_hash=h("operation-b"))
        self.assertNotEqual(left.machine_hash, right.machine_hash)

    def test_profile_hash_is_order_independent_but_record_is_auditable(self):
        numeric = NumericModelV0("exact.int", h("exact-int"), True)
        a = MachineCapabilityV0("cap.a", h("a"), "compute", ("exact.int",))
        b = MachineCapabilityV0("cap.b", h("b"), "compute", ("exact.int",))
        first = MachineFieldV0(
            "machine.one",
            capabilities=(a, b),
            numeric_models=(numeric,),
            executable_formats=("format.b", "format.a"),
        )
        second = MachineFieldV0(
            "machine.one",
            capabilities=(b, a),
            numeric_models=(numeric,),
            executable_formats=("format.a", "format.b"),
        )
        self.assertEqual(first.machine_hash, second.machine_hash)
        self.assertEqual(first.record_hash, second.record_hash)


class StructuralLawIdentityBoundaryV0Tests(unittest.TestCase):
    def _law(self, *, falsifier: str, law_id: str = "law.test"):
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

    def test_falsification_protocol_does_not_define_law_semantics(self):
        left = self._law(falsifier=h("falsifier-a"), law_id="law.a")
        right = self._law(falsifier=h("falsifier-b"), law_id="law.b")
        self.assertEqual(left.law_semantic_hash, right.law_semantic_hash)
        self.assertNotEqual(left.law_claim_hash, right.law_claim_hash)

    def test_validity_boundary_remains_semantic(self):
        policy = EvidencePolicyV0(()).policy_hash
        left = StructuralLawClaimV0(
            "law.a", h("regime"), h("transformation"), h("boundary-a"),
            h("falsifier"), policy, assumption_hashes=(h("assumption"),)
        )
        right = StructuralLawClaimV0(
            "law.b", h("regime"), h("transformation"), h("boundary-b"),
            h("falsifier"), policy, assumption_hashes=(h("assumption"),)
        )
        self.assertNotEqual(left.law_semantic_hash, right.law_semantic_hash)


if __name__ == "__main__":
    unittest.main()
