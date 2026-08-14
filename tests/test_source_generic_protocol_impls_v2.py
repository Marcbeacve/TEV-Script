from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


def program(body: str) -> str:
    return 'script Demo version "2.0.0";\n' + body


BOX = '''generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
'''
ITERABLE = '''protocol Iterable{type Item;fn first(self)->Self::Item;}
'''
GENERIC_ITERABLE = '''generic impl<T> Box<T>:Iterable{type Item=T;fn first(self)->T=self.value;}
'''


class SourceGenericProtocolImplsV2Tests(unittest.TestCase):
    def test_constrained_demand_materializes_exact_generic_witness(self):
        source = program(BOX + ITERABLE + GENERIC_ITERABLE + '''generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();
fn main_value()->Int=first_of<Box<Int>>(box<Int>(7));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        self.assertEqual(len(compiled.generic_protocol_impl_templates), 1)
        self.assertEqual(len(compiled.generic_protocol_impl_specializations), 1)
        impl_spec = compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(impl_spec.receiver_source_type, 'Box<Int>')
        self.assertEqual(impl_spec.type_argument_ids, ('Int',))
        self.assertEqual(impl_spec.associated_types, (('Item', 'Int', 'Int'),))
        self.assertEqual(len(compiled.protocol_witnesses), 1)
        self.assertEqual(compiled.protocol_witnesses[0].witness_hash, impl_spec.witness_hash)
        constrained = [x for x in compiled.constrained_function_specializations if x.function_name == 'first_of'][0]
        self.assertEqual(constrained.associated_type_bindings, (('T', 'Item', 'Int'),))

    def test_direct_method_demand_materializes_same_impl_specialization(self):
        constrained_source = program(BOX + ITERABLE + GENERIC_ITERABLE + '''generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();
fn main_value()->Int=first_of<Box<Int>>(box<Int>(8));
entry main:Int=main_value();''')
        direct_source = program(BOX + ITERABLE + GENERIC_ITERABLE + '''fn main_value()->Int=box<Int>(8).first();
entry main:Int=main_value();''')
        c1, r1 = compile_and_run_program_v2(constrained_source)
        c2, r2 = compile_and_run_program_v2(direct_source)
        self.assertEqual(r1.result_encoded, {'$int': '8'})
        self.assertEqual(r2.result_encoded, {'$int': '8'})
        self.assertEqual(c1.generic_protocol_impl_specializations[0].specialization_hash, c2.generic_protocol_impl_specializations[0].specialization_hash)
        self.assertEqual(c1.generic_protocol_impl_specializations[0].witness_hash, c2.generic_protocol_impl_specializations[0].witness_hash)

    def test_no_demand_keeps_template_but_generates_no_witness_or_specialization(self):
        compiled = compile_program_v2(program(BOX + ITERABLE + GENERIC_ITERABLE + 'entry main:Int=0;'))
        self.assertEqual(len(compiled.generic_protocol_impl_templates), 1)
        self.assertEqual(compiled.generic_protocol_impl_specializations, ())
        self.assertEqual(compiled.protocol_witnesses, ())

    def test_two_demanded_receivers_generate_two_specializations_only(self):
        source = program(BOX + ITERABLE + GENERIC_ITERABLE + '''generic fn first_of<X:Iterable>(x:X)->X::Item=x.first();
fn i()->Int=first_of<Box<Int>>(box<Int>(1));
fn t()->Text=first_of<Box<Text>>(box<Text>("x"));
entry main:Int=i();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        self.assertEqual({x.receiver_source_type for x in compiled.generic_protocol_impl_specializations}, {'Box<Int>', 'Box<Text>'})
        self.assertEqual({w.receiver_source_type for w in compiled.protocol_witnesses}, {'Box<Int>', 'Box<Text>'})
        self.assertEqual(len(compiled.generic_protocol_impl_templates), 1)

    def test_type_parameter_alpha_rename_preserves_template_hash(self):
        a = compile_program_v2(program(BOX + ITERABLE + GENERIC_ITERABLE + 'entry main:Int=0;'))
        renamed = GENERIC_ITERABLE.replace('impl<T> Box<T>', 'impl<U> Box<U>').replace('type Item=T', 'type Item=U').replace(')->T=', ')->U=')
        b = compile_program_v2(program(BOX + ITERABLE + renamed + 'entry main:Int=0;'))
        self.assertEqual(a.generic_protocol_impl_templates[0].template_hash, b.generic_protocol_impl_templates[0].template_hash)

    def test_body_change_changes_template_specialization_and_witness(self):
        base = BOX + '''protocol Tagged{fn tag(self)->Int;}
'''
        a_source = program(base + '''generic impl<T> Box<T>:Tagged{fn tag(self)->Int=1;}
fn main_value()->Int=box<Int>(1).tag(); entry main:Int=main_value();''')
        b_source = program(base + '''generic impl<T> Box<T>:Tagged{fn tag(self)->Int=2;}
fn main_value()->Int=box<Int>(1).tag(); entry main:Int=main_value();''')
        a = compile_program_v2(a_source)
        b = compile_program_v2(b_source)
        self.assertNotEqual(a.generic_protocol_impl_templates[0].template_hash, b.generic_protocol_impl_templates[0].template_hash)
        self.assertNotEqual(a.generic_protocol_impl_specializations[0].specialization_hash, b.generic_protocol_impl_specializations[0].specialization_hash)
        self.assertNotEqual(a.generic_protocol_impl_specializations[0].witness_hash, b.generic_protocol_impl_specializations[0].witness_hash)

    def test_generic_and_concrete_protocol_impl_family_overlap_fails_closed(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic impl<T> Box<T>:P{fn p(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_disjoint_concrete_and_nested_generic_protocol_impls_coexist(self):
        source = program('''generic record Wrap<T>{value:T;}
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{fn x(self)->Int;}
impl Wrap<Text>:P{fn x(self)->Int=7;}
generic impl<T> Wrap<Option<T>>:P{fn x(self)->Int=1;}
fn a()->Int=wrap<Text>("z").x();
fn b()->Int=wrap<Option<Int>>(Some(2)).x();
entry main:Int=a()+b();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '8'})
        receivers = {w.receiver_source_type for w in compiled.protocol_witnesses if w.protocol_name == "P"}
        self.assertEqual(receivers, {'Wrap<Text>', 'Wrap<Option<Int>>'})

    def test_nested_generic_pattern_overlapping_concrete_receiver_fails_closed(self):
        source = program('''generic record Wrap<T>{value:T;}
protocol P{fn x(self)->Int;}
impl Wrap<Option<Int>>:P{fn x(self)->Int=7;}
generic impl<T> Wrap<Option<T>>:P{fn x(self)->Int=1;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_same_method_concrete_and_generic_disjoint_receivers_across_protocols_coexist(self):
        source = program('''generic record Wrap<T>{value:T;}
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{fn x(self)->Int;}
protocol Q{fn x(self)->Int;}
impl Wrap<Text>:P{fn x(self)->Int=7;}
generic impl<T> Wrap<Option<T>>:Q{fn x(self)->Int=2;}
entry main:Int=wrap<Option<Int>>(Some(1)).x();''')
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '2'})

    def test_two_generic_impls_same_family_protocol_fail_coherence(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;}
generic impl<T> Box<T>:P{fn p(self)->Int=0;}
generic impl<U> Box<U>:P{fn p(self)->Int=1;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_generic_impls_same_family_cannot_export_same_method_name(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn x(self)->Int;}
protocol Q{fn x(self)->Int;}
generic impl<T> Box<T>:P{fn x(self)->Int=0;}
generic impl<T> Box<T>:Q{fn x(self)->Int=1;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_nested_receiver_pattern_specializes_exact_inner_type_and_erases(self):
        source = program('''generic record Wrap<T>{value:T;}
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{fn p(self)->Int;}
generic impl<T> Wrap<Option<T>>:P{fn p(self)->Int=1;}
generic fn use<X:P>(x:X)->Int=x.p();
entry main:Int=use<Wrap<Option<Int>>>(wrap<Option<Int>>(Some(7)));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        template = compiled.generic_protocol_impl_templates[0]
        specialization = compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(template.receiver_pattern, 'Wrap<Option<T>>')
        self.assertEqual(specialization.type_argument_ids, ('Int',))
        self.assertEqual(specialization.receiver_source_type, 'Wrap<Option<Int>>')
        self.assertNotIn('Wrap<Option<T>>', str(export_program_ir_v4_pure(compiled)))

    def test_nested_receiver_pattern_direct_method_uses_same_specialization(self):
        source = program('''generic record Wrap<T>{value:T;}
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{fn p(self)->Int;}
generic impl<T> Wrap<Option<T>>:P{fn p(self)->Int=1;}
entry main:Int=wrap<Option<Int>>(Some(7)).p();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        self.assertEqual(compiled.generic_protocol_impl_specializations[0].type_argument_ids, ('Int',))

    def test_disjoint_nested_patterns_same_protocol_coexist(self):
        source = program('''generic record Wrap<T>{value:T;}
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{fn p(self)->Int;}
generic impl<T> Wrap<Option<T>>:P{fn p(self)->Int=1;}
generic impl<T,E> Wrap<Result<T,E>>:P{fn p(self)->Int=2;}
fn a()->Int=wrap<Option<Int>>(Some(1)).p();
fn b()->Int=wrap<Result<Int,Text>>(Ok(2)).p();
entry main:Int=a()+b();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '3'})
        self.assertEqual(len(compiled.generic_protocol_impl_templates), 2)
        self.assertEqual(len(compiled.generic_protocol_impl_specializations), 2)

    def test_wildcard_and_nested_pattern_overlap_fails_closed(self):
        source = program('''generic record Wrap<T>{value:T;}
protocol P{fn p(self)->Int;}
generic impl<T> Wrap<T>:P{fn p(self)->Int=1;}
generic impl<U> Wrap<Option<U>>:P{fn p(self)->Int=2;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_nonlinear_pattern_matches_repeated_type_and_rejects_unequal_actual(self):
        prefix = '''generic record Pair<A,B>{left:A;right:B;}
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{fn p(self)->Int;}
generic impl<T> Pair<T,T>:P{fn p(self)->Int=1;}'''
        good = program(prefix + 'generic fn use<X:P>(x:X)->Int=x.p(); entry main:Int=use<Pair<Int,Int>>(pair<Int,Int>(2,3));')
        compiled, receipt = compile_and_run_program_v2(good)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        self.assertEqual(compiled.generic_protocol_impl_specializations[0].type_argument_ids, ('Int',))
        self.assertNotIn('Pair<T,T>', str(export_program_ir_v4_pure(compiled)))
        bad = program(prefix + 'generic fn use<X:P>(x:X)->Int=x.p(); entry main:Int=use<Pair<Int,Text>>(pair<Int,Text>(2,"x"));')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(bad)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_CONSTRAINT_WITNESS')

    def test_nonlinear_pattern_requires_every_declared_parameter(self):
        source = program('''generic record Wrap<T>{value:T;}
protocol P{fn p(self)->Int;}
generic impl<T,E> Wrap<Option<T>>:P{fn p(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN')

    def test_nonlinear_pattern_concrete_overlap_respects_repeated_type_equality(self):
        prefix = '''generic record Pair<A,B>{left:A;right:B;}
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{fn p(self)->Int;}
generic impl<T> Pair<T,T>:P{fn p(self)->Int=1;}'''
        disjoint = program(prefix + 'impl Pair<Int,Text>:P{fn p(self)->Int=7;} entry main:Int=pair<Int,Text>(2,"x").p();')
        _compiled, receipt = compile_and_run_program_v2(disjoint)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        overlap = program(prefix + 'impl Pair<Int,Int>:P{fn p(self)->Int=7;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(overlap)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_nonlinear_pattern_occurs_check_allows_impossible_cycle_patterns_to_coexist(self):
        source = program('''generic record Pair<A,B>{left:A;right:B;}
protocol P{fn p(self)->Int;}
generic impl<T> Pair<T,Option<T>>:P{fn p(self)->Int=1;}
generic impl<U> Pair<Option<U>,U>:P{fn p(self)->Int=2;}
entry main:Int=0;''')
        compiled = compile_program_v2(source)
        self.assertEqual(len(compiled.generic_protocol_impl_templates), 2)

    def test_nonlinear_pattern_alpha_rename_preserves_template_hash(self):
        prefix = '''generic record Pair<A,B>{left:A;right:B;}
protocol P{fn p(self)->Int;}
'''
        left = compile_program_v2(program(prefix + 'generic impl<T> Pair<T,T>:P{fn p(self)->Int=0;} entry main:Int=0;'))
        right = compile_program_v2(program(prefix + 'generic impl<U> Pair<U,U>:P{fn p(self)->Int=0;} entry main:Int=0;'))
        self.assertEqual(left.generic_protocol_impl_templates[0].template_hash, right.generic_protocol_impl_templates[0].template_hash)

    def test_nested_pattern_type_parameter_alpha_rename_preserves_template_hash(self):
        prefix = '''generic record Wrap<T>{value:T;}
protocol P{fn p(self)->Int;}
'''
        left = compile_program_v2(program(prefix + 'generic impl<T> Wrap<Option<T>>:P{fn p(self)->Int=0;} entry main:Int=0;'))
        right = compile_program_v2(program(prefix + 'generic impl<U> Wrap<Option<U>>:P{fn p(self)->Int=0;} entry main:Int=0;'))
        self.assertEqual(left.generic_protocol_impl_templates[0].template_hash, right.generic_protocol_impl_templates[0].template_hash)

    def test_same_method_across_protocols_is_allowed_for_disjoint_patterns(self):
        source = program('''generic record Wrap<T>{value:T;}
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{fn x(self)->Int;}
protocol Q{fn x(self)->Int;}
generic impl<T> Wrap<Option<T>>:P{fn x(self)->Int=1;}
generic impl<T,E> Wrap<Result<T,E>>:Q{fn x(self)->Int=2;}
entry main:Int=wrap<Result<Int,Text>>(Ok(2)).x();''')
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '2'})

    def test_receiver_type_parameter_order_must_match_declaration(self):
        source = program('''generic record Pair<A,B>{left:A;right:B;}
protocol P{fn p(self)->Int;}
generic impl<A,B> Pair<B,A>:P{fn p(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_PATTERN')

    def test_missing_required_method_fails_before_demand(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;fn q(self)->Int;}
generic impl<T> Box<T>:P{fn p(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_SIGNATURE')

    def test_signature_mismatch_fails_before_demand(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{type Item;fn first(self)->Self::Item;}
generic impl<T> Box<T>:P{type Item=T;fn first(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_SIGNATURE')

    def test_associated_type_set_must_match_protocol_exactly(self):
        missing = program('''generic record Box<T>{value:T;}
protocol P{type Item;fn first(self)->Self::Item;}
generic impl<T> Box<T>:P{fn first(self)->T=self.value;}
entry main:Int=0;''')
        extra = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;}
generic impl<T> Box<T>:P{type Item=T;fn p(self)->Int=0;}
entry main:Int=0;''')
        for source in (missing, extra):
            with self.assertRaises(TevScriptError) as ctx:
                compile_program_v2(source)
            self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_TYPE')

    def test_unknown_symbolic_type_fails_before_demand(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self,x:Int)->Int;}
generic impl<T> Box<T>:P{fn p(self,x:Unknown)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_TYPE')

    def test_unknown_global_call_fails_before_demand(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;}
generic impl<T> Box<T>:P{fn p(self)->Int=missing<T>(self);}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_CALL')

    def test_internal_method_cycle_fails_before_demand(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn a(self)->Int;fn b(self)->Int;}
generic impl<T> Box<T>:P{fn a(self)->Int=self.b();fn b(self)->Int=self.a();}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_METHOD_CYCLE')

    def test_generic_witness_self_dependency_fails_closed(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;}
generic fn use<X:P>(x:X)->Int=x.p();
generic impl<T> Box<T>:P{fn p(self)->Int=use<Box<T>>(self);}
fn main_value()->Int=use<Box<Int>>(Box(value=1));
entry main:Int=main_value();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_CYCLE')

    def test_generic_impl_method_can_use_external_closed_concrete_witness(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{inner:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(inner=x);
protocol Valued{fn value_int(self)->Int;}
impl Box<Int>:Valued{fn value_int(self)->Int=self.value;}
generic fn value_of<X:Valued>(x:X)->Int=x.value_int();
protocol Computed{fn compute(self)->Int;}
generic impl<T> Wrap<T>:Computed{fn compute(self)->Int=value_of<T>(self.inner);}
fn main_value()->Int=wrap<Box<Int>>(box<Int>(5)).compute();
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '5'})
        self.assertEqual({x.protocol_name for x in compiled.generic_protocol_impl_specializations}, {'Computed'})
        self.assertIn('value_of', {x.function_name for x in compiled.constrained_function_specializations})
        computed = [w for w in compiled.protocol_witnesses if w.protocol_name == 'Computed'][0]
        self.assertTrue(computed.method_constraint_specializations)

    def test_generic_impl_can_demand_another_generic_impl_by_direct_method(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{inner:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(inner=x);
protocol Tagged{fn tag(self)->Int;}
generic impl<T> Box<T>:Tagged{fn tag(self)->Int=1;}
protocol Computed{fn compute(self)->Int;}
generic impl<T> Wrap<T>:Computed{fn compute(self)->Int=self.inner.tag();}
fn main_value()->Int=wrap<Box<Int>>(box<Int>(9)).compute();
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        self.assertEqual({(x.protocol_name, x.receiver_source_type) for x in compiled.generic_protocol_impl_specializations}, {('Computed', 'Wrap<Box<Int>>'), ('Tagged', 'Box<Int>')})

    def test_generic_impl_internal_method_dag_is_allowed(self):
        source = program('''generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol P{fn a(self)->Int;fn b(self)->Int;}
generic impl<T> Box<T>:P{fn a(self)->Int=self.b()+1;fn b(self)->Int=2;}
fn main_value()->Int=box<Int>(0).a();
entry main:Int=main_value();''')
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '3'})

    def test_generic_impl_is_erased_from_detached_program_ir(self):
        source = program(BOX + ITERABLE + GENERIC_ITERABLE + '''fn main_value()->Int=box<Int>(6).first();
entry main:Int=main_value();''')
        compiled, source_receipt = compile_and_run_program_v2(source)
        detached = copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable = run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash, source_receipt.result_hash)
        text = str(detached)
        for marker in ('GENERIC_PROTOCOL_IMPL', 'WITNESS', 'PROTOCOL', 'impl<T>'):
            self.assertNotIn(marker, text)

    def test_historical_no_generic_impl_semantic_hash_remains_exact(self):
        source = '''script Demo version "2.0.0";
generic record Pair<T>{left:T;right:T;}
generic fn make<T>(x:T,y:T)->Pair<T>=Pair(left=x,right=y);
impl Pair<Int>{fn sum(self)->Int=self.left+self.right;}
fn main_value()->Int=make<Int>(2,3).sum();
entry main:Int=main_value();'''
        compiled = compile_program_v2(source)
        self.assertEqual(compiled.semantic_hash, '3876de1a8e3867e0893867b15c7f0df3f9f31c2d956615c1b586860e5435a804')
        self.assertEqual(compiled.generic_protocol_impl_templates, ())
        self.assertEqual(compiled.generic_protocol_impl_specializations, ())


    def test_associated_receiver_pattern_binds_witness_evidence_and_erases(self):
        source = program('''generic record Box<T>{value:T;}
generic record Pair<A,B>{left:A;right:B;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{fn q(self)->Int;}
generic impl<T> Box<T>:P{type Item=T;fn first(self)->T=self.value;}
generic impl<T:P> Pair<T,T::Item>:Q{fn q(self)->Int=1;}
entry main:Int=pair<Box<Int>,Int>(box<Int>(2),3).q();''')
        compiled, source_receipt = compile_and_run_program_v2(source)
        self.assertEqual(source_receipt.result_encoded, {'$int': '1'})
        q_spec = [x for x in compiled.generic_protocol_impl_specializations if x.protocol_name == 'Q'][0]
        q_witness = [x for x in compiled.protocol_witnesses if x.protocol_name == 'Q'][0]
        self.assertEqual(q_spec.receiver_associated_projections, (('T', 'Item', 'Int'),))
        self.assertEqual(q_witness.receiver_associated_projections, (('T', 'Item', 'Int'),))
        detached = copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable = run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash, source_receipt.result_hash)
        self.assertNotIn('T::Item', str(detached))
        self.assertNotIn('Pair<T,T::Item>', str(detached))

    def test_associated_receiver_pattern_mismatch_fails_after_prerequisite_witness(self):
        source = program('''generic record Box<T>{value:T;}
generic record Pair<A,B>{left:A;right:B;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{fn q(self)->Int;}
generic impl<T> Box<T>:P{type Item=T;fn first(self)->T=self.value;}
generic impl<T:P> Pair<T,T::Item>:Q{fn q(self)->Int=1;}
entry main:Int=pair<Box<Int>,Text>(box<Int>(2),"x").q();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_RECEIVER_ASSOCIATED_MISMATCH')

    def test_associated_receiver_projection_requires_prior_anchor_and_authority(self):
        prefix = '''generic record Pair<A,B>{left:A;right:B;}
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{fn q(self)->Int;}
'''
        before_anchor = program(prefix + 'generic impl<T:P> Pair<T::Item,T>:Q{fn q(self)->Int=0;} entry main:Int=0;')
        no_authority = program(prefix + 'generic impl<T> Pair<T,T::Item>:Q{fn q(self)->Int=0;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as anchor_ctx:
            compile_program_v2(before_anchor)
        self.assertEqual(anchor_ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_RECEIVER_ASSOCIATED_ANCHOR')
        with self.assertRaises(TevScriptError) as authority_ctx:
            compile_program_v2(no_authority)
        self.assertEqual(authority_ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_PROJECTION')

    def test_associated_receiver_pattern_alpha_rename_preserves_template_hash(self):
        prefix = '''generic record Pair<A,B>{left:A;right:B;}
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{fn q(self)->Int;}
'''
        left = compile_program_v2(program(prefix + 'generic impl<T:P> Pair<T,T::Item>:Q{fn q(self)->Int=0;} entry main:Int=0;'))
        right = compile_program_v2(program(prefix + 'generic impl<U:P> Pair<U,U::Item>:Q{fn q(self)->Int=0;} entry main:Int=0;'))
        left_q = [x for x in left.generic_protocol_impl_templates if x.protocol_name == 'Q'][0]
        right_q = [x for x in right.generic_protocol_impl_templates if x.protocol_name == 'Q'][0]
        self.assertEqual(left_q.template_hash, right_q.template_hash)

    def test_associated_receiver_projection_type_id_changes_specialization_and_witness(self):
        source = program('''generic record Box<T>{value:T;}
generic record Pair<A,B>{left:A;right:B;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{fn q(self)->Int;}
generic impl<T> Box<T>:P{type Item=T;fn first(self)->T=self.value;}
generic impl<T:P> Pair<T,T::Item>:Q{fn q(self)->Int=1;}
fn a()->Int=pair<Box<Int>,Int>(box<Int>(2),3).q();
fn b()->Int=pair<Box<Text>,Text>(box<Text>("a"),"b").q();
entry main:Int=a()+b();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '2'})
        q_specs = sorted((x for x in compiled.generic_protocol_impl_specializations if x.protocol_name == 'Q'), key=lambda item: item.receiver_source_type)
        self.assertEqual(len(q_specs), 2)
        self.assertEqual({x.receiver_associated_projections for x in q_specs}, {(('T', 'Item', 'Int'),), (('T', 'Item', 'Text'),)})
        self.assertEqual(len({x.specialization_hash for x in q_specs}), 2)
        q_witnesses = [x for x in compiled.protocol_witnesses if x.protocol_name == 'Q']
        self.assertEqual(len({x.witness_hash for x in q_witnesses}), 2)


if __name__ == '__main__':
    unittest.main()
