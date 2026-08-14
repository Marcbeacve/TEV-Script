from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


class SourceCallsV2Tests(unittest.TestCase):
    def test_plain_function_calls_plain_function(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn add1(x:Int)->Int=x+1;
        fn twice(x:Int)->Int=add1(add1(x));
        entry main:Int=twice(3);
        '''
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"5"})
        self.assertEqual(compiled.entry.function_kind, "pure")

    def test_generic_function_call_requires_explicit_type_arguments_and_executes(self) -> None:
        source = '''
        script Demo version "2.0.0";
        generic fn identity<T>(x:T)->T=x;
        generic fn wrapper<T>(x:T)->T=identity<T>(x);
        entry main:Int=wrapper<Int>(7);
        '''
        _, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"7"})

    def test_transitive_call_chain_is_inlined_and_executes(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn a(x:Int)->Int=x+1;
        fn b(x:Int)->Int=a(x)*2;
        fn c(x:Int)->Int=b(x)+3;
        entry main:Int=c(4);
        '''
        _, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"13"})

    def test_callee_body_change_changes_caller_and_program_identity(self) -> None:
        left = '''
        script Demo version "2.0.0";
        fn helper(x:Int)->Int=x+1;
        fn caller(x:Int)->Int=helper(x)*2;
        entry main:Int=caller(3);
        '''
        right = '''
        script Demo version "2.0.0";
        fn helper(x:Int)->Int=x+2;
        fn caller(x:Int)->Int=helper(x)*2;
        entry main:Int=caller(3);
        '''
        a, ra = compile_and_run_program_v2(left)
        b, rb = compile_and_run_program_v2(right)
        self.assertEqual(ra.result_encoded, {"$int":"8"})
        self.assertEqual(rb.result_encoded, {"$int":"10"})
        self.assertNotEqual(dict(a.function_template_hashes)["Demo.caller"], dict(b.function_template_hashes)["Demo.caller"])
        self.assertNotEqual(a.semantic_hash, b.semantic_hash)

    def test_call_graph_cycle_fails_closed(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn a(x:Int)->Int=b(x);
        fn b(x:Int)->Int=a(x);
        entry main:Int=a(1);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_CALL_CYCLE")

    def test_pure_function_cannot_call_recursive_function(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn down(n:Int)->Int decreases n max_depth 8 = if n==0 then 0 else self(n-1);
        fn wrapper(n:Int)->Int=down(n);
        entry main:Int=wrapper(3);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_CALL_RECURSIVE")

    def test_inline_parameter_hygiene_prevents_capture(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn helper(x:Int,y:Int)->Int=x-y;
        fn caller(x:Int)->Int=helper(x+10,x);
        entry main:Int=caller(4);
        '''
        _, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {"$int":"10"})

    def test_generic_call_without_required_type_argument_is_rejected(self) -> None:
        source = '''
        script Demo version "2.0.0";
        generic fn identity<T>(x:T)->T=x;
        generic fn wrapper<T>(x:T)->T=identity(x);
        entry main:Int=wrapper<Int>(1);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_PROGRAM_CALL_ARITY")


if __name__ == "__main__":
    unittest.main()
