from __future__ import annotations

from dataclasses import replace
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
    finalize_effect_transition_v4,
    plan_effect_action_r2_v4,
    validate_planned_effect_transition_v4,
)
from tev_script.ir_v4_effects import (
    build_capability_table_v4,
    build_effect_scenario_v4,
    build_state_schema_v4,
)
from tev_script.ir_v4_values import build_type_table_v4


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_value(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _table():
    return build_type_table_v4({
        "boundary": {"maximum_value_nesting": 128},
        "types": [
            {"type_id": "Bool", "kind": "primitive"},
            {"type_id": "Int", "kind": "primitive"},
            {"type_id": "Rat", "kind": "primitive"},
            {"type_id": "Text", "kind": "primitive"},
            {"type_id": "Unit", "kind": "unit"},
            {"type_id": "Vec2", "kind": "primitive"},
            {"type_id": "Vec3", "kind": "primitive"},
        ],
    })


def cint(value: int):
    return {"op": "CONST", "type": "Int", "value": {"$int": str(value)}}


def load_state(name: str):
    return {"op": "LOAD_STATE", "name": name, "type": "Int"}


def load_param(name: str):
    return {"op": "LOAD_PARAM", "name": name, "type": "Int"}


def plus(left, right):
    return {
        "op": "BINARY", "operator": "PLUS", "left_type": "Int", "right_type": "Int", "result_type": "Int",
        "left": left, "right": right,
    }


def gt(left, right):
    return {
        "op": "BINARY", "operator": "GT", "left_type": "Int", "right_type": "Int", "result_type": "Bool",
        "left": left, "right": right,
    }


class FakeAtomicProvider:
    def __init__(self, descriptor, *, status="PASS", mode="normal"):
        self._descriptor = descriptor
        self.status = status
        self.mode = mode
        self.calls = 0

    @property
    def descriptor(self):
        return self._descriptor

    def commit_batch(self, batch, authority):
        self.calls += 1
        if self.status == "FAIL":
            return build_provider_batch_observation_v4(
                batch_hash=batch.batch_hash,
                provider_descriptor_hash=self.descriptor.descriptor_hash,
                authority_grant_hash=authority.grant_hash,
                status="FAIL",
                intent_receipts=[],
                provider_batch_receipt_hash=_sha("provider-fail:" + batch.batch_hash),
            )
        pairs = [(intent.intent_hash, _sha("effect:" + intent.intent_hash)) for intent in batch.intents]
        if self.mode == "reverse":
            pairs = list(reversed(pairs))
        elif self.mode == "missing":
            pairs = pairs[:-1]
        observation = build_provider_batch_observation_v4(
            batch_hash=batch.batch_hash,
            provider_descriptor_hash=self.descriptor.descriptor_hash,
            authority_grant_hash=authority.grant_hash,
            status="PASS",
            intent_receipts=pairs,
            provider_batch_receipt_hash=_sha("provider-pass:" + batch.batch_hash),
        )
        if self.mode == "tamper_hash":
            observation = replace(observation, observation_hash="0" * 64)
        return observation


class IrV4EffectCommandsR2Tests(unittest.TestCase):
    def setUp(self):
        self.table = _table()
        self.states = build_state_schema_v4([
            {"name": "count", "type": "Int", "initial": {"$int": "0"}},
        ], self.table)
        self.capabilities = build_capability_table_v4([], self.table)
        self.scenario = build_effect_scenario_v4(
            {"capability_table_hash": self.capabilities.table_hash, "capabilities": []},
            self.table,
            self.capabilities,
        )
        self.commands = build_effect_command_table_v4([
            {"command_id": "log.write", "parameters": ["Int"], "kind": "effect_command", "idempotency_policy": "content_addressed_v1"},
        ], self.table)
        self.contract = self.commands.contracts[0]
        self.action = build_effect_action_r2_v4({
            "action_id": "persist",
            "parameters": [{"name": "bias", "type": "Int"}],
            "steps": [
                {"op": "REQUEST_EFFECT", "command_id": "log.write", "arguments": [load_state("count")]},
                {"op": "SET_STATE", "state": "count", "value": plus(load_state("count"), load_param("bias"))},
                {"op": "REQUEST_EFFECT", "command_id": "log.write", "arguments": [load_state("count")]},
                {"op": "ASSERT", "condition": gt(load_state("count"), cint(0))},
            ],
        }, self.table, self.states, self.capabilities, self.commands)
        self.descriptor = build_effect_provider_descriptor_v4(
            provider_id="provider.atomic",
            provider_version="1.0.0",
            provider_implementation_hash="a" * 64,
            supported_contract_hashes=[self.contract.contract_hash],
        )

    def plan(self, *, count=2, bias=3):
        return plan_effect_action_r2_v4(
            self.action, self.table, self.states, self.capabilities, self.commands, self.scenario,
            {"count": count}, [bias],
        )

    def grant(self, plan, *, scope="b" * 64, descriptor=None):
        descriptor = descriptor or self.descriptor
        return build_effect_authority_grant_v4(
            descriptor,
            plan.command_batch,
            allowed_contract_hashes=[self.contract.contract_hash],
            authority_scope_hash=scope,
        )

    def test_planning_emits_ordered_content_addressed_outbox_without_provider(self):
        provider = FakeAtomicProvider(self.descriptor)
        plan = self.plan()
        self.assertEqual(provider.calls, 0)
        self.assertEqual(len(plan.command_batch.intents), 2)
        self.assertEqual(plan.command_batch.intents[0].argument_encodings, ({"$int": "2"},))
        self.assertEqual(plan.command_batch.intents[1].argument_encodings, ({"$int": "5"},))
        self.assertNotEqual(plan.command_batch.intents[0].idempotency_key, plan.command_batch.intents[1].idempotency_key)
        self.assertEqual(plan.proposed_final_state[0]["value"], {"$int": "5"})

    def test_exact_replanning_preserves_context_intent_batch_and_receipt_hashes(self):
        a = self.plan()
        b = self.plan()
        self.assertEqual(a.plan_context_hash, b.plan_context_hash)
        self.assertEqual(a.command_batch.batch_hash, b.command_batch.batch_hash)
        self.assertEqual(tuple(x.intent_hash for x in a.command_batch.intents), tuple(x.intent_hash for x in b.command_batch.intents))
        self.assertEqual(a.planning_receipt_hash, b.planning_receipt_hash)

    def test_same_literal_command_arguments_in_different_state_context_get_different_idempotency(self):
        literal_action = build_effect_action_r2_v4({
            "action_id": "constant",
            "parameters": [],
            "steps": [
                {"op": "REQUEST_EFFECT", "command_id": "log.write", "arguments": [cint(1)]},
                {"op": "SET_STATE", "state": "count", "value": plus(load_state("count"), cint(1))},
            ],
        }, self.table, self.states, self.capabilities, self.commands)
        a = plan_effect_action_r2_v4(literal_action, self.table, self.states, self.capabilities, self.commands, self.scenario, {"count": 2}, [])
        b = plan_effect_action_r2_v4(literal_action, self.table, self.states, self.capabilities, self.commands, self.scenario, {"count": 3}, [])
        self.assertEqual(a.command_batch.intents[0].argument_encodings, b.command_batch.intents[0].argument_encodings)
        self.assertNotEqual(a.plan_context_hash, b.plan_context_hash)
        self.assertNotEqual(a.command_batch.intents[0].idempotency_key, b.command_batch.intents[0].idempotency_key)

    def test_assert_after_request_aborts_before_any_physical_authority_exists(self):
        bad = build_effect_action_r2_v4({
            "action_id": "reject",
            "parameters": [],
            "steps": [
                {"op": "REQUEST_EFFECT", "command_id": "log.write", "arguments": [cint(1)]},
                {"op": "ASSERT", "condition": gt(cint(0), cint(1))},
            ],
        }, self.table, self.states, self.capabilities, self.commands)
        provider = FakeAtomicProvider(self.descriptor)
        with self.assertRaises(TevScriptError) as captured:
            plan_effect_action_r2_v4(bad, self.table, self.states, self.capabilities, self.commands, self.scenario, {"count": 0}, [])
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_ASSERT")
        self.assertEqual(provider.calls, 0)

    def test_authorized_atomic_commit_then_finalize_authorizes_proposed_state(self):
        plan = self.plan()
        grant = self.grant(plan)
        provider = FakeAtomicProvider(self.descriptor)
        ledger = EffectCommitLedgerV4()
        commit = commit_effect_command_batch_v4(plan.command_batch, provider, grant, ledger)
        self.assertEqual(commit.status, "PASS")
        self.assertEqual(provider.calls, 1)
        final = finalize_effect_transition_v4(plan, commit)
        self.assertEqual(final.final_state, plan.proposed_final_state)
        self.assertEqual(final.final_state_hash, plan.proposed_final_state_hash)
        self.assertEqual(final.provider_descriptor_hash, self.descriptor.descriptor_hash)
        self.assertEqual(final.authority_grant_hash, grant.grant_hash)

    def test_ledger_replay_returns_same_commit_without_second_provider_call(self):
        plan = self.plan(); grant = self.grant(plan); provider = FakeAtomicProvider(self.descriptor); ledger = EffectCommitLedgerV4()
        first = commit_effect_command_batch_v4(plan.command_batch, provider, grant, ledger)
        second = commit_effect_command_batch_v4(plan.command_batch, provider, grant, ledger)
        self.assertEqual(first.receipt_hash, second.receipt_hash)
        self.assertEqual(provider.calls, 1)

    def test_same_committed_batch_cannot_be_reclaimed_under_different_authority(self):
        plan = self.plan(); provider = FakeAtomicProvider(self.descriptor); ledger = EffectCommitLedgerV4()
        grant_a = self.grant(plan, scope="b" * 64)
        grant_b = self.grant(plan, scope="c" * 64)
        commit_effect_command_batch_v4(plan.command_batch, provider, grant_a, ledger)
        with self.assertRaises(TevScriptError) as captured:
            commit_effect_command_batch_v4(plan.command_batch, provider, grant_b, ledger)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_IDEMPOTENCY_AUTHORITY")
        self.assertEqual(provider.calls, 1)

    def test_provider_failure_never_finalizes_and_can_retry_because_failure_is_not_ledger_commit(self):
        plan = self.plan(); grant = self.grant(plan); provider = FakeAtomicProvider(self.descriptor, status="FAIL"); ledger = EffectCommitLedgerV4()
        failed = commit_effect_command_batch_v4(plan.command_batch, provider, grant, ledger)
        self.assertEqual(failed.status, "FAIL")
        self.assertIsNone(ledger.lookup(plan.command_batch.batch_hash))
        with self.assertRaises(TevScriptError) as captured:
            finalize_effect_transition_v4(plan, failed)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_FINALIZE_STATUS")
        provider.status = "PASS"
        passed = commit_effect_command_batch_v4(plan.command_batch, provider, grant, ledger)
        self.assertEqual(passed.status, "PASS")
        self.assertEqual(provider.calls, 2)

    def test_wrong_provider_is_rejected_before_commit_call(self):
        plan = self.plan(); grant = self.grant(plan)
        other_descriptor = build_effect_provider_descriptor_v4(
            provider_id="provider.other", provider_version="1.0.0", provider_implementation_hash="d" * 64,
            supported_contract_hashes=[self.contract.contract_hash],
        )
        other = FakeAtomicProvider(other_descriptor)
        with self.assertRaises(TevScriptError) as captured:
            commit_effect_command_batch_v4(plan.command_batch, other, grant, EffectCommitLedgerV4())
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_AUTHORITY")
        self.assertEqual(other.calls, 0)

    def test_tampered_or_rebound_authority_is_rejected_before_provider(self):
        plan = self.plan(); grant = self.grant(plan); provider = FakeAtomicProvider(self.descriptor)
        forged = replace(grant, batch_hash="0" * 64)
        with self.assertRaises(TevScriptError) as captured:
            commit_effect_command_batch_v4(plan.command_batch, provider, forged, EffectCommitLedgerV4())
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_AUTHORITY_HASH")
        self.assertEqual(provider.calls, 0)

    def test_provider_missing_or_reordered_intent_receipts_fail_exact_coverage(self):
        plan = self.plan(); grant = self.grant(plan)
        for mode in ("missing", "reverse"):
            provider = FakeAtomicProvider(self.descriptor, mode=mode)
            with self.assertRaises(TevScriptError) as captured:
                commit_effect_command_batch_v4(plan.command_batch, provider, grant, EffectCommitLedgerV4())
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_PROVIDER_INTENTS")
            self.assertEqual(provider.calls, 1)

    def test_provider_observation_hash_tamper_is_rejected(self):
        plan = self.plan(); grant = self.grant(plan); provider = FakeAtomicProvider(self.descriptor, mode="tamper_hash")
        with self.assertRaises(TevScriptError) as captured:
            commit_effect_command_batch_v4(plan.command_batch, provider, grant, EffectCommitLedgerV4())
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_PROVIDER_OBSERVATION_HASH")

    def test_batch_tamper_is_rejected_before_provider(self):
        plan = self.plan(); grant = self.grant(plan); provider = FakeAtomicProvider(self.descriptor)
        intent = plan.command_batch.intents[0]
        tampered_intent = replace(intent, idempotency_key="0" * 64)
        tampered_batch = replace(plan.command_batch, intents=(tampered_intent, *plan.command_batch.intents[1:]))
        with self.assertRaises(TevScriptError) as captured:
            commit_effect_command_batch_v4(tampered_batch, provider, grant, EffectCommitLedgerV4())
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_IDEMPOTENCY_HASH")
        self.assertEqual(provider.calls, 0)

    def test_commit_receipt_tamper_is_rejected_at_finalization(self):
        plan = self.plan(); grant = self.grant(plan); provider = FakeAtomicProvider(self.descriptor); ledger = EffectCommitLedgerV4()
        commit = commit_effect_command_batch_v4(plan.command_batch, provider, grant, ledger)
        forged = replace(commit, receipt_hash="0" * 64)
        with self.assertRaises(TevScriptError) as captured:
            finalize_effect_transition_v4(plan, forged)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_COMMIT_RECEIPT_HASH")

    def test_non_atomic_provider_descriptor_is_rejected_by_construction(self):
        with self.assertRaises(TevScriptError) as captured:
            build_effect_provider_descriptor_v4(
                provider_id="provider.best_effort", provider_version="1", provider_implementation_hash="e" * 64,
                supported_contract_hashes=[self.contract.contract_hash], commit_semantics="best_effort",
            )
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_PROVIDER_ATOMICITY")

    def test_r2_action_without_command_is_rejected_in_favor_of_r1(self):
        with self.assertRaises(TevScriptError) as captured:
            build_effect_action_r2_v4({
                "action_id": "pure_state", "parameters": [],
                "steps": [{"op": "SET_STATE", "state": "count", "value": cint(1)}],
            }, self.table, self.states, self.capabilities, self.commands)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_COMMAND_ACTION_PROFILE")


    def test_r2_observe_all_reserves_canonically_before_request(self):
        capabilities=build_capability_table_v4([{"capability_id":"sensor.read","parameters":["Int"],"return_type":"Int","kind":"observation"}],self.table)
        sensor=capabilities.require("sensor.read")
        scenario=build_effect_scenario_v4({"capability_table_hash":capabilities.table_hash,"capabilities":[{"capability_id":"sensor.read","contract_hash":sensor.contract_hash,"calls":[{"arguments":[{"$int":"1"}],"return":{"$int":"10"}},{"arguments":[{"$int":"2"}],"return":{"$int":"20"}}]}]},self.table,capabilities)
        action=build_effect_action_r2_v4({"action_id":"observe_then_request","parameters":[],"steps":[{"op":"OBSERVE_ALL","reservation_policy":"canonical_bind_then_capability_ordinal_v1","observations":[{"bind":"b","capability_id":"sensor.read","arguments":[cint(2)]},{"bind":"a","capability_id":"sensor.read","arguments":[cint(1)]}]},{"op":"REQUEST_EFFECT","command_id":"log.write","arguments":[{"op":"LOAD_LOCAL","name":"a","type":"Int"}]}]},self.table,self.states,capabilities,self.commands)
        self.assertEqual([item["bind"] for item in action.steps[0]["observations"]],["a","b"])
        plan=plan_effect_action_r2_v4(action,self.table,self.states,capabilities,self.commands,scenario,{"count":0},[])
        self.assertEqual([row["call_index"] for row in plan.capability_transcript],[0,1])
        self.assertEqual(plan.command_batch.intents[0].argument_encodings,({"$int":"10"},))
        self.assertEqual(plan.observation_calls,2)

    def test_transcript_changes_rebind_same_literal_command_batch_authority(self):
        capabilities=build_capability_table_v4([{"capability_id":"sensor.read","parameters":["Int"],"return_type":"Int","kind":"observation"}],self.table)
        sensor=capabilities.require("sensor.read")
        def scenario(value):
            return build_effect_scenario_v4({"capability_table_hash":capabilities.table_hash,"capabilities":[{"capability_id":"sensor.read","contract_hash":sensor.contract_hash,"calls":[{"arguments":[{"$int":"1"}],"return":{"$int":str(value)}}]}]},self.table,capabilities)
        action=build_effect_action_r2_v4({"action_id":"transcript_bound","parameters":[],"steps":[{"op":"OBSERVE_ALL","reservation_policy":"canonical_bind_then_capability_ordinal_v1","observations":[{"bind":"a","capability_id":"sensor.read","arguments":[cint(1)]}]},{"op":"REQUEST_EFFECT","command_id":"log.write","arguments":[cint(7)]}]},self.table,self.states,capabilities,self.commands)
        a=plan_effect_action_r2_v4(action,self.table,self.states,capabilities,self.commands,scenario(10),{"count":0},[])
        b=plan_effect_action_r2_v4(action,self.table,self.states,capabilities,self.commands,scenario(11),{"count":0},[])
        self.assertEqual(a.proposed_final_state_hash,b.proposed_final_state_hash)
        self.assertEqual(a.command_batch.intents[0].argument_encodings,b.command_batch.intents[0].argument_encodings)
        self.assertNotEqual(a.capability_transcript_hash,b.capability_transcript_hash)
        self.assertNotEqual(a.plan_context_hash,b.plan_context_hash)
        self.assertNotEqual(a.command_batch.batch_hash,b.command_batch.batch_hash)
        self.assertNotEqual(a.command_batch.intents[0].idempotency_key,b.command_batch.intents[0].idempotency_key)

    def test_rehashed_transcript_tamper_still_fails_causal_plan_context(self):
        plan=self.plan()
        forged_transcript=({"capability_id":"forged.observe","contract_hash":"f"*64,"call_index":0,"arguments":[],"return":{"$int":"1"}},)
        transcript_hash=_hash_value({"schema":"TEV_SCRIPT_IR_V4_EFFECT_CAPABILITY_TRANSCRIPT_V1","calls":forged_transcript})
        forged=replace(plan,capability_transcript=forged_transcript,capability_transcript_hash=transcript_hash,observation_calls=1)
        with self.assertRaises(TevScriptError) as captured:
            validate_planned_effect_transition_v4(forged)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_IR_V4_COMMAND_PLAN_CONTEXT")

if __name__ == "__main__":
    unittest.main()
