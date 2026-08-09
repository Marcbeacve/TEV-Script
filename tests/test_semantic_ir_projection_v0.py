from __future__ import annotations
import unittest

from tev_script.pipeline_v1 import compile_v1_mapping_to_ir_v3
from tev_script.semantic_projection_v0 import project_ir_v3_program, derive_handler_rule

SRC = b"""script P version "1.0.0";
capability sensor.read() -> Bool observation;
capability motor.open() -> Unit effect;
entity Door {
    state open: Bool = false;
    on request {
        if sensor.read() {
            open = true;
            call motor.open();
            emit changed();
        }
    }
    on changed { }
}
"""

class SemanticIrProjectionV0Tests(unittest.TestCase):
    def setUp(self):
        self.ir = compile_v1_mapping_to_ir_v3({"a.tevs": SRC}).target.ir

    def test_program_projection_is_path_invariant(self):
        other = compile_v1_mapping_to_ir_v3({"other/path.tevs": SRC}).target.ir
        self.assertEqual(project_ir_v3_program(self.ir).field_hash, project_ir_v3_program(other).field_hash)

    def test_handler_derives_multidomain_effects(self):
        rule = derive_handler_rule(self.ir,"Door","request")
        self.assertGreaterEqual(len(rule.facts_for("tev.rule.effect")), 4)

if __name__ == "__main__":
    unittest.main()
