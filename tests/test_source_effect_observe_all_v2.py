from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_effect_program_v2 import (
    compile_and_run_effect_program_v2,
    compile_effect_command_program_v2,
    compile_effect_program_v2,
)


class SourceEffectObserveAllV2Tests(unittest.TestCase):
    SOURCE='''
    script ObserveAll version "2.0.0";
    state sum:Int=0;
    capability observation sensor.read(Int)->Int;
    action sample() {
        observe all {
            b=sensor.read(2);
            a=sensor.read(1);
        }
        set sum=a+b;
    }
    entry main=sample();
    '''

    def scenario(self, compiled):
        contract=compiled.capabilities.require("sensor.read")
        return {
            "capability_table_hash":compiled.capabilities.table_hash,
            "capabilities":[{
                "capability_id":"sensor.read",
                "contract_hash":contract.contract_hash,
                "calls":[
                    {"arguments":[{"$int":"1"}],"return":{"$int":"10"}},
                    {"arguments":[{"$int":"2"}],"return":{"$int":"20"}},
                ],
            }],
        }

    def test_source_observe_all_runs_and_then_updates_state(self):
        compiled=compile_effect_program_v2(self.SOURCE)
        _compiled,ir,receipt=compile_and_run_effect_program_v2(self.SOURCE,self.scenario(compiled))
        self.assertEqual(receipt.observation_calls,2)
        self.assertEqual(len(receipt.capability_transcript_hash),64)
        int(receipt.capability_transcript_hash,16)
        self.assertEqual(receipt.final_state[0]["value"],{"$int":"30"})
        group=next(step for step in ir["action"]["steps"] if step["op"]=="OBSERVE_ALL")
        self.assertEqual([item["bind"] for item in group["observations"]],["a","b"])
        self.assertEqual(group["reservation_policy"],"canonical_bind_then_capability_ordinal_v1")

    def test_observation_declaration_order_is_surface_only(self):
        alternate=self.SOURCE.replace(
            'b=sensor.read(2);\n            a=sensor.read(1);',
            'a=sensor.read(1);\n            b=sensor.read(2);',
        )
        a=compile_effect_program_v2(self.SOURCE)
        b=compile_effect_program_v2(alternate)
        self.assertEqual(a.semantic_hash,b.semantic_hash)
        self.assertEqual(a.action_hashes,b.action_hashes)

    def test_sibling_observation_result_is_not_available_to_sibling_argument(self):
        source=self.SOURCE.replace('b=sensor.read(2);','b=sensor.read(a);')
        with self.assertRaises(TevScriptError): compile_effect_program_v2(source)

    def test_duplicate_bind_and_empty_group_fail_closed(self):
        duplicate=self.SOURCE.replace('b=sensor.read(2);','a=sensor.read(2);')
        with self.assertRaises(TevScriptError): compile_effect_program_v2(duplicate)
        empty=self.SOURCE.replace('b=sensor.read(2);\n            a=sensor.read(1);','')
        with self.assertRaises(TevScriptError): compile_effect_program_v2(empty)

    def test_effects_r2_accepts_observe_all_but_keeps_command_authority_separate(self):
        source='script ObserveAllR2 version "2.0.0"; capability observation sensor.read(Int)->Int; command file.replace(Text,Text); action x() { observe all { a=sensor.read(1); } request file.replace("x.txt","data"); } entry main=x();'
        compiled=compile_effect_command_program_v2(source)
        action=dict(compiled.actions)["x"]
        self.assertEqual(action.steps[0]["op"],"OBSERVE_ALL")
        self.assertEqual(action.steps[1]["op"],"REQUEST_EFFECT")
        self.assertEqual(action.observation_call_upper_bound,1)
        self.assertEqual(action.command_request_upper_bound,1)

if __name__=="__main__": unittest.main()
