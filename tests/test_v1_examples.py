from __future__ import annotations

from fractions import Fraction
from pathlib import Path
import unittest

from tev_script.ir_v3_values import VariantValueV3
from tev_script.lowering_ir_v3_linked_v1 import lower_linked_program_v1_to_ir_v3
from tev_script.pipeline_v1 import analyze_v1_paths, compile_v1_paths_to_ir_v2
from tev_script.runtime_v3 import ScriptRuntimeV3

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "v1"


class V1ExampleTests(unittest.TestCase):
    def test_calculator_is_real_v1_ir_v3_program(self) -> None:
        analysis = analyze_v1_paths([EXAMPLES / "Calculator.tevs"])
        target = lower_linked_program_v1_to_ir_v3(analysis.linked_program)
        runtime = ScriptRuntimeV3(
            target.ir,
            expected_source_semantic_hash=analysis.linked_program.semantic_hash,
        )

        add = VariantValueV3("Calculator.Operation", "Add")
        multiply = VariantValueV3("Calculator.Operation", "Multiply")
        divide = VariantValueV3("Calculator.Operation", "Divide")

        runtime.invoke("Calculator", "calculate", add, Fraction(5, 1))
        runtime.invoke("Calculator", "calculate", multiply, Fraction(3, 1))
        self.assertEqual(runtime.state("Calculator")["accumulator"], Fraction(15, 1))

        runtime.invoke("Calculator", "calculate", divide, Fraction(0, 1))
        state = runtime.state("Calculator")
        self.assertEqual(state["accumulator"], Fraction(15, 1))
        last = state["last"]
        self.assertEqual(last.variant, "Err")
        self.assertEqual(last.payload.variant, "DivisionByZero")

    def test_erasable_example_reaches_certified_ir_v2_surface(self) -> None:
        compiled = compile_v1_paths_to_ir_v2([EXAMPLES / "ErasableToIrV2.tevs"])
        self.assertEqual(compiled.target.ir["schema"], "TEV_SCRIPT_PROGRAM_IR_V2")
        self.assertEqual(compiled.target.linked_semantic_hash, compiled.analysis.linked_program.semantic_hash)
        opcodes = {
            instruction["op"]
            for entity in compiled.target.ir["entities"]
            for handler in entity["handlers"]
            for instruction in handler["instructions"]
        }
        self.assertNotIn("MAKE_RECORD", opcodes)
        self.assertNotIn("MAKE_VARIANT", opcodes)
        self.assertNotIn("TEST_VARIANT", opcodes)

    def test_algebraic_capability_example_requires_ir_v3(self) -> None:
        analysis = analyze_v1_paths([EXAMPLES / "AlgebraicCapability.tevs"])
        self.assertFalse(analysis.ir_v2_boundary.admissible)
        target = lower_linked_program_v1_to_ir_v3(analysis.linked_program)
        self.assertEqual(target.ir["schema"], "TEV_SCRIPT_PROGRAM_IR_V3")
        type_ids = {item["type_id"] for item in target.ir["types"]}
        self.assertIn("AlgebraicCapability.Sample", type_ids)
        self.assertIn(
            "Result<AlgebraicCapability.Sample,AlgebraicCapability.SensorError>",
            type_ids,
        )
        self.assertIn("Option<AlgebraicCapability.Sample>", type_ids)

    def test_multimodule_ecosystem_links_and_lowers_deterministically(self) -> None:
        paths = [
            EXAMPLES / "ecosystem" / "main.tevs",
            EXAMPLES / "ecosystem" / "model.tevs",
            EXAMPLES / "ecosystem" / "rules.tevs",
            EXAMPLES / "ecosystem" / "storage.tevs",
        ]
        forward = analyze_v1_paths(paths)
        reverse = analyze_v1_paths(reversed(paths))
        self.assertEqual(
            forward.linked_program.canonical_json,
            reverse.linked_program.canonical_json,
        )
        self.assertEqual(
            forward.linked_program.semantic_hash,
            reverse.linked_program.semantic_hash,
        )

        target = lower_linked_program_v1_to_ir_v3(forward.linked_program)
        self.assertEqual(target.ir["source_semantic_hash"], forward.linked_program.semantic_hash)
        type_ids = {item["type_id"] for item in target.ir["types"]}
        self.assertIn("ecosystem.model.Resource", type_ids)
        self.assertIn("Option<ecosystem.model.Resource>", type_ids)


if __name__ == "__main__":
    unittest.main()
