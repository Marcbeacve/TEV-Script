from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.effect_commit_ledger_v2 import JsonEffectCommitLedgerV4
from tev_script.file_effect_provider_v2 import AtomicFileReplaceProviderV2, build_file_replace_command_table_v4
from tev_script.ir_v4_effect_commands import (
    EffectCommitLedgerV4,
    build_effect_action_r2_v4,
    build_effect_authority_grant_v4,
    build_provider_batch_observation_v4,
    commit_effect_command_batch_v4,
    effect_command_commit_receipt_to_dict_v4,
    plan_effect_action_r2_v4,
)
from tev_script.ir_v4_effects import build_capability_table_v4, build_effect_scenario_v4, build_state_schema_v4
from tev_script.ir_v4_values import build_type_table_v4


def ctext(value): return {"op":"CONST","type":"Text","value":value}
def cint(value): return {"op":"CONST","type":"Int","value":{"$int":str(value)}}
def h(value): return hashlib.sha256(value.encode()).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)


class FailingProvider:
    def __init__(self, descriptor): self._descriptor=descriptor
    @property
    def descriptor(self): return self._descriptor
    def commit_batch(self,batch,authority):
        return build_provider_batch_observation_v4(
            batch_hash=batch.batch_hash,
            provider_descriptor_hash=self.descriptor.descriptor_hash,
            authority_grant_hash=authority.grant_hash,
            status="FAIL",
            intent_receipts=[],
            provider_batch_receipt_hash=h("fail:"+batch.batch_hash),
        )


class DurableEffectLedgerV2Tests(unittest.TestCase):
    def setUp(self):
        self.table=build_type_table_v4({"boundary":{"maximum_value_nesting":128},"types":[
            {"type_id":"Bool","kind":"primitive"},{"type_id":"Int","kind":"primitive"},{"type_id":"Rat","kind":"primitive"},
            {"type_id":"Text","kind":"primitive"},{"type_id":"Unit","kind":"unit"},{"type_id":"Vec2","kind":"primitive"},{"type_id":"Vec3","kind":"primitive"},
        ]})
        self.states=build_state_schema_v4([{"name":"done","type":"Int","initial":{"$int":"0"}}],self.table)
        self.caps=build_capability_table_v4([],self.table)
        self.scenario=build_effect_scenario_v4({"capability_table_hash":self.caps.table_hash,"capabilities":[]},self.table,self.caps)
        self.commands=build_file_replace_command_table_v4(self.table)
        self.contract=self.commands.contracts[0]
        self.action=build_effect_action_r2_v4({"action_id":"save","parameters":[],"steps":[
            {"op":"REQUEST_EFFECT","command_id":"file.replace","arguments":[ctext("out.txt"),ctext("hello")]},
            {"op":"SET_STATE","state":"done","value":cint(1)},
        ]},self.table,self.states,self.caps,self.commands)
        self.plan=plan_effect_action_r2_v4(self.action,self.table,self.states,self.caps,self.commands,self.scenario,{"done":0},[])

    def grant(self,provider):
        return build_effect_authority_grant_v4(
            provider.descriptor,self.plan.command_batch,
            allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash,
        )

    def test_reopen_ledger_suppresses_provider_after_process_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); ledger_path=root/'ledger.json'
            provider1=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant1=self.grant(provider1); ledger1=JsonEffectCommitLedgerV4(ledger_path)
            first=commit_effect_command_batch_v4(self.plan.command_batch,provider1,grant1,ledger1)
            self.assertTrue(ledger_path.exists()); self.assertEqual(provider1.commit_calls,1)
            first_mtime=(root/'out.txt').stat().st_mtime_ns

            ledger2=JsonEffectCommitLedgerV4(ledger_path)
            provider2=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant2=self.grant(provider2)
            second=commit_effect_command_batch_v4(self.plan.command_batch,provider2,grant2,ledger2)
            self.assertEqual(first.receipt_hash,second.receipt_hash)
            self.assertEqual(provider2.commit_calls,0)
            self.assertEqual((root/'out.txt').stat().st_mtime_ns,first_mtime)
            self.assertEqual(ledger2.entry_count,1)
            self.assertEqual(ledger1.ledger_hash,ledger2.ledger_hash)

    def test_ledger_hash_tamper_is_rejected_on_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); path=root/'ledger.json'; provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            commit_effect_command_batch_v4(self.plan.command_batch,provider,self.grant(provider),JsonEffectCommitLedgerV4(path))
            raw=json.loads(path.read_text(encoding='utf-8')); raw['ledger_hash']='0'*64; path.write_text(canonical(raw),encoding='utf-8')
            with self.assertRaises(TevScriptError) as captured: JsonEffectCommitLedgerV4(path)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_EFFECT_LEDGER_HASH')

    def test_receipt_tamper_is_rejected_on_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); path=root/'ledger.json'; provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            commit_effect_command_batch_v4(self.plan.command_batch,provider,self.grant(provider),JsonEffectCommitLedgerV4(path))
            raw=json.loads(path.read_text(encoding='utf-8')); raw['entries'][0]['receipt']['receipt_hash']='0'*64
            content={"schema":"TEV_SCRIPT_EFFECT_COMMIT_LEDGER_CONTENT_V4_V1","entries":raw['entries']}
            raw['ledger_hash']=hashlib.sha256(canonical(content).encode()).hexdigest(); path.write_text(canonical(raw),encoding='utf-8')
            with self.assertRaises(TevScriptError) as captured: JsonEffectCommitLedgerV4(path)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_IR_V4_COMMAND_COMMIT_RECEIPT_HASH')

    def test_valid_fail_receipt_cannot_be_persisted_as_commit(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash); grant=self.grant(provider)
            failed=commit_effect_command_batch_v4(self.plan.command_batch,FailingProvider(provider.descriptor),grant,EffectCommitLedgerV4())
            self.assertEqual(failed.status,'FAIL')
            ledger=JsonEffectCommitLedgerV4(root/'ledger.json')
            with self.assertRaises(TevScriptError) as captured: ledger.record(failed)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_EFFECT_LEDGER_STATUS')
            self.assertFalse((root/'ledger.json').exists())

    def test_conflicting_valid_receipt_for_same_batch_is_rejected_without_clobber(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); path=root/'ledger.json'; provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash); ledger=JsonEffectCommitLedgerV4(path)
            original=commit_effect_command_batch_v4(self.plan.command_batch,provider,self.grant(provider),ledger)
            before=path.read_bytes()
            payload={
                "schema":"TEV_SCRIPT_IR_V4_EFFECT_COMMAND_BATCH_COMMIT_RECEIPT_R2_V1",
                "batch_hash":original.batch_hash,"plan_context_hash":original.plan_context_hash,"command_table_hash":original.command_table_hash,
                "provider_descriptor_hash":original.provider_descriptor_hash,"authority_grant_hash":original.authority_grant_hash,"status":"PASS",
                "intent_receipts":[{"intent_hash":x.intent_hash,"provider_effect_receipt_hash":x.provider_effect_receipt_hash} for x in original.intent_receipts],
                "provider_batch_receipt_hash":h('different-batch-receipt'),"provider_observation_hash":h('different-observation'),
            }
            conflict=replace(original,provider_batch_receipt_hash=payload['provider_batch_receipt_hash'],provider_observation_hash=payload['provider_observation_hash'],receipt_hash=hashlib.sha256(canonical(payload).encode()).hexdigest())
            # Ensure it is independently well-formed before ledger conflict logic.
            effect_command_commit_receipt_to_dict_v4(conflict)
            with self.assertRaises(TevScriptError) as captured: ledger.record(conflict)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_EFFECT_LEDGER_CONFLICT')
            self.assertEqual(path.read_bytes(),before)

    def test_parent_must_exist_and_ledger_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'missing'/'ledger.json'
            with self.assertRaises(TevScriptError) as captured: JsonEffectCommitLedgerV4(path)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_EFFECT_LEDGER_PARENT')
            self.assertFalse(path.parent.exists())

    def test_snapshot_is_canonical_sorted_and_hash_stable(self):
        with tempfile.TemporaryDirectory() as td:
            ledger=JsonEffectCommitLedgerV4(Path(td)/'ledger.json')
            snapshot=ledger.snapshot()
            self.assertEqual(snapshot['entries'],[])
            self.assertEqual(len(snapshot['ledger_hash']),64)
            self.assertEqual(snapshot,ledger.snapshot())


if __name__=='__main__': unittest.main()
