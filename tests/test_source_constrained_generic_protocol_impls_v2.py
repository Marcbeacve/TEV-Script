from __future__ import annotations

import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


def program(body: str) -> str:
    return 'script Conditional version "2.0.0";\n' + body


BASE_TYPES = '''generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
'''


class SourceConstrainedGenericProtocolImplsV2Tests(unittest.TestCase):
    def test_no_demand_keeps_prerequisite_template_lazy_without_witness(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=0;}
entry main:Int=0;''')
        compiled = compile_program_v2(source)
        self.assertEqual(len(compiled.generic_protocol_impl_templates), 1)
        template = compiled.generic_protocol_impl_templates[0]
        self.assertEqual(len(template.prerequisite_constraints), 1)
        self.assertEqual(template.prerequisite_associated_constraints, ())
        self.assertEqual(compiled.generic_protocol_impl_specializations, ())
        self.assertEqual(compiled.protocol_witnesses, ())

    def test_concrete_prerequisite_witness_authorizes_specialization(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(7)));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        spec = compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(spec.receiver_source_type, 'Wrap<Box<Int>>')
        self.assertEqual(len(spec.prerequisite_witnesses), 1)
        p_witness = [w for w in compiled.protocol_witnesses if w.protocol_name == 'P'][0]
        self.assertEqual(spec.prerequisite_witnesses[0][2], p_witness.witness_hash)
        q_witness = [w for w in compiled.protocol_witnesses if w.protocol_name == 'Q'][0]
        self.assertEqual(q_witness.witness_hash, spec.witness_hash)

    def test_direct_method_demand_also_resolves_prerequisite(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
entry main:Int=wrap<Box<Int>>(box<Int>(8)).q();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '8'})
        self.assertEqual(len(compiled.generic_protocol_impl_specializations), 1)
        self.assertEqual(len(compiled.generic_protocol_impl_specializations[0].prerequisite_witnesses), 1)

    def test_missing_prerequisite_witness_fails_only_when_demanded(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=0;}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(1)));''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_WITNESS')

    def test_two_prerequisite_protocols_are_both_bound(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol R{fn r(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
impl Box<Int>:R{fn r(self)->Int=1;}
generic impl<T:P+R> Wrap<T>:Q{fn q(self)->Int=self.value.p()+self.value.r();}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(4)));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '5'})
        spec = compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(len(spec.prerequisite_witnesses), 2)
        expected = sorted(w.witness_hash for w in compiled.protocol_witnesses if w.protocol_name in {'P', 'R'})
        actual = sorted(item[2] for item in spec.prerequisite_witnesses)
        self.assertEqual(actual, expected)

    def test_constraint_order_and_type_parameter_alpha_rename_are_nonsemantic(self):
        prefix = BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol R{fn r(self)->Int;}
protocol Q{fn q(self)->Int;}
'''
        a = compile_program_v2(program(prefix + '''generic impl<T:P+R> Wrap<T>:Q{fn q(self)->Int=0;}
entry main:Int=0;'''))
        b = compile_program_v2(program(prefix + '''generic impl<U:R+P> Wrap<U>:Q{fn q(self)->Int=0;}
entry main:Int=0;'''))
        self.assertEqual(a.generic_protocol_impl_templates[0].template_hash, b.generic_protocol_impl_templates[0].template_hash)
        self.assertEqual(a.generic_protocol_impl_templates[0].prerequisite_constraints, b.generic_protocol_impl_templates[0].prerequisite_constraints)

    def test_prerequisite_witness_change_changes_specialization_and_final_witness_not_template(self):
        common = BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
{p_impl}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(3)));'''
        a = compile_program_v2(program(common.replace('{p_impl}', 'impl Box<Int>:P{fn p(self)->Int=self.value;}')))
        b = compile_program_v2(program(common.replace('{p_impl}', 'impl Box<Int>:P{fn p(self)->Int=self.value+0;}')))
        self.assertEqual(a.generic_protocol_impl_templates[0].template_hash, b.generic_protocol_impl_templates[0].template_hash)
        sa = a.generic_protocol_impl_specializations[0]
        sb = b.generic_protocol_impl_specializations[0]
        self.assertNotEqual(sa.prerequisite_witnesses, sb.prerequisite_witnesses)
        self.assertNotEqual(sa.specialization_hash, sb.specialization_hash)
        self.assertNotEqual(sa.witness_hash, sb.witness_hash)

    def test_associated_prerequisite_refinement_accepts_exact_type_id(self):
        source = program(BASE_TYPES + '''protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{type Item=Int;fn p(self)->Int=self.value;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(9)));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '9'})
        template = compiled.generic_protocol_impl_templates[0]
        spec = compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(template.prerequisite_associated_constraints, ((0, 'Item', 'Int'),))
        self.assertEqual(spec.prerequisite_associated_constraints, ((0, 'Item', 'Int'),))

    def test_associated_prerequisite_refinement_mismatch_fails_closed(self):
        source = program(BASE_TYPES + '''protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{type Item=Text;fn p(self)->Int=self.value;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(9)));''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_REFINEMENT')

    def test_refinement_target_can_depend_on_impl_type_parameter(self):
        source = program(BASE_TYPES + '''protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{type Item=Box<Int>;fn p(self)->Int=self.value;}
generic impl<T:P<Item=T>> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
entry main:Int=wrap<Box<Int>>(box<Int>(9)).q();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '9'})
        spec = compiled.generic_protocol_impl_specializations[0]
        box_type_id = compiled.types.resolve_source_type('Box<Int>').type_id
        self.assertEqual(spec.prerequisite_associated_constraints, ((0, 'Item', box_type_id),))

    def test_cross_parameter_dependent_prerequisite_refinement_matches(self):
        source = program('''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
generic record Pair<A,B>{left:A;right:B;}
generic fn left<T>(x:T)->Left<T>=Left(value=x);
generic fn right<T>(x:T)->Right<T>=Right(value=x);
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
protocol R{fn score(self)->Int;}
impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
impl Right<Text>:Q{type Item=Int;fn size(self)->Int=2;}
generic impl<A:P,B:Q<Item=A::Item>> Pair<A,B>:R{fn score(self)->Int=self.right.size();}
entry main:Int=pair<Left<Int>,Right<Text>>(left<Int>(7),right<Text>("x")).score();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '2'})
        template = compiled.generic_protocol_impl_templates[0]
        spec = compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(template.prerequisite_associated_constraints, ((1, 'Item', '__T0::Item'),))
        self.assertEqual(spec.prerequisite_associated_constraints, ((1, 'Item', 'Int'),))
        detached = json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn('A::Item', json.dumps(detached, sort_keys=True))
        self.assertEqual(run_program_ir_v4_pure(detached).result_encoded, {'$int': '2'})

    def test_cross_parameter_dependent_prerequisite_refinement_mismatch_fails(self):
        source = program('''generic record Left<T>{value:T;}
generic record Right<T>{value:T;}
generic record Pair<A,B>{left:A;right:B;}
generic fn left<T>(x:T)->Left<T>=Left(value=x);
generic fn right<T>(x:T)->Right<T>=Right(value=x);
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
protocol R{fn score(self)->Int;}
impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
impl Right<Text>:Q{type Item=Text;fn size(self)->Int=2;}
generic impl<A:P,B:Q<Item=A::Item>> Pair<A,B>:R{fn score(self)->Int=self.right.size();}
entry main:Int=pair<Left<Int>,Right<Text>>(left<Int>(7),right<Text>("x")).score();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_PREREQUISITE_REFINEMENT')

    def test_dependent_prerequisite_alpha_rename_preserves_template_hash(self):
        prefix = '''generic record Pair<A,B>{left:A;right:B;}
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Item;fn size(self)->Int;}
protocol R{fn score(self)->Int;}
'''
        a = compile_program_v2(program(prefix + '''generic impl<A:P,B:Q<Item=A::Item>> Pair<A,B>:R{fn score(self)->Int=0;}
entry main:Int=0;'''))
        b = compile_program_v2(program(prefix + '''generic impl<X:P,Y:Q<Item=X::Item>> Pair<X,Y>:R{fn score(self)->Int=0;}
entry main:Int=0;'''))
        self.assertEqual(a.generic_protocol_impl_templates[0].template_hash, b.generic_protocol_impl_templates[0].template_hash)

    def test_unknown_prerequisite_protocol_fails_before_demand(self):
        source = program(BASE_TYPES + '''protocol Q{fn q(self)->Int;}
generic impl<T:Missing> Wrap<T>:Q{fn q(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_CONSTRAINT_PROTOCOL')

    def test_ambiguous_prerequisite_intersection_fails_before_demand(self):
        source = program(BASE_TYPES + '''protocol P{fn same(self)->Int;}
protocol R{fn same(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T:P+R> Wrap<T>:Q{fn q(self)->Int=0;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_METHOD_COLLISION')

    def test_prerequisite_generic_impl_is_materialized_recursively(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T> Box<T>:P{fn p(self)->Int=1;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(2)));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        receivers = {(x.protocol_name, x.receiver_source_type) for x in compiled.generic_protocol_impl_specializations}
        self.assertEqual(receivers, {('P', 'Box<Int>'), ('Q', 'Wrap<Box<Int>>')})
        q_spec = [x for x in compiled.generic_protocol_impl_specializations if x.protocol_name == 'Q'][0]
        p_spec = [x for x in compiled.generic_protocol_impl_specializations if x.protocol_name == 'P'][0]
        self.assertEqual(q_spec.prerequisite_witnesses[0][2], p_spec.witness_hash)

    def test_prerequisite_cycle_through_generic_method_fails_closed(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T> Box<T>:P{fn p(self)->Int=wrap<Box<T>>(self).q();}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=0;}
generic fn q_of<T:Q>(x:T)->Int=x.q();
entry main:Int=q_of<Wrap<Box<Int>>>(wrap<Box<Int>>(box<Int>(1)));''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_CYCLE')

    def test_conditions_do_not_create_more_specific_wins_coherence(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol R{fn r(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:R> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_constrained_generic_impl_is_erased_from_detached_program_ir(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=self.value.p();}
entry main:Int=wrap<Box<Int>>(box<Int>(6)).q();''')
        compiled = compile_program_v2(source)
        detached = json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        receipt = run_program_ir_v4_pure(detached)
        self.assertEqual(receipt.result_encoded, {'$int': '6'})
        wire = json.dumps(detached, sort_keys=True).lower()
        self.assertNotIn('generic_protocol_impl', wire)
        self.assertNotIn('prerequisite_witness', wire)


    def test_prerequisite_projection_drives_output_associated_type_and_runtime(self):
        source = program(BASE_TYPES + """protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Out;fn get(self)->Self::Out;}
impl Box<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=self.value.first();}
entry main:Int=wrap<Box<Int>>(box<Int>(7)).get();""")
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        q_witness = [w for w in compiled.protocol_witnesses if w.protocol_name == 'Q'][0]
        self.assertEqual(q_witness.associated_types, (('Out', 'Int', 'Int'),))
        self.assertEqual(compiled.generic_protocol_impl_specializations[0].associated_types, (('Out', 'Int', 'Int'),))
        detached = json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn('::', json.dumps(detached, sort_keys=True))

    def test_nested_prerequisite_projection_in_option_signature_is_erased(self):
        source = program(BASE_TYPES + """protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Out;fn maybe(self)->Option<Self::Out>;}
impl Box<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn maybe(self)->Option<T::Item>=Some(self.value.first());}
entry main:Option<Int>=wrap<Box<Int>>(box<Int>(4)).maybe();""")
        compiled = compile_program_v2(source)
        q_witness = [w for w in compiled.protocol_witnesses if w.protocol_name == 'Q'][0]
        self.assertEqual(q_witness.associated_types, (('Out', 'Int', 'Int'),))
        detached = json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn('::', json.dumps(detached, sort_keys=True))
        run_program_ir_v4_pure(detached)

    def test_prerequisite_projection_in_explicit_call_type_argument_is_specialized(self):
        source = program(BASE_TYPES + """generic fn identity<T>(x:T)->T=x;
protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Out;fn get(self)->Self::Out;}
impl Box<Int>:P{type Item=Int;fn first(self)->Int=self.value;}
generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=identity<T::Item>(self.value.first());}
entry main:Int=wrap<Box<Int>>(box<Int>(11)).get();""")
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '11'})
        detached = json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn('T::Item', json.dumps(detached, sort_keys=True))

    def test_projection_type_parameter_alpha_rename_preserves_template_hash(self):
        prefix = BASE_TYPES + """protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Out;fn get(self)->Self::Out;}
"""
        a = compile_program_v2(program(prefix + """generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=self.value.first();}
entry main:Int=0;"""))
        b = compile_program_v2(program(prefix + """generic impl<U:P> Wrap<U>:Q{type Out=U::Item;fn get(self)->U::Item=self.value.first();}
entry main:Int=0;"""))
        self.assertEqual(a.generic_protocol_impl_templates[0].template_hash, b.generic_protocol_impl_templates[0].template_hash)

    def test_unconstrained_prerequisite_projection_fails_before_demand(self):
        source = program(BASE_TYPES + """protocol Q{type Out;fn get(self)->Self::Out;}
generic impl<T> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=0;}
entry main:Int=0;""")
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_PROJECTION')

    def test_projection_member_must_be_declared_by_prerequisite_protocol(self):
        source = program(BASE_TYPES + """protocol P{fn p(self)->Int;}
protocol Q{type Out;fn get(self)->Self::Out;}
generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=0;}
entry main:Int=0;""")
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_ASSOCIATED_PROJECTION')

    def test_prerequisite_associated_binding_change_changes_output_witness_not_template(self):
        common = BASE_TYPES + """protocol P{type Item;fn first(self)->Self::Item;}
protocol Q{type Out;fn get(self)->Self::Out;}
{P_IMPL}
generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=self.value.first();}
entry main:Int=0;"""
        int_source = common.replace('{P_IMPL}', 'impl Box<Int>:P{type Item=Int;fn first(self)->Int=self.value;}')
        text_source = common.replace('{P_IMPL}', 'impl Box<Int>:P{type Item=Text;fn first(self)->Text="x";}')
        int_compiled = compile_program_v2(program(int_source.replace('entry main:Int=0;', 'entry main:Int=wrap<Box<Int>>(box<Int>(3)).get();')))
        text_compiled = compile_program_v2(program(text_source.replace('entry main:Int=0;', 'entry main:Text=wrap<Box<Int>>(box<Int>(3)).get();')))
        self.assertEqual(int_compiled.generic_protocol_impl_templates[0].template_hash, text_compiled.generic_protocol_impl_templates[0].template_hash)
        int_spec = int_compiled.generic_protocol_impl_specializations[0]
        text_spec = text_compiled.generic_protocol_impl_specializations[0]
        self.assertNotEqual(int_spec.specialization_hash, text_spec.specialization_hash)
        self.assertNotEqual(int_spec.witness_hash, text_spec.witness_hash)
        self.assertEqual(int_spec.associated_types, (('Out', 'Int', 'Int'),))
        self.assertEqual(text_spec.associated_types, (('Out', 'Text', 'Text'),))

    def test_nested_receiver_pattern_binds_inner_type_before_prerequisite_resolution(self):
        source = program(BASE_TYPES + '''protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic impl<T:P> Wrap<Option<T>>:Q{fn q(self)->Int=1;}
generic fn q_of<X:Q>(x:X)->Int=x.q();
entry main:Int=q_of<Wrap<Option<Box<Int>>>>(wrap<Option<Box<Int>>>(Some(box<Int>(7))));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        spec = [item for item in compiled.generic_protocol_impl_specializations if item.protocol_name == 'Q'][0]
        self.assertEqual(spec.receiver_source_type, 'Wrap<Option<Box<Int>>>')
        self.assertEqual(len(spec.type_argument_ids), 1)
        self.assertTrue(spec.type_argument_ids[0].startswith('Conditional.Box__g_'))
        self.assertEqual(len(spec.prerequisite_witnesses), 1)

    def test_nonlinear_receiver_pattern_binds_single_prerequisite_from_repeated_type(self):
        source = program(BASE_TYPES + '''generic record Pair<A,B>{left:A;right:B;}
generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);
protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic impl<T:P> Pair<T,T>:Q{fn q(self)->Int=1;}
generic fn q_of<X:Q>(x:X)->Int=x.q();
entry main:Int=q_of<Pair<Box<Int>,Box<Int>>>(pair<Box<Int>,Box<Int>>(box<Int>(1),box<Int>(2)));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '1'})
        spec = [item for item in compiled.generic_protocol_impl_specializations if item.protocol_name == 'Q'][0]
        self.assertEqual(len(spec.type_argument_ids), 1)
        self.assertTrue(spec.type_argument_ids[0].startswith('Conditional.Box__g_'))
        self.assertEqual(len(spec.prerequisite_witnesses), 1)


    def test_closed_associated_refinement_domains_dispatch_without_priority(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{type Item=Int;fn p(self)->Int=10;}
impl Box<Text>:P{type Item=Text;fn p(self)->Int=20;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<U:P<Item=Text>> Wrap<U>:Q{fn q(self)->Int=2;}
fn a()->Int=wrap<Box<Int>>(box<Int>(0)).q();
fn b()->Int=wrap<Box<Text>>(box<Text>("x")).q();
entry main:Int=a()+b();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '3'})
        q_specs = sorted(
            x.receiver_source_type
            for x in compiled.generic_protocol_impl_specializations
            if x.protocol_name == 'Q'
        )
        self.assertEqual(q_specs, ['Wrap<Box<Int>>', 'Wrap<Box<Text>>'])

    def test_closed_associated_refinement_domains_with_no_match_expose_no_method(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{type Item=Rat;fn p(self)->Int=0;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:P<Item=Text>> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=wrap<Box<Int>>(box<Int>(0)).q();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_METHOD_DISPATCH')

    def test_closed_refinement_disjointness_does_not_relax_other_overlap_forms(self):
        base = '''generic record Wrap<T>{value:T;}
protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
'''
        cases = (
            base + '''generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=0;''',
            base + '''generic impl<T> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=0;''',
            base + '''generic impl<T:P<Item=T>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:P<Item=Text>> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=0;''',
            '''generic record Wrap<T>{value:T;}
protocol P{type Item;fn p(self)->Int;}
protocol R{type Item;fn r(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:R<Item=Text>> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=0;''',
        )
        for source_text in cases:
            with self.subTest(source=source_text):
                with self.assertRaises(TevScriptError) as ctx:
                    compile_program_v2(program(source_text))
                self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_COHERENCE')

    def test_closed_refinement_applicability_materializes_generic_prerequisite_witnesses(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<X> Box<X>:P{type Item=X;fn p(self)->Int=0;}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:P<Item=Text>> Wrap<T>:Q{fn q(self)->Int=2;}
fn a()->Int=wrap<Box<Int>>(box<Int>(0)).q();
fn b()->Int=wrap<Box<Text>>(box<Text>("x")).q();
entry main:Int=a()+b();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '3'})
        p_specs = sorted(
            x.receiver_source_type
            for x in compiled.generic_protocol_impl_specializations
            if x.protocol_name == 'P'
        )
        self.assertEqual(p_specs, ['Box<Int>', 'Box<Text>'])

    def test_closed_refinement_applicability_cycle_fails_closed(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);
protocol P{type Item;fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
generic impl<T> Box<T>:P{type Item=T;fn p(self)->Int=wrap<Box<T>>(self).q();}
generic impl<T:P<Item=Int>> Wrap<T>:Q{fn q(self)->Int=1;}
generic impl<T:P<Item=Text>> Wrap<T>:Q{fn q(self)->Int=2;}
entry main:Int=wrap<Box<Int>>(box<Int>(0)).q();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_GENERIC_IMPL_CYCLE')



if __name__ == '__main__':
    unittest.main()
