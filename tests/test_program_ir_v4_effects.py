from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effects import (
    build_capability_table_v4,
    build_effect_action_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
    execute_effect_action_v4,
)
from tev_script.ir_v4_values import build_type_table_v4
from tev_script.program_ir_v4 import (
    build_program_ir_v4_effects,
    canonical_program_ir_v4_bytes,
    run_program_ir_v4,
    run_program_ir_v4_effects,
    validate_program_ir_v4,
    validate_program_ir_v4_effects,
    validate_program_ir_v4_pure,
    validate_program_ir_v4_recursive,
)


def _table():
    return build_type_table_v4({
        "boundary":{"maximum_value_nesting":128},
        "types":[
            {"type_id":"Bool","kind":"primitive"},
            {"type_id":"Int","kind":"primitive"},
            {"type_id":"Rat","kind":"primitive"},
            {"type_id":"Text","kind":"primitive"},
            {"type_id":"Unit","kind":"unit"},
            {"type_id":"Vec2","kind":"primitive"},
            {"type_id":"Vec3","kind":"primitive"},
        ],
    })

def cint(n): return {"op":"CONST","type":"Int","value":{"$int":str(n)}}
def load_state(n): return {"op":"LOAD_STATE","name":n,"type":"Int"}
def load_param(n): return {"op":"LOAD_PARAM","name":n,"type":"Int"}
def load_local(n): return {"op":"LOAD_LOCAL","name":n,"type":"Int"}
def plus(a,b): return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}

def _rehash(ir):
    payload=dict(ir); payload.pop("program_ir_hash",None)
    ir["program_ir_hash"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


class ProgramIRV4EffectsTests(unittest.TestCase):
    def setUp(self):
        self.table=_table()
        self.states=build_state_schema_v4([
            {"name":"count","type":"Int","initial":{"$int":"0"}},
            {"name":"last","type":"Int","initial":{"$int":"0"}},
        ],self.table)
        self.caps=build_capability_table_v4([
            {"capability_id":"sensor.read","parameters":["Int"],"return_type":"Int","kind":"observation"},
        ],self.table)
        c=self.caps.contracts[0]
        self.action=build_effect_action_v4({
            "action_id":"tick","parameters":[{"name":"bias","type":"Int"}],"steps":[
                {"op":"OBSERVE","capability_id":"sensor.read","arguments":[load_state("count")],"bind":"sample"},
                {"op":"SET_STATE","state":"last","value":load_local("sample")},
                {"op":"SET_STATE","state":"count","value":plus(load_local("sample"),load_param("bias"))},
            ]},self.table,self.states,self.caps)
        self.scenario=build_effect_scenario_v4({
            "capability_table_hash":self.caps.table_hash,
            "capabilities":[{"capability_id":"sensor.read","contract_hash":c.contract_hash,"calls":[{"arguments":[{"$int":"2"}],"return":{"$int":"10"}}]}],
        },self.table,self.caps)
        self.source_hash="1"*64

    def ir(self):
        return build_program_ir_v4_effects(
            program_id="Demo",source_semantic_hash=self.source_hash,table=self.table,states=self.states,
            capabilities=self.caps,action=self.action,scenario=self.scenario,current_state={"count":2,"last":0},arguments=[3],
        )

    def test_detached_json_matches_direct_transition(self):
        direct=execute_effect_action_v4(self.action,self.table,self.states,self.caps,self.scenario,{"count":2,"last":0},[3])
        ir=self.ir(); detached=json.loads(canonical_program_ir_v4_bytes(ir).decode())
        validation=validate_program_ir_v4_effects(detached)
        portable=run_program_ir_v4_effects(detached)
        self.assertEqual(portable.final_state,direct.final_state)
        self.assertEqual(portable.final_state_hash,direct.final_state_hash)
        self.assertEqual(portable.capability_transcript_hash,direct.capability_transcript_hash)
        self.assertEqual(portable.transition_receipt_hash,direct.receipt_hash)
        self.assertEqual(validation.action_hash,self.action.action_hash)
        self.assertEqual(validation.scenario_hash,self.scenario.scenario_hash)

    def test_general_dispatch_accepts_effects_profile(self):
        ir=self.ir()
        validation=validate_program_ir_v4(ir)
        receipt=run_program_ir_v4(ir)
        self.assertEqual(validation.program_ir_hash,ir["program_ir_hash"])
        self.assertEqual(receipt.final_state_hash,run_program_ir_v4_effects(ir).final_state_hash)

    def test_state_schema_tamper_rejected_after_outer_rehash(self):
        tampered=copy.deepcopy(self.ir())
        tampered["state_schema"]["states"][0]["type"]="Text"
        _rehash(tampered)
        with self.assertRaises(TevScriptError): validate_program_ir_v4_effects(tampered)

    def test_capability_contract_tamper_rejected_after_outer_rehash(self):
        tampered=copy.deepcopy(self.ir())
        tampered["capabilities"]["contracts"][0]["return_type"]="Text"
        _rehash(tampered)
        with self.assertRaises(TevScriptError): validate_program_ir_v4_effects(tampered)

    def test_action_tamper_rejected_after_outer_rehash(self):
        tampered=copy.deepcopy(self.ir())
        tampered["action"]["steps"][1]["state"]="count"
        _rehash(tampered)
        with self.assertRaises(TevScriptError) as captured: validate_program_ir_v4_effects(tampered)
        self.assertIn(captured.exception.diagnostic.code,{"TEVS_PROGRAM_IR_V4_EFFECTS_ACTION_HASH","TEVS_PROGRAM_IR_V4_EFFECTS_ACTION_BOUND"})

    def test_scenario_return_tamper_rejected_after_outer_rehash(self):
        tampered=copy.deepcopy(self.ir())
        tampered["scenario"]["capabilities"][0]["calls"][0]["return"]={"$int":"11"}
        _rehash(tampered)
        with self.assertRaises(TevScriptError) as captured: validate_program_ir_v4_effects(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_EFFECTS_SCENARIO_HASH")

    def test_current_state_tamper_without_outer_rehash_rejected(self):
        tampered=copy.deepcopy(self.ir())
        tampered["execution"]["current_state"][0]["value"]={"$int":"3"}
        with self.assertRaises(TevScriptError) as captured: validate_program_ir_v4_effects(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_HASH")

    def test_valid_rehashed_current_state_replacement_is_blocked_by_external_pin(self):
        original=self.ir(); expected=original["program_ir_hash"]
        replacement=copy.deepcopy(original)
        replacement["execution"]["current_state"][0]["value"]={"$int":"3"}
        # Scenario must match new observed argument too, making replacement internally valid.
        replacement["scenario"]["capabilities"][0]["calls"][0]["arguments"]=[{"$int":"3"}]
        # Rebuild scenario hash from semantic objects by constructing a new artifact is simpler and stronger.
        c=self.caps.contracts[0]
        scenario2=build_effect_scenario_v4({"capability_table_hash":self.caps.table_hash,"capabilities":[{"capability_id":"sensor.read","contract_hash":c.contract_hash,"calls":[{"arguments":[{"$int":"3"}],"return":{"$int":"10"}}]}]},self.table,self.caps)
        replacement=build_program_ir_v4_effects(program_id="Demo",source_semantic_hash=self.source_hash,table=self.table,states=self.states,capabilities=self.caps,action=self.action,scenario=scenario2,current_state={"count":3,"last":0},arguments=[3])
        validate_program_ir_v4_effects(replacement)
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_effects(replacement,expected_program_ir_hash=expected)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_EXPECTED_HASH")

    def test_source_semantic_pin_is_enforced(self):
        ir=self.ir()
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_effects(ir,expected_source_semantic_hash="2"*64)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_EXPECTED_SOURCE")

    def test_pure_and_recursive_validators_do_not_reinterpret_effects(self):
        ir=self.ir()
        for validator in (validate_program_ir_v4_pure,validate_program_ir_v4_recursive):
            with self.assertRaises(TevScriptError): validator(ir)


if __name__=="__main__": unittest.main()
