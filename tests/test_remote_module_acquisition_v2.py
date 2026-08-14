from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.module_linker_v2 import compile_program_from_module_bundle_v2
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4
from tev_script.remote_module_acquisition_v2 import (
    RemoteModuleFetchResponseV2,
    acquire_remote_module_bundle_v2,
    build_remote_module_manifest_v2,
    build_remote_module_transport_descriptor_v2,
    canonical_remote_module_url_v2,
    validate_remote_module_acquisition_result_v2,
    validate_remote_module_manifest_v2,
)


class FakeTransport:
    def __init__(self, sources, *, provider_id='test.remote.a', final_url=None, status=200, maximum=2*1024*1024):
        self.sources=dict(sources)
        self.final_url=final_url
        self.status=status
        self.calls=[]
        self.descriptor=build_remote_module_transport_descriptor_v2(
            provider_id=provider_id,
            provider_version='1.0',
            implementation_hash=hashlib.sha256(provider_id.encode()).hexdigest(),
            maximum_response_bytes=maximum,
        )

    def fetch(self, canonical_url, *, maximum_bytes):
        self.calls.append((canonical_url,maximum_bytes))
        body=self.sources[canonical_url]
        return RemoteModuleFetchResponseV2(self.final_url or canonical_url,self.status,body)


class RemoteModuleAcquisitionV2Tests(unittest.TestCase):
    UTIL_URL='https://example.test/math-util.tevs'
    CORE_URL='https://example.test/core-num.tevs'
    UTIL='module math.util version "2.0.0"; export fn inc(x:Int)->Int=x+1; export fn twice(x:Int)->Int=inc(inc(x));'
    CORE='module core.num version "2.0.0"; export fn inc(x:Int)->Int=x+1;'

    def manifest(self, entries):
        return build_remote_module_manifest_v2(entries)

    def test_content_pinned_remote_acquisition_builds_offline_bundle_and_program_ir(self):
        body=self.UTIL.encode('utf-8')
        manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        transport=FakeTransport({self.UTIL_URL:body})
        acquired=acquire_remote_module_bundle_v2(manifest,transport)
        detached=json.loads(json.dumps(acquired))
        validated=validate_remote_module_acquisition_result_v2(detached,expected_transport_descriptor_hash=transport.descriptor.descriptor_hash,expected_manifest_hash=manifest['manifest_hash'])
        self.assertEqual(validated['bundle']['bundle_hash'],acquired['bundle']['bundle_hash'])
        self.assertEqual(len(transport.calls),1)
        app='script App version "2.0.0"; import math.util as u; fn solve(x:Int)->Int=u.twice(x); entry main:Int=solve(5);'
        linked=compile_program_from_module_bundle_v2(app,validated['bundle'])
        ir=export_program_ir_v4_pure(linked.compiled)
        receipt=run_program_ir_v4(json.loads(json.dumps(ir)))
        self.assertEqual(receipt.result_encoded,{'$int':'7'})
        self.assertNotIn(self.UTIL_URL,json.dumps(ir))

    def test_transitive_remote_modules_are_acquired_then_linked_offline(self):
        core=self.CORE.encode(); util='module math.util version "2.0.0"; import core.num as c; export fn twice(x:Int)->Int=c.inc(c.inc(x));'.encode()
        manifest=self.manifest([
            {'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(util).hexdigest()},
            {'module_id':'core.num','url':self.CORE_URL,'expected_sha256':hashlib.sha256(core).hexdigest()},
        ])
        transport=FakeTransport({self.UTIL_URL:util,self.CORE_URL:core})
        result=acquire_remote_module_bundle_v2(manifest,transport)
        app='script App version "2.0.0"; import math.util as u; fn solve(x:Int)->Int=u.twice(x); entry main:Int=solve(5);'
        linked=compile_program_from_module_bundle_v2(app,result['bundle'])
        self.assertEqual(run_program_ir_v4(export_program_ir_v4_pure(linked.compiled)).result_encoded,{'$int':'7'})
        self.assertEqual(len(transport.calls),2)

    def test_same_pinned_content_different_transport_provenance_changes_evidence_not_bundle(self):
        body=self.UTIL.encode(); manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        a=acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body},provider_id='test.remote.a'))
        b=acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body},provider_id='test.remote.b'))
        self.assertEqual(a['bundle'],b['bundle'])
        self.assertNotEqual(a['evidence']['transport']['descriptor_hash'],b['evidence']['transport']['descriptor_hash'])
        self.assertNotEqual(a['evidence']['evidence_hash'],b['evidence']['evidence_hash'])

    def test_wrong_content_hash_fails_before_bundle_exists(self):
        body=self.UTIL.encode(); manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':'0'*64}])
        with self.assertRaises(TevScriptError) as captured:
            acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body}))
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_CONTENT_PIN')

    def test_acquired_declared_module_id_must_match_manifest(self):
        body='module other.mod version "2.0.0"; export fn inc(x:Int)->Int=x+1;'.encode()
        manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        with self.assertRaises(TevScriptError) as captured:
            acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body}))
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_ID')

    def test_redirect_and_non_200_are_rejected(self):
        body=self.UTIL.encode(); manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        with self.assertRaises(TevScriptError) as captured:
            acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body},final_url='https://other.test/util.tevs'))
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_REDIRECT')
        with self.assertRaises(TevScriptError) as captured:
            acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body},status=304))
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_HTTP')

    def test_url_policy_is_https_no_credentials_query_fragment_or_custom_port(self):
        self.assertEqual(canonical_remote_module_url_v2('HTTPS://Example.TEST:443/a.tevs'),'https://example.test/a.tevs')
        for bad in ['http://example.test/a.tevs','https://u:p@example.test/a.tevs','https://example.test/a.tevs?q=1','https://example.test/a.tevs#x','https://example.test:444/a.tevs']:
            with self.subTest(url=bad):
                with self.assertRaises(TevScriptError): canonical_remote_module_url_v2(bad)

    def test_manifest_tamper_and_external_pins_fail_closed(self):
        body=self.UTIL.encode(); manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        tampered=copy.deepcopy(manifest); tampered['entries'][0]['expected_sha256']='0'*64
        with self.assertRaises(TevScriptError): validate_remote_module_manifest_v2(tampered)
        transport=FakeTransport({self.UTIL_URL:body}); result=acquire_remote_module_bundle_v2(manifest,transport)
        with self.assertRaises(TevScriptError): validate_remote_module_acquisition_result_v2(result,expected_manifest_hash='0'*64)
        with self.assertRaises(TevScriptError): validate_remote_module_acquisition_result_v2(result,expected_transport_descriptor_hash='0'*64)

    def test_evidence_source_tamper_is_detected(self):
        body=self.UTIL.encode(); manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        result=acquire_remote_module_bundle_v2(manifest,FakeTransport({self.UTIL_URL:body}))
        tampered=copy.deepcopy(result); tampered['evidence']['entries'][0]['source'] += '\n// changed'
        with self.assertRaises(TevScriptError) as captured:
            validate_remote_module_acquisition_result_v2(tampered)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_CONTENT_PIN')

    def test_transport_response_budget_is_enforced(self):
        body=self.UTIL.encode(); manifest=self.manifest([{'module_id':'math.util','url':self.UTIL_URL,'expected_sha256':hashlib.sha256(body).hexdigest()}])
        transport=FakeTransport({self.UTIL_URL:body},maximum=max(1,len(body)-1))
        with self.assertRaises(TevScriptError) as captured:
            acquire_remote_module_bundle_v2(manifest,transport)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_REMOTE_MODULE_BUDGET')


if __name__=='__main__': unittest.main()
