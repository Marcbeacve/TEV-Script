from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import (
    PROGRAM_IR_V4_EFFECTS_SCHEMA,
    PROGRAM_IR_V4_PURE_SCHEMA,
    PROGRAM_IR_V4_RECURSIVE_SCHEMA,
)
from tev_script.runtime_v5_total import initial_total_core_checkpoint, run_total_core_quantum
from tev_script.source_effect_program_v2 import compile_effect_program_v2
from tev_script.source_total_core_v31 import compile_total_core_v31


AUTHORITY = "a" * 64

PURE_SOURCE = (
    'script Calc version "2.0.0"; '
    'fn add1(x:Int)->Int=x+1; '
    'entry main:Int=add1(4);'
)
PURE_SOURCE_FORMATTED = '''
script Calc version "2.0.0";
fn add1( x : Int ) -> Int = x + 1;
entry main : Int = add1(4);
'''
RECURSIVE_SOURCE = '''
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
'''
EFFECT_SOURCE = '''
script Effects version "2.0.0";
state count:Int=0;
capability observation sensor.read(Int)->Int;
action tick() {
    observe sample=sensor.read(count);
    set count=sample;
}
entry main=tick();
'''

PROCESS_PURE = f'''
process Demo version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.total.result End;
label End = halt;
entry Start;
'''

PROCESS_RECURSIVE = f'''
process DemoRec version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Rec result tev.total.result End;
label End = halt;
entry Start;
'''

PROCESS_MULTI = f'''
process DemoMulti version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Calc profile pure;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Calc result tev.total.pure Second;
label Second = invoke_v4 Rec result tev.total.recursive End;
label End = halt;
entry Start;
'''

PROCESS_EFFECTS = f'''
process DemoEffects version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Effects profile effects;
field actual = [];
label Start = invoke_v4 Effects result tev.total.effects End;
label End = halt;
entry Start;
'''


class SourceTotalCoreV31Tests(unittest.TestCase):
    def effect_scenario(self, result: int) -> dict:
        compiled = compile_effect_program_v2(EFFECT_SOURCE)
        contract = compiled.capabilities.require("sensor.read")
        return {
            "capability_table_hash": compiled.capabilities.table_hash,
            "capabilities": [{
                "capability_id": "sensor.read",
                "contract_hash": contract.contract_hash,
                "calls": [{
                    "arguments": [{"$int": "0"}],
                    "return": {"$int": str(result)},
                }],
            }],
        }

    def test_pure_project_compiles_exact_v4_unit_and_runs(self) -> None:
        program = compile_total_core_v31(
            PROCESS_PURE,
            unit_sources={"Calc": PURE_SOURCE},
        )
        self.assertEqual(program.language_version, "3.1.0")
        self.assertEqual(program.profile, "total_core")
        self.assertEqual(len(program.v4_units), 1)
        unit = program.v4_units[0]
        self.assertEqual(unit.unit_id, "Calc")
        self.assertEqual(unit.profile, "pure")
        self.assertEqual(unit.program_ir_v4["schema"], PROGRAM_IR_V4_PURE_SCHEMA)
        self.assertEqual(unit.program_ir_hash, unit.program_ir_v4["program_ir_hash"])

        result = run_total_core_quantum(program, initial_total_core_checkpoint(program))
        self.assertEqual(result.status, "HALTED")
        bridge = next(f for f in result.field.facts if f.relation == "tev.total.result")
        self.assertEqual(bridge.arguments[0]["result_encoded"], {"$int": "5"})

    def test_recursive_project_uses_recursive_v4_authority(self) -> None:
        program = compile_total_core_v31(
            PROCESS_RECURSIVE,
            unit_sources={"Rec": RECURSIVE_SOURCE},
        )
        unit = program.v4_units[0]
        self.assertEqual(unit.profile, "recursive")
        self.assertEqual(unit.program_ir_v4["schema"], PROGRAM_IR_V4_RECURSIVE_SCHEMA)
        result = run_total_core_quantum(program, initial_total_core_checkpoint(program))
        bridge = next(f for f in result.field.facts if f.relation == "tev.total.result")
        self.assertEqual(bridge.arguments[0]["result_encoded"], {"$int": "120"})

    def test_mapping_order_is_nonsemantic(self) -> None:
        left = compile_total_core_v31(
            PROCESS_MULTI,
            unit_sources={"Calc": PURE_SOURCE, "Rec": RECURSIVE_SOURCE},
        )
        right = compile_total_core_v31(
            PROCESS_MULTI,
            unit_sources={"Rec": RECURSIVE_SOURCE, "Calc": PURE_SOURCE},
        )
        self.assertEqual(left.source_semantic_hash, right.source_semantic_hash)
        self.assertEqual(left.program_hash, right.program_hash)
        self.assertEqual(left.v4_units, right.v4_units)

    def test_v2_surface_formatting_is_nonsemantic(self) -> None:
        compact = compile_total_core_v31(
            PROCESS_PURE,
            unit_sources={"Calc": PURE_SOURCE},
        )
        formatted = compile_total_core_v31(
            PROCESS_PURE,
            unit_sources={"Calc": PURE_SOURCE_FORMATTED},
        )
        self.assertEqual(compact.source_semantic_hash, formatted.source_semantic_hash)
        self.assertEqual(compact.program_hash, formatted.program_hash)

    def test_effect_scenario_is_external_evidence_not_source_semantics(self) -> None:
        first = compile_total_core_v31(
            PROCESS_EFFECTS,
            unit_sources={"Effects": EFFECT_SOURCE},
            effect_inputs={"Effects": {"scenario": self.effect_scenario(9)}},
        )
        second = compile_total_core_v31(
            PROCESS_EFFECTS,
            unit_sources={"Effects": EFFECT_SOURCE},
            effect_inputs={"Effects": {"scenario": self.effect_scenario(12)}},
        )
        self.assertEqual(first.source_semantic_hash, second.source_semantic_hash)
        self.assertNotEqual(first.program_hash, second.program_hash)
        self.assertNotEqual(first.v4_units[0].program_ir_hash, second.v4_units[0].program_ir_hash)
        self.assertEqual(first.v4_units[0].program_ir_v4["schema"], PROGRAM_IR_V4_EFFECTS_SCHEMA)

        result = run_total_core_quantum(first, initial_total_core_checkpoint(first))
        bridge = next(f for f in result.field.facts if f.relation == "tev.total.effects")
        self.assertEqual(bridge.arguments[0]["final_state"][0]["value"], {"$int": "9"})

    def test_missing_or_extra_unit_source_is_rejected(self) -> None:
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(PROCESS_PURE, unit_sources={})
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(
                PROCESS_PURE,
                unit_sources={"Calc": PURE_SOURCE, "Extra": PURE_SOURCE},
            )

    def test_declared_profile_must_match_child_program(self) -> None:
        recursive_as_pure = PROCESS_PURE.replace("unit Calc profile pure", "unit Calc profile recursive")
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(
                recursive_as_pure,
                unit_sources={"Calc": PURE_SOURCE},
            )

    def test_effect_input_is_required_only_for_effect_units(self) -> None:
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(
                PROCESS_EFFECTS,
                unit_sources={"Effects": EFFECT_SOURCE},
            )
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(
                PROCESS_PURE,
                unit_sources={"Calc": PURE_SOURCE},
                effect_inputs={"Calc": {"scenario": {}}},
            )

    def test_effect_input_has_closed_shape(self) -> None:
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(
                PROCESS_EFFECTS,
                unit_sources={"Effects": EFFECT_SOURCE},
                effect_inputs={
                    "Effects": {
                        "scenario": self.effect_scenario(9),
                        "unexpected": True,
                    }
                },
            )

    def test_duplicate_unit_and_wrong_process_version_are_rejected(self) -> None:
        duplicate = PROCESS_PURE.replace(
            "unit Calc profile pure;",
            "unit Calc profile pure; unit Calc profile pure;",
        )
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(duplicate, unit_sources={"Calc": PURE_SOURCE})
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(
                PROCESS_PURE.replace('version "3.1.0"', 'version "3.0.0"'),
                unit_sources={"Calc": PURE_SOURCE},
            )

    def test_source_cannot_manufacture_proof_admission(self) -> None:
        forged = PROCESS_PURE.replace(
            "field actual = [];",
            f"proof_admission {'c' * 64}; field actual = [];",
        )
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(forged, unit_sources={"Calc": PURE_SOURCE})

    def test_child_must_be_v2_source(self) -> None:
        wrong = PURE_SOURCE.replace('version "2.0.0"', 'version "3.1.0"')
        with self.assertRaises(TevScriptError):
            compile_total_core_v31(PROCESS_PURE, unit_sources={"Calc": wrong})


if __name__ == "__main__":
    unittest.main()
