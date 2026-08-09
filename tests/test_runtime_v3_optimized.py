from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.python_host_v1 import build_python_program_v1
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2
from tev_script.runtime_v3 import ScriptRuntimeV3
from tev_script.runtime_v3_optimized import OptimizedScriptRuntimeV3

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text(encoding="utf-8")
)["valid_program"]

COUNTER_SOURCE = b'''script Counter version "1.0.0";
entity E {
    state x: Int = 0;
    on inc {
        x = x + 1;
    }
}
'''

BRANCH_SOURCE = b'''script BranchCounter version "1.0.0";
entity E {
    state x: Int = 0;
    on inc(flag: Bool) {
        if flag {
            x = x + 1;
        }
    }
}
'''

ARITH_SOURCE = b'''script Arithmetic version "1.0.0";
entity E {
    state a: Int = 3;
    state b: Int = 11;
    state c: Int = 5;
    on step {
        a = a + 2;
        b = b - 3;
        c = c * 4;
    }
}
'''


class OptimizedRuntimeEquivalenceTests(unittest.TestCase):
    def test_counter_matches_reference_for_repeated_hot_path(self) -> None:
        artifact = build_python_program_v1({"Counter.tevs": COUNTER_SOURCE})
        ir = artifact.ir()
        reference = ScriptRuntimeV3(copy.deepcopy(ir))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(ir))

        for _ in range(10_000):
            self.assertEqual(reference.invoke("E", "inc"), optimized.invoke("E", "inc"))

        self.assertEqual(reference.state("E"), optimized.state("E"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))
        self.assertEqual(reference.semantic_hash, optimized.semantic_hash)
        self.assertEqual(reference.source_semantic_hash, optimized.source_semantic_hash)
        self.assertEqual(optimized.state("E")["x"], 10_000)

    def test_counter_compiles_to_closed_parameter_free_fast_profile(self) -> None:
        artifact = build_python_program_v1({"Counter.tevs": COUNTER_SOURCE})
        ir = artifact.ir()
        optimized = OptimizedScriptRuntimeV3(ir)
        handler = optimized.entities["E"].handlers["inc"]
        source_handler = next(
            raw
            for raw in ir["entities"][0]["handlers"]
            if raw["event_id"] == "inc"
        )
        logical_cost = sum(item.logical_cost for item in handler.instructions)

        self.assertEqual(handler.parameter_types, ())
        self.assertFalse(handler.can_emit)
        self.assertFalse(handler.meter_budget)
        self.assertNotEqual(handler.fast_kind, 0)

        # The compiler's instruction_budget is an upper contractual limit
        # (currently 8192 for this source), not the dynamic cost of this
        # particular handler. Optimization must preserve that declared budget
        # exactly while the execution plan preserves the five logical source
        # instructions (LOAD_STATE, CONST, BINARY, STORE_STATE, RETURN).
        self.assertEqual(logical_cost, 5)
        self.assertEqual(handler.instruction_budget, source_handler["instruction_budget"])
        self.assertGreaterEqual(handler.instruction_budget, logical_cost)

    def test_guarded_bool_branch_uses_closed_fast_profile_and_matches_reference(self) -> None:
        artifact = build_python_program_v1({"BranchCounter.tevs": BRANCH_SOURCE})
        ir = artifact.ir()
        reference = ScriptRuntimeV3(copy.deepcopy(ir))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(ir))

        handler = optimized.entities["E"].handlers["inc"]
        source_handler = next(
            raw
            for raw in ir["entities"][0]["handlers"]
            if raw["event_id"] == "inc"
        )
        logical_cost = sum(item.logical_cost for item in handler.instructions)

        self.assertNotEqual(handler.fast_kind, 0)
        self.assertTrue(handler.meter_budget)
        self.assertEqual(handler.parameter_types, ("Bool",))
        self.assertEqual(logical_cost, len(source_handler["instructions"]))
        self.assertEqual(handler.instruction_budget, source_handler["instruction_budget"])
        self.assertGreaterEqual(handler.instruction_budget, logical_cost)

        for flag in (False, True, False, True, True):
            self.assertEqual(reference.invoke("E", "inc", flag), optimized.invoke("E", "inc", flag))
            self.assertEqual(reference.state("E"), optimized.state("E"))

        self.assertEqual(optimized.state("E")["x"], 3)

    def test_specialized_add_sub_mul_integer_paths_match_reference(self) -> None:
        artifact = build_python_program_v1({"Arithmetic.tevs": ARITH_SOURCE})
        ir = artifact.ir()
        reference = ScriptRuntimeV3(copy.deepcopy(ir))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(ir))

        for _ in range(100):
            self.assertEqual(reference.invoke("E", "step"), optimized.invoke("E", "step"))
            self.assertEqual(reference.state("E"), optimized.state("E"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))

    def test_algebraic_transition_matches_reference(self) -> None:
        reference = ScriptRuntimeV3(copy.deepcopy(BASE))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(BASE))

        self.assertEqual(reference.invoke("E", "start"), optimized.invoke("E", "start"))
        self.assertEqual(reference.state("E"), optimized.state("E"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))

        self.assertEqual(reference.invoke("E", "update"), optimized.invoke("E", "update"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))

    def test_record_constructor_preserves_source_evaluation_order_and_canonical_field_order(self) -> None:
        program = copy.deepcopy(BASE)
        start = next(
            handler
            for handler in program["entities"][0]["handlers"]
            if handler["event_id"] == "start"
        )
        # The descriptor order is a,b. Force MAKE_RECORD to consume values in
        # source/evaluation order b,a and update the preceding constants to
        # match those stack types. A compiled constructor must then reorder the
        # semantic record back to canonical descriptor order without changing
        # which value belonged to which source field.
        start["instructions"][0] = {"op": "CONST", "type": "Rat", "value": {"$rat": ["3", "1"]}}
        start["instructions"][1] = {"op": "CONST", "type": "Int", "value": {"$int": "2"}}
        start["instructions"][2]["fields"] = ["b", "a"]

        from tev_script.canonical import canonical_hash

        program["debug_hash"] = canonical_hash(program["debug"])
        semantic = {
            key: value
            for key, value in program.items()
            if key not in {"semantic_hash", "debug", "debug_hash"}
        }
        program["semantic_hash"] = canonical_hash(semantic)

        reference = ScriptRuntimeV3(copy.deepcopy(program))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(program))
        self.assertEqual(reference.invoke("E", "start"), optimized.invoke("E", "start"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))

    def test_capability_boundary_matches_reference(self) -> None:
        observed_reference: list[object] = []
        observed_optimized: list[object] = []
        pair = BASE["entities"][0]["states"][3]["initial"]

        reference = ScriptRuntimeV3(
            copy.deepcopy(BASE),
            {
                "world.read": lambda: copy.deepcopy(pair),
                "sink.write": observed_reference.append,
            },
        )
        optimized = OptimizedScriptRuntimeV3(
            copy.deepcopy(BASE),
            {
                "world.read": lambda: copy.deepcopy(pair),
                "sink.write": observed_optimized.append,
            },
        )

        self.assertEqual(reference.invoke("E", "pulse"), optimized.invoke("E", "pulse"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))
        self.assertEqual(observed_reference, observed_optimized)

    def test_declared_emitted_event_matches_reference(self) -> None:
        reference = ScriptRuntimeV3(copy.deepcopy(BASE))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(BASE))
        self.assertEqual(reference.invoke("E", "update"), optimized.invoke("E", "update"))

    def test_unknown_valid_zero_argument_event_preserves_reference_behavior(self) -> None:
        reference = ScriptRuntimeV3(copy.deepcopy(BASE))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(BASE))
        self.assertEqual(reference.invoke("E", "unknown"), optimized.invoke("E", "unknown"))

    def test_guarded_fast_profile_preserves_external_bool_coercion(self) -> None:
        artifact = build_python_program_v1({"BranchCounter.tevs": BRANCH_SOURCE})
        ir = artifact.ir()
        reference = ScriptRuntimeV3(copy.deepcopy(ir))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(ir))

        with self.assertRaises(TevScriptError) as reference_error:
            reference.invoke("E", "inc", 1)
        with self.assertRaises(TevScriptError) as optimized_error:
            optimized.invoke("E", "inc", 1)
        self.assertEqual(
            reference_error.exception.diagnostic.code,
            optimized_error.exception.diagnostic.code,
        )

    def test_checkpoint_capture_bytes_match_reference(self) -> None:
        artifact = build_python_program_v1({"Counter.tevs": COUNTER_SOURCE})
        ir = artifact.ir()
        reference = ScriptRuntimeV3(copy.deepcopy(ir))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(ir))

        for _ in range(17):
            reference.invoke("E", "inc")
            optimized.invoke("E", "inc")

        reference_checkpoint = RuntimeCheckpointV2.capture(reference).to_canonical_json()
        optimized_checkpoint = RuntimeCheckpointV2.capture(optimized).to_canonical_json()  # type: ignore[arg-type]
        self.assertEqual(reference_checkpoint, optimized_checkpoint)

    def test_missing_capability_preserves_diagnostic_code(self) -> None:
        reference = ScriptRuntimeV3(copy.deepcopy(BASE))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(BASE))

        with self.assertRaises(TevScriptError) as reference_error:
            reference.invoke("E", "pulse")
        with self.assertRaises(TevScriptError) as optimized_error:
            optimized.invoke("E", "pulse")

        self.assertEqual(
            reference_error.exception.diagnostic.code,
            optimized_error.exception.diagnostic.code,
        )
        self.assertEqual(optimized_error.exception.diagnostic.code, "TEVS_IR_V3_CAPABILITY_MISSING")

    def test_noncanonical_invocation_preserves_diagnostic_code(self) -> None:
        reference = ScriptRuntimeV3(copy.deepcopy(BASE))
        optimized = OptimizedScriptRuntimeV3(copy.deepcopy(BASE))

        with self.assertRaises(TevScriptError) as reference_error:
            reference.invoke("E", "bad.event")
        with self.assertRaises(TevScriptError) as optimized_error:
            optimized.invoke("E", "bad.event")

        self.assertEqual(
            reference_error.exception.diagnostic.code,
            optimized_error.exception.diagnostic.code,
        )
        self.assertEqual(optimized_error.exception.diagnostic.code, "TEVS_IR_V3_INVOCATION_ID")


if __name__ == "__main__":
    unittest.main()
