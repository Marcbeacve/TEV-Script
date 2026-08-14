from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import (
    canonical_program_ir_v4_bytes,
    export_program_ir_v4_recursive,
    run_program_ir_v4,
    run_program_ir_v4_recursive,
    validate_program_ir_v4,
    validate_program_ir_v4_recursive,
)
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


def _rehash(ir: dict) -> None:
    payload=dict(ir); payload.pop("program_ir_hash",None)
    ir["program_ir_hash"]=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()


class ProgramIRV4RecursiveTests(unittest.TestCase):
    FACTORIAL='''
    script Demo version "2.0.0";
    recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
    entry main:Int=factorial(5);
    '''

    def test_factorial_detached_json_matches_source_runtime(self) -> None:
        compiled,source_receipt=compile_and_run_program_v2(self.FACTORIAL)
        ir=export_program_ir_v4_recursive(compiled)
        detached=json.loads(canonical_program_ir_v4_bytes(ir).decode())
        validation=validate_program_ir_v4_recursive(detached)
        receipt=run_program_ir_v4_recursive(detached)
        self.assertEqual(receipt.result_encoded,source_receipt.result_encoded)
        self.assertEqual(receipt.result_hash,source_receipt.result_hash)
        self.assertEqual(receipt.result_encoded,{"$int":"120"})
        self.assertEqual(validation.contract.measure_parameter,"n")
        self.assertEqual(validation.contract.max_depth,8)

    def test_generic_recursive_list_is_portable(self) -> None:
        source='''
        script Demo version "2.0.0";
        recursive fn repeat<T>(n:Int,x:T,acc:List<T,4>)->List<T,4> decreases n max_depth 4 = if n==0 then acc else self(n-1,x,list.push(acc,x));
        entry main:List<Int,4>=repeat<Int>(3,7,[]);
        '''
        compiled,old=compile_and_run_program_v2(source)
        ir=export_program_ir_v4_recursive(compiled)
        new=run_program_ir_v4(json.loads(json.dumps(ir)))
        self.assertEqual(new.result_encoded,old.result_encoded)
        self.assertEqual(new.result_hash,old.result_hash)

    def test_general_dispatch_validates_recursive_profile(self) -> None:
        ir=export_program_ir_v4_recursive(compile_program_v2(self.FACTORIAL))
        validation=validate_program_ir_v4(ir)
        receipt=run_program_ir_v4(ir)
        self.assertEqual(validation.program_ir_hash,ir["program_ir_hash"])
        self.assertEqual(receipt.result_encoded,{"$int":"120"})

    def test_contract_tamper_is_rejected_even_after_outer_rehash(self) -> None:
        ir=export_program_ir_v4_recursive(compile_program_v2(self.FACTORIAL))
        tampered=copy.deepcopy(ir)
        tampered["entry"]["recursion_contract"]["max_depth"]=7
        _rehash(tampered)
        with self.assertRaises(TevScriptError) as captured:
            validate_program_ir_v4_recursive(tampered)
        self.assertIn(captured.exception.diagnostic.code,{"TEVS_PROGRAM_IR_V4_RECURSION_CONTRACT","TEVS_PROGRAM_IR_V4_RECURSION_CONTRACT_HASH"})

    def test_body_tamper_is_rejected_after_outer_rehash(self) -> None:
        ir=export_program_ir_v4_recursive(compile_program_v2(self.FACTORIAL))
        tampered=copy.deepcopy(ir)
        def mutate(v):
            if isinstance(v,dict):
                if v.get("op")=="CONST" and v.get("value")=={"$int":"1"}:
                    v["value"]={"$int":"2"}; return True
                return any(mutate(x) for x in v.values())
            if isinstance(v,list): return any(mutate(x) for x in v)
            return False
        self.assertTrue(mutate(tampered["entry"]["body"]))
        _rehash(tampered)
        with self.assertRaises(TevScriptError): validate_program_ir_v4_recursive(tampered)

    def test_external_hash_pin_rejects_valid_replacement(self) -> None:
        ir=export_program_ir_v4_recursive(compile_program_v2(self.FACTORIAL))
        expected=ir["program_ir_hash"]
        replacement=export_program_ir_v4_recursive(compile_program_v2(self.FACTORIAL.replace('factorial(5)','factorial(4)')))
        validate_program_ir_v4_recursive(replacement)
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_recursive(replacement,expected_program_ir_hash=expected)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_PROGRAM_IR_V4_EXPECTED_HASH")

    def test_pure_schema_is_not_accepted_by_recursive_validator(self) -> None:
        from tev_script.program_ir_v4 import export_program_ir_v4_pure
        pure=export_program_ir_v4_pure(compile_program_v2('script Demo version "2.0.0"; fn f(x:Int)->Int=x+1; entry main:Int=f(1);'))
        with self.assertRaises(TevScriptError): validate_program_ir_v4_recursive(pure)


if __name__=="__main__": unittest.main()
