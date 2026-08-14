from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v2 import main
from tev_script.remote_module_acquisition_v2 import RemoteModuleFetchResponseV2, UrllibHttpsModuleTransportV2, build_remote_module_manifest_v2
from tev_script.signed_remote_module_manifest_v2 import sign_remote_module_manifest_ed25519_v2


class CliSignedRemoteModulesV2Tests(unittest.TestCase):
    URL='https://example.test/math-util.tevs'
    MODULE='module math.util version "2.0.0"; export fn twice(x:Int)->Int=x+2;'
    APP='script App version "2.0.0"; import math.util as u; fn solve(x:Int)->Int=u.twice(x); entry main:Int=solve(5);'
    KEY=b'\x33'*32

    def call(self,args):
        out=io.StringIO(); err=io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):
            code=main(args)
        return code,out.getvalue(),err.getvalue()

    def signed_manifest(self):
        body=self.MODULE.encode('utf-8')
        manifest=build_remote_module_manifest_v2([{
            'module_id':'math.util',
            'url':self.URL,
            'expected_sha256':hashlib.sha256(body).hexdigest(),
        }])
        return sign_remote_module_manifest_ed25519_v2(manifest,self.KEY,key_id='release')

    def test_verify_acquire_extract_compile_run_with_external_key_pin(self):
        signed=self.signed_manifest(); pin=signed['public_key_sha256']; body=self.MODULE.encode('utf-8')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); signed_path=root/'signed.json'; acquisition=root/'acquisition.json'; bundle=root/'bundle.json'; app=root/'app.tevs'; ir=root/'program.json'; receipt=root/'receipt.json'
            signed_path.write_text(json.dumps(signed),encoding='utf-8'); app.write_text(self.APP,encoding='utf-8')
            code,out,err=self.call(['verify-signed-remote-module-manifest',str(signed_path),'--expected-public-key-sha256',pin])
            self.assertEqual((code,err),(0,'')); verified=json.loads(out)
            self.assertFalse(verified['network_accessed']); self.assertFalse(verified['runtime_network_acquisition']); self.assertEqual(verified['public_key_sha256'],pin)

            calls=[]
            original_fetch=UrllibHttpsModuleTransportV2.fetch
            def fake_fetch(instance,canonical_url,*,maximum_bytes):
                calls.append((canonical_url,maximum_bytes,instance.descriptor.descriptor_hash))
                return RemoteModuleFetchResponseV2(canonical_url,200,body)
            UrllibHttpsModuleTransportV2.fetch=fake_fetch
            try:
                code,out,err=self.call(['acquire-signed-remote-modules',str(signed_path),'--expected-public-key-sha256',pin,'-o',str(acquisition)])
            finally:
                UrllibHttpsModuleTransportV2.fetch=original_fetch
            self.assertEqual((code,err),(0,'')); acquired_summary=json.loads(out)
            self.assertTrue(acquired_summary['network_accessed']); self.assertFalse(acquired_summary['runtime_network_acquisition']); self.assertEqual(acquired_summary['public_key_sha256'],pin); self.assertEqual(len(calls),1)
            acquired=json.loads(acquisition.read_text(encoding='utf-8')); transport_hash=acquired['acquisition']['evidence']['transport']['descriptor_hash']

            code,out,err=self.call(['extract-signed-remote-module-bundle',str(acquisition),'--expected-public-key-sha256',pin,'--expected-transport-descriptor-hash',transport_hash,'-o',str(bundle)])
            self.assertEqual((code,err),(0,'')); extracted=json.loads(out)
            self.assertFalse(extracted['network_accessed']); self.assertFalse(extracted['runtime_network_acquisition']); self.assertEqual(extracted['public_key_sha256'],pin)
            code,out,err=self.call(['compile-modules',str(app),'--bundle',str(bundle),'-o',str(ir)])
            self.assertEqual((code,err),(0,'')); self.assertFalse(json.loads(out)['runtime_module_acquisition'])
            code,out,err=self.call(['run',str(ir),'-o',str(receipt)])
            self.assertEqual((code,err),(0,'')); result=json.loads(receipt.read_text(encoding='utf-8')); self.assertEqual(result['result_encoded'],{'$int':'7'})

    def test_wrong_key_pin_does_not_commit_extract_output(self):
        signed=self.signed_manifest(); pin=signed['public_key_sha256']; body=self.MODULE.encode('utf-8')
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); signed_path=root/'signed.json'; acquisition=root/'acquisition.json'; bundle=root/'bundle.json'
            signed_path.write_text(json.dumps(signed),encoding='utf-8')
            original_fetch=UrllibHttpsModuleTransportV2.fetch
            def fake_fetch(instance,canonical_url,*,maximum_bytes):
                return RemoteModuleFetchResponseV2(canonical_url,200,body)
            UrllibHttpsModuleTransportV2.fetch=fake_fetch
            try:
                self.assertEqual(self.call(['acquire-signed-remote-modules',str(signed_path),'--expected-public-key-sha256',pin,'-o',str(acquisition)])[0],0)
            finally:
                UrllibHttpsModuleTransportV2.fetch=original_fetch
            bundle.write_text('SENTINEL',encoding='utf-8')
            code,out,err=self.call(['extract-signed-remote-module-bundle',str(acquisition),'--expected-public-key-sha256','0'*64,'-o',str(bundle)])
            self.assertEqual(code,2); self.assertEqual(out,''); self.assertTrue(err); self.assertEqual(bundle.read_text(encoding='utf-8'),'SENTINEL')


if __name__=='__main__': unittest.main()
