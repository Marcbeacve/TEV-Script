from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.module_linker_v2 import compile_program_from_module_bundle_v2
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4
from tev_script.remote_module_acquisition_v2 import (
    RemoteModuleFetchResponseV2,
    build_remote_module_manifest_v2,
    build_remote_module_transport_descriptor_v2,
)
from tev_script.signed_remote_module_manifest_v2 import (
    acquire_signed_remote_module_bundle_v2,
    module_bundle_from_signed_remote_acquisition_v2,
    sign_remote_module_manifest_ed25519_v2,
    validate_signed_remote_module_acquisition_result_v2,
    verify_signed_remote_module_manifest_v2,
)


class FakeTransport:
    def __init__(self,url,body):
        self.url=url; self.body=body
        self.descriptor=build_remote_module_transport_descriptor_v2(
            provider_id='test.signed.remote',provider_version='1',implementation_hash='2'*64,maximum_response_bytes=2*1024*1024
        )
    def fetch(self,canonical_url,*,maximum_bytes):
        return RemoteModuleFetchResponseV2(canonical_url,200,self.body)


class SignedRemoteModuleManifestV2Tests(unittest.TestCase):
    URL='https://example.test/math-util.tevs'
    MODULE='module math.util version "2.0.0"; export fn twice(x:Int)->Int=x+2;'
    KEY_A=b'\x11'*32
    KEY_B=b'\x22'*32

    def manifest(self):
        body=self.MODULE.encode()
        return build_remote_module_manifest_v2([{'module_id':'math.util','url':self.URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])

    def signed(self,key=None):
        return sign_remote_module_manifest_ed25519_v2(self.manifest(),key or self.KEY_A,key_id='release')

    def test_valid_ed25519_signature_requires_external_public_key_pin(self):
        signed=self.signed(); pin=signed['public_key_sha256']
        verified=verify_signed_remote_module_manifest_v2(signed,expected_public_key_sha256=pin)
        self.assertEqual(verified['manifest']['manifest_hash'],self.manifest()['manifest_hash'])
        self.assertEqual(verified['verification']['public_key_sha256'],pin)
        self.assertEqual(verified['verification']['algorithm'],'ed25519')
        self.assertEqual(len(verified['verification']['verification_hash']),64)

    def test_attacker_key_with_same_key_id_is_rejected_by_external_pin(self):
        trusted=self.signed(self.KEY_A); attacker=self.signed(self.KEY_B)
        self.assertEqual(trusted['key_id'],attacker['key_id'])
        self.assertNotEqual(trusted['public_key_sha256'],attacker['public_key_sha256'])
        with self.assertRaises(TevScriptError) as captured:
            verify_signed_remote_module_manifest_v2(attacker,expected_public_key_sha256=trusted['public_key_sha256'])
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_SIGNATURE_TRUST')

    def test_signature_tamper_is_detected_even_with_rehashed_envelope(self):
        signed=self.signed(); pin=signed['public_key_sha256']; tampered=copy.deepcopy(signed)
        raw=bytearray(base64.b64decode(tampered['signature_b64'])); raw[0]^=1; sig=bytes(raw)
        tampered['signature_b64']=base64.b64encode(sig).decode('ascii'); tampered['signature_sha256']=hashlib.sha256(sig).hexdigest()
        payload={k:tampered[k] for k in tampered if k!='envelope_hash'}
        tampered['envelope_hash']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        with self.assertRaises(TevScriptError) as captured:
            verify_signed_remote_module_manifest_v2(tampered,expected_public_key_sha256=pin)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_SIGNATURE_INVALID')

    def test_manifest_tamper_cannot_be_resigned_by_envelope_hash_only(self):
        signed=self.signed(); pin=signed['public_key_sha256']; tampered=copy.deepcopy(signed)
        tampered['manifest']['entries'][0]['expected_sha256']='0'*64
        payload={k:tampered[k] for k in tampered if k!='envelope_hash'}
        tampered['envelope_hash']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
        with self.assertRaises(TevScriptError):
            verify_signed_remote_module_manifest_v2(tampered,expected_public_key_sha256=pin)

    def test_signed_acquire_validate_extract_compile_and_run_offline(self):
        signed=self.signed(); pin=signed['public_key_sha256']; body=self.MODULE.encode(); transport=FakeTransport(self.URL,body)
        result=acquire_signed_remote_module_bundle_v2(signed,expected_public_key_sha256=pin,transport=transport)
        detached=json.loads(json.dumps(result))
        validated=validate_signed_remote_module_acquisition_result_v2(detached,expected_public_key_sha256=pin,expected_transport_descriptor_hash=transport.descriptor.descriptor_hash)
        bundle=module_bundle_from_signed_remote_acquisition_v2(validated,expected_public_key_sha256=pin,expected_transport_descriptor_hash=transport.descriptor.descriptor_hash)
        app='script App version "2.0.0"; import math.util as u; fn solve(x:Int)->Int=u.twice(x); entry main:Int=solve(5);'
        linked=compile_program_from_module_bundle_v2(app,bundle)
        self.assertEqual(run_program_ir_v4(export_program_ir_v4_pure(linked.compiled)).result_encoded,{'$int':'7'})

    def test_signed_result_wrong_key_or_transport_pin_fails(self):
        signed=self.signed(); pin=signed['public_key_sha256']; transport=FakeTransport(self.URL,self.MODULE.encode())
        result=acquire_signed_remote_module_bundle_v2(signed,expected_public_key_sha256=pin,transport=transport)
        with self.assertRaises(TevScriptError): validate_signed_remote_module_acquisition_result_v2(result,expected_public_key_sha256='0'*64)
        with self.assertRaises(TevScriptError): validate_signed_remote_module_acquisition_result_v2(result,expected_public_key_sha256=pin,expected_transport_descriptor_hash='0'*64)


if __name__=='__main__': unittest.main()
