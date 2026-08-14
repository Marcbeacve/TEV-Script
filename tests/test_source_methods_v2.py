import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2

PAIR_PREFIX = 'script Demo version "2.0.0";\ngeneric record Pair<T>{left:T;right:T;}\ngeneric fn make<T>(x:T,y:T)->Pair<T>=Pair(left=x,right=y);\n'


class SourceMethodsV2Tests(unittest.TestCase):
    def test_concrete_impl_postfix_call_is_fully_inlined(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(2,3).sum();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"5"})
        method_templates=[item for item in compiled.function_template_hashes if "__tev_method_" in item[0]]
        self.assertEqual(len(method_templates),1)
        body=str(export_program_ir_v4_pure(compiled)["entry"]["body"])
        self.assertNotIn("CALL_METHOD",body)
        self.assertNotIn("method_call",body)

    def test_parameter_dotted_method_call_dispatches_statically(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
fn use(p:Pair<Int>)->Int=p.sum();
fn main_value()->Int=use(make<Int>(6,7));
entry main:Int=main_value();'''
        _compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"13"})

    def test_method_extra_argument_and_method_composition(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{
fn sum(self)->Int=self.left+self.right;
fn plus(self,n:Int)->Int=self.sum()+n;
}
fn main_value()->Int=make<Int>(2,3).plus(4);
entry main:Int=main_value();'''
        _compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"9"})

    def test_missing_method_fails_closed(self):
        source=PAIR_PREFIX+'''fn use(p:Pair<Int>)->Int=p.sum();
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_METHOD_DISPATCH")

    def test_duplicate_receiver_method_fails_closed(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left;}
impl Pair<Int>{fn sum(self)->Int=self.right;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_METHOD_DUPLICATE")

    def test_non_record_impl_receiver_fails_closed(self):
        source='''script Demo version "2.0.0";
impl Int{fn value(self)->Int=1;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_METHOD_RECEIVER")

    def test_generic_impl_receiver_is_not_admitted_in_r1(self):
        source=PAIR_PREFIX+'''impl Pair<T>{fn first(self)->T=self.left;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_METHOD_RECEIVER")

    def test_method_requires_explicit_self(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(p)->Int=p.left;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_METHOD_SELF")

    def test_generic_caller_cannot_assume_concrete_impl(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
generic fn use<T>(p:Pair<T>)->Int=p.sum();
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_METHOD_DISPATCH")

    def test_method_body_change_changes_semantic_identity(self):
        base=PAIR_PREFIX+'''impl Pair<Int>{fn pick(self)->Int=BODY;}
fn main_value()->Int=make<Int>(2,3).pick();
entry main:Int=main_value();'''
        left=compile_program_v2(base.replace("BODY","self.left"))
        right=compile_program_v2(base.replace("BODY","self.right"))
        self.assertNotEqual(left.semantic_hash,right.semantic_hash)
        left_methods=[item for item in left.function_template_hashes if "__tev_method_" in item[0]]
        right_methods=[item for item in right.function_template_hashes if "__tev_method_" in item[0]]
        self.assertEqual(left_methods[0][0],right_methods[0][0])
        self.assertNotEqual(left_methods[0][1],right_methods[0][1])
        self.assertNotEqual(left.entry.entry_hash,right.entry.entry_hash)

    def test_method_cycle_is_rejected_by_hygienic_inliner(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{
fn a(self)->Int=self.b();
fn b(self)->Int=self.a();
}
fn main_value()->Int=make<Int>(1,2).a();
entry main:Int=main_value();'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CALL_CYCLE")

    def test_detached_program_ir_preserves_method_result(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(8,9).sum();
entry main:Int=main_value();'''
        compiled,source_receipt=compile_and_run_program_v2(source)
        detached=copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable=run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_encoded,source_receipt.result_encoded)
        self.assertEqual(portable.result_hash,source_receipt.result_hash)
        self.assertNotIn("CALL_METHOD",str(detached))

    def test_unknown_qualified_global_call_still_fails_closed(self):
        source='''script Demo version "2.0.0";
fn bad()->Int=unknown.fn();
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CALL")


if __name__=="__main__":
    unittest.main()
