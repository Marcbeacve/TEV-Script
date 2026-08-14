from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_effect_commands import (
    EffectCommitLedgerV4,
    build_effect_action_r2_v4,
    build_effect_authority_grant_v4,
    build_effect_command_table_v4,
    build_effect_provider_descriptor_v4,
    build_provider_batch_observation_v4,
    commit_effect_command_batch_v4,
    effect_authority_grant_to_dict_v4,
    effect_command_batch_to_dict_v4,
    effect_command_commit_receipt_to_dict_v4,
    effect_provider_descriptor_to_dict_v4,
    finalized_effect_transition_to_dict_v4,
    finalize_effect_transition_v4,
    load_effect_authority_grant_v4,
    load_effect_command_batch_v4,
    load_effect_command_commit_receipt_v4,
    load_effect_provider_descriptor_v4,
    load_planned_effect_transition_v4,
    plan_effect_action_r2_v4,
    planned_effect_transition_to_dict_v4,
)
from tev_script.ir_v4_effects import build_capability_table_v4, build_effect_scenario_v4, build_state_schema_v4
from tev_script.ir_v4_values import build_type_table_v4


def sha(text): return hashlib.sha256(text.encode()).hexdigest()
def cint(n): return {"op":"CONST","type":"Int","value":{"$int":str(n)}}
def state(name): return {"op":"LOAD_STATE","name":name,"type":"Int"}
def param(name): return {"op":"LOAD_PARAM","name":name,"type":"Int"}
def plus(a,b): return {"op":"BINARY","operator":"PLUS","left_type":"Int","right_type":"Int","result_type":"Int","left":a,"right":b}


class Provider:
    def __init__(self, descriptor): self._descriptor=descriptor; self.calls=0
    @property
    def descriptor(self): return self._descriptor
    def commit_batch(self,batch,authority):
        self.calls+=1
        return build_provider_batch_observation_v4(
            batch_hash=batch.batch_hash,
            provider_descriptor_hash=self.descriptor.descriptor_hash,
            authority_grant_hash=authority.grant_hash,
            status="PASS",
            intent_receipts=[(intent.intent_hash,sha("fx:"+intent.intent_hash)) for intent in batch.intents],
            provider_batch_receipt_hash=sha("batch:"+batch.batch_hash),
        )


class EffectCommandArtifactsV4Tests(unittest.TestCase):
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
        self.plan=plan_effect_action_r2_v4(self.action,self.table,self.states,self.caps,self.commands,self.scenario,{"count":2},[3])
        self.descriptor=build_effect_provider_descriptor_v4(provider_id="provider.atomic",provider_version="1",provider_implementation_hash="a"*64,supported_contract_hashes=[self.commands.contracts[0].contract_hash])

    def detach(self,value): return json.loads(json.dumps(value,sort_keys=True,separators=(",",":")))

    def test_plan_and_batch_artifacts_roundtrip_without_python_identity(self):
        plan_wire=self.detach(planned_effect_transition_to_dict_v4(self.plan))
        loaded=load_planned_effect_transition_v4(plan_wire)
        self.assertEqual(loaded.planning_receipt_hash,self.plan.planning_receipt_hash)
        self.assertEqual(loaded.command_batch.batch_hash,self.plan.command_batch.batch_hash)
        batch=load_effect_command_batch_v4(self.detach(effect_command_batch_to_dict_v4(self.plan.command_batch)))
        self.assertEqual(batch,self.plan.command_batch)

    def test_descriptor_and_grant_artifacts_roundtrip(self):
        descriptor=load_effect_provider_descriptor_v4(self.detach(effect_provider_descriptor_to_dict_v4(self.descriptor)))
        grant=build_effect_authority_grant_v4(descriptor,self.plan.command_batch,allowed_contract_hashes=[self.commands.contracts[0].contract_hash],authority_scope_hash="b"*64)
        loaded=load_effect_authority_grant_v4(self.detach(effect_authority_grant_to_dict_v4(grant)))
        self.assertEqual(loaded.grant_hash,grant.grant_hash)
        self.assertEqual(loaded.batch_hash,self.plan.command_batch.batch_hash)

    def test_full_detached_lifecycle_plan_authorize_commit_finalize(self):
        loaded_plan=load_planned_effect_transition_v4(self.detach(planned_effect_transition_to_dict_v4(self.plan)))
        loaded_descriptor=load_effect_provider_descriptor_v4(self.detach(effect_provider_descriptor_to_dict_v4(self.descriptor)))
        grant=build_effect_authority_grant_v4(loaded_descriptor,loaded_plan.command_batch,allowed_contract_hashes=[self.commands.contracts[0].contract_hash],authority_scope_hash="c"*64)
        loaded_grant=load_effect_authority_grant_v4(self.detach(effect_authority_grant_to_dict_v4(grant)))
        provider=Provider(loaded_descriptor)
        commit=commit_effect_command_batch_v4(loaded_plan.command_batch,provider,loaded_grant,EffectCommitLedgerV4())
        loaded_commit=load_effect_command_commit_receipt_v4(self.detach(effect_command_commit_receipt_to_dict_v4(commit)))
        final=finalize_effect_transition_v4(loaded_plan,loaded_commit)
        final_wire=self.detach(finalized_effect_transition_to_dict_v4(final))
        self.assertEqual(final_wire["final_state"][0]["value"],{"$int":"5"})
        self.assertEqual(final_wire["batch_hash"],loaded_plan.command_batch.batch_hash)
        self.assertEqual(provider.calls,1)

    def test_plan_artifact_tamper_is_rejected(self):
        wire=planned_effect_transition_to_dict_v4(self.plan)
        tampered=copy.deepcopy(wire)
        tampered["proposed_final_state"][0]["value"]={"$int":"9"}
        with self.assertRaises(TevScriptError) as captured: load_planned_effect_transition_v4(tampered)
        self.assertIn(captured.exception.diagnostic.code,{"TEVS_IR_V4_COMMAND_PLAN_STATE","TEVS_IR_V4_COMMAND_ARTIFACT_HASH"})

    def test_batch_artifact_idempotency_tamper_is_rejected(self):
        wire=effect_command_batch_to_dict_v4(self.plan.command_batch)
        tampered=copy.deepcopy(wire); tampered["intents"][0]["idempotency_key"]="0"*64
        with self.assertRaises(TevScriptError) as captured: load_effect_command_batch_v4(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_COMMAND_IDEMPOTENCY_HASH")

    def test_provider_descriptor_artifact_hash_tamper_is_rejected(self):
        wire=effect_provider_descriptor_to_dict_v4(self.descriptor)
        tampered=copy.deepcopy(wire); tampered["provider_version"]="2"
        with self.assertRaises(TevScriptError) as captured: load_effect_provider_descriptor_v4(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_COMMAND_PROVIDER_DESCRIPTOR_HASH")

    def test_authority_artifact_hash_tamper_is_rejected(self):
        grant=build_effect_authority_grant_v4(self.descriptor,self.plan.command_batch,allowed_contract_hashes=[self.commands.contracts[0].contract_hash],authority_scope_hash="d"*64)
        wire=effect_authority_grant_to_dict_v4(grant); tampered=copy.deepcopy(wire); tampered["authority_scope_hash"]="e"*64
        with self.assertRaises(TevScriptError) as captured: load_effect_authority_grant_v4(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_COMMAND_AUTHORITY_HASH")

    def test_commit_artifact_hash_tamper_is_rejected(self):
        grant=build_effect_authority_grant_v4(self.descriptor,self.plan.command_batch,allowed_contract_hashes=[self.commands.contracts[0].contract_hash],authority_scope_hash="f"*64)
        commit=commit_effect_command_batch_v4(self.plan.command_batch,Provider(self.descriptor),grant,EffectCommitLedgerV4())
        wire=effect_command_commit_receipt_to_dict_v4(commit); tampered=copy.deepcopy(wire); tampered["provider_batch_receipt_hash"]="0"*64
        with self.assertRaises(TevScriptError) as captured: load_effect_command_commit_receipt_v4(tampered)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_COMMAND_COMMIT_RECEIPT_HASH")


if __name__=="__main__": unittest.main()
