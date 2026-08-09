from __future__ import annotations

import json
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.ir_validation import validate_program_ir
from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.lowering_ir_v2_linked_v1 import lower_linked_program_v1_to_ir_v2
from tev_script.lowering_ir_v2_v1 import lower_v1_to_ir_v2
from tev_script.runtime import ScriptRuntime
from tev_script.static_semantics_v1 import analyze_v1_static_semantics

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "conformance" / "v1-irv2-lowering-cases.json").read_text()
)


def build(sources: list[dict[str, str]]):
    plan = link_v1_sources(
        [
            SourceInputV1(item["path"], item["source"].encode())
            for item in sources
        ]
    )
    semantics = analyze_v1_static_semantics(plan)
    linked = emit_linked_program_v1(semantics)
    return semantics, linked


def linked_lower(sources: list[dict[str, str]]):
    _semantics, linked = build(sources)
    return linked, lower_linked_program_v1_to_ir_v2(linked)


class V1LinkedIrV2ParityTests(unittest.TestCase):
    def test_linked_target_and_source_driven_candidate_have_same_ir_semantics(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                semantics, linked = build(case["sources"])
                direct = lower_v1_to_ir_v2(semantics)
                canonical = lower_linked_program_v1_to_ir_v2(linked)
                self.assertEqual(
                    direct.ir["semantic_hash"],
                    canonical.ir["semantic_hash"],
                )
                self.assertEqual(
                    {
                        key: value
                        for key, value in direct.ir.items()
                        if key not in {"debug", "debug_hash"}
                    },
                    {
                        key: value
                        for key, value in canonical.ir.items()
                        if key not in {"debug", "debug_hash"}
                    },
                )
                validate_program_ir(canonical.ir)

    def test_linked_target_debug_identity_is_linked_semantic_hash_not_source_path(self) -> None:
        linked, lowered = linked_lower(
            [
                {
                    "path": "arbitrary/location/root.tevs",
                    "source": 'script Root version "1.0.0"; entity E { on start { return; } }',
                }
            ]
        )
        self.assertEqual(
            lowered.ir["debug"]["source_path"],
            "<TEV_SCRIPT_LINKED_PROGRAM_V1>",
        )
        self.assertEqual(
            lowered.ir["debug"]["v1_linked_semantic_hash"],
            linked.semantic_hash,
        )

    def test_tampered_linked_program_is_rejected_before_lowering(self) -> None:
        linked, _lowered = linked_lower(
            [
                {
                    "path": "root.tevs",
                    "source": 'script Root version "1.0.0"; entity E { state x: Int = 1; on start { return; } }',
                }
            ]
        )
        tampered = json.loads(json.dumps(linked.program))
        tampered["entities"][0]["states"][0]["initial"]["value"] = "999"
        with self.assertRaises(TevScriptError) as captured:
            lower_linked_program_v1_to_ir_v2(tampered)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V1_LINKED_LOWER_SEMANTIC_HASH",
        )


class V1LinkedIrV2RuntimeTests(unittest.TestCase):
    def test_call_by_value_observation_argument_executes_once(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "call-by-value-observation-argument"
        )
        _linked, lowered = linked_lower(case["sources"])
        calls = 0

        def delta() -> Fraction:
            nonlocal calls
            calls += 1
            return Fraction(3, 2)

        runtime = ScriptRuntime(lowered.ir, {"time.delta": delta})
        runtime.invoke("E", "update")
        self.assertEqual(calls, 1)
        self.assertEqual(runtime.state("E")["out"], Fraction(3, 1))

    def test_short_circuit_observations_are_not_eager(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "short-circuit-observations"
        )
        _linked, lowered = linked_lower(case["sources"])
        calls = 0

        def probe() -> bool:
            nonlocal calls
            calls += 1
            return True

        runtime = ScriptRuntime(lowered.ir, {"probe.read": probe})
        runtime.invoke("E", "update")
        self.assertEqual(calls, 0)
        self.assertEqual(runtime.state("E")["hits"], 1)

    def test_behavior_fragment_order_is_preserved_from_linked_uses(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "behavior-effect-order"
        )
        linked, lowered = linked_lower(case["sources"])
        self.assertEqual(
            linked.program["entities"][0]["uses"],
            ["Root.A", "Root.B"],
        )
        logs: list[str] = []
        runtime = ScriptRuntime(lowered.ir, {"debug.log": logs.append})
        runtime.invoke("E", "update")
        self.assertEqual(logs, ["A", "B", "E"])

    def test_bounded_for_is_unrolled_from_canonical_linked_statement(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "bounded-for-unroll"
        )
        linked, lowered = linked_lower(case["sources"])
        body = linked.program["entities"][0]["handlers"][0]["body"]
        self.assertEqual(body[0]["kind"], "for")
        runtime = ScriptRuntime(lowered.ir)
        runtime.invoke("E", "start")
        self.assertEqual(runtime.state("E")["sum"], 6)
        instructions = lowered.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertFalse(
            any(item["op"] in {"JUMP", "JUMP_IF_FALSE"} for item in instructions)
        )

    def test_event_int_to_rat_widening_survives_linked_target(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "behavior-event-chain-with-widening"
        )
        _linked, lowered = linked_lower(case["sources"])
        runtime = ScriptRuntime(lowered.ir)
        emitted = runtime.invoke("E", "start")
        self.assertEqual(runtime.state("E")["seen"], Fraction(1, 1))
        self.assertEqual(emitted[0].arguments, (Fraction(1, 1),))

    def test_custom_primitive_capabilities_execute_from_linked_contract(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "custom-primitive-capabilities"
        )
        _linked, lowered = linked_lower(case["sources"])
        writes: list[int] = []
        runtime = ScriptRuntime(
            lowered.ir,
            {
                "sensor.read": lambda: 7,
                "sink.write": writes.append,
            },
        )
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["x"], 7)
        self.assertEqual(writes, [7])


class V1LinkedIrV2BoundaryTests(unittest.TestCase):
    def test_runtime_record_state_requires_irv3_from_linked_authority(self) -> None:
        case = next(
            item
            for item in CASES["negative"]
            if item["id"] == "record-runtime-state"
        )
        _semantics, linked = build(case["sources"])
        with self.assertRaises(TevScriptError) as captured:
            lower_linked_program_v1_to_ir_v2(linked)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V1_LOWER_IR3_REQUIRED",
        )

    def test_runtime_match_requires_irv3_from_linked_authority(self) -> None:
        case = next(
            item
            for item in CASES["negative"]
            if item["id"] == "runtime-match"
        )
        _semantics, linked = build(case["sources"])
        with self.assertRaises(TevScriptError) as captured:
            lower_linked_program_v1_to_ir_v2(linked)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_V1_LOWER_IR3_REQUIRED",
        )

    def test_unused_v1_types_remain_legal_when_runtime_surface_is_irv2(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "unused-v1-type-declarations-do-not-block"
        )
        linked, lowered = linked_lower(case["sources"])
        self.assertTrue(linked.program["records"])
        self.assertTrue(linked.program["enums"])
        validate_program_ir(lowered.ir)

    def test_v1_only_constant_intermediate_can_erase_before_linked_runtime_lowering(self) -> None:
        case = next(
            item
            for item in CASES["positive"]
            if item["id"] == "v1-only-constant-intermediate-erases-before-ir"
        )
        linked, lowered = linked_lower(case["sources"])
        self.assertTrue(linked.program["records"])
        runtime = ScriptRuntime(lowered.ir)
        self.assertEqual(runtime.state("E")["x"], 7)
        semantic_ir = {
            key: value
            for key, value in lowered.ir.items()
            if key not in {"debug", "debug_hash"}
        }
        self.assertNotIn("Root.R", json.dumps(semantic_ir, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
