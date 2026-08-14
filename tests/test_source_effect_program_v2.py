from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_effect_program_v2 import (
    build_effect_program_ir_v4,
    compile_and_run_effect_program_v2,
    compile_effect_program_v2,
    compile_effect_command_program_v2,
    compile_and_plan_effect_command_program_v2,
    effect_scenario_skeleton_v2,
)


class SourceEffectProgramV2Tests(unittest.TestCase):
    SOURCE='''
    script Demo version "2.0.0";
    state count:Int=0;
    state last:Int=0;
    capability observation sensor.read(Int)->Int;
    action tick(bias:Int) {
        observe sample=sensor.read(count);
        let next:Int=sample+bias;
        set last=sample;
        set count=next;
        assert count>0;
    }
    entry main=tick(3);
    '''

    def scenario(self, compiled, argument=0, result=10):
        contract=compiled.capabilities.require("sensor.read")
        return {
            "capability_table_hash":compiled.capabilities.table_hash,
            "capabilities":[{
                "capability_id":"sensor.read",
                "contract_hash":contract.contract_hash,
                "calls":[{"arguments":[{"$int":str(argument)}],"return":{"$int":str(result)}}],
            }],
        }

    def test_source_effect_program_compiles_and_runs_end_to_end(self):
        compiled=compile_effect_program_v2(self.SOURCE)
        scenario=self.scenario(compiled,0,10)
        compiled2,ir,receipt=compile_and_run_effect_program_v2(self.SOURCE,scenario)
        self.assertEqual(compiled.semantic_hash,compiled2.semantic_hash)
        self.assertEqual(ir["profile"],"effects")
        final={item["name"]:item["value"] for item in receipt.final_state}
        self.assertEqual(final["count"],{"$int":"13"})
        self.assertEqual(final["last"],{"$int":"10"})
        self.assertEqual(receipt.observation_calls,1)

    def test_current_state_is_execution_instance_not_source_semantics(self):
        compiled=compile_effect_program_v2(self.SOURCE)
        ir0=build_effect_program_ir_v4(compiled,self.scenario(compiled,0,10))
        ir2=build_effect_program_ir_v4(compiled,self.scenario(compiled,2,10),current_state={"count":2,"last":0})
        self.assertEqual(ir0["source"]["semantic_hash"],ir2["source"]["semantic_hash"])
        self.assertNotEqual(ir0["program_ir_hash"],ir2["program_ir_hash"])

    def test_scenario_is_execution_instance_not_source_semantics(self):
        compiled=compile_effect_program_v2(self.SOURCE)
        ir_a=build_effect_program_ir_v4(compiled,self.scenario(compiled,0,10))
        ir_b=build_effect_program_ir_v4(compiled,self.scenario(compiled,0,20))
        self.assertEqual(ir_a["source"]["semantic_hash"],ir_b["source"]["semantic_hash"])
        self.assertNotEqual(ir_a["scenario"]["scenario_hash"],ir_b["scenario"]["scenario_hash"])
        self.assertNotEqual(ir_a["program_ir_hash"],ir_b["program_ir_hash"])

    def test_whitespace_and_independent_declaration_order_are_surface_only(self):
        alternate='''
        script Demo version "2.0.0";
        capability observation sensor.read(Int) -> Int;
        state last : Int = 0;
        state count : Int = 0;
        action tick( bias : Int ) {
            observe sample = sensor.read(count);
            let next : Int = sample + bias;
            set last = sample;
            set count = next;
            assert count > 0;
        }
        entry main = tick(3);
        '''
        a=compile_effect_program_v2(self.SOURCE)
        b=compile_effect_program_v2(alternate)
        self.assertEqual(a.semantic_hash,b.semantic_hash)
        self.assertEqual(a.state_schema_hash,b.state_schema_hash)
        self.assertEqual(a.capability_table_hash,b.capability_table_hash)
        self.assertEqual(a.action_hashes,b.action_hashes)

    def test_collection_state_uses_normal_v2_type_and_expression_semantics(self):
        source='''
        script Demo version "2.0.0";
        state items:List<Int,4>=[];
        action append(x:Int) { set items=list.push(items,x); }
        entry main=append(7);
        '''
        compiled=compile_effect_program_v2(source)
        scenario=effect_scenario_skeleton_v2(compiled)
        _,_,receipt=compile_and_run_effect_program_v2(source,scenario)
        final=receipt.final_state[0]
        self.assertEqual(final["type"],"List<Int,4>")
        self.assertEqual(final["value"],{"$list":{"type":"List<Int,4>","items":[{"$int":"7"}]}})

    def test_scenario_skeleton_is_contract_bound_and_empty(self):
        compiled=compile_effect_program_v2(self.SOURCE)
        skeleton=effect_scenario_skeleton_v2(compiled)
        self.assertEqual(skeleton["capability_table_hash"],compiled.capabilities.table_hash)
        self.assertEqual(skeleton["capabilities"][0]["contract_hash"],compiled.capabilities.contracts[0].contract_hash)
        self.assertEqual(skeleton["capabilities"][0]["calls"],[])

    def test_physical_capability_source_is_not_accepted_in_r1(self):
        source='''
        script Demo version "2.0.0";
        capability effect file.write(Text)->Int;
        action x() { assert true; }
        entry main=x();
        '''
        with self.assertRaises(TevScriptError): compile_effect_program_v2(source)

    def test_implicit_host_call_inside_action_is_rejected(self):
        source='''
        script Demo version "2.0.0";
        state x:Int=0;
        action bad() { set x=file.write("x"); }
        entry main=bad();
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_effect_program_v2(source)
        self.assertIn(captured.exception.diagnostic.code,{"TEVS_V2_PROGRAM_CALL","TEVS_V2_PROGRAM_NAME"})

    def test_unknown_state_or_capability_fails_at_compile_time(self):
        unknown_state='''
        script Demo version "2.0.0";
        action bad() { set missing=1; }
        entry main=bad();
        '''
        with self.assertRaises(TevScriptError): compile_effect_program_v2(unknown_state)
        unknown_cap='''
        script Demo version "2.0.0";
        state x:Int=0;
        action bad() { observe y=sensor.missing(x); set x=y; }
        entry main=bad();
        '''
        with self.assertRaises(TevScriptError): compile_effect_program_v2(unknown_cap)

    def test_r2_command_request_compiles_and_plans_without_physical_execution(self):
        source='\n        script FileDemo version "2.0.0";\n        state writes:Int=0;\n        command file.replace(Text,Text);\n        action publish() {\n            request file.replace("out.txt","hello");\n            set writes=writes+1;\n        }\n        entry main=publish();\n        '
        with self.assertRaises(TevScriptError) as captured:
            compile_effect_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_EFFECT_R2_REQUIRED')
        compiled=compile_effect_command_program_v2(source)
        self.assertEqual(compiled.commands.contracts[0].command_id,'file.replace')
        scenario={"capability_table_hash":compiled.capabilities.table_hash,"capabilities":[]}
        compiled2, program_ir, planned=compile_and_plan_effect_command_program_v2(source,scenario)
        self.assertEqual(compiled2.semantic_hash,compiled.semantic_hash)
        self.assertEqual(program_ir['schema'],'TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_R2_V1')
        batch=planned.plan_artifact['command_batch']
        self.assertEqual(len(batch['intents']),1)
        self.assertEqual(batch['intents'][0]['command_id'],'file.replace')
        self.assertEqual(planned.plan_artifact['proposed_final_state'][0]['value'],{'$int':'1'})

    def test_local_cannot_shadow_state_or_parameter(self):
        state_shadow='''
        script Demo version "2.0.0";
        state x:Int=0;
        action bad() { let x:Int=1; set x=1; }
        entry main=bad();
        '''
        with self.assertRaises(TevScriptError): compile_effect_program_v2(state_shadow)
        param_shadow='''
        script Demo version "2.0.0";
        state x:Int=0;
        action bad(p:Int) { let p:Int=1; set x=p; }
        entry main=bad(2);
        '''
        with self.assertRaises(TevScriptError): compile_effect_program_v2(param_shadow)


if __name__=="__main__": unittest.main()
