from __future__ import annotations

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


class SourceAsyncAwaitAllR1Tests(unittest.TestCase):
    def test_plain_source_fan_out_fan_in_runs(self) -> None:
        source = '''
        script AsyncDemo version "2.0.0";
        fn square(x:Int)->Int=x*x;
        entry main:Int=await all(a:Int=square(3), b:Int=square(4)) => a+b;
        '''
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"25"})
        self.assertEqual(compiled.entry.function_kind, "pure")

    def test_generic_function_can_use_structured_await_all(self) -> None:
        source = '''
        script AsyncGeneric version "2.0.0";
        generic fn chooseFirst<T>(x:T,y:T)->T=await all(a:T=x,b:T=y)=>a;
        entry main:Text=chooseFirst<Text>("left","right");
        '''
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, "left")

    def test_nested_scopes_are_source_expressions(self) -> None:
        source = '''
        script AsyncNested version "2.0.0";
        entry main:Int=await all(
            a:Int=await all(x:Int=1,y:Int=2)=>x+y,
            b:Int=4
        )=>a+b;
        '''
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"7"})

    def test_collection_values_flow_through_task_bindings(self) -> None:
        source = '''
        script AsyncCollections version "2.0.0";
        entry main:Int=await all(
            a:List<Int,4>=[1,2],
            b:Array<Int,2>=[3,4]
        )=>len(a)+len(b);
        '''
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"4"})

    def test_task_declaration_order_is_not_semantic(self) -> None:
        left = '''
        script AsyncOrder version "2.0.0";
        entry main:Int=await all(a:Int=1,b:Int=2)=>a+b;
        '''
        right = '''
        script AsyncOrder version "2.0.0";
        entry main:Int=await all(b:Int=2,a:Int=1)=>a+b;
        '''
        a, ar = compile_and_run_program_v2(left)
        b, br = compile_and_run_program_v2(right)
        self.assertEqual(a.semantic_hash, b.semantic_hash)
        self.assertEqual(a.entry.entry_hash, b.entry.entry_hash)
        self.assertEqual(ar.result_hash, br.result_hash)

    def test_sibling_task_result_is_not_visible_to_other_task(self) -> None:
        source = '''
        script AsyncIsolation version "2.0.0";
        entry main:Int=await all(a:Int=1,b:Int=a+1)=>a+b;
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_NAME")

    def test_task_binding_cannot_shadow_outer_value(self) -> None:
        source = '''
        script AsyncShadow version "2.0.0";
        fn f(x:Int)->Int=await all(x:Int=1)=>x;
        entry main:Int=f(9);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_TASK_BINDING")

    def test_task_count_is_bounded_at_64(self) -> None:
        tasks = ",".join(f"t{i}:Int={i}" for i in range(65))
        source = f'''script AsyncBound version "2.0.0"; entry main:Int=await all({tasks})=>t0;'''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_TASK_BOUND")

    def test_program_ir_roundtrip_preserves_task_scope_without_scheduler_dependency(self) -> None:
        source = '''
        script AsyncPortable version "2.0.0";
        fn twice(x:Int)->Int=x*2;
        entry main:Int=await all(a:Int=twice(5),b:Int=twice(7))=>a+b;
        '''
        compiled, source_receipt = compile_and_run_program_v2(source)
        ir = export_program_ir_v4_pure(compiled)
        wire = canonical_program_ir_v4_bytes(ir)
        detached = json.loads(wire.decode("utf-8"))
        validation = validate_program_ir_v4_pure(detached)
        portable = run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_encoded, source_receipt.result_encoded)
        self.assertEqual(portable.result_hash, source_receipt.result_hash)
        self.assertEqual(validation.program_ir_hash, detached["program_ir_hash"])
        self.assertEqual(detached["entry"]["body"]["op"], "TASK_SCOPE")

    def test_recursive_function_may_use_pure_task_scope_in_nonrecursive_branch(self) -> None:
        source = '''
        script AsyncRecursiveBase version "2.0.0";
        recursive fn countdown(n:Int)->Int decreases n max_depth 8 =
            if n==0 then await all(a:Int=20,b:Int=22)=>a+b else self(n-1);
        entry main:Int=countdown(3);
        '''
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"42"})

    def test_self_call_inside_task_scope_is_rejected_in_r1(self) -> None:
        source = '''
        script AsyncRecursiveReject version "2.0.0";
        recursive fn countdown(n:Int)->Int decreases n max_depth 8 =
            if n==0 then 0 else await all(a:Int=self(n-1),b:Int=1)=>a+b;
        entry main:Int=countdown(3);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_TASK_RECURSION")


if __name__ == "__main__":
    unittest.main()
