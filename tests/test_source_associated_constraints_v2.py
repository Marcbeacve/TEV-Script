from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2

BOX = "generic record Box<T>{value:T;}\ngeneric fn box<T>(x:T)->Box<T>=Box(value=x);\n"
ITERABLE = "protocol Iterable{type Item;fn first(self)->Self::Item;}\n"
BOX_INT = "impl Box<Int>:Iterable{type Item=Int;fn first(self)->Int=self.value;}\n"
BOX_TEXT = "impl Box<Text>:Iterable{type Item=Text;fn first(self)->Text=self.value;}\n"


def program(body: str) -> str:
    return 'script Demo version "2.0.0";\n' + body


class SourceAssociatedConstraintsV2Tests(unittest.TestCase):
    def test_exact_refinement_accepts_matching_witness(self):
        source = program(BOX + ITERABLE + BOX_INT + '''generic fn first_int<T:Iterable<Item=Int>>(x:T)->Int=x.first();
fn main_value()->Int=first_int<Box<Int>>(box<Int>(7));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'first_int'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('T', 'Item', 'Int'),))

    def test_wrong_witness_is_rejected_even_when_body_ignores_projection(self):
        source = program(BOX + ITERABLE + BOX_TEXT + '''generic fn only_int<T:Iterable<Item=Int>>(x:T)->Int=1;
fn main_value()->Int=only_int<Box<Text>>(box<Text>("x"));
entry main:Int=main_value();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_MISMATCH')

    def test_nested_concrete_required_type_uses_type_id(self):
        source = program(BOX + '''protocol Wrapped{type Item;fn get(self)->Self::Item;}
impl Box<Option<Int>>:Wrapped{type Item=Option<Int>;fn get(self)->Option<Int>=self.value;}
generic fn get_int<T:Wrapped<Item=Option<Int>>>(x:T)->Option<Int>=x.get();
fn main_value()->Option<Int>=get_int<Box<Option<Int>>>(box<Option<Int>>(Some(5)));
entry main:Option<Int>=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$option': {'type': 'Option<Int>', 'variant': 'Some', 'value': {'$int': '5'}}})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'get_int'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('T', 'Item', 'Option<Int>'),))

    def test_user_generic_required_type_is_materialized(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{value:Box<T>;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:Box<T>)->Wrap<T>=Wrap(value=x);
protocol Wrapped{type Item;fn get(self)->Self::Item;}
impl Wrap<Int>:Wrapped{type Item=Box<Int>;fn get(self)->Box<Int>=self.value;}
generic fn get_box<T:Wrapped<Item=Box<Int>>>(x:T)->Box<Int>=x.get();
fn main_value()->Int=get_box<Wrap<Int>>(wrap<Int>(box<Int>(11))).value;
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '11'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'get_box'][0]
        self.assertTrue(spec.associated_constraint_bindings[0][2].startswith('Demo.Box__g_'))

    def test_multiple_refinements_are_order_canonical(self):
        prefix = '''generic record Pair<T>{left:T;right:Text;}
generic fn pair<T>(x:T,y:Text)->Pair<T>=Pair(left=x,right=y);
protocol KV{type Key;type Value;fn key(self)->Self::Key;fn value(self)->Self::Value;}
impl Pair<Int>:KV{type Key=Int;type Value=Text;fn key(self)->Int=self.left;fn value(self)->Text=self.right;}
'''
        tail = '''(x:T)->Int=x.key();
fn main_value()->Int=key_int<Pair<Int>>(pair<Int>(8,"v"));
entry main:Int=main_value();'''
        a = compile_program_v2(program(prefix + 'generic fn key_int<T:KV<Key=Int,Value=Text>>' + tail))
        b = compile_program_v2(program(prefix + 'generic fn key_int<T:KV<Value=Text,Key=Int>>' + tail))
        self.assertEqual(a.constrained_function_template_hashes, b.constrained_function_template_hashes)
        sa = [x for x in a.constrained_function_specializations if x.function_name == 'key_int'][0]
        sb = [x for x in b.constrained_function_specializations if x.function_name == 'key_int'][0]
        self.assertEqual(sa.specialization_hash, sb.specialization_hash)
        self.assertEqual(sa.associated_constraint_bindings, (('T', 'Key', 'Int'), ('T', 'Value', 'Text')))

    def test_duplicate_refinement_fails_closed(self):
        source = program(BOX + ITERABLE + 'generic fn bad<T:Iterable<Item=Int,Item=Int>>(x:T)->Int=0; entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_DUPLICATE')

    def test_empty_refinement_list_fails_closed(self):
        source = program(BOX + ITERABLE + 'generic fn bad<T:Iterable<>>(x:T)->Int=0; entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT')

    def test_unknown_associated_member_fails_statically(self):
        source = program(BOX + ITERABLE + 'generic fn bad<T:Iterable<Other=Int>>(x:T)->Int=0; entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT')

    def test_unknown_required_type_fails_before_specialization(self):
        source = program(BOX + ITERABLE + 'generic fn bad<T:Iterable<Item=Unknown>>(x:T)->Int=0; entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_TYPE')

    def test_required_type_can_depend_on_same_type_parameter_by_type_id(self):
        source = program(BOX + ITERABLE + '''impl Box<Int>:Iterable{type Item=Box<Int>;fn first(self)->Box<Int>=self;}
generic fn same<T:Iterable<Item=T>>(x:T)->Int=1;
entry main:Int=same<Box<Int>>(box<Int>(5));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'same'][0]
        box_type_id = compiled.types.resolve_source_type('Box<Int>').type_id
        self.assertEqual(spec.associated_constraint_bindings, (('T', 'Item', box_type_id),))

    def test_cross_parameter_dependent_refinement_matches_witness_type_id(self):
        source = program('''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
generic fn left<T>(x:T)->Left<T>=Left(value=x);
generic fn right<T>(x:T)->Right<T>=Right(value=x);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
impl Right<Text>:Q{type Item=Int;fn size(self)->Int=2;}
generic fn same<A:P,B:Q<Item=A::Item>>(a:A,b:B)->Int=b.size();
entry main:Int=same<Left<Int>,Right<Text>>(left<Int>(7),right<Text>("x"));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '2'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'same'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('B', 'Item', 'Int'),))
        detached = copy.deepcopy(export_program_ir_v4_pure(compiled))
        self.assertNotIn('A::Item', str(detached))
        self.assertEqual(run_program_ir_v4_pure(detached).result_hash, receipt.result_hash)

    def test_dependent_refinement_resolution_is_not_constraint_declaration_order_sensitive(self):
        source = program('''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
generic fn left<T>(x:T)->Left<T>=Left(value=x);
generic fn right<T>(x:T)->Right<T>=Right(value=x);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
impl Right<Text>:Q{type Item=Int;fn size(self)->Int=4;}
generic fn same<B:Q<Item=A::Item>,A:P>(b:B,a:A)->Int=b.size();
entry main:Int=same<Right<Text>,Left<Int>>(right<Text>("x"),left<Int>(7));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '4'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'same'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('B', 'Item', 'Int'),))

    def test_cross_parameter_dependent_refinement_mismatch_fails_closed(self):
        source = program('''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
generic fn left<T>(x:T)->Left<T>=Left(value=x);
generic fn right<T>(x:T)->Right<T>=Right(value=x);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
impl Right<Text>:Q{type Item=Text;fn size(self)->Int=2;}
generic fn same<A:P,B:Q<Item=A::Item>>(a:A,b:B)->Int=b.size();
entry main:Int=same<Left<Int>,Right<Text>>(left<Int>(7),right<Text>("x"));''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_MISMATCH')

    def test_nested_dependent_required_type_is_resolved_after_all_witnesses(self):
        source = program('''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
generic fn left<T>(x:T)->Left<T>=Left(value=x);
generic fn right<T>(x:T)->Right<T>=Right(value=x);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
impl Right<Text>:Q{type Item=Option<Int>;fn size(self)->Int=3;}
generic fn same<A:P,B:Q<Item=Option<A::Item>>>(a:A,b:B)->Int=b.size();
entry main:Int=same<Left<Int>,Right<Text>>(left<Int>(7),right<Text>("x"));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '3'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'same'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('B', 'Item', 'Option<Int>'),))

    def test_dependent_refinement_type_parameter_alpha_rename_preserves_template_hash(self):
        prefix = '''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
'''
        a = compile_program_v2(program(prefix + '''generic fn same<A:P,B:Q<Item=A::Item>>(a:A,b:B)->Int=0;
entry main:Int=0;'''))
        b = compile_program_v2(program(prefix + '''generic fn same<X:P,Y:Q<Item=X::Item>>(a:X,b:Y)->Int=0;
entry main:Int=0;'''))
        self.assertEqual(a.constrained_function_template_hashes, b.constrained_function_template_hashes)

    def test_dependent_refinement_projection_must_have_static_protocol_owner(self):
        source = program(BOX + ITERABLE + '''generic fn bad<A:Iterable,B:Iterable<Item=A::Missing>>(a:A,b:B)->Int=0;
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_TYPE')

    def test_direct_entry_uses_same_refined_specialization(self):
        source = program(BOX + ITERABLE + BOX_INT + '''generic fn first_int<T:Iterable<Item=Int>>(x:T)->Int=x.first();
entry main:Int=first_int<Box<Int>>(box<Int>(13));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '13'})
        self.assertEqual(compiled.entry.function_name, '__tev_entry_expression_v2')
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'first_int'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('T', 'Item', 'Int'),))

    def test_refinement_change_changes_template_identity(self):
        base = BOX + ITERABLE
        a = compile_program_v2(program(base + 'generic fn constrained<T:Iterable<Item=Int>>(x:T)->Int=0; entry main:Int=0;'))
        b = compile_program_v2(program(base + 'generic fn constrained<T:Iterable<Item=Text>>(x:T)->Int=0; entry main:Int=0;'))
        self.assertNotEqual(a.constrained_function_template_hashes, b.constrained_function_template_hashes)
        self.assertNotEqual(a.semantic_hash, b.semantic_hash)

    def test_plain_constraint_preserves_historical_template_hash(self):
        source = program('''generic record Pair<T>{left:T;right:T;}
generic fn make<T>(a:T,b:T)->Pair<T>=Pair(left=a,right=b);
protocol Summable{fn sum(self)->Int;}
impl Pair<Int>:Summable{fn sum(self)->Int=self.left+self.right;}
generic fn total<T:Summable>(x:T)->Int=x.sum();
entry main:Int=0;''')
        compiled = compile_program_v2(source)
        self.assertEqual(compiled.constrained_function_template_hashes, (('Demo.total', '2ab436788ae153da4cd942ae0424a2ab97435c21d7d36d1eca3ce6acacd7c632'),))

    def test_refinement_is_erased_from_detached_program_ir(self):
        source = program(BOX + ITERABLE + BOX_INT + '''generic fn first_int<T:Iterable<Item=Int>>(x:T)->Int=x.first();
fn main_value()->Int=first_int<Box<Int>>(box<Int>(3));
entry main:Int=main_value();''')
        compiled, source_receipt = compile_and_run_program_v2(source)
        detached = copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable = run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash, source_receipt.result_hash)
        text = str(detached)
        for marker in ('Item=Int', 'ASSOCIATED_CONSTRAINT', 'WITNESS', 'PROTOCOL'):
            self.assertNotIn(marker, text)

    def test_two_type_parameters_have_independent_refinements(self):
        source = program(BOX + ITERABLE + BOX_INT + BOX_TEXT + '''generic fn combine<A:Iterable<Item=Int>,B:Iterable<Item=Text>>(a:A,b:B)->Int=a.first();
fn main_value()->Int=combine<Box<Int>,Box<Text>>(box<Int>(17),box<Text>("x"));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '17'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'combine'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('A', 'Item', 'Int'), ('B', 'Item', 'Text')))

    def test_declared_refinement_never_replaces_witness_projection_authority(self):
        source = program(BOX + ITERABLE + BOX_TEXT + '''generic fn lie<T:Iterable<Item=Int>>(x:T)->T::Item=x.first();
entry main:Int=0;''')
        compiled = compile_program_v2(source)
        self.assertEqual(compiled.constrained_function_specializations, ())
        bad_call = source.replace('entry main:Int=0;', 'fn main_value()->Int=0; entry main:Text=lie<Box<Text>>(box<Text>("x"));')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(bad_call)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_MISMATCH')


if __name__ == '__main__':
    unittest.main()
