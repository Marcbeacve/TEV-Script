from __future__ import annotations

import copy
import unittest

from tev_script.compiler import compile_bytes
from tev_script.diagnostics import TevScriptError
from tev_script.lift_ir_v2_to_v3 import lift_ir_v2_to_v3
from tev_script.runtime import ScriptRuntime
from tev_script.runtime_v3 import ScriptRuntimeV3

SOURCE = b'''script Lift version "0.2.0";
entity E {
  state x: Int = 0;
  state ratio: Rat = 1.5;
  on start {
    x = x + 1;
    emit ping(x);
  }
  on ping(value: Int) {
    x = value + 1;
  }
}
'''


class IrV2ToV3LiftTests(unittest.TestCase):
    def test_lift_preserves_primitive_state_encoding_and_source_identity(self) -> None:
        source = compile_bytes("Lift.tevs", SOURCE, debug_source_name="a.tevs")
        lifted = lift_ir_v2_to_v3(source.ir)
        self.assertEqual(lifted.ir["source_schema"], "TEV_SCRIPT_PROGRAM_IR_V2")
        self.assertEqual(
            lifted.ir["lowering_profile"],
            "TEV_SCRIPT_V2_LIFT_TO_IR_V3_PROFILE_V1",
        )
        self.assertEqual(lifted.ir["source_semantic_hash"], source.ir["semantic_hash"])
        self.assertEqual(
            lifted.ir["entities"][0]["states"],
            source.ir["entities"][0]["states"],
        )
        self.assertEqual(
            [item["type_id"] for item in lifted.ir["types"]],
            ["Bool", "Int", "Rat", "Text", "Unit", "Vec2", "Vec3"],
        )

    def test_v2_and_lifted_v3_execute_same_event_chain_and_final_state(self) -> None:
        source = compile_bytes("Lift.tevs", SOURCE)
        lifted = lift_ir_v2_to_v3(source.ir)
        v2 = ScriptRuntime(source.ir)
        v3 = ScriptRuntimeV3(lifted.ir, expected_source_semantic_hash=source.ir["semantic_hash"])

        emitted_v2 = v2.invoke("E", "start")
        emitted_v3 = v3.invoke("E", "start")
        self.assertEqual(v2.state("E"), v3.state("E"))
        self.assertEqual(v2.state("E")["x"], 2)
        self.assertEqual([event.event_id for event in emitted_v2], ["ping"])
        self.assertEqual([event.event_id for event in emitted_v3], ["ping"])
        self.assertEqual(emitted_v3[0].canonical_arguments(v3.type_table), ({"$int":"1"},))

    def test_debug_path_changes_do_not_change_lifted_v3_semantic_identity(self) -> None:
        left = compile_bytes("Lift.tevs", SOURCE, debug_source_name="left/path.tevs")
        right = compile_bytes("Lift.tevs", SOURCE, debug_source_name="right/path.tevs")
        self.assertEqual(left.ir["semantic_hash"], right.ir["semantic_hash"])
        self.assertNotEqual(left.ir["debug_hash"], right.ir["debug_hash"])
        left_v3 = lift_ir_v2_to_v3(left.ir)
        right_v3 = lift_ir_v2_to_v3(right.ir)
        self.assertEqual(left_v3.ir["semantic_hash"], right_v3.ir["semantic_hash"])
        self.assertNotEqual(left_v3.ir["debug_hash"], right_v3.ir["debug_hash"])

    def test_invalid_v2_input_is_rejected_before_lift(self) -> None:
        source = compile_bytes("Lift.tevs", SOURCE)
        tampered = copy.deepcopy(source.ir)
        tampered["entities"][0]["states"][0]["initial"] = {"$int":"999"}
        with self.assertRaises(TevScriptError):
            lift_ir_v2_to_v3(tampered)


if __name__ == "__main__":
    unittest.main()
