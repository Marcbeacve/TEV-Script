from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effects import (
    OBSERVE_ALL_RESERVATION_POLICY_V4,
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
        "boundary":{"maximum_value_nesting":32},
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
def load_local(name:str): return {"op":"LOAD_LOCAL","name":name,"type":"Int"}
def plus(a,b): return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}


class IrV4ObserveAllR1Tests(unittest.TestCase):
    def setUp(self):
        self.table=table()
        self.states=build_state_schema_v4([
            {"name":"sum","type":"Int","initial":{"$int":"0"}},
        ],self.table)
        self.capabilities=build_capability_table_v4([
            {"capability_id":"sensor.read","parameters":["Int"],"return_type":"Int","kind":"observation"},
        ],self.table)
        self.contract=self.capabilities.require("sensor.read")

    def action(self, observations):
        return build_effect_action_v4({
            "action_id":"sample_pair",
            "parameters":[],
            "steps":[
                {
                    "op":"OBSERVE_ALL",
                    "reservation_policy":OBSERVE_ALL_RESERVATION_POLICY_V4,
                    "observations":observations,
                },
                {"op":"SET_STATE","state":"sum","value":plus(load_local("a"),load_local("b"))},
            ],
        },self.table,self.states,self.capabilities)

    def scenario(self, first=10, second=20):
        return build_effect_scenario_v4({
            "capability_table_hash":self.capabilities.table_hash,
            "capabilities":[{
                "capability_id":"sensor.read",
                "contract_hash":self.contract.contract_hash,
                "calls":[
                    {"arguments":[{"$int":"1"}],"return":{"$int":str(first)}},
                    {"arguments":[{"$int":"2"}],"return":{"$int":str(second)}},
                ],
            }],
        },self.table,self.capabilities)

    def observations(self, reverse=False):
        items=[
            {"bind":"a","capability_id":"sensor.read","arguments":[cint(1)]},
            {"bind":"b","capability_id":"sensor.read","arguments":[cint(2)]},
        ]
        return list(reversed(items)) if reverse else items

    def test_same_capability_calls_are_reserved_by_canonical_bind_order(self):
        action=self.action(self.observations(reverse=True))
        receipt=execute_effect_action_v4(
            action,self.table,self.states,self.capabilities,self.scenario(),initial_state_v4(self.states),
        )
        self.assertEqual(receipt.observation_calls,2)
        self.assertEqual([item["call_index"] for item in receipt.capability_transcript],[0,1])
        self.assertEqual([item["return"] for item in receipt.capability_transcript],[{"$int":"10"},{"$int":"20"}])
        self.assertEqual(receipt.final_state[0]["value"],{"$int":"30"})

    def test_declaration_order_is_surface_only(self):
        a=self.action(self.observations(False))
        b=self.action(self.observations(True))
        self.assertEqual(a.action_hash,b.action_hash)
        self.assertEqual(a.steps,b.steps)

    def test_sibling_result_is_not_visible_to_sibling_arguments(self):
        observations=[
            {"bind":"a","capability_id":"sensor.read","arguments":[cint(1)]},
            {"bind":"b","capability_id":"sensor.read","arguments":[load_local("a")]},
        ]
        with self.assertRaises(TevScriptError):
            self.action(observations)

    def test_reservation_policy_is_semantic_and_forgery_fails_closed(self):
        raw={
            "action_id":"bad",
            "parameters":[],
            "steps":[{
                "op":"OBSERVE_ALL",
                "reservation_policy":"locked_shared_cursor_v0",
                "observations":self.observations(),
            }],
        }
        with self.assertRaises(TevScriptError) as captured:
            build_effect_action_v4(raw,self.table,self.states,self.capabilities)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_OBSERVE_ALL_POLICY")

    def test_group_is_bounded_and_binds_are_unique(self):
        too_many=[{"bind":f"x{i}","capability_id":"sensor.read","arguments":[cint(i)]} for i in range(65)]
        with self.assertRaises(TevScriptError) as captured:
            self.action(too_many)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_OBSERVE_ALL_BOUND")
        duplicate=[
            {"bind":"a","capability_id":"sensor.read","arguments":[cint(1)]},
            {"bind":"a","capability_id":"sensor.read","arguments":[cint(2)]},
        ]
        with self.assertRaises(TevScriptError): self.action(duplicate)

    def test_argument_mismatch_fails_before_transition_receipt(self):
        action=self.action(self.observations())
        bad=build_effect_scenario_v4({
            "capability_table_hash":self.capabilities.table_hash,
            "capabilities":[{
                "capability_id":"sensor.read","contract_hash":self.contract.contract_hash,
                "calls":[
                    {"arguments":[{"$int":"1"}],"return":{"$int":"10"}},
                    {"arguments":[{"$int":"999"}],"return":{"$int":"20"}},
                ],
            }],
        },self.table,self.capabilities)
        with self.assertRaises(TevScriptError) as captured:
            execute_effect_action_v4(action,self.table,self.states,self.capabilities,bad,initial_state_v4(self.states))
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_EFFECT_CAPABILITY_ARGUMENTS")


if __name__=="__main__": unittest.main()
