from __future__ import annotations

import itertools
import json
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.ir_validation import validate_program_ir
from tev_script.linker_v1 import SourceInputV1
from tev_script.lowering_boundary_v1 import analyze_ir_v2_lowering_boundary
from tev_script.lowering_ir_v2_v1 import (
    lower_v1_sources_to_ir_v2,
)
from tev_script.runtime import ScriptRuntime
from tev_script.static_semantics_v1 import analyze_v1_static_semantics
from tev_script.linker_v1 import link_v1_sources

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "conformance" / "v1-irv2-lowering-cases.json").read_text()
)


def src(path: str, text: str) -> SourceInputV1:
    return SourceInputV1(path, text.encode())


def lower(sources: list[dict[str, str]]):
    return lower_v1_sources_to_ir_v2(
        [src(item["path"], item["source"]) for item in sources]
    )


class V1IrV2LoweringCorpusTests(unittest.TestCase):
    def test_positive_corpus_produces_valid_certified_irv2_shape(self) -> None:
        for case in CASES["positive"]:
            with self.subTest(case=case["id"]):
                bundle = lower(case["sources"])
                validate_program_ir(bundle.ir)
                self.assertEqual(bundle.ir["schema"], "TEV_SCRIPT_PROGRAM_IR_V2")
                self.assertEqual(bundle.ir["language_version"], "0.2.0")
                self.assertEqual(bundle.ir["program_id"], case["sources"][0]["source"].split()[1])
                self.assertTrue(bundle.lowering_boundary.lowerable)
                self.assertTrue(bundle.v1_static_semantic_hash)

    def test_negative_corpus_requires_irv3_without_lossy_encoding(self) -> None:
        for case in CASES["negative"]:
            with self.subTest(case=case["id"]):
                with self.assertRaises(TevScriptError) as captured:
                    lower(case["sources"])
                self.assertEqual(captured.exception.diagnostic.code, case["code"])


class V1IrV2RuntimeSemanticsTests(unittest.TestCase):
    def test_minimal_v1_program_executes_on_existing_runtime(self) -> None:
        case = next(item for item in CASES["positive"] if item["id"] == "minimal-v1-to-irv2")
        bundle = lower(case["sources"])
        runtime = ScriptRuntime(bundle.ir)
        runtime.invoke("E", "start")
        self.assertEqual(runtime.state("E")["x"], 2)

    def test_user_function_is_inlined_not_exposed_as_ir_pure_callable(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "modules-and-pure-function-inlining"
        )
        bundle = lower(case["sources"])
        instructions = bundle.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertFalse(
            any(
                item["op"] == "CALL_PURE" and item.get("function_id") == "math.twice"
                for item in instructions
            )
        )
        runtime = ScriptRuntime(bundle.ir)
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["out"], Fraction(6, 1))

    def test_function_arguments_are_call_by_value_and_observed_once(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "call-by-value-observation-argument"
        )
        bundle = lower(case["sources"])
        calls = 0

        def delta() -> Fraction:
            nonlocal calls
            calls += 1
            return Fraction(3, 2)

        runtime = ScriptRuntime(bundle.ir, {"time.delta": delta})
        runtime.invoke("E", "update")
        self.assertEqual(calls, 1)
        self.assertEqual(runtime.state("E")["out"], Fraction(3, 1))

    def test_behavior_effect_order_is_dependency_use_order_then_entity(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "behavior-effect-order"
        )
        bundle = lower(case["sources"])
        logs: list[str] = []
        runtime = ScriptRuntime(bundle.ir, {"debug.log": logs.append})
        runtime.invoke("E", "update")
        self.assertEqual(logs, ["A", "B", "E"])

    def test_for_is_statically_unrolled_with_exact_loop_constants(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "bounded-for-unroll"
        )
        bundle = lower(case["sources"])
        runtime = ScriptRuntime(bundle.ir)
        runtime.invoke("E", "start")
        self.assertEqual(runtime.state("E")["sum"], 6)
        instructions = bundle.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertFalse(any(item["op"] in {"JUMP", "JUMP_IF_FALSE"} for item in instructions))

    def test_short_circuit_preserves_observation_non_execution(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "short-circuit-observations"
        )
        bundle = lower(case["sources"])
        calls = 0

        def probe() -> bool:
            nonlocal calls
            calls += 1
            return True

        runtime = ScriptRuntime(bundle.ir, {"probe.read": probe})
        runtime.invoke("E", "update")
        self.assertEqual(calls, 0)
        self.assertEqual(runtime.state("E")["hits"], 1)
        instructions = bundle.ir["entities"][0]["handlers"][0]["instructions"]
        self.assertTrue(any(item["op"] == "JUMP_IF_FALSE" for item in instructions))

    def test_custom_primitive_capability_contract_executes(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "custom-primitive-capabilities"
        )
        bundle = lower(case["sources"])
        writes: list[int] = []
        runtime = ScriptRuntime(
            bundle.ir,
            {
                "sensor.read": lambda: 7,
                "sink.write": writes.append,
            },
        )
        runtime.invoke("E", "update")
        self.assertEqual(runtime.state("E")["x"], 7)
        self.assertEqual(writes, [7])

    def test_composed_emitted_int_is_widened_before_rat_handler(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "behavior-event-chain-with-widening"
        )
        bundle = lower(case["sources"])
        runtime = ScriptRuntime(bundle.ir)
        emitted = runtime.invoke("E", "start")
        self.assertEqual(runtime.state("E")["seen"], Fraction(1, 1))
        self.assertEqual(emitted[0].event_id, "pulse")
        self.assertEqual(emitted[0].arguments, (Fraction(1, 1),))

    def test_v1_only_constant_intermediate_is_erased_before_runtime_ir(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "v1-only-constant-intermediate-erases-before-ir"
        )
        bundle = lower(case["sources"])
        runtime = ScriptRuntime(bundle.ir)
        self.assertEqual(runtime.state("E")["x"], 7)
        serialized = json.dumps(bundle.ir, sort_keys=True)
        self.assertNotIn('"Root.R"', serialized)


class V1IrV2DeterminismTests(unittest.TestCase):
    def test_source_input_permutation_and_paths_do_not_change_ir_bytes(self) -> None:
        logical = [
            (
                "root.tevs",
                'script Root version "1.0.0"; import math; behavior A { on update { log "A"; } } entity E { use A; state out: Rat = 0; on update { out = twice(2); } }',
            ),
            (
                "math.tevs",
                'module math version "1.0.0"; export fn twice(x: Rat) -> Rat = x * 2;',
            ),
        ]
        observed: set[str] = set()
        semantic_hashes: set[str] = set()
        for run, permutation in enumerate(itertools.permutations(range(len(logical)))):
            inputs = [
                SourceInputV1(
                    f"relocated/{run}/{logical[index][0]}",
                    logical[index][1].encode(),
                )
                for index in permutation
            ]
            bundle = lower_v1_sources_to_ir_v2(inputs)
            observed.add(bundle.canonical_json)
            semantic_hashes.add(bundle.ir["semantic_hash"])
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(semantic_hashes), 1)

    def test_source_parameter_renaming_does_not_change_ir_semantics(self) -> None:
        left = lower([
            {
                "path": "left.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on pulse(x: Int) { log "a"; } } entity E { use A; on pulse(y: Int) { log "e"; } }',
            }
        ])
        right = lower([
            {
                "path": "right.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on pulse(first: Int) { log "a"; } } entity E { use A; on pulse(second: Int) { log "e"; } }',
            }
        ])
        self.assertEqual(left.ir["semantic_hash"], right.ir["semantic_hash"])

    def test_behavior_use_order_remains_semantic_after_lowering(self) -> None:
        left = lower([
            {
                "path": "left.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on update { log "A"; } } behavior B { on update { log "B"; } } entity E { use A; use B; on start { return; } }',
            }
        ])
        right = lower([
            {
                "path": "right.tevs",
                "source": 'script Root version "1.0.0"; behavior A { on update { log "A"; } } behavior B { on update { log "B"; } } entity E { use B; use A; on start { return; } }',
            }
        ])
        self.assertNotEqual(left.ir["semantic_hash"], right.ir["semantic_hash"])


class V1IrV2BoundaryTests(unittest.TestCase):
    def test_boundary_reports_ir3_reason_before_lowering(self) -> None:
        sources = [
            src(
                "root.tevs",
                'script Root version "1.0.0"; record R { x: Int; } entity E { state r: R = R(x = 1); on start { return; } }',
            )
        ]
        semantics = analyze_v1_static_semantics(link_v1_sources(sources))
        boundary = analyze_ir_v2_lowering_boundary(semantics)
        self.assertFalse(boundary.lowerable)
        self.assertIn(
            "TEVS_V1_LOWER_IR3_STATE_TYPE",
            {item.code for item in boundary.blockers},
        )

    def test_unused_v1_type_declarations_do_not_block_irv2_lowering(self) -> None:
        case = next(
            item for item in CASES["positive"]
            if item["id"] == "unused-v1-type-declarations-do-not-block"
        )
        bundle = lower(case["sources"])
        self.assertTrue(bundle.lowering_boundary.lowerable)
        validate_program_ir(bundle.ir)


if __name__ == "__main__":
    unittest.main()
