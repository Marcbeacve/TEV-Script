import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2

PAIR_PREFIX = 'script Demo version "2.0.0";\ngeneric record Pair<T>{left:T;right:T;}\ngeneric fn make<T>(x:T,y:T)->Pair<T>=Pair(left=x,right=y);\n'
SUMMABLE = 'protocol Summable{fn sum(self)->Int;}\n'
PAIR_SUMMABLE = 'impl Pair<Int> : Summable{fn sum(self)->Int=self.left+self.right;}\n'
TOTAL = 'generic fn total<T:Summable>(x:T)->Int=x.sum();\n'


class SourceProtocolConstraintsV2Tests(unittest.TestCase):
    def test_constrained_generic_call_specializes_with_exact_witness(self):
        source=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''fn main_value()->Int=total<Pair<Int>>(make<Int>(2,3));
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"5"})
        self.assertEqual(len(compiled.constrained_function_template_hashes),1)
        self.assertEqual(len(compiled.constrained_function_specializations),1)
        specialization=compiled.constrained_function_specializations[0]
        witness=compiled.protocol_witnesses[0]
        self.assertEqual(specialization.function_name,"total")
        self.assertEqual(specialization.type_argument_ids,(witness.receiver_runtime_type,))
        self.assertEqual(specialization.constraint_bindings,(("T",witness.protocol_hash,witness.witness_hash),))
        self.assertFalse(any(name.endswith('.total') for name,_hash in compiled.function_template_hashes))

    def test_direct_entry_constrained_call_uses_same_specialization(self):
        wrapper=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''fn main_value()->Int=total<Pair<Int>>(make<Int>(2,3));
entry main:Int=main_value();'''
        direct=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''entry main:Int=total<Pair<Int>>(make<Int>(2,3));'''
        a,ra=compile_and_run_program_v2(wrapper)
        b,rb=compile_and_run_program_v2(direct)
        self.assertEqual(ra.result_encoded,rb.result_encoded)
        self.assertEqual(a.constrained_function_specializations[0].specialization_hash,b.constrained_function_specializations[0].specialization_hash)

    def test_missing_explicit_protocol_witness_fails_closed(self):
        source=PAIR_PREFIX+SUMMABLE+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
'''+TOTAL+'''fn main_value()->Int=total<Pair<Int>>(make<Int>(2,3));
entry main:Int=main_value();'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CONSTRAINT_WITNESS")

    def test_structural_method_without_protocol_impl_is_not_a_witness(self):
        source=PAIR_PREFIX+SUMMABLE+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
'''+TOTAL+'''entry main:Int=0;'''
        compiled=compile_program_v2(source)
        self.assertEqual(compiled.protocol_witnesses,())
        self.assertEqual(len(compiled.constrained_function_template_hashes),1)
        self.assertEqual(compiled.constrained_function_specializations,())

    def test_unknown_constraint_protocol_fails_closed(self):
        source='''script Demo version "2.0.0";
generic fn bad<T:Missing>(x:T)->Int=0;
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CONSTRAINT_PROTOCOL")

    def test_constrained_parameter_cannot_call_method_outside_contract(self):
        source=PAIR_PREFIX+SUMMABLE+'''impl Pair<Int> : Summable{
fn sum(self)->Int=self.left+self.right;
fn helper(self)->Int=99;
}
generic fn bad<T:Summable>(x:T)->Int=x.helper();
fn main_value()->Int=bad<Pair<Int>>(make<Int>(2,3));
entry main:Int=main_value();'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CONSTRAINT_METHOD")

    def test_constraint_composes_through_another_constrained_generic(self):
        source=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''generic fn outer<U:Summable>(x:U)->Int=total<U>(x);
fn main_value()->Int=outer<Pair<Int>>(make<Int>(4,5));
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"9"})
        names={item.function_name for item in compiled.constrained_function_specializations}
        self.assertEqual(names,{"outer","total"})

    def test_repeated_identical_specialization_is_deduplicated(self):
        source=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''fn a()->Int=total<Pair<Int>>(make<Int>(1,2));
fn b()->Int=total<Pair<Int>>(make<Int>(3,4));
fn main_value()->Int=a()+b();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"10"})
        total_specs=[item for item in compiled.constrained_function_specializations if item.function_name=="total"]
        self.assertEqual(len(total_specs),1)

    def test_witness_body_change_changes_specialization_not_constrained_template(self):
        base=PAIR_PREFIX+SUMMABLE+'''impl Pair<Int> : Summable{fn sum(self)->Int=BODY;}
'''+TOTAL+'''fn main_value()->Int=total<Pair<Int>>(make<Int>(2,3));
entry main:Int=main_value();'''
        left=compile_program_v2(base.replace("BODY","self.left+self.right"))
        right=compile_program_v2(base.replace("BODY","self.left"))
        self.assertEqual(left.constrained_function_template_hashes,right.constrained_function_template_hashes)
        self.assertEqual(left.protocol_hashes,right.protocol_hashes)
        self.assertNotEqual(left.protocol_witnesses[0].witness_hash,right.protocol_witnesses[0].witness_hash)
        self.assertNotEqual(left.constrained_function_specializations[0].specialization_hash,right.constrained_function_specializations[0].specialization_hash)
        self.assertNotEqual(left.semantic_hash,right.semantic_hash)

    def test_constrained_source_body_change_changes_template_and_specialization(self):
        base=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+'''generic fn total<T:Summable>(x:T)->Int=BODY;
fn main_value()->Int=total<Pair<Int>>(make<Int>(2,3));
entry main:Int=main_value();'''
        one=compile_program_v2(base.replace("BODY","x.sum()"))
        two=compile_program_v2(base.replace("BODY","x.sum()+1"))
        self.assertNotEqual(one.constrained_function_template_hashes,two.constrained_function_template_hashes)
        self.assertNotEqual(one.constrained_function_specializations[0].specialization_hash,two.constrained_function_specializations[0].specialization_hash)

    def test_same_template_two_concrete_witnesses_produce_two_specializations(self):
        source='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol Valued{fn value_int(self)->Int;}
impl Box<Int> : Valued{fn value_int(self)->Int=self.value;}
impl Box<Text> : Valued{fn value_int(self)->Int=7;}
generic fn value_of<T:Valued>(x:T)->Int=x.value_int();
fn a()->Int=value_of<Box<Int>>(box<Int>(3));
fn b()->Int=value_of<Box<Text>>(box<Text>("x"));
fn main_value()->Int=a()+b();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"10"})
        specs=[item for item in compiled.constrained_function_specializations if item.function_name=="value_of"]
        self.assertEqual(len(specs),2)
        self.assertEqual(len({item.type_argument_ids for item in specs}),2)
        self.assertEqual(len({item.specialization_hash for item in specs}),2)

    def test_two_constrained_type_parameters_bind_two_witnesses(self):
        source='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol Valued{fn value_int(self)->Int;}
impl Box<Int> : Valued{fn value_int(self)->Int=self.value;}
impl Box<Text> : Valued{fn value_int(self)->Int=7;}
generic fn add_values<A:Valued,B:Valued>(a:A,b:B)->Int=a.value_int()+b.value_int();
fn main_value()->Int=add_values<Box<Int>,Box<Text>>(box<Int>(3),box<Text>("x"));
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"10"})
        spec=compiled.constrained_function_specializations[0]
        self.assertEqual(len(spec.type_argument_ids),2)
        self.assertEqual(tuple(item[0] for item in spec.constraint_bindings),("A","B"))

    def test_unconstrained_type_parameter_is_still_bound_in_specialization_identity(self):
        source='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol Valued{fn value_int(self)->Int;}
impl Box<Int> : Valued{fn value_int(self)->Int=self.value;}
generic fn choose<A:Valued,B>(a:A,b:B)->Int=a.value_int();
fn x()->Int=choose<Box<Int>,Int>(box<Int>(3),4);
fn y()->Int=choose<Box<Int>,Text>(box<Int>(3),"z");
fn main_value()->Int=x()+y();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"6"})
        specs=[item for item in compiled.constrained_function_specializations if item.function_name=="choose"]
        self.assertEqual(len(specs),2)
        self.assertNotEqual(specs[0].type_argument_ids,specs[1].type_argument_ids)
        self.assertNotEqual(specs[0].specialization_hash,specs[1].specialization_hash)

    def test_constrained_function_is_source_template_not_ordinary_pure_template(self):
        source=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''entry main:Int=0;'''
        compiled=compile_program_v2(source)
        self.assertEqual(tuple(name for name,_hash in compiled.constrained_function_template_hashes),("Demo.total",))
        self.assertFalse(any(name.endswith('.total') for name,_hash in compiled.function_template_hashes))
        self.assertEqual(compiled.constrained_function_specializations,())

    def test_program_ir_detached_erases_constraint_runtime_surface(self):
        source=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+TOTAL+'''fn main_value()->Int=total<Pair<Int>>(make<Int>(8,9));
entry main:Int=main_value();'''
        compiled,source_receipt=compile_and_run_program_v2(source)
        detached=copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable=run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash,source_receipt.result_hash)
        text=str(detached)
        for token in ("PROTOCOL","WITNESS","CONSTRAINT","CALL_METHOD"):
            self.assertNotIn(token,text)

    def test_no_constraint_program_preserves_historical_semantic_hash(self):
        source=PAIR_PREFIX+'''impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(2,3).sum();
entry main:Int=main_value();'''
        compiled=compile_program_v2(source)
        self.assertEqual(compiled.semantic_hash,"3876de1a8e3867e0893867b15c7f0df3f9f31c2d956615c1b586860e5435a804")
        self.assertEqual(compiled.constrained_function_template_hashes,())
        self.assertEqual(compiled.constrained_function_specializations,())

    def test_constraint_protocol_method_signature_still_governs_impl(self):
        source=PAIR_PREFIX+'''protocol Summable{fn sum(self,n:Int)->Int;}
impl Pair<Int> : Summable{fn sum(self)->Int=self.left+self.right;}
generic fn total<T:Summable>(x:T)->Int=x.sum();
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_SIGNATURE")

    def test_constraint_call_cycle_is_rejected_before_specialization(self):
        source=PAIR_PREFIX+SUMMABLE+PAIR_SUMMABLE+'''generic fn a<T:Summable>(x:T)->Int=b<T>(x);
generic fn b<T:Summable>(x:T)->Int=a<T>(x);
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CALL_CYCLE")

    def test_method_constrained_self_witness_cycle_fails_closed(self):
        source=PAIR_PREFIX+SUMMABLE+'''generic fn total<T:Summable>(x:T)->Int=x.sum();
impl Pair<Int> : Summable{fn sum(self)->Int=total<Pair<Int>>(self);}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_WITNESS_CYCLE")

    def test_method_can_call_constrained_generic_using_external_closed_witness(self):
        source='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol Valued{fn value_int(self)->Int;}
protocol Computed{fn compute(self)->Int;}
generic fn value_of<T:Valued>(x:T)->Int=x.value_int();
impl Box<Int> : Valued{fn value_int(self)->Int=self.value;}
impl Wrap<Int> : Computed{fn compute(self)->Int=value_of<Box<Int>>(box<Int>(self.value));}
fn main_value()->Int=wrap<Int>(11).compute();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"11"})
        computed=[w for w in compiled.protocol_witnesses if w.protocol_name=="Computed"][0]
        valued=[w for w in compiled.protocol_witnesses if w.protocol_name=="Valued"][0]
        self.assertEqual(valued.method_constraint_specializations,())
        self.assertEqual(len(computed.method_constraint_specializations),1)
        method_name, hashes=computed.method_constraint_specializations[0]
        self.assertEqual(method_name,"compute")
        self.assertEqual(len(hashes),1)
        specialization=[x for x in compiled.constrained_function_specializations if x.function_name=="value_of"][0]
        self.assertEqual(hashes,(specialization.specialization_hash,))
        self.assertEqual(specialization.constraint_bindings[0][2],valued.witness_hash)

    def test_witness_strata_are_independent_of_impl_declaration_order(self):
        prefix='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol Valued{fn value_int(self)->Int;}
protocol Computed{fn compute(self)->Int;}
generic fn value_of<T:Valued>(x:T)->Int=x.value_int();
'''
        valued='''impl Box<Int> : Valued{fn value_int(self)->Int=self.value;}
'''
        computed='''impl Wrap<Int> : Computed{fn compute(self)->Int=value_of<Box<Int>>(box<Int>(self.value));}
'''
        suffix='''fn main_value()->Int=wrap<Int>(11).compute();
entry main:Int=main_value();'''
        a,ra=compile_and_run_program_v2(prefix+valued+computed+suffix)
        b,rb=compile_and_run_program_v2(prefix+computed+valued+suffix)
        self.assertEqual(ra.result_encoded,rb.result_encoded)
        self.assertEqual(a.semantic_hash,b.semantic_hash)
        self.assertEqual(
            tuple((w.protocol_name,w.receiver_source_type,w.witness_hash) for w in a.protocol_witnesses),
            tuple((w.protocol_name,w.receiver_source_type,w.witness_hash) for w in b.protocol_witnesses),
        )
        self.assertEqual(
            tuple(x.specialization_hash for x in a.constrained_function_specializations),
            tuple(x.specialization_hash for x in b.constrained_function_specializations),
        )

    def test_method_external_missing_witness_without_producer_is_not_misreported_as_cycle(self):
        source='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol Valued{fn value_int(self)->Int;}
protocol Computed{fn compute(self)->Int;}
generic fn value_of<T:Valued>(x:T)->Int=x.value_int();
impl Wrap<Int> : Computed{fn compute(self)->Int=value_of<Box<Int>>(box<Int>(self.value));}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_CONSTRAINT_WITNESS")

    def test_non_witness_helper_can_consume_own_witness_after_required_methods_close(self):
        source=PAIR_PREFIX+SUMMABLE+'''generic fn total<T:Summable>(x:T)->Int=x.sum();
impl Pair<Int> : Summable{
fn sum(self)->Int=self.left+self.right;
fn helper(self)->Int=total<Pair<Int>>(self);
}
fn main_value()->Int=make<Int>(2,3).helper();
entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"5"})
        witness=compiled.protocol_witnesses[0]
        self.assertEqual(witness.method_constraint_specializations,())
        helper_specs=[item for item in compiled.constrained_function_specializations if item.function_name=="total"]
        self.assertEqual(len(helper_specs),1)
        self.assertEqual(helper_specs[0].constraint_bindings[0][2],witness.witness_hash)

    def test_mutual_protocol_witness_dependency_cycle_fails_closed(self):
        source='''script Demo version "2.0.0";
generic record A<T>{value:T;}
generic record B<T>{value:T;}
generic fn make_a<T>(x:T)->A<T>=A(value=x);
generic fn make_b<T>(x:T)->B<T>=B(value=x);
protocol PA{fn a(self)->Int;}
protocol PB{fn b(self)->Int;}
generic fn use_a<T:PA>(x:T)->Int=x.a();
generic fn use_b<T:PB>(x:T)->Int=x.b();
impl A<Int> : PA{fn a(self)->Int=use_b<B<Int>>(make_b<Int>(self.value));}
impl B<Int> : PB{fn b(self)->Int=use_a<A<Int>>(make_a<Int>(self.value));}
entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_PROTOCOL_WITNESS_CYCLE")

    def test_external_witness_change_transitively_changes_dependent_witness(self):
        base='''script Demo version "2.0.0";
generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol Valued{fn value_int(self)->Int;}
protocol Computed{fn compute(self)->Int;}
generic fn value_of<T:Valued>(x:T)->Int=x.value_int();
impl Box<Int> : Valued{fn value_int(self)->Int=VALUED_BODY;}
impl Wrap<Int> : Computed{fn compute(self)->Int=value_of<Box<Int>>(box<Int>(self.value));}
entry main:Int=0;'''
        left=compile_program_v2(base.replace("VALUED_BODY","self.value"))
        right=compile_program_v2(base.replace("VALUED_BODY","self.value+0"))
        left_valued=[w for w in left.protocol_witnesses if w.protocol_name=="Valued"][0]
        right_valued=[w for w in right.protocol_witnesses if w.protocol_name=="Valued"][0]
        left_computed=[w for w in left.protocol_witnesses if w.protocol_name=="Computed"][0]
        right_computed=[w for w in right.protocol_witnesses if w.protocol_name=="Computed"][0]
        self.assertNotEqual(left_valued.witness_hash,right_valued.witness_hash)
        self.assertNotEqual(left_computed.method_constraint_specializations,right_computed.method_constraint_specializations)
        self.assertNotEqual(left_computed.witness_hash,right_computed.witness_hash)
        self.assertNotEqual(left.semantic_hash,right.semantic_hash)


if __name__=="__main__":
    unittest.main()
