from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effects import (
    build_capability_table_v4,
    build_effect_action_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
    execute_effect_action_v4,
    initial_state_v4,
)
from tev_script.ir_v4_values import build_type_table_v4


def table():
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


def cint(n:int): return {"op":"CONST","type":"Int","value":{"$int":str(n)}}
def load_state(name:str): return {"op":"LOAD_STATE","name":name,"type":"Int"}
def load_param(name:str): return {"op":"LOAD_PARAM","name":name,"type":"Int"}
def load_local(name:str): return {"op":"LOAD_LOCAL","name":name,"type":"Int"}
def plus(a,b): return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}
def gt(a,b): return {"op":"BINARY","operator":"GT","left_type":"Int","right_type":"Int","result_type":"Bool","left":a,"right":b}


class IrV4EffectsTests(unittest.TestCase):
    def setUp(self):
        self.table=table()
        self.states=build_state_schema_v4([
            {"name":"count","type":"Int","initial":{"$int":"0"}},
            {"name":"last","type":"Int","initial":{"$int":"0"}},
        ],self.table)
        self.capabilities=build_capability_table_v4([
            {"capability_id":"sensor.read","parameters":["Int"],"return_type":"Int","kind":"observation"},
        ],self.table)
        contract=self.capabilities.contracts[0]
        self.action=build_effect_action_v4({
            "action_id":"tick",
            "parameters":[{"name":"bias","type":"Int"}],
            "steps":[
                {"op":"OBSERVE","capability_id":"sensor.read","arguments":[load_state("count")],"bind":"sample"},
                {"op":"LET_LOCAL","name":"next","type":"Int","value":plus(load_local("sample"),load_param("bias"))},
                {"op":"SET_STATE","state":"last","value":load_local("sample")},
                {"op":"SET_STATE","state":"count","value":load_local("next")},
                {"op":"ASSERT","condition":gt(load_state("count"),cint(0))},
            ],
        },self.table,self.states,self.capabilities)
        self.scenario=build_effect_scenario_v4({
            "capability_table_hash":self.capabilities.table_hash,
            "capabilities":[{
                "capability_id":"sensor.read","contract_hash":contract.contract_hash,
                "calls":[{"arguments":[{"$int":"2"}],"return":{"$int":"10"}}],
            }],
        },self.table,self.capabilities)

    def test_transaction_executes_observation_and_commits_final_state(self):
        current={"count":2,"last":0}
        before=copy.deepcopy(current)
        receipt=execute_effect_action_v4(self.action,self.table,self.states,self.capabilities,self.scenario,current,[3])
        self.assertEqual(current,before)
        final={item["name"]:item["value"] for item in receipt.final_state}
        self.assertEqual(final["count"],{"$int":"13"})
        self.assertEqual(final["last"],{"$int":"10"})
        self.assertEqual(receipt.observation_calls,1)
        self.assertEqual(receipt.capability_transcript[0]["arguments"],[{"$int":"2"}])
        self.assertEqual(receipt.capability_transcript[0]["return"],{"$int":"10"})

    def test_exact_replay_is_receipt_deterministic(self):
        a=execute_effect_action_v4(self.action,self.table,self.states,self.capabilities,self.scenario,{"count":2,"last":0},[3])
        b=execute_effect_action_v4(self.action,self.table,self.states,self.capabilities,self.scenario,{"last":0,"count":2},[3])
        self.assertEqual(a.receipt_hash,b.receipt_hash)
        self.assertEqual(a.final_state_hash,b.final_state_hash)
        self.assertEqual(a.capability_transcript_hash,b.capability_transcript_hash)

    def test_assert_failure_is_fail_closed_and_input_state_is_unchanged(self):
        current={"count":2,"last":0}
        bad_action=build_effect_action_v4({
            "action_id":"reject",
            "parameters":[],
            "steps":[
                {"op":"SET_STATE","state":"count","value":cint(99)},
                {"op":"ASSERT","condition":gt(cint(0),cint(1))},
            ],
        },self.table,self.states,self.capabilities)
        empty=build_effect_scenario_v4({"capability_table_hash":self.capabilities.table_hash,"capabilities":[]},self.table,self.capabilities)
        with self.assertRaises(TevScriptError) as captured:
            execute_effect_action_v4(bad_action,self.table,self.states,self.capabilities,empty,current,[])
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_ASSERT")
        self.assertEqual(current,{"count":2,"last":0})

    def test_scripted_argument_divergence_fails_closed(self):
        contract=self.capabilities.contracts[0]
        wrong=build_effect_scenario_v4({
            "capability_table_hash":self.capabilities.table_hash,
            "capabilities":[{"capability_id":"sensor.read","contract_hash":contract.contract_hash,"calls":[{"arguments":[{"$int":"3"}],"return":{"$int":"10"}}]}],
        },self.table,self.capabilities)
        with self.assertRaises(TevScriptError) as captured:
            execute_effect_action_v4(self.action,self.table,self.states,self.capabilities,wrong,{"count":2,"last":0},[3])
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_CAPABILITY_ARGUMENTS")

    def test_script_overflow_and_underflow_are_distinct_fail_closed_cases(self):
        contract=self.capabilities.contracts[0]
        no_calls=build_effect_scenario_v4({
            "capability_table_hash":self.capabilities.table_hash,
            "capabilities":[{"capability_id":"sensor.read","contract_hash":contract.contract_hash,"calls":[]}],
        },self.table,self.capabilities)
        with self.assertRaises(TevScriptError) as captured:
            execute_effect_action_v4(self.action,self.table,self.states,self.capabilities,no_calls,{"count":2,"last":0},[3])
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_CAPABILITY_OVERFLOW")

        passive=build_effect_action_v4({"action_id":"passive","parameters":[],"steps":[{"op":"SET_STATE","state":"count","value":cint(1)}]},self.table,self.states,self.capabilities)
        with self.assertRaises(TevScriptError) as captured:
            execute_effect_action_v4(passive,self.table,self.states,self.capabilities,self.scenario,{"count":2,"last":0},[])
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_CAPABILITY_UNDERFLOW")

    def test_physical_effect_capability_is_not_admitted_in_r1(self):
        with self.assertRaises(TevScriptError) as captured:
            build_capability_table_v4([{"capability_id":"file.write","parameters":["Text"],"return_type":"Int","kind":"effect"}],self.table)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_CAPABILITY_KIND")

    def test_capability_contract_and_table_hash_bind_signature(self):
        changed=build_capability_table_v4([
            {"capability_id":"sensor.read","parameters":[],"return_type":"Int","kind":"observation"},
        ],self.table)
        self.assertNotEqual(changed.table_hash,self.capabilities.table_hash)
        self.assertNotEqual(changed.contracts[0].contract_hash,self.capabilities.contracts[0].contract_hash)

    def test_state_schema_hash_separates_type_from_initial_value(self):
        other_initial=build_state_schema_v4([
            {"name":"count","type":"Int","initial":{"$int":"7"}},
            {"name":"last","type":"Int","initial":{"$int":"0"}},
        ],self.table)
        self.assertEqual(other_initial.schema_hash,self.states.schema_hash)
        self.assertNotEqual(other_initial.initial_state_hash,self.states.initial_state_hash)
        self.assertEqual(initial_state_v4(other_initial),{"count":7,"last":0})

    def test_state_and_parameter_shadowing_are_rejected(self):
        with self.assertRaises(TevScriptError):
            build_effect_action_v4({"action_id":"bad","parameters":[{"name":"count","type":"Int"}],"steps":[{"op":"SET_STATE","state":"count","value":cint(1)}]},self.table,self.states,self.capabilities)
        with self.assertRaises(TevScriptError):
            build_effect_action_v4({"action_id":"bad","parameters":[{"name":"x","type":"Int"}],"steps":[{"op":"LET_LOCAL","name":"x","type":"Int","value":cint(1)}]},self.table,self.states,self.capabilities)

    def test_action_hash_binds_state_schema_and_capability_contracts(self):
        same=build_effect_action_v4({
            "action_id":"tick","parameters":[{"name":"bias","type":"Int"}],"steps":[
                {"op":"OBSERVE","capability_id":"sensor.read","arguments":[load_state("count")],"bind":"sample"},
                {"op":"LET_LOCAL","name":"next","type":"Int","value":plus(load_local("sample"),load_param("bias"))},
                {"op":"SET_STATE","state":"last","value":load_local("sample")},
                {"op":"SET_STATE","state":"count","value":load_local("next")},
                {"op":"ASSERT","condition":gt(load_state("count"),cint(0))},
            ]},self.table,self.states,self.capabilities)
        self.assertEqual(same.action_hash,self.action.action_hash)
        changed_caps=build_capability_table_v4([{"capability_id":"sensor.read","parameters":["Int"],"return_type":"Text","kind":"observation"}],self.table)
        probe_original=build_effect_action_v4({"action_id":"probe","parameters":[],"steps":[{"op":"OBSERVE","capability_id":"sensor.read","arguments":[load_state("count")],"bind":"sample"}]},self.table,self.states,self.capabilities)
        probe_changed=build_effect_action_v4({"action_id":"probe","parameters":[],"steps":[{"op":"OBSERVE","capability_id":"sensor.read","arguments":[load_state("count")],"bind":"sample"}]},self.table,self.states,changed_caps)
        self.assertNotEqual(probe_original.action_hash,probe_changed.action_hash)


if __name__=="__main__": unittest.main()
