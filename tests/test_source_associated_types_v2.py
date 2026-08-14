from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2
from tev_script.source_types_v2 import parse_type_ref_v2, resolve_type_ref_v2


BOX = 'generic record Box<T>{value:T;}\ngeneric fn box<T>(x:T)->Box<T>=Box(value=x);\n'
ITERABLE = 'protocol Iterable{type Item;fn first(self)->Self::Item;}\n'
BOX_INT_ITERABLE = 'impl Box<Int>:Iterable{type Item=Int;fn first(self)->Int=self.value;}\n'


def program(body: str) -> str:
    return 'script Demo version "2.0.0";\n' + body


class SourceAssociatedTypesV2Tests(unittest.TestCase):
    def test_associated_type_ref_is_symbolic_and_requires_resolver(self):
        ref = parse_type_ref_v2('T::Item')
        self.assertEqual(ref.kind, 'associated')
        self.assertEqual(ref.name, 'T::Item')
        with self.assertRaises(TevScriptError) as ctx:
            resolve_type_ref_v2(ref)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_ASSOCIATED_TYPE_UNRESOLVED')

    def test_witness_bound_projection_runs_and_is_erased_from_program_ir(self):
        source = program(BOX + ITERABLE + BOX_INT_ITERABLE + '''
generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();
fn main_value()->Int=first_of<Box<Int>>(box<Int>(7));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        witness = compiled.protocol_witnesses[0]
        self.assertEqual(witness.associated_types, (('Item', 'Int', 'Int'),))
        specs = [item for item in compiled.constrained_function_specializations if item.function_name == 'first_of']
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].associated_type_bindings, (('T', 'Item', 'Int'),))
        detached = copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable = run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash, receipt.result_hash)
        text = str(detached)
        for marker in ('Self::', 'T::', 'ASSOCIATED', 'WITNESS', 'PROTOCOL'):
            self.assertNotIn(marker, text)

    def test_nested_option_projection_specializes_to_concrete_type(self):
        source = program(BOX + ITERABLE + BOX_INT_ITERABLE + '''
generic fn maybe<T:Iterable>(x:T)->Option<T::Item>=Some(x.first());
fn main_value()->Option<Int>=maybe<Box<Int>>(box<Int>(9));
entry main:Option<Int>=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$option': {'type': 'Option<Int>', 'variant': 'Some', 'value': {'$int': '9'}}})
        spec = [item for item in compiled.constrained_function_specializations if item.function_name == 'maybe'][0]
        self.assertEqual(spec.associated_type_bindings, (('T', 'Item', 'Int'),))

    def test_task_annotation_projection_is_specialized_before_ir(self):
        source = program(BOX + ITERABLE + BOX_INT_ITERABLE + '''
generic fn fan<T:Iterable>(x:T)->T::Item=await all(a:T::Item=x.first())=>a;
fn main_value()->Int=fan<Box<Int>>(box<Int>(12));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '12'})
        self.assertNotIn('T::Item', str(export_program_ir_v4_pure(compiled)))

    def test_projected_parameter_type_is_enforced(self):
        source = program(BOX + ITERABLE + BOX_INT_ITERABLE + '''
generic fn keep<T:Iterable>(x:T,v:T::Item)->T::Item=v;
fn main_value()->Int=keep<Box<Int>>(box<Int>(1),6);
entry main:Int=main_value();''')
        _compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '6'})

    def test_direct_entry_constrained_projection_uses_compile_time_wrapper(self):
        source = program(BOX + ITERABLE + BOX_INT_ITERABLE + '''
generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();
entry main:Int=first_of<Box<Int>>(box<Int>(13));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '13'})
        self.assertEqual(compiled.entry.function_name, '__tev_entry_expression_v2')
        self.assertEqual(len([s for s in compiled.constrained_function_specializations if s.function_name == 'first_of']), 1)

    def test_same_protocol_two_receivers_produce_distinct_associated_specializations(self):
        source = program(BOX + ITERABLE + '''
impl Box<Int>:Iterable{type Item=Int;fn first(self)->Int=self.value;}
impl Box<Text>:Iterable{type Item=Text;fn first(self)->Text=self.value;}
generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();
fn int_value()->Int=first_of<Box<Int>>(box<Int>(4));
fn text_value()->Text=first_of<Box<Text>>(box<Text>("x"));
entry main:Int=int_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '4'})
        specs = [s for s in compiled.constrained_function_specializations if s.function_name == 'first_of']
        self.assertEqual(len(specs), 2)
        self.assertEqual({s.associated_type_bindings for s in specs}, {(('T', 'Item', 'Int'),), (('T', 'Item', 'Text'),)})
        self.assertEqual(len({s.specialization_hash for s in specs}), 2)

    def test_associated_declaration_order_is_canonical(self):
        a = program('protocol P{type A;type B;fn get(self)->Int;} entry main:Int=0;')
        b = program('protocol P{type B;type A;fn get(self)->Int;} entry main:Int=0;')
        ca = compile_program_v2(a)
        cb = compile_program_v2(b)
        self.assertEqual(ca.protocol_hashes, cb.protocol_hashes)
        self.assertEqual(ca.semantic_hash, cb.semantic_hash)

    def test_associated_binding_change_changes_witness_and_specialization_not_protocol(self):
        common = BOX + 'protocol Marker{type Item;fn id(self)->Int;}\n'
        tail = 'generic fn identify<T:Marker>(x:T)->Int=x.id(); fn main_value()->Int=identify<Box<Int>>(box<Int>(3)); entry main:Int=main_value();'
        a = compile_program_v2(program(common + 'impl Box<Int>:Marker{type Item=Int;fn id(self)->Int=self.value;}\n' + tail))
        b = compile_program_v2(program(common + 'impl Box<Int>:Marker{type Item=Text;fn id(self)->Int=self.value;}\n' + tail))
        self.assertEqual(a.protocol_hashes, b.protocol_hashes)
        self.assertNotEqual(a.protocol_witnesses[0].witness_hash, b.protocol_witnesses[0].witness_hash)
        sa = [x for x in a.constrained_function_specializations if x.function_name == 'identify'][0]
        sb = [x for x in b.constrained_function_specializations if x.function_name == 'identify'][0]
        self.assertNotEqual(sa.specialization_hash, sb.specialization_hash)

    def test_missing_associated_binding_fails_closed(self):
        source = program(BOX + ITERABLE + 'impl Box<Int>:Iterable{fn first(self)->Int=self.value;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_MISSING_ASSOCIATED_TYPE')

    def test_extra_associated_binding_fails_closed(self):
        source = program(BOX + 'protocol P{fn get(self)->Int;} impl Box<Int>:P{type Item=Int;fn get(self)->Int=self.value;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_UNKNOWN_ASSOCIATED_TYPE')

    def test_duplicate_associated_declaration_fails_closed(self):
        source = program('protocol P{type Item;type Item;fn get(self)->Int;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_DUPLICATE_ASSOCIATED_TYPE')

    def test_duplicate_associated_binding_fails_closed(self):
        source = program(BOX + 'protocol P{type Item;fn get(self)->Int;} impl Box<Int>:P{type Item=Int;type Item=Text;fn get(self)->Int=self.value;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_TYPE_DUPLICATE')

    def test_associated_binding_requires_protocol_impl(self):
        source = program(BOX + 'impl Box<Int>{type Item=Int;fn get(self)->Int=self.value;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_TYPE_IMPL')

    def test_associated_binding_must_be_concrete(self):
        source = program(BOX + 'protocol P{type Item;fn get(self)->Int;} impl Box<Int>:P{type Item=Unknown;fn get(self)->Int=self.value;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_TYPE_BINDING')

    def test_protocol_projection_must_reference_declared_self_associated_type(self):
        source = program(BOX + 'protocol P{type Item;fn get(self)->Self::Other;} impl Box<Int>:P{type Item=Int;fn get(self)->Int=self.value;} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_ASSOCIATED_TYPE')

    def test_projection_requires_constraint_on_root_type_parameter(self):
        source = program(BOX + 'generic fn bad<T>(x:T)->T::Item=x; entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_TYPE_CONSTRAINT')

    def test_projection_member_must_exist_on_constraint_protocol(self):
        source = program(BOX + 'protocol P{fn get(self)->Int;} generic fn bad<T:P>(x:T)->T::Item=x.get(); entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_TYPE_CONSTRAINT')

    def test_projected_protocol_signature_must_match_impl_binding(self):
        source = program(BOX + ITERABLE + 'impl Box<Int>:Iterable{type Item=Int;fn first(self)->Text="x";} entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_SIGNATURE')

    def test_invalid_projection_hidden_in_uncalled_template_body_is_rejected(self):
        source = program(BOX + 'protocol P{type Item;fn get(self)->Int;} generic fn bad<T:P>(x:T)->Int=await all(a:T::Missing=1)=>1; entry main:Int=0;')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_TYPE_CONSTRAINT')


    def test_nested_self_projection_in_protocol_signature_is_projected_from_witness(self):
        source = program(BOX + '''protocol MaybeFirst{type Item;fn first(self)->Option<Self::Item>;}
impl Box<Int>:MaybeFirst{type Item=Int;fn first(self)->Option<Int>=Some(self.value);}
fn main_value()->Option<Int>=box<Int>(5).first();
entry main:Option<Int>=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$option': {'type': 'Option<Int>', 'variant': 'Some', 'value': {'$int': '5'}}})
        self.assertEqual(compiled.protocol_witnesses[0].associated_types, (('Item', 'Int', 'Int'),))

    def test_associated_witness_can_depend_on_external_closed_constrained_witness(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{inner:Box<T>;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:Box<T>)->Wrap<T>=Wrap(inner=x);
protocol Valued{fn value_int(self)->Int;}
impl Box<Int>:Valued{fn value_int(self)->Int=self.value;}
generic fn value_of<T:Valued>(x:T)->Int=x.value_int();
protocol Computed{type Out;fn compute(self)->Self::Out;}
impl Wrap<Int>:Computed{type Out=Int;fn compute(self)->Int=value_of<Box<Int>>(self.inner);}
fn main_value()->Int=wrap<Int>(box<Int>(14)).compute();
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '14'})
        computed = [w for w in compiled.protocol_witnesses if w.protocol_name == 'Computed'][0]
        self.assertEqual(computed.associated_types, (('Out', 'Int', 'Int'),))
        self.assertTrue(computed.method_constraint_specializations)
        dependency_hash = computed.method_constraint_specializations[0][1][0]
        self.assertIn(dependency_hash, {spec.specialization_hash for spec in compiled.constrained_function_specializations})


if __name__ == '__main__':
    unittest.main()
