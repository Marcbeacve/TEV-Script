from __future__ import annotations

import unittest

from tev_script.causal_analysis_v1 import (
    derive_reaction_footprints,
    find_reaction_footprint,
    prove_authority_capacity,
    prove_independence,
    prove_preparability,
    reaction_authority_lease,
)
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    CapabilityLawV1,
    ResourceAccessV1,
    ResourceLawV1,
)
from tev_script.pipeline_v1 import compile_v1_mapping_to_ir_v3


def compile_source(source: bytes):
    return compile_v1_mapping_to_ir_v3({"Probe.tevs": source}).target.ir


class CausalAnalysisTests(unittest.TestCase):
    def test_reaction_closure_unions_transitive_handler_effects(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability audit.write(Text) -> Unit effect;
entity E {
 state x: Int = 0;
 state y: Int = 0;
 on start { x = 1; emit follow(); }
 on follow { y = x + 1; call audit.write("done"); emit final(); }
}
''')
        footprint = find_reaction_footprint(ir, "E", "start")
        self.assertEqual(footprint.reachable_events, ("follow", "start"))
        self.assertEqual(footprint.state_reads, ("x",))
        self.assertEqual(footprint.state_writes, ("x", "y"))
        self.assertEqual(footprint.effects, ("audit.write",))
        self.assertEqual(footprint.emitted_events, ("final", "follow"))

    def test_cycle_is_detected_but_remains_bounded_by_ir_event_budget(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
entity E { state x: Int = 0; on tick { x = x + 1; emit tick(); } }
''')
        footprint = find_reaction_footprint(ir, "E", "tick")
        self.assertTrue(footprint.cyclic_event_graph)
        self.assertEqual(footprint.maximum_event_chain, 128)
        self.assertGreaterEqual(footprint.instruction_ceiling, 128)

    def test_internal_state_footprint_predicts_independence(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
entity E {
 state x: Int = 0; state y: Int = 0;
 on ax { x = x + 1; }
 on by { y = y + 1; }
 on readx { y = x; }
}
''')
        catalog = CapabilityLawCatalogV1("empty", True)
        ax = find_reaction_footprint(ir, "E", "ax")
        by = find_reaction_footprint(ir, "E", "by")
        readx = find_reaction_footprint(ir, "E", "readx")
        self.assertTrue(prove_independence(ax, by, catalog).independent)
        self.assertFalse(prove_independence(ax, readx, catalog).independent)

    def test_distinct_capability_ids_can_alias_same_external_resource(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability motor.left(Int) -> Unit effect;
capability motor.right(Int) -> Unit effect;
entity A { on go { call motor.left(1); } }
entity B { on go { call motor.right(1); } }
''')
        catalog = CapabilityLawCatalogV1(
            "robot", True,
            resources=(ResourceLawV1("drive"),),
            capabilities=(
                CapabilityLawV1("motor.left", "effect", (ResourceAccessV1("drive", "write"),), effect_protocol="immediate"),
                CapabilityLawV1("motor.right", "effect", (ResourceAccessV1("drive", "write"),), effect_protocol="immediate"),
            ),
        )
        a = find_reaction_footprint(ir, "A", "go")
        b = find_reaction_footprint(ir, "B", "go")
        result = prove_independence(a, b, catalog)
        self.assertFalse(result.independent)
        self.assertTrue(any(reason.startswith("resource_conflict") for reason in result.reasons))

    def test_read_read_requires_snapshot_or_stable_law(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability sensor.a() -> Int observation;
capability sensor.b() -> Int observation;
entity A { state x: Int = 0; on go { x = sensor.a(); } }
entity B { state y: Int = 0; on go { y = sensor.b(); } }
''')
        a = find_reaction_footprint(ir, "A", "go")
        b = find_reaction_footprint(ir, "B", "go")
        resource = (ResourceLawV1("sensor"),)
        sequential = CapabilityLawCatalogV1(
            "seq", True, resource,
            (
                CapabilityLawV1("sensor.a", "observation", (ResourceAccessV1("sensor", "read"),), observation_semantics="sequence_sensitive"),
                CapabilityLawV1("sensor.b", "observation", (ResourceAccessV1("sensor", "read"),), observation_semantics="sequence_sensitive"),
            ),
        )
        snapshot = CapabilityLawCatalogV1(
            "snap", True, resource,
            (
                CapabilityLawV1("sensor.a", "observation", (ResourceAccessV1("sensor", "read"),), observation_semantics="snapshot"),
                CapabilityLawV1("sensor.b", "observation", (ResourceAccessV1("sensor", "read"),), observation_semantics="snapshot"),
            ),
        )
        self.assertFalse(prove_independence(a, b, sequential).independent)
        self.assertTrue(prove_independence(a, b, snapshot).independent)

    def test_effect_before_observation_same_region_is_not_preparable(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability world.set(Int) -> Unit effect;
capability world.read() -> Int observation;
entity E { state seen: Int = 0; on go { call world.set(1); seen = world.read(); } }
''')
        catalog = CapabilityLawCatalogV1(
            "world", True,
            resources=(ResourceLawV1("world"),),
            capabilities=(
                CapabilityLawV1("world.set", "effect", (ResourceAccessV1("world", "write"),), effect_protocol="immediate"),
                CapabilityLawV1("world.read", "observation", (ResourceAccessV1("world", "read"),), observation_semantics="stable"),
            ),
        )
        footprint = find_reaction_footprint(ir, "E", "go")
        result = prove_preparability(ir, footprint, catalog)
        self.assertFalse(result.preparable)
        self.assertEqual(result.hazards, (("world.set", "world.read"),))

    def test_disjoint_effect_observation_is_preparable(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability motor.set(Int) -> Unit effect;
capability thermal.read() -> Int observation;
entity E { state seen: Int = 0; on go { call motor.set(1); seen = thermal.read(); } }
''')
        catalog = CapabilityLawCatalogV1(
            "robot", True,
            resources=(ResourceLawV1("drive"), ResourceLawV1("thermal")),
            capabilities=(
                CapabilityLawV1("motor.set", "effect", (ResourceAccessV1("drive", "write"),), effect_protocol="immediate"),
                CapabilityLawV1("thermal.read", "observation", (ResourceAccessV1("thermal", "read"),), observation_semantics="stable"),
            ),
        )
        result = prove_preparability(ir, find_reaction_footprint(ir, "E", "go"), catalog)
        self.assertTrue(result.preparable)
        self.assertEqual(result.atomicity, "state_atomic_external_partial_possible")

    def test_unknown_deployment_law_fails_closed_for_effectful_reaction(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability motor.set(Int) -> Unit effect;
entity E { on go { call motor.set(1); } }
''')
        footprint = find_reaction_footprint(ir, "E", "go")
        result = prove_preparability(ir, footprint, CapabilityLawCatalogV1("unknown", False))
        self.assertFalse(result.preparable)
        self.assertIn("deployment_catalog_not_complete", result.reasons)


    def test_capability_law_kind_mismatch_fails_closed(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability motor.set(Int) -> Unit effect;
entity E { on go { call motor.set(1); } }
''')
        wrong = CapabilityLawCatalogV1(
            "wrong", True,
            resources=(ResourceLawV1("drive"),),
            capabilities=(
                CapabilityLawV1(
                    "motor.set", "observation",
                    (ResourceAccessV1("drive", "read"),),
                    observation_semantics="stable",
                ),
            ),
        )
        result = prove_preparability(ir, find_reaction_footprint(ir, "E", "go"), wrong)
        self.assertFalse(result.preparable)
        self.assertTrue(any(reason.startswith("capability_kind_mismatch") for reason in result.reasons))

    def test_reaction_authority_lease_and_linear_capacity_are_explicit(self) -> None:
        ir = compile_source(b'''script P version "1.0.0";
capability door.open() -> Unit effect;
entity A { on go { call door.open(); } }
entity B { on go { call door.open(); } }
''')
        one = CapabilityLawCatalogV1(
            "one", True,
            resources=(ResourceLawV1("door-control", kind="authority", capacity=1),),
            capabilities=(
                CapabilityLawV1(
                    "door.open", "effect",
                    (ResourceAccessV1("door-control", "reserve"),),
                    effect_protocol="immediate",
                ),
            ),
        )
        two = CapabilityLawCatalogV1(
            "two", True,
            resources=(ResourceLawV1("door-control", kind="authority", capacity=2),),
            capabilities=one.capabilities,
        )
        a = find_reaction_footprint(ir, "A", "go")
        b = find_reaction_footprint(ir, "B", "go")
        self.assertEqual(
            reaction_authority_lease(a, one),
            (ResourceAccessV1("door-control", "reserve"),),
        )
        self.assertTrue(prove_authority_capacity((a,), one).independent)
        self.assertFalse(prove_authority_capacity((a, b), one).independent)
        self.assertTrue(prove_authority_capacity((a, b), two).independent)

    def test_footprint_identity_is_deterministic(self) -> None:
        ir = compile_source(b'''script P version "1.0.0"; entity E { state x: Int = 0; on go { x = x + 1; } }''')
        one = derive_reaction_footprints(ir)
        two = derive_reaction_footprints(ir)
        self.assertEqual([x.footprint_hash for x in one], [x.footprint_hash for x in two])


if __name__ == "__main__":
    unittest.main()
