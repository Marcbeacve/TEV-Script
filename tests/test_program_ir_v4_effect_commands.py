from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effect_commands import build_effect_action_r2_v4, build_effect_command_table_v4, plan_effect_action_r2_v4
from tev_script.ir_v4_effects import build_capability_table_v4, build_effect_scenario_v4, build_state_schema_v4
from tev_script.ir_v4_values import build_type_table_v4
from tev_script.program_ir_v4_effect_commands import (
    build_program_ir_v4_effects_r2,
    canonical_program_ir_v4_effects_r2_bytes,
    plan_program_ir_v4_effects_r2,
    validate_program_ir_v4_effects_r2,
)


def cint(n): return {"op":"CONST","type":"Int","value":{"$int":str(n)}}
def state(n): return {"op":"LOAD_STATE","name":n,"type":"Int"}
def param(n): return {"op":"LOAD_PARAM","name":n,"type":"Int"}
def plus(a,b): return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}
def rehash(ir):
    payload=dict(ir); payload.pop("program_ir_hash",None)
    ir["program_ir_hash"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


class ProgramIRV4EffectsR2Tests(unittest.TestCase):
    def setUp(self):
        self.table=build_type_table_v4({"boundary":{"maximum_value_nesting":128},"types":[
            {"type_id":"Bool","kind":"primitive"},{"type_id":"Int","kind":"primitive"},{"type_id":"Rat","kind":"primitive"},
            {"type_id":"Text","kind":"primitive"},{"type_id":"Unit","kind":"unit"},{"type_id":"Vec2","kind":"primitive"},{"type_id":"Vec3","kind":"primitive"},
        ]})
        self.states=build_state_schema_v4([{"name":"count","type":"Int","initial":{"$int":"0"}}],self.table)
        self.caps=build_capability_table_v4([],self.table)
        self.scenario=build_effect_scenario_v4({"capability_table_hash":self.caps.table_hash,"capabilities":[]},self.table,self.caps)
        self.commands=build_effect_command_table_v4([{"command_id":"file.write","parameters":["Int"],"kind":"effect_command","idempotency_policy":"content_addressed_v1"}],self.table)
        self.action=build_effect_action_r2_v4({"action_id":"save","parameters":[{"name":"bias","type":"Int"}],"steps":[
            {"op":"SET_STATE","state":"count","value":plus(state("count"),param("bias"))},
            {"op":"REQUEST_EFFECT","command_id":"file.write","arguments":[state("count")]},
        ]},self.table,self.states,self.caps,self.commands)
        self.source_hash="1"*64

    def ir(self,*,count=2,bias=3):
        return build_program_ir_v4_effects_r2(
            program_id="Demo",source_semantic_hash=self.source_hash,table=self.table,states=self.states,
            capabilities=self.caps,commands=self.commands,action=self.action,scenario=self.scenario,
            current_state={"count":count},arguments=[bias],
        )

    def test_detached_program_ir_plans_same_transition_as_direct_kernel(self):
        ir=self.ir(); detached=json.loads(canonical_program_ir_v4_effects_r2_bytes(ir).decode())
        validation=validate_program_ir_v4_effects_r2(detached)
        result=plan_program_ir_v4_effects_r2(detached)
        direct=plan_effect_action_r2_v4(self.action,self.table,self.states,self.caps,self.commands,self.scenario,{"count":2},[3])
        self.assertEqual(result.receipt.status,"PLANNED_NOT_FINALIZED")
        self.assertEqual(result.receipt.planning_receipt_hash,direct.planning_receipt_hash)
        self.assertEqual(result.receipt.command_batch_hash,direct.command_batch.batch_hash)
        self.assertEqual(result.receipt.proposed_final_state_hash,direct.proposed_final_state_hash)
        self.assertEqual(result.plan_artifact["proposed_final_state"][0]["value"],{"$int":"5"})
        self.assertEqual(validation.program_ir_hash,ir["program_ir_hash"])

    def test_program_ir_hash_binds_execution_instance_not_source_semantics(self):
        a=self.ir(count=2); b=self.ir(count=3)
        self.assertEqual(a["source"]["semantic_hash"],b["source"]["semantic_hash"])
        self.assertNotEqual(a["program_ir_hash"],b["program_ir_hash"])
        self.assertNotEqual(plan_program_ir_v4_effects_r2(a).receipt.command_batch_hash,plan_program_ir_v4_effects_r2(b).receipt.command_batch_hash)

    def test_command_contract_tamper_rejected_after_outer_rehash(self):
        ir=self.ir(); tampered=copy.deepcopy(ir)
        tampered["commands"]["contracts"][0]["parameters"]=[]
        rehash(tampered)
        with self.assertRaises(TevScriptError): validate_program_ir_v4_effects_r2(tampered)

    def test_action_tamper_rejected_after_outer_rehash(self):
        ir=self.ir(); tampered=copy.deepcopy(ir)
        tampered["action"]["steps"][1]["arguments"]=[cint(99)]
        rehash(tampered)
        with self.assertRaises(TevScriptError) as captured: validate_program_ir_v4_effects_r2(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_R2_ACTION_HASH")

    def test_scenario_hash_tamper_rejected(self):
        ir=self.ir(); tampered=copy.deepcopy(ir); tampered["scenario"]["scenario_hash"]="0"*64; rehash(tampered)
        with self.assertRaises(TevScriptError) as captured: validate_program_ir_v4_effects_r2(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_R2_SCENARIO_HASH")

    def test_current_state_tamper_without_outer_hash_is_rejected(self):
        ir=self.ir(); tampered=copy.deepcopy(ir); tampered["execution"]["current_state"][0]["value"]={"$int":"9"}
        with self.assertRaises(TevScriptError) as captured: validate_program_ir_v4_effects_r2(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_R2_HASH")

    def test_external_program_and_source_pins_are_enforced(self):
        ir=self.ir()
        with self.assertRaises(TevScriptError) as captured:
            plan_program_ir_v4_effects_r2(ir,expected_program_ir_hash="0"*64)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_R2_EXPECTED_HASH")
        with self.assertRaises(TevScriptError) as captured:
            plan_program_ir_v4_effects_r2(ir,expected_source_semantic_hash="2"*64)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_R2_EXPECTED_SOURCE")

    def test_plan_artifact_hash_is_bound_into_plan_receipt(self):
        result=plan_program_ir_v4_effects_r2(self.ir())
        self.assertEqual(result.receipt.plan_artifact_hash,result.plan_artifact["artifact_hash"])
        self.assertEqual(len(result.receipt.receipt_hash),64)


    def test_detached_program_ir_preserves_r2_observe_all_and_causal_batch(self):
        caps=build_capability_table_v4([{"capability_id":"sensor.read","parameters":["Int"],"return_type":"Int","kind":"observation"}],self.table)
        sensor=caps.require("sensor.read")
        scenario=build_effect_scenario_v4({"capability_table_hash":caps.table_hash,"capabilities":[{"capability_id":"sensor.read","contract_hash":sensor.contract_hash,"calls":[{"arguments":[{"$int":"1"}],"return":{"$int":"10"}},{"arguments":[{"$int":"2"}],"return":{"$int":"20"}}]}]},self.table,caps)
        action=build_effect_action_r2_v4({"action_id":"async_save","parameters":[],"steps":[{"op":"OBSERVE_ALL","reservation_policy":"canonical_bind_then_capability_ordinal_v1","observations":[{"bind":"b","capability_id":"sensor.read","arguments":[cint(2)]},{"bind":"a","capability_id":"sensor.read","arguments":[cint(1)]}]},{"op":"REQUEST_EFFECT","command_id":"file.write","arguments":[{"op":"LOAD_LOCAL","name":"a","type":"Int"}]}]},self.table,self.states,caps,self.commands)
        ir=build_program_ir_v4_effects_r2(program_id="AsyncR2",source_semantic_hash=self.source_hash,table=self.table,states=self.states,capabilities=caps,commands=self.commands,action=action,scenario=scenario,current_state={"count":0},arguments=[])
        detached=json.loads(canonical_program_ir_v4_effects_r2_bytes(ir).decode())
        self.assertEqual(detached["action"]["steps"][0]["op"],"OBSERVE_ALL")
        self.assertEqual([item["bind"] for item in detached["action"]["steps"][0]["observations"]],["a","b"])
        result=plan_program_ir_v4_effects_r2(detached)
        direct=plan_effect_action_r2_v4(action,self.table,self.states,caps,self.commands,scenario,{"count":0},[])
        self.assertEqual(result.receipt.planning_receipt_hash,direct.planning_receipt_hash)
        self.assertEqual(result.receipt.command_batch_hash,direct.command_batch.batch_hash)
        self.assertEqual([row["call_index"] for row in result.plan_artifact["capability_transcript"]],[0,1])
        self.assertEqual(result.plan_artifact["command_batch"]["intents"][0]["arguments"],[{"$int":"10"}])

if __name__=="__main__": unittest.main()
