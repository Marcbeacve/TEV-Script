from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.file_effect_provider_v2 import (
    AtomicFileReplaceProviderV2,
    build_file_effect_scope_v2,
    build_file_replace_command_table_v4,
    file_effect_receipt_to_dict_v2,
)
from tev_script.ir_v4_effect_commands import (
    EffectCommitLedgerV4,
    build_effect_action_r2_v4,
    build_effect_authority_grant_v4,
    commit_effect_command_batch_v4,
    finalize_effect_transition_v4,
    plan_effect_action_r2_v4,
)
from tev_script.ir_v4_effects import build_capability_table_v4, build_effect_scenario_v4, build_state_schema_v4
from tev_script.ir_v4_values import build_type_table_v4


def ctext(value): return {"op":"CONST","type":"Text","value":value}
def cint(value): return {"op":"CONST","type":"Int","value":{"$int":str(value)}}


class FileEffectProviderV2Tests(unittest.TestCase):
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

    def action(self,path='out.txt',data='hello'):
        return build_effect_action_r2_v4({"action_id":"save","parameters":[],"steps":[
            {"op":"REQUEST_EFFECT","command_id":"file.replace","arguments":[ctext(path),ctext(data)]},
            {"op":"SET_STATE","state":"done","value":cint(1)},
        ]},self.table,self.states,self.caps,self.commands)

    def plan(self,path='out.txt',data='hello'):
        return plan_effect_action_r2_v4(self.action(path,data),self.table,self.states,self.caps,self.commands,self.scenario,{"done":0},[])

    def test_single_file_replace_commit_is_atomic_and_finalizes_state(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); target=root/'out.txt'; target.write_text('old',encoding='utf-8')
            plan=self.plan(); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            self.assertEqual(target.read_text(encoding='utf-8'),'old')
            grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
            commit=commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
            final=finalize_effect_transition_v4(plan,commit)
            self.assertEqual(target.read_text(encoding='utf-8'),'hello')
            self.assertEqual(final.final_state[0]['value'],{'$int':'1'})
            self.assertEqual(len(provider.effect_receipts),1)
            wire=file_effect_receipt_to_dict_v2(provider.effect_receipts[0])
            self.assertEqual(wire['relative_path'],'out.txt')
            self.assertEqual(wire['data_sha256'],wire['final_sha256'])

    def test_ledger_replay_does_not_touch_provider_twice(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); plan=self.plan(); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
            ledger=EffectCommitLedgerV4()
            first=commit_effect_command_batch_v4(plan.command_batch,provider,grant,ledger)
            first_mtime=(root/'out.txt').stat().st_mtime_ns
            second=commit_effect_command_batch_v4(plan.command_batch,provider,grant,ledger)
            self.assertEqual(first.receipt_hash,second.receipt_hash)
            self.assertEqual(provider.commit_calls,1)
            self.assertEqual((root/'out.txt').stat().st_mtime_ns,first_mtime)

    def test_retry_after_effect_before_ledger_reconciles_without_second_physical_replace(self):
        class FailingLedger:
            def __init__(self): self.seen = None
            def lookup(self, _batch_hash): return None
            def record(self, receipt):
                self.seen = receipt
                raise RuntimeError("simulated ledger boundary failure")

        with tempfile.TemporaryDirectory() as td:
            root=Path(td); plan=self.plan()
            first_provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant=build_effect_authority_grant_v4(first_provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=first_provider.scope.scope_hash)
            failing=FailingLedger()
            with self.assertRaises(RuntimeError):
                commit_effect_command_batch_v4(plan.command_batch,first_provider,grant,failing)
            self.assertEqual((root/'out.txt').read_text(encoding='utf-8'),'hello')
            self.assertEqual(first_provider.physical_replace_calls,1)
            self.assertIsNotNone(failing.seen)

            retry_provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            self.assertEqual(retry_provider.descriptor.descriptor_hash,first_provider.descriptor.descriptor_hash)
            retry=commit_effect_command_batch_v4(plan.command_batch,retry_provider,grant,EffectCommitLedgerV4())
            self.assertEqual(retry_provider.commit_calls,1)
            self.assertEqual(retry_provider.physical_replace_calls,0)
            self.assertEqual(retry.receipt_hash,failing.seen.receipt_hash)
            self.assertEqual((root/'out.txt').read_text(encoding='utf-8'),'hello')

    def test_grant_for_other_root_is_rejected_without_file_write(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root_a=Path(a); root_b=Path(b); plan=self.plan(); provider_a=AtomicFileReplaceProviderV2(root_a,contract_hash=self.contract.contract_hash)
            provider_b=AtomicFileReplaceProviderV2(root_b,contract_hash=self.contract.contract_hash,provider_implementation_hash=provider_a.descriptor.provider_implementation_hash)
            # Grant is structurally valid for A's descriptor/batch but scope is B.
            grant=build_effect_authority_grant_v4(provider_a.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider_b.scope.scope_hash)
            with self.assertRaises(TevScriptError) as captured:
                commit_effect_command_batch_v4(plan.command_batch,provider_a,grant,EffectCommitLedgerV4())
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_PROVIDER_SCOPE_AUTHORITY')
            self.assertFalse((root_a/'out.txt').exists()); self.assertFalse((root_b/'out.txt').exists())

    def test_parent_traversal_absolute_and_missing_parent_fail_without_write(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root=Path(td); outside_path=Path(outside)/'escape.txt'
            cases=['../escape.txt',str(outside_path),'missing/out.txt']
            for path in cases:
                with self.subTest(path=path):
                    plan=self.plan(path=path); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
                    grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
                    with self.assertRaises(TevScriptError): commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
            self.assertFalse(outside_path.exists()); self.assertFalse((root/'missing').exists())

    def test_windows_ambiguous_and_reserved_segments_are_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for path in ['name.','name ','x:y','CON','nul.txt','COM1.log','LPT9']:
                with self.subTest(path=path):
                    plan=self.plan(path=path); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
                    grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
                    with self.assertRaises(TevScriptError):
                        commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
                    self.assertEqual(provider.physical_replace_calls,0)

    def test_existing_nested_directory_is_valid_and_reconciles_exact_content(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'nested').mkdir()
            plan=self.plan(path='nested/out.txt',data='nested')
            provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
            first=commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
            self.assertEqual(first.status,'PASS')
            self.assertEqual(provider.physical_replace_calls,1)
            self.assertEqual((root/'nested'/'out.txt').read_text(encoding='utf-8'),'nested')
            retry_provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            second=commit_effect_command_batch_v4(plan.command_batch,retry_provider,grant,EffectCommitLedgerV4())
            self.assertEqual(second.receipt_hash,first.receipt_hash)
            self.assertEqual(retry_provider.physical_replace_calls,0)

    def test_parent_link_or_junction_escape_is_rejected_without_skip(self):
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as outside:
            root=Path(td); outside_target=Path(outside)/'victim.txt'; outside_target.write_text('safe',encoding='utf-8')
            link=root/'escape'
            if os.name == 'nt':
                completed=subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(link),str(Path(outside))],capture_output=True,text=True,check=False)
                self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            else:
                link.symlink_to(Path(outside),target_is_directory=True)
            try:
                plan=self.plan(path='escape/victim.txt'); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
                grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
                with self.assertRaises(TevScriptError) as captured:
                    commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
                self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_PROVIDER_PATH_ESCAPE')
                self.assertEqual(outside_target.read_text(encoding='utf-8'),'safe')
            finally:
                if os.name == 'nt': os.rmdir(link)
                else: link.unlink()

    def test_multi_intent_batch_returns_fail_before_any_file_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            action=build_effect_action_r2_v4({"action_id":"two","parameters":[],"steps":[
                {"op":"REQUEST_EFFECT","command_id":"file.replace","arguments":[ctext('a.txt'),ctext('A')]},
                {"op":"REQUEST_EFFECT","command_id":"file.replace","arguments":[ctext('b.txt'),ctext('B')]},
                {"op":"SET_STATE","state":"done","value":cint(1)},
            ]},self.table,self.states,self.caps,self.commands)
            plan=plan_effect_action_r2_v4(action,self.table,self.states,self.caps,self.commands,self.scenario,{"done":0},[])
            provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant=build_effect_authority_grant_v4(provider.descriptor,plan.command_batch,allowed_contract_hashes=[self.contract.contract_hash],authority_scope_hash=provider.scope.scope_hash)
            commit=commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
            self.assertEqual(commit.status,'FAIL')
            self.assertFalse((root/'a.txt').exists()); self.assertFalse((root/'b.txt').exists())
            with self.assertRaises(TevScriptError): finalize_effect_transition_v4(plan,commit)

    def test_scope_hash_is_root_specific(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            sa=build_file_effect_scope_v2(a); sb=build_file_effect_scope_v2(b)
            self.assertNotEqual(sa.scope_hash,sb.scope_hash)

    def test_provider_root_path_swap_cannot_redirect_commit(self):
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td); root=parent/'root'; moved=parent/'root-original'
            root.mkdir(); root.joinpath('out.txt').write_text('authorized-old',encoding='utf-8')
            plan=self.plan(); provider=AtomicFileReplaceProviderV2(root,contract_hash=self.contract.contract_hash)
            grant=build_effect_authority_grant_v4(
                provider.descriptor,
                plan.command_batch,
                allowed_contract_hashes=[self.contract.contract_hash],
                authority_scope_hash=provider.scope.scope_hash,
            )
            root.rename(moved)
            root.mkdir()
            root.joinpath('out.txt').write_text('outside-sentinel',encoding='utf-8')
            commit=commit_effect_command_batch_v4(plan.command_batch,provider,grant,EffectCommitLedgerV4())
            self.assertEqual(commit.status,'PASS')
            self.assertEqual(moved.joinpath('out.txt').read_text(encoding='utf-8'),'hello')
            self.assertEqual(root.joinpath('out.txt').read_text(encoding='utf-8'),'outside-sentinel')


if __name__=='__main__': unittest.main()
