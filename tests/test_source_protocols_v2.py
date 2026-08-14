import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2

PAIR_PREFIX = 'script Demo version "2.0.0";\ngeneric record Pair<T>{left:T;right:T;}\ngeneric fn make<T>(x:T,y:T)->Pair<T>=Pair(left=x,right=y);\n'


class SourceProtocolsV2Tests(unittest.TestCase):
    def test_explicit_conformance_builds_content_addressed_witness(self):
        source=PAIR_PREFIX+'''protocol Summable{fn sum(self)->Int;}
impl Pair<Int> : Summable{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(2,3).sum();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"5"})
        self.assertEqual(len(compiled.protocol_hashes),1)
        self.assertEqual(len(compiled.protocol_witnesses),1)
        witness=compiled.protocol_witnesses[0]
        self.assertEqual(witness.protocol_name,"Summable")
        self.assertEqual(witness.receiver_source_type,"Pair<Int>")
        self.assertTrue(witness.receiver_runtime_type.startswith("Demo.Pair__g_"))
        method_hash=dict(witness.method_template_hashes)["sum"]
        compiled_method_hash=[h for n,h in compiled.function_template_hashes if "__tev_method_" in n][0]
        self.assertEqual(method_hash,compiled_method_hash)

    def test_structural_match_without_explicit_conformance_creates_no_witness(self):
        source=PAIR_PREFIX+'''protocol Summable{fn sum(self)->Int;}
impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
entry main:Int=0;'''
        compiled=compile_program_v2(source)
        self.assertEqual(len(compiled.protocol_hashes),1)
        self.assertEqual(compiled.protocol_witnesses,())

    def test_unknown_protocol_in_impl_fails_closed(self):
        source=PAIR_PREFIX+'''impl Pair<Int> : Missing{fn sum(self)->Int=0;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_UNKNOWN")

    def test_missing_required_method_fails_closed(self):
        source=PAIR_PREFIX+'''protocol Both{fn left_value(self)->Int;fn right_value(self)->Int;}
impl Pair<Int> : Both{fn left_value(self)->Int=self.left;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_MISSING_METHOD")

    def test_two_partial_blocks_cannot_jointly_satisfy_protocol(self):
        source=PAIR_PREFIX+'''protocol Both{fn left_value(self)->Int;fn right_value(self)->Int;}
impl Pair<Int> : Both{fn left_value(self)->Int=self.left;}
impl Pair<Int> : Both{fn right_value(self)->Int=self.right;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_MISSING_METHOD")

    def test_signature_mismatch_fails_closed(self):
        source=PAIR_PREFIX+'''protocol Shift{fn shift(self,n:Int)->Int;}
impl Pair<Int> : Shift{fn shift(self,n:Text)->Int=self.left;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_SIGNATURE")

    def test_return_signature_mismatch_fails_closed(self):
        source=PAIR_PREFIX+'''protocol Pick{fn pick(self)->Int;}
impl Pair<Int> : Pick{fn pick(self)->Text="x";}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_SIGNATURE")

    def test_duplicate_protocol_declaration_fails_closed(self):
        source='''script Demo version "2.0.0";
protocol P{fn a(self)->Int;}
protocol P{fn a(self)->Int;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE")

    def test_duplicate_protocol_method_fails_closed(self):
        source='''script Demo version "2.0.0";
protocol P{fn a(self)->Int;fn a(self)->Int;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_METHOD")

    def test_duplicate_protocol_impl_for_same_receiver_fails_closed(self):
        source=PAIR_PREFIX+'''protocol P{fn a(self)->Int;}
impl Pair<Int> : P{fn a(self)->Int=self.left;}
impl Pair<Int> : P{fn helper(self)->Int=self.right;fn a2(self)->Int=0;}
entry main:Int=0;'''
        # The second block is itself incomplete, which is fail-closed before duplicate witness.
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertIn(ctx.exception.diagnostic.code,{"TEVS_V2_PROGRAM_PROTOCOL_MISSING_METHOD","TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_IMPL"})

    def test_protocol_parameter_names_are_not_semantic(self):
        left='''script Demo version "2.0.0";
protocol P{fn add(self,x:Int)->Int;}
entry main:Int=0;'''
        right=left.replace("x:Int","renamed:Int")
        a=compile_program_v2(left)
        b=compile_program_v2(right)
        self.assertEqual(a.protocol_hashes,b.protocol_hashes)
        self.assertEqual(a.semantic_hash,b.semantic_hash)

    def test_protocol_method_order_is_canonical(self):
        left='''script Demo version "2.0.0";
protocol P{fn a(self)->Int;fn b(self,n:Int)->Int;}
entry main:Int=0;'''
        right='''script Demo version "2.0.0";
protocol P{fn b(self,n:Int)->Int;fn a(self)->Int;}
entry main:Int=0;'''
        a=compile_program_v2(left)
        b=compile_program_v2(right)
        self.assertEqual(a.protocol_hashes,b.protocol_hashes)
        self.assertEqual(a.semantic_hash,b.semantic_hash)

    def test_method_body_change_changes_witness_not_protocol_hash(self):
        base=PAIR_PREFIX+'''protocol Picker{fn pick(self)->Int;}
impl Pair<Int> : Picker{fn pick(self)->Int=BODY;}
entry main:Int=0;'''
        left=compile_program_v2(base.replace("BODY","self.left"))
        right=compile_program_v2(base.replace("BODY","self.right"))
        self.assertEqual(left.protocol_hashes,right.protocol_hashes)
        self.assertNotEqual(left.protocol_witnesses[0].witness_hash,right.protocol_witnesses[0].witness_hash)
        self.assertNotEqual(left.semantic_hash,right.semantic_hash)

    def test_protocol_signature_change_changes_protocol_and_witness_hash(self):
        one=PAIR_PREFIX+'''protocol P{fn f(self,n:Int)->Int;}
impl Pair<Int> : P{fn f(self,n:Int)->Int=self.left+n;}
entry main:Int=0;'''
        two=PAIR_PREFIX+'''protocol P{fn f(self,n:Int,m:Int)->Int;}
impl Pair<Int> : P{fn f(self,n:Int,m:Int)->Int=self.left+n+m;}
entry main:Int=0;'''
        a=compile_program_v2(one)
        b=compile_program_v2(two)
        self.assertNotEqual(a.protocol_hashes,b.protocol_hashes)
        self.assertNotEqual(a.protocol_witnesses[0].witness_hash,b.protocol_witnesses[0].witness_hash)

    def test_extra_helper_method_does_not_enter_witness_method_set(self):
        source=PAIR_PREFIX+'''protocol P{fn sum(self)->Int;}
impl Pair<Int> : P{fn helper(self)->Int=1;fn sum(self)->Int=self.left+self.right;}
entry main:Int=0;'''
        compiled=compile_program_v2(source)
        witness=compiled.protocol_witnesses[0]
        self.assertEqual(tuple(name for name,_hash in witness.method_template_hashes),("sum",))

    def test_same_protocol_can_have_distinct_concrete_receiver_witnesses(self):
        source='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
protocol Valued{fn value(self)->Int;}
impl Box<Int> : Valued{fn value(self)->Int=self.value;}
impl Box<Text> : Valued{fn value(self)->Int=7;}
entry main:Int=0;'''
        compiled=compile_program_v2(source)
        self.assertEqual(len(compiled.protocol_witnesses),2)
        runtime_types={w.receiver_runtime_type for w in compiled.protocol_witnesses}
        witness_hashes={w.witness_hash for w in compiled.protocol_witnesses}
        self.assertEqual(len(runtime_types),2)
        self.assertEqual(len(witness_hashes),2)

    def test_protocol_type_must_be_concrete_in_r1(self):
        source='''script Demo version "2.0.0";
protocol P{fn f(self,x:Unknown)->Int;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_TYPE")

    def test_protocol_self_is_required(self):
        source='''script Demo version "2.0.0";
protocol P{fn f(x)->Int;}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_SELF")

    def test_detached_program_ir_contains_no_protocol_runtime_dispatch(self):
        source=PAIR_PREFIX+'''protocol P{fn sum(self)->Int;}
impl Pair<Int> : P{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(8,9).sum();
entry main:Int=main_value();'''
        compiled,source_receipt=compile_and_run_program_v2(source)
        detached=copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable=run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash,source_receipt.result_hash)
        text=str(detached)
        self.assertNotIn("PROTOCOL",text)
        self.assertNotIn("WITNESS",text)
        self.assertNotIn("CALL_METHOD",text)

    def test_no_protocol_program_preserves_pre_protocol_semantic_hash(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(2,3).sum();
entry main:Int=main_value();'''
        compiled=compile_program_v2(source)
        self.assertEqual(compiled.semantic_hash,"3876de1a8e3867e0893867b15c7f0df3f9f31c2d956615c1b586860e5435a804")
        self.assertEqual(compiled.protocol_hashes,())
        self.assertEqual(compiled.protocol_witnesses,())


if __name__=="__main__":
    unittest.main()
