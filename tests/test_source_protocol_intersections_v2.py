from __future__ import annotations

import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


PAIR = "generic record Pair<T>{left:T;right:T;}\ngeneric fn make<T>(a:T,b:T)->Pair<T>=Pair(left=a,right=b);\n"
LEFT_RIGHT = "protocol Left{fn left_value(self)->Int;}\nprotocol Right{fn right_value(self)->Int;}\n"
PAIR_IMPLS = "impl Pair<Int>:Left{fn left_value(self)->Int=self.left;}\nimpl Pair<Int>:Right{fn right_value(self)->Int=self.right;}\n"


def program(body: str) -> str:
    return 'script Demo version "2.0.0";\n' + body


class SourceProtocolIntersectionsV2Tests(unittest.TestCase):
    def test_two_protocol_intersection_unions_static_method_surface(self):
        source = program(PAIR + LEFT_RIGHT + PAIR_IMPLS + '''
generic fn sum_both<T:Left+Right>(x:T)->Int=x.left_value()+x.right_value();
fn main_value()->Int=sum_both<Pair<Int>>(make<Int>(2,5));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'sum_both'][0]
        self.assertEqual(len(spec.constraint_bindings), 2)
        self.assertEqual(len(spec.protocol_intersections), 1)
        self.assertEqual(spec.protocol_intersections[0][0], 'T')

    def test_intersection_protocol_order_is_nonsemantic(self):
        tail = '''(x:T)->Int=x.left_value()+x.right_value();
fn main_value()->Int=sum_both<Pair<Int>>(make<Int>(2,5));
entry main:Int=main_value();'''
        a = compile_program_v2(program(PAIR + LEFT_RIGHT + PAIR_IMPLS + 'generic fn sum_both<T:Left+Right>' + tail))
        b = compile_program_v2(program(PAIR + LEFT_RIGHT + PAIR_IMPLS + 'generic fn sum_both<T:Right+Left>' + tail))
        self.assertEqual(a.constrained_function_template_hashes, b.constrained_function_template_hashes)
        sa = [x for x in a.constrained_function_specializations if x.function_name == 'sum_both'][0]
        sb = [x for x in b.constrained_function_specializations if x.function_name == 'sum_both'][0]
        self.assertEqual(sa.specialization_hash, sb.specialization_hash)
        self.assertEqual(sa.protocol_intersections, sb.protocol_intersections)

    def test_missing_one_witness_fails_closed(self):
        source = program('''generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
generic fn both<T:P+Q>(x:T)->Int=x.p();
fn main_value()->Int=both<Box<Int>>(box<Int>(1));
entry main:Int=main_value();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_CONSTRAINT_WITNESS')

    def test_duplicate_protocol_in_intersection_fails_closed(self):
        source = program('''protocol P{fn p(self)->Int;}
generic fn bad<T:P+P>(x:T)->Int=0;
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_DUPLICATE')

    def test_method_name_collision_fails_before_witness_resolution(self):
        source = program('''protocol P{fn x(self)->Int;}
protocol Q{fn x(self)->Int;}
generic fn bad<T:P+Q>(x:T)->Int=0;
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_METHOD_COLLISION')

    def test_associated_name_collision_fails_before_witness_resolution(self):
        source = program('''protocol P{type Item;fn p(self)->Int;}
protocol Q{type Item;fn q(self)->Int;}
generic fn bad<T:P+Q>(x:T)->Int=0;
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_INTERSECTION_ASSOCIATED_COLLISION')

    def test_disjoint_associated_projections_merge_from_exact_witness_set(self):
        source = program('''generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol HasItem{type Item;fn item(self)->Self::Item;}
protocol HasName{type Name;fn name(self)->Self::Name;}
impl Box<Int>:HasItem{type Item=Int;fn item(self)->Int=self.value;}
impl Box<Int>:HasName{type Name=Text;fn name(self)->Text="n";}
generic fn item_of<T:HasItem+HasName>(x:T)->T::Item=x.item();
fn main_value()->Int=item_of<Box<Int>>(box<Int>(9));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '9'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'item_of'][0]
        self.assertEqual(spec.associated_type_bindings, (('T', 'Item', 'Int'), ('T', 'Name', 'Text')))

    def test_refinements_can_target_disjoint_members_across_intersection(self):
        source = program('''generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol HasItem{type Item;fn item(self)->Self::Item;}
protocol HasName{type Name;fn name(self)->Self::Name;}
impl Box<Int>:HasItem{type Item=Int;fn item(self)->Int=self.value;}
impl Box<Int>:HasName{type Name=Text;fn name(self)->Text="n";}
generic fn combined<T:HasName<Name=Text>+HasItem<Item=Int>>(x:T)->T::Item=x.item();
fn main_value()->Int=combined<Box<Int>>(box<Int>(9));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '9'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'combined'][0]
        self.assertEqual(spec.associated_constraint_bindings, (('T', 'Item', 'Int'), ('T', 'Name', 'Text')))
        self.assertEqual(len(spec.protocol_intersections), 1)

    def test_wrong_refinement_on_one_intersection_member_fails_closed(self):
        source = program('''generic record Box<T>{value:T;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
protocol HasItem{type Item;fn item(self)->Self::Item;}
protocol HasName{type Name;fn name(self)->Self::Name;}
impl Box<Int>:HasItem{type Item=Int;fn item(self)->Int=self.value;}
impl Box<Int>:HasName{type Name=Text;fn name(self)->Text="n";}
generic fn bad<T:HasItem<Item=Text>+HasName<Name=Text>>(x:T)->Int=0;
fn main_value()->Int=bad<Box<Int>>(box<Int>(1));
entry main:Int=main_value();''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_ASSOCIATED_CONSTRAINT_MISMATCH')

    def test_unknown_associated_refinement_member_across_intersection_fails_statically(self):
        source = program('''protocol P{type A;fn p(self)->Int;}
protocol Q{type B;fn q(self)->Int;}
generic fn bad<T:P<C=Int>+Q>(x:T)->Int=0;
entry main:Int=0;''')
        with self.assertRaises(TevScriptError):
            compile_program_v2(source)

    def test_direct_entry_intersection_uses_same_specialization(self):
        source = program(PAIR + LEFT_RIGHT + PAIR_IMPLS + '''
generic fn sum_both<T:Left+Right>(x:T)->Int=x.left_value()+x.right_value();
entry main:Int=sum_both<Pair<Int>>(make<Int>(3,4));''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '7'})
        self.assertEqual(compiled.entry.function_name, '__tev_entry_expression_v2')
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'sum_both'][0]
        self.assertEqual(len(spec.protocol_intersections), 1)

    def test_intersection_is_erased_from_detached_program_ir(self):
        source = program(PAIR + LEFT_RIGHT + PAIR_IMPLS + '''
generic fn sum_both<T:Left+Right>(x:T)->Int=x.left_value()+x.right_value();
fn main_value()->Int=sum_both<Pair<Int>>(make<Int>(2,5));
entry main:Int=main_value();''')
        compiled, source_receipt = compile_and_run_program_v2(source)
        detached = copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable = run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_hash, source_receipt.result_hash)
        text = str(detached)
        for marker in ('INTERSECTION', 'PROTOCOL', 'WITNESS', 'Left+Right'):
            self.assertNotIn(marker, text)

    def test_witness_body_change_changes_intersection_and_specialization_not_template(self):
        prefix = PAIR + LEFT_RIGHT
        tail = '''generic fn sum_both<T:Left+Right>(x:T)->Int=x.left_value()+x.right_value();
fn main_value()->Int=sum_both<Pair<Int>>(make<Int>(2,5));
entry main:Int=main_value();'''
        a = compile_program_v2(program(prefix + 'impl Pair<Int>:Left{fn left_value(self)->Int=self.left;}\nimpl Pair<Int>:Right{fn right_value(self)->Int=self.right;}\n' + tail))
        b = compile_program_v2(program(prefix + 'impl Pair<Int>:Left{fn left_value(self)->Int=self.left+1;}\nimpl Pair<Int>:Right{fn right_value(self)->Int=self.right;}\n' + tail))
        self.assertEqual(a.constrained_function_template_hashes, b.constrained_function_template_hashes)
        sa = [x for x in a.constrained_function_specializations if x.function_name == 'sum_both'][0]
        sb = [x for x in b.constrained_function_specializations if x.function_name == 'sum_both'][0]
        self.assertNotEqual(sa.protocol_intersections, sb.protocol_intersections)
        self.assertNotEqual(sa.specialization_hash, sb.specialization_hash)

    def test_separate_single_constraints_on_two_type_parameters_do_not_create_intersection(self):
        source = program('''generic record A<T>{value:T;}
generic fn a<T>(x:T)->A<T>=A(value=x);
protocol P{fn p(self)->Int;}
protocol Q{fn q(self)->Int;}
impl A<Int>:P{fn p(self)->Int=self.value;}
impl A<Int>:Q{fn q(self)->Int=self.value;}
generic fn combine<X:P,Y:Q>(x:X,y:Y)->Int=x.p()+y.q();
fn main_value()->Int=combine<A<Int>,A<Int>>(a<Int>(2),a<Int>(3));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '5'})
        spec = [x for x in compiled.constrained_function_specializations if x.function_name == 'combine'][0]
        self.assertEqual(spec.protocol_intersections, ())

    def test_intersection_composes_through_another_intersection_generic(self):
        source = program(PAIR + LEFT_RIGHT + PAIR_IMPLS + '''
generic fn inner<T:Left+Right>(x:T)->Int=x.left_value()+x.right_value();
generic fn outer<T:Right+Left>(x:T)->Int=inner<T>(x);
fn main_value()->Int=outer<Pair<Int>>(make<Int>(4,6));
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '10'})
        inner = [x for x in compiled.constrained_function_specializations if x.function_name == 'inner'][0]
        outer = [x for x in compiled.constrained_function_specializations if x.function_name == 'outer'][0]
        self.assertEqual(inner.protocol_intersections, outer.protocol_intersections)


    def test_witness_strata_can_use_external_closed_intersection(self):
        source = program('''generic record Box<T>{value:T;}
generic record Wrap<T>{inner:Box<T>;}
generic fn box<T>(x:T)->Box<T>=Box(value=x);
generic fn wrap<T>(x:Box<T>)->Wrap<T>=Wrap(inner=x);
protocol P{fn p(self)->Int;} protocol Q{fn q(self)->Int;}
impl Box<Int>:P{fn p(self)->Int=self.value;}
impl Box<Int>:Q{fn q(self)->Int=self.value+1;}
generic fn both<T:P+Q>(x:T)->Int=x.p()+x.q();
protocol Computed{fn compute(self)->Int;}
impl Wrap<Int>:Computed{fn compute(self)->Int=both<Box<Int>>(self.inner);}
fn main_value()->Int=wrap<Int>(box<Int>(5)).compute();
entry main:Int=main_value();''')
        compiled, receipt = compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded, {'$int': '11'})
        computed = [w for w in compiled.protocol_witnesses if w.protocol_name == 'Computed'][0]
        self.assertTrue(computed.method_constraint_specializations)
        both = [x for x in compiled.constrained_function_specializations if x.function_name == 'both'][0]
        self.assertEqual(len(both.protocol_intersections), 1)

    def test_witness_strata_self_dependency_through_intersection_fails_closed(self):
        source = program('''generic record Box<T>{value:T;}
protocol P{fn p(self)->Int;} protocol Q{fn q(self)->Int;}
impl Box<Int>:Q{fn q(self)->Int=self.value;}
generic fn both<T:P+Q>(x:T)->Int=x.p()+x.q();
impl Box<Int>:P{fn p(self)->Int=both<Box<Int>>(self);}
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_PROTOCOL_WITNESS_CYCLE')

    def test_unknown_protocol_in_intersection_fails_closed(self):
        source = program('''protocol P{fn p(self)->Int;}
generic fn bad<T:P+Missing>(x:T)->Int=0;
entry main:Int=0;''')
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code, 'TEVS_V2_PROGRAM_CONSTRAINT_PROTOCOL')

    def test_plain_single_constraint_historical_template_hash_is_unchanged(self):
        source = program('''generic record Pair<T>{left:T;right:T;}
generic fn make<T>(a:T,b:T)->Pair<T>=Pair(left=a,right=b);
protocol Summable{fn sum(self)->Int;}
impl Pair<Int>:Summable{fn sum(self)->Int=self.left+self.right;}
generic fn total<T:Summable>(x:T)->Int=x.sum();
entry main:Int=0;''')
        compiled = compile_program_v2(source)
        self.assertEqual(compiled.constrained_function_template_hashes, (('Demo.total', '2ab436788ae153da4cd942ae0424a2ab97435c21d7d36d1eca3ce6acacd7c632'),))


if __name__ == '__main__':
    unittest.main()
