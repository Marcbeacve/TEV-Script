from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v2 import main
from tev_script.remote_module_acquisition_v2 import (
    RemoteModuleFetchResponseV2,
    UrllibHttpsModuleTransportV2,
    build_remote_module_manifest_v2,
)


class CliRemoteModulesV2Tests(unittest.TestCase):
    URL='https://example.test/math-util.tevs'
    MODULE='module math.util version "2.0.0"; export fn twice(x:Int)->Int=x+2;'
    APP='script App version "2.0.0"; import math.util as u; fn solve(x:Int)->Int=u.twice(x); entry main:Int=solve(5);'

    def call(self,args):
        out=io.StringIO(); err=io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            code=main(args)
        return code,out.getvalue(),err.getvalue()

    def test_acquisition_is_network_phase_then_extract_compile_run_are_offline(self):
        body=self.MODULE.encode('utf-8')
        manifest=build_remote_module_manifest_v2([{
            'module_id':'math.util',
            'url':self.URL,
            'expected_sha256':hashlib.sha256(body).hexdigest(),
        }])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); manifest_path=root/'manifest.json'; acquisition=root/'acquisition.json'; bundle=root/'bundle.json'; app=root/'app.tevs'; ir=root/'program.json'; receipt=root/'receipt.json'
            manifest_path.write_text(json.dumps(manifest),encoding='utf-8'); app.write_text(self.APP,encoding='utf-8')
            code,out,err=self.call(['check-remote-module-manifest',str(manifest_path)])
            self.assertEqual((code,err),(0,'')); checked=json.loads(out); self.assertFalse(checked['network_accessed']); self.assertFalse(checked['runtime_network_acquisition'])

            calls=[]
            def fake_fetch(instance,canonical_url,*,maximum_bytes):
                calls.append((canonical_url,maximum_bytes,instance.descriptor.descriptor_hash))
                return RemoteModuleFetchResponseV2(canonical_url,200,body)
            original_fetch=UrllibHttpsModuleTransportV2.fetch
            UrllibHttpsModuleTransportV2.fetch=fake_fetch
            try:
                code,out,err=self.call(['acquire-remote-modules',str(manifest_path),'-o',str(acquisition)])
            finally:
                UrllibHttpsModuleTransportV2.fetch=original_fetch
            self.assertEqual((code,err),(0,'')); acquired_summary=json.loads(out)
            self.assertTrue(acquired_summary['network_accessed']); self.assertFalse(acquired_summary['runtime_network_acquisition']); self.assertEqual(len(calls),1)
            acquired=json.loads(acquisition.read_text(encoding='utf-8'))
            descriptor_hash=acquired['evidence']['transport']['descriptor_hash']

            code,out,err=self.call(['extract-remote-module-bundle',str(acquisition),'-o',str(bundle),'--expected-transport-descriptor-hash',descriptor_hash,'--expected-manifest-hash',manifest['manifest_hash']])
            self.assertEqual((code,err),(0,'')); extracted=json.loads(out); self.assertFalse(extracted['network_accessed']); self.assertFalse(extracted['runtime_network_acquisition'])
            code,out,err=self.call(['compile-modules',str(app),'--bundle',str(bundle),'-o',str(ir)])
            self.assertEqual((code,err),(0,'')); self.assertFalse(json.loads(out)['runtime_module_acquisition'])
            code,out,err=self.call(['run',str(ir),'-o',str(receipt)])
            self.assertEqual((code,err),(0,'')); result=json.loads(receipt.read_text(encoding='utf-8')); self.assertEqual(result['result_encoded'],{'$int':'7'})

    def test_wrong_extract_pin_does_not_commit_bundle_output(self):
        body=self.MODULE.encode('utf-8')
        manifest=build_remote_module_manifest_v2([{'module_id':'math.util','url':self.URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); manifest_path=root/'manifest.json'; acquisition=root/'acquisition.json'; bundle=root/'bundle.json'
            manifest_path.write_text(json.dumps(manifest),encoding='utf-8')
            def fake_fetch(instance,canonical_url,*,maximum_bytes):
                return RemoteModuleFetchResponseV2(canonical_url,200,body)
            original_fetch=UrllibHttpsModuleTransportV2.fetch
            UrllibHttpsModuleTransportV2.fetch=fake_fetch
            try:
                self.assertEqual(self.call(['acquire-remote-modules',str(manifest_path),'-o',str(acquisition)])[0],0)
            finally:
                UrllibHttpsModuleTransportV2.fetch=original_fetch
            bundle.write_text('SENTINEL',encoding='utf-8')
            code,out,err=self.call(['extract-remote-module-bundle',str(acquisition),'-o',str(bundle),'--expected-manifest-hash','0'*64])
            self.assertEqual(code,2); self.assertEqual(out,''); self.assertTrue(err); self.assertEqual(bundle.read_text(encoding='utf-8'),'SENTINEL')


if __name__=='__main__': unittest.main()
