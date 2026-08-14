from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2, parse_program_v2, run_program_v2


class SourceProgramV2ExecutionTests(unittest.TestCase):
    def test_array_generic_program_compiles_and_runs_end_to_end(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn middle<T>(xs: Array<T,3>) -> T = array.get(xs, 1);
        entry main: Int = middle<Int>([4,9,7]);
        '''
        compiled, receipt=compile_and_run_program_v2(source)
        self.assertEqual(compiled.schema,"TEV_SCRIPT_COMPILED_PROGRAM_V2_V1")
        self.assertEqual(receipt.schema,"TEV_SCRIPT_PROGRAM_V2_RUN_RECEIPT_V1")
        self.assertEqual(receipt.result_type,"Int")
        self.assertEqual(receipt.result_encoded,{"$int":"9"})
        self.assertEqual(len(compiled.semantic_hash),64)
        self.assertEqual(len(compiled.entry.entry_hash),64)
        self.assertEqual(len(receipt.receipt_hash),64)

    def test_list_append_source_program_is_persistent_and_bounded(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn append<T>(xs: List<T,4>, x: T) -> List<T,4> = list.push(xs, x);
        entry main: List<Int,4> = append<Int>([1,2], 3);
        '''
        _compiled, receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded["$list"]["items"],[{"$int":"1"},{"$int":"2"},{"$int":"3"}])
        overflow=source.replace('append<Int>([1,2], 3)','append<Int>([1,2,3,4], 5)')
        with self.assertRaises(TevScriptError): compile_and_run_program_v2(overflow)

    def test_generic_record_constructor_is_real_source_syntax(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic record Box<T> { value: T; }
        generic fn box<T>(x: T) -> Box<T> = Box(value = x);
        entry main: Box<Int> = box<Int>(7);
        '''
        compiled, receipt=compile_and_run_program_v2(source)
        self.assertEqual(len(compiled.record_template_hashes),1)
        self.assertTrue(receipt.result_type.startswith("Demo.Box__g_"))
        self.assertEqual(receipt.result_encoded["$record"]["fields"][0]["name"],"value")
        self.assertEqual(receipt.result_encoded["$record"]["fields"][0]["value"],{"$int":"7"})

    def test_generic_record_dependency_order_is_not_source_order_authority(self) -> None:
        left='''
        script Demo version "2.0.0";
        generic record Wrapper<T> { box: Box<T>; }
        generic record Box<T> { value: T; }
        generic fn wrap<T>(x: T) -> Wrapper<T> = Wrapper(box = Box(value = x));
        entry main: Wrapper<Int> = wrap<Int>(5);
        '''
        right='''
        script Demo version "2.0.0";
        generic record Box<T> { value: T; }
        generic record Wrapper<T> { box: Box<T>; }
        generic fn wrap<T>(x: T) -> Wrapper<T> = Wrapper(box = Box(value = x));
        entry main: Wrapper<Int> = wrap<Int>(5);
        '''
        a,ra=compile_and_run_program_v2(left); b,rb=compile_and_run_program_v2(right)
        self.assertEqual(a.semantic_hash,b.semantic_hash)
        self.assertEqual(ra.result_hash,rb.result_hash)
        inner=ra.result_encoded["$record"]["fields"][0]["value"]
        self.assertIn("$record",inner)

    def test_if_expression_supports_generic_choice_without_dynamic_typing(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn choose<T>(flag: Bool, a: T, b: T) -> T = if flag then a else b;
        entry main: Int = choose<Int>(true, 7, 9);
        '''
        _compiled, receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"7"})

    def test_generic_equality_is_typed_after_monomorphization(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn same<T>(a: T, b: T) -> Bool = a == b;
        entry main: Bool = same<Int>(7, 7);
        '''
        _compiled, receipt=compile_and_run_program_v2(source)
        self.assertIs(receipt.result_encoded,True)

    def test_map_lookup_source_program_returns_language_option(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn lookup<T>(m: Map<Text,T,4>, key: Text) -> Option<T> = map.get(m, key);
        entry main: Option<Int> = lookup<Int>(map{"b":2,"a":1}, "a");
        '''
        _compiled, receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$option":{"type":"Option<Int>","variant":"Some","value":{"$int":"1"}}})

    def test_function_body_collection_literal_uses_declared_return_context(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn singleton<T>(x: T) -> List<T,4> = [x];
        entry main: List<Text,4> = singleton<Text>("x");
        '''
        _compiled, receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$list":{"type":"List<Text,4>","items":["x"]}})

    def test_compile_and_run_are_separate_and_repeatable(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn identity<T>(x: T) -> T = x;
        entry main: Text = identity<Text>("hello");
        '''
        compiled=compile_program_v2(source)
        a=run_program_v2(compiled); b=run_program_v2(compiled)
        self.assertEqual(a.receipt_hash,b.receipt_hash)
        self.assertEqual(a.result_encoded,"hello")

    def test_generic_type_closing_gt_adjacent_to_assignment_does_not_steal_ge_operator(self) -> None:
        compact = """
        script Demo version "2.0.0";
        fn ge(a:Int,b:Int)->Bool=a>=b;
        generic fn id<T>(x:T)->T=x;
        entry main:List<Int,4>=id<List<Int,4>>([1,2]);
        """
        compiled, receipt = compile_and_run_program_v2(compact)
        self.assertEqual(receipt.result_encoded, {"$list":{"type":"List<Int,4>","items":[{"$int":"1"},{"$int":"2"}]}})
        ge_hash = dict(compiled.function_template_hashes)["Demo.ge"]
        self.assertEqual(len(ge_hash), 64)


class SourceProgramV2IdentityTests(unittest.TestCase):
    def test_whitespace_comments_and_field_order_are_surface_only(self) -> None:
        compact='''script Demo version "2.0.0"; generic record Pair<T>{right:T;left:T;} generic fn first<T>(x:T,y:T)->T=x; entry main:Int=first<Int>(1,2);'''
        spaced='''
        // same program, formatted differently
        script   Demo   version "2.0.0";
        generic record Pair<T> {
            left: T;
            right: T;
        }
        generic fn first<T>(x: T, y: T) -> T = x;
        entry main: Int = first<Int>(1, 2);
        '''
        a=compile_program_v2(compact); b=compile_program_v2(spaced)
        self.assertEqual(a.semantic_hash,b.semantic_hash)
        self.assertEqual(a.record_template_hashes,b.record_template_hashes)
        self.assertEqual(a.function_template_hashes,b.function_template_hashes)
        self.assertEqual(a.entry.entry_hash,b.entry.entry_hash)

    def test_independent_function_declaration_order_is_not_semantic(self) -> None:
        left='''
        script Demo version "2.0.0";
        generic fn identity<T>(x:T)->T=x;
        generic fn choose<T>(flag:Bool,a:T,b:T)->T=if flag then a else b;
        entry main:Int=identity<Int>(3);
        '''
        right='''
        script Demo version "2.0.0";
        generic fn choose<T>(flag:Bool,a:T,b:T)->T=if flag then a else b;
        generic fn identity<T>(x:T)->T=x;
        entry main:Int=identity<Int>(3);
        '''
        self.assertEqual(compile_program_v2(left).semantic_hash,compile_program_v2(right).semantic_hash)

    def test_body_change_changes_program_identity_and_result(self) -> None:
        left='''script Demo version "2.0.0"; generic fn pick<T>(xs:Array<T,3>)->T=array.get(xs,1); entry main:Int=pick<Int>([4,9,7]);'''
        right='''script Demo version "2.0.0"; generic fn pick<T>(xs:Array<T,3>)->T=array.get(xs,2); entry main:Int=pick<Int>([4,9,7]);'''
        a,ra=compile_and_run_program_v2(left); b,rb=compile_and_run_program_v2(right)
        self.assertNotEqual(a.semantic_hash,b.semantic_hash)
        self.assertNotEqual(a.function_template_hashes,b.function_template_hashes)
        self.assertEqual(ra.result_encoded,{"$int":"9"})
        self.assertEqual(rb.result_encoded,{"$int":"7"})

    def test_entry_value_change_changes_entry_and_program_hash(self) -> None:
        left='''script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; entry main:Int=identity<Int>(1);'''
        right='''script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; entry main:Int=identity<Int>(2);'''
        a=compile_program_v2(left); b=compile_program_v2(right)
        self.assertNotEqual(a.entry.entry_hash,b.entry.entry_hash)
        self.assertNotEqual(a.semantic_hash,b.semantic_hash)

    def test_unused_declaration_body_is_still_program_semantics(self) -> None:
        left='''script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; generic fn unused<T>(x:T)->T=x; entry main:Int=identity<Int>(1);'''
        right='''script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; generic fn unused<T>(x:T)->T=if true then x else x; entry main:Int=identity<Int>(1);'''
        self.assertNotEqual(compile_program_v2(left).semantic_hash,compile_program_v2(right).semantic_hash)


class SourceProgramV2NegativeTests(unittest.TestCase):
    def test_v1_version_is_not_silently_reinterpreted_as_v2(self) -> None:
        source='''script Demo version "1.0.0"; generic fn identity<T>(x:T)->T=x; entry main:Int=identity<Int>(1);'''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_VERSION")

    def test_array_entry_argument_requires_exact_length(self) -> None:
        source='''script Demo version "2.0.0"; generic fn middle<T>(xs:Array<T,3>)->T=array.get(xs,1); entry main:Int=middle<Int>([4,9]);'''
        with self.assertRaises(TevScriptError): compile_program_v2(source)

    def test_entry_declared_type_must_equal_instantiated_function_return(self) -> None:
        source='''script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; entry main:Text=identity<Int>(1);'''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_ENTRY_TYPE")

    def test_entry_accepts_general_expression_surface_and_typechecks_it(self) -> None:
        source='script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; entry main:Int=1+2;'
        parsed=parse_program_v2(source)
        self.assertIsNotNone(parsed.entry.expression)
        _compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"3"})
        bad=source.replace("entry main:Int=1+2;","entry main:Text=1+2;")
        with self.assertRaises(TevScriptError): compile_program_v2(bad)

    def test_generic_calls_inside_function_body_require_explicit_type_arguments(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic fn identity<T>(x:T)->T=x;
        generic fn wrapper<T>(x:T)->T=identity(x);
        entry main:Int=wrapper<Int>(1);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_CALL_ARITY")

    def test_generic_record_cycle_is_rejected_before_registry_mutation(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic record A<T>{b:B<T>;}
        generic record B<T>{a:A<T>;}
        generic fn identity<T>(x:T)->T=x;
        entry main:Int=identity<Int>(1);
        '''
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_PROGRAM_RECORD_CYCLE")

    def test_undeclared_generic_record_dependency_is_rejected(self) -> None:
        source='''
        script Demo version "2.0.0";
        generic record A<T>{b:Missing<T>;}
        generic fn identity<T>(x:T)->T=x;
        entry main:Int=identity<Int>(1);
        '''
        with self.assertRaises(TevScriptError): compile_program_v2(source)

    def test_unsupported_host_or_network_call_is_rejected_at_compile_time(self) -> None:
        for body in ('open("x")','network.get("https://example.com")','eval("1+1")'):
            source=f'''script Demo version "2.0.0"; generic fn bad<T>(x:T)->T={body}; entry main:Int=bad<Int>(1);'''
            with self.subTest(body=body):
                with self.assertRaises(TevScriptError): compile_program_v2(source)

    def test_duplicate_symbols_and_missing_entry_fail_closed(self) -> None:
        duplicate='''script Demo version "2.0.0"; generic fn id<T>(x:T)->T=x; generic fn id<U>(x:U)->U=x; entry main:Int=id<Int>(1);'''
        missing='''script Demo version "2.0.0"; generic fn id<T>(x:T)->T=x;'''
        with self.assertRaises(TevScriptError): compile_program_v2(duplicate)
        with self.assertRaises(TevScriptError): compile_program_v2(missing)

    def test_entry_arguments_remain_contextual_not_arbitrary_expression_eval(self) -> None:
        source='''script Demo version "2.0.0"; generic fn identity<T>(x:T)->T=x; entry main:Int=identity<Int>(1+2);'''
        with self.assertRaises(TevScriptError): compile_program_v2(source)


if __name__ == "__main__":
    unittest.main()
