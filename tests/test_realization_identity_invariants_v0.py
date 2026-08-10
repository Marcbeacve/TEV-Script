from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.semantic_machine_v0 import (
    MachineCapabilityV0,
    MachineFieldV0,
    NumericModelV0,
)


def h(label: str) -> str:
    return canonical_hash({"test": label})


class MachineProfileIdentityV0Tests(unittest.TestCase):
    def _profile(self, machine_id: str, *, operation_hash: str | None = None):
        numeric = NumericModelV0("exact.int", h("exact-int"), True)
        capability = MachineCapabilityV0(
            "opaque.compute",
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


if __name__ == "__main__":
    unittest.main()
