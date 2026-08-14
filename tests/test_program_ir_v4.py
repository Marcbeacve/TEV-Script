from __future__ import annotations

import copy
import hashlib
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import (
    canonical_program_ir_v4_bytes,
    export_program_ir_v4_pure,
    run_program_ir_v4_pure,
    validate_program_ir_v4_pure,
)
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


def _rehash(ir: dict) -> None:
    payload = dict(ir)
    payload.pop("program_ir_hash", None)
    ir["program_ir_hash"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


class ProgramIRV4PureTests(unittest.TestCase):
    SOURCE = '''
    script Demo version "2.0.0";
    fn add1(x:Int)->Int=x+1;
    generic fn middle<T>(xs:Array<T,3>)->T=array.get(xs,1);
    fn combine(x:Int)->Int=add1(x)*2;
    entry main:Int=combine(4);
    '''

    def test_export_json_roundtrip_and_independent_execution_match_source(self) -> None:
        compiled, source_receipt = compile_and_run_program_v2(self.SOURCE)
        ir = export_program_ir_v4_pure(compiled)
        wire = canonical_program_ir_v4_bytes(ir)
        detached = json.loads(wire.decode("utf-8"))
        validation = validate_program_ir_v4_pure(detached)
        portable_receipt = run_program_ir_v4_pure(detached)
        self.assertEqual(portable_receipt.result_type, source_receipt.result_type)
        self.assertEqual(portable_receipt.result_encoded, source_receipt.result_encoded)
        self.assertEqual(portable_receipt.result_hash, source_receipt.result_hash)
        self.assertEqual(validation.program_ir_hash, ir["program_ir_hash"])
        self.assertEqual(validation.source_semantic_hash, compiled.semantic_hash)

    def test_inlined_program_ir_has_no_runtime_function_dispatch(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn a(x:Int)->Int=x+1;
        fn b(x:Int)->Int=a(x)*2;
        fn c(x:Int)->Int=b(x)+3;
        entry main:Int=c(4);
        '''
        ir = export_program_ir_v4_pure(compile_program_v2(source))
        def walk(value):
            if isinstance(value, dict):
                if value.get("op") == "CALL":
                    return True
                return any(walk(v) for v in value.values())
            if isinstance(value, list):
                return any(walk(v) for v in value)
            return False
        self.assertFalse(walk(ir["entry"]["body"]))
        self.assertEqual(run_program_ir_v4_pure(ir).result_encoded, {"$int":"13"})

    def test_semantically_identical_source_formatting_exports_identical_ir(self) -> None:
        compact = 'script Demo version "2.0.0"; fn add(x:Int,y:Int)->Int=x+y; entry main:Int=add(2,3);'
        spaced = '''
        // surface-only formatting
        script Demo version "2.0.0";
        fn add( x : Int , y : Int ) -> Int = x + y;
        entry main : Int = add(2,3);
        '''
        self.assertEqual(
            export_program_ir_v4_pure(compile_program_v2(compact)),
            export_program_ir_v4_pure(compile_program_v2(spaced)),
        )

    def test_type_table_tamper_is_rejected_even_before_execution(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.SOURCE))
        tampered = copy.deepcopy(ir)
        for descriptor in tampered["type_table"]["types"]:
            if descriptor["type_id"] == "Int":
                descriptor["type_id"] = "Text"
                break
        _rehash(tampered)
        with self.assertRaises(TevScriptError):
            validate_program_ir_v4_pure(tampered)

    def test_body_tamper_is_rejected_even_if_outer_hash_is_recomputed(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.SOURCE))
        tampered = copy.deepcopy(ir)
        body = tampered["entry"]["body"]
        def mutate(value) -> bool:
            if isinstance(value, dict):
                if value.get("op") == "CONST" and value.get("type") == "Int" and value.get("value") == {"$int":"2"}:
                    value["value"] = {"$int":"3"}
                    return True
                return any(mutate(v) for v in value.values())
            if isinstance(value, list):
                return any(mutate(v) for v in value)
            return False
        self.assertTrue(mutate(body))
        _rehash(tampered)
        with self.assertRaises(TevScriptError) as captured:
            validate_program_ir_v4_pure(tampered)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_PROGRAM_IR_V4_BODY_HASH")

    def test_argument_tamper_without_hash_update_is_rejected(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.SOURCE))
        tampered = copy.deepcopy(ir)
        tampered["entry"]["arguments"][0]["value"] = {"$int":"5"}
        with self.assertRaises(TevScriptError) as captured:
            validate_program_ir_v4_pure(tampered)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_PROGRAM_IR_V4_HASH")

    def test_static_bound_tamper_is_rejected_even_if_outer_hash_is_recomputed(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.SOURCE))
        tampered = copy.deepcopy(ir)
        tampered["entry"]["static_step_upper_bound"] += 1
        _rehash(tampered)
        with self.assertRaises(TevScriptError) as captured:
            validate_program_ir_v4_pure(tampered)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_PROGRAM_IR_V4_STATIC_BOUND")

    def test_type_closure_tamper_is_rejected(self) -> None:
        source = '''
        script Demo version "2.0.0";
        generic fn middle<T>(xs:Array<T,3>)->T=array.get(xs,1);
        entry main:Int=middle<Int>([4,9,7]);
        '''
        ir = export_program_ir_v4_pure(compile_program_v2(source))
        tampered = copy.deepcopy(ir)
        tampered["entry"]["type_closure_roots"] = ["Int"]
        _rehash(tampered)
        with self.assertRaises(TevScriptError):
            validate_program_ir_v4_pure(tampered)

    def test_recursive_entry_is_not_silently_exported_as_pure_ir(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
        entry main:Int=factorial(5);
        '''
        compiled = compile_program_v2(source)
        with self.assertRaises(TevScriptError) as captured:
            export_program_ir_v4_pure(compiled)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_PROGRAM_IR_V4_PROFILE")

    def test_external_program_hash_pin_rejects_valid_rehashed_replacement(self) -> None:
        ir = export_program_ir_v4_pure(compile_program_v2(self.SOURCE))
        expected_hash = ir["program_ir_hash"]
        tampered = copy.deepcopy(ir)
        tampered["entry"]["arguments"][0]["value"] = {"$int":"5"}
        _rehash(tampered)
        self.assertNotEqual(tampered["program_ir_hash"], expected_hash)
        validate_program_ir_v4_pure(tampered)
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(tampered, expected_program_ir_hash=expected_hash)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_PROGRAM_IR_V4_EXPECTED_HASH")

    def test_external_source_semantic_pin_rejects_other_valid_program(self) -> None:
        left = export_program_ir_v4_pure(compile_program_v2(self.SOURCE))
        other_source = """
        script Demo version \"2.0.0\";
        fn add1(x:Int)->Int=x+2;
        fn combine(x:Int)->Int=add1(x)*2;
        entry main:Int=combine(4);
        """
        right = export_program_ir_v4_pure(compile_program_v2(other_source))
        validate_program_ir_v4_pure(right)
        with self.assertRaises(TevScriptError) as captured:
            run_program_ir_v4_pure(
                right,
                expected_source_semantic_hash=left["source"]["semantic_hash"],
            )
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_PROGRAM_IR_V4_EXPECTED_SOURCE")


if __name__ == "__main__":
    unittest.main()
