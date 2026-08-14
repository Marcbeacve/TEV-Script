from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.file_observation_acquisition_v2 import (
    MAX_FILE_READ_BYTES_V2,
    acquire_file_read_observations_v2,
    build_file_read_acquisition_request_v2,
    scenario_from_file_read_evidence_v2,
    validate_file_read_acquisition_evidence_v2,
)
from tev_script.ir_v4_effects import build_effect_scenario_v4
from tev_script.program_ir_v4 import run_program_ir_v4_effects
from tev_script.source_effect_program_v2 import build_effect_program_ir_v4, compile_effect_program_v2


class FileObservationAcquisitionV2Tests(unittest.TestCase):
    SOURCE = '''
    script ReadDemo version "2.0.0";
    state content:Text="";
    capability observation file.read(Text)->Text;
    action load() {
        observe body=file.read("input.txt");
        set content=body;
    }
    entry main=load();
    '''

    def compiled(self):
        return compile_effect_program_v2(self.SOURCE)

    def test_acquired_evidence_derives_replayable_scenario_and_runtime_never_reads_host(self):
        compiled=self.compiled()
        request=build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); target=root/'input.txt'; target.write_text('alpha',encoding='utf-8')
            evidence=acquire_file_read_observations_v2(request,compiled.capabilities,root)
            scenario=scenario_from_file_read_evidence_v2(evidence,compiled.capabilities)
            self.assertNotIn('provider',scenario)
            self.assertNotIn('authority_scope_hash',scenario)
            program_ir=build_effect_program_ir_v4(compiled,scenario)
            target.write_text('CHANGED_AFTER_ACQUISITION',encoding='utf-8')
            receipt=run_program_ir_v4_effects(program_ir)
            self.assertEqual(receipt.final_state[0]['value'],'alpha')
            self.assertEqual(target.read_text(encoding='utf-8'),'CHANGED_AFTER_ACQUISITION')

    def test_same_content_in_two_roots_has_same_scenario_but_distinct_provenance_evidence(self):
        compiled=self.compiled(); request=build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            Path(a,'input.txt').write_text('same',encoding='utf-8'); Path(b,'input.txt').write_text('same',encoding='utf-8')
            ea=acquire_file_read_observations_v2(request,compiled.capabilities,a)
            eb=acquire_file_read_observations_v2(request,compiled.capabilities,b)
            self.assertNotEqual(ea['authority_scope_hash'],eb['authority_scope_hash'])
            self.assertNotEqual(ea['evidence_hash'],eb['evidence_hash'])
            sa=scenario_from_file_read_evidence_v2(ea,compiled.capabilities)
            sb=scenario_from_file_read_evidence_v2(eb,compiled.capabilities)
            self.assertEqual(sa,sb)
            self.assertEqual(build_effect_scenario_v4(sa,compiled.types.table,compiled.capabilities).scenario_hash,build_effect_scenario_v4(sb,compiled.types.table,compiled.capabilities).scenario_hash)

    def test_evidence_content_tamper_is_rejected_even_if_outer_hash_is_unchanged(self):
        compiled=self.compiled(); request=build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        with tempfile.TemporaryDirectory() as td:
            Path(td,'input.txt').write_text('alpha',encoding='utf-8')
            evidence=acquire_file_read_observations_v2(request,compiled.capabilities,td)
            tampered=copy.deepcopy(evidence); tampered['calls'][0]['return']='beta'
            with self.assertRaises(TevScriptError) as captured:
                validate_file_read_acquisition_evidence_v2(tampered,compiled.capabilities)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_READ_EVIDENCE_CONTENT')

    def test_scope_and_provider_external_pins_are_enforced(self):
        compiled=self.compiled(); request=build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        with tempfile.TemporaryDirectory() as td:
            Path(td,'input.txt').write_text('alpha',encoding='utf-8')
            evidence=acquire_file_read_observations_v2(request,compiled.capabilities,td)
            validated=validate_file_read_acquisition_evidence_v2(evidence,compiled.capabilities,expected_authority_scope_hash=evidence['authority_scope_hash'],expected_provider_descriptor_hash=evidence['provider']['descriptor_hash'])
            self.assertEqual(validated['evidence_hash'],evidence['evidence_hash'])
            with self.assertRaises(TevScriptError):
                validate_file_read_acquisition_evidence_v2(evidence,compiled.capabilities,expected_authority_scope_hash='0'*64)
            with self.assertRaises(TevScriptError):
                validate_file_read_acquisition_evidence_v2(evidence,compiled.capabilities,expected_provider_descriptor_hash='0'*64)

    def test_shared_path_policy_is_transitively_bound_into_provider_descriptor(self):
        compiled=self.compiled(); request=build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        with tempfile.TemporaryDirectory() as td:
            Path(td,'input.txt').write_text('alpha',encoding='utf-8')
            evidence=acquire_file_read_observations_v2(request,compiled.capabilities,td)
            provider=evidence['provider']
            self.assertEqual(len(provider['implementation_hash']),64)
            self.assertEqual(len(provider['shared_file_policy_hash']),64)
            self.assertNotEqual(provider['implementation_hash'],provider['shared_file_policy_hash'])

    def test_path_escape_absolute_missing_and_windows_ambiguous_names_fail_closed(self):
        compiled=self.compiled()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); root.joinpath('ok.txt').write_text('ok',encoding='utf-8')
            bad=['../escape.txt',str(root.absolute()/'ok.txt'),'missing.txt','CON','x:y','name.']
            for path in bad:
                with self.subTest(path=path):
                    request=build_file_read_acquisition_request_v2(compiled.capabilities,[path])
                    with self.assertRaises(TevScriptError):
                        acquire_file_read_observations_v2(request,compiled.capabilities,root)

    def test_invalid_utf8_and_oversize_file_are_rejected(self):
        compiled=self.compiled()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            root.joinpath('bad.txt').write_bytes(b'\xff')
            request=build_file_read_acquisition_request_v2(compiled.capabilities,['bad.txt'])
            with self.assertRaises(TevScriptError) as captured:
                acquire_file_read_observations_v2(request,compiled.capabilities,root)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_READ_UTF8')
            root.joinpath('big.txt').write_bytes(b'a'*(MAX_FILE_READ_BYTES_V2+1))
            request=build_file_read_acquisition_request_v2(compiled.capabilities,['big.txt'])
            with self.assertRaises(TevScriptError) as captured:
                acquire_file_read_observations_v2(request,compiled.capabilities,root)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_READ_BUDGET')

    def test_wrong_file_read_signature_is_rejected(self):
        source='''
        script Bad version "2.0.0";
        state x:Int=0;
        capability observation file.read(Int)->Text;
        action a(){ set x=1; }
        entry main=a();
        '''
        compiled=compile_effect_program_v2(source)
        with self.assertRaises(TevScriptError) as captured:
            build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_READ_CONTRACT')

    def test_request_hash_tamper_is_rejected_before_any_read(self):
        compiled=self.compiled(); request=build_file_read_acquisition_request_v2(compiled.capabilities,['input.txt'])
        request['request_hash']='0'*64
        with tempfile.TemporaryDirectory() as td:
            Path(td,'input.txt').write_text('alpha',encoding='utf-8')
            with self.assertRaises(TevScriptError) as captured:
                acquire_file_read_observations_v2(request,compiled.capabilities,td)
            self.assertEqual(captured.exception.diagnostic.code,'TEVS_FILE_READ_REQUEST_HASH')


if __name__=='__main__': unittest.main()
