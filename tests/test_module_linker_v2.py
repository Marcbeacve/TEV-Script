from __future__ import annotations

import copy
import json
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.module_linker_v2 import build_module_bundle_v2, build_module_lock_v2, compile_program_from_module_bundle_v2, compile_program_with_modules_v2, module_sources_from_bundle_v2, parse_pure_module_v2, validate_module_bundle_v2, validate_module_lock_v2
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4
from tev_script.source_program_v2 import run_program_v2


class ModuleLinkerV2Tests(unittest.TestCase):
    UTIL = """
    module math.util version \"2.0.0\";
    export fn inc(x:Int)->Int=x+1;
    export fn twice(x:Int)->Int=inc(inc(x));
    """
    APP = """
    script App version \"2.0.0\";
    import math.util as util;
    fn solve(x:Int)->Int=util.twice(x);
    entry main:Int=solve(5);
    """

    def test_simple_module_links_runs_and_disappears_before_runtime(self):
        modules={"math.util":self.UTIL}
        lock=build_module_lock_v2(modules)
        linked=compile_program_with_modules_v2(self.APP,modules,expected_lock=lock)
        receipt=run_program_v2(linked.compiled)
        self.assertEqual(receipt.result_encoded,{"$int":"7"})
        ir=export_program_ir_v4_pure(linked.compiled)
        detached=json.loads(json.dumps(ir))
        runtime=run_program_ir_v4(detached)
        self.assertEqual(runtime.result_encoded,{"$int":"7"})
        self.assertNotIn("module",json.dumps(detached).lower())

    def test_generic_export_is_statically_linked(self):
        modules={"lib.id":"""module lib.id version \"2.0.0\"; export generic fn identity<T>(x:T)->T=x;"""}
        app="""script App version \"2.0.0\"; import lib.id as ids; fn solve(x:Int)->Int=ids.identity<Int>(x); entry main:Int=solve(9);"""
        linked=compile_program_with_modules_v2(app,modules)
        self.assertEqual(run_program_v2(linked.compiled).result_encoded,{"$int":"9"})

    def test_recursive_program_can_call_imported_pure_helper(self):
        modules={"math.step":'''module math.step version "2.0.0"; export fn dec(x:Int)->Int=x-1;'''}
        app="""script App version "2.0.0";
        import math.step as step;
        recursive fn countdown(n:Int)->Int decreases n max_depth 8 = if n==0 then 0 else self(step.dec(n));
        entry main:Int=countdown(5);
        """
        linked=compile_program_with_modules_v2(app,modules)
        self.assertEqual(linked.compiled.entry.function_kind,'recursive')
        self.assertEqual(run_program_v2(linked.compiled).result_encoded,{"$int":"0"})

    def test_transitive_dependency_change_changes_parent_and_program_identity(self):
        core1="""module core.num version \"2.0.0\"; export fn inc(x:Int)->Int=x+1;"""
        core2="""module core.num version \"2.0.0\"; export fn inc(x:Int)->Int=x+2;"""
        util="""module math.util version \"2.0.0\"; import core.num as c; export fn twice(x:Int)->Int=c.inc(c.inc(x));"""
        app="""script App version \"2.0.0\"; import math.util as u; fn solve(x:Int)->Int=u.twice(x); entry main:Int=solve(5);"""
        m1={"core.num":core1,"math.util":util}; m2={"core.num":core2,"math.util":util}
        l1=build_module_lock_v2(m1); l2=build_module_lock_v2(m2)
        by1={m["module_id"]:m for m in l1["modules"]}; by2={m["module_id"]:m for m in l2["modules"]}
        self.assertNotEqual(by1["core.num"]["module_semantic_hash"],by2["core.num"]["module_semantic_hash"])
        self.assertNotEqual(by1["math.util"]["dependency_lock_hash"],by2["math.util"]["dependency_lock_hash"])
        self.assertNotEqual(by1["math.util"]["module_semantic_hash"],by2["math.util"]["module_semantic_hash"])
        p1=compile_program_with_modules_v2(app,m1); p2=compile_program_with_modules_v2(app,m2)
        self.assertNotEqual(p1.compiled.semantic_hash,p2.compiled.semantic_hash)
        self.assertEqual(run_program_v2(p1.compiled).result_encoded,{"$int":"7"})
        self.assertEqual(run_program_v2(p2.compiled).result_encoded,{"$int":"9"})

    def test_module_whitespace_is_semantically_irrelevant_but_exact_source_lock_changes(self):
        a="module math.util version \"2.0.0\"; export fn inc(x:Int)->Int=x+1;"
        b="""module math.util version \"2.0.0\";

// surface comment
export fn inc ( x : Int ) -> Int = x + 1 ;
"""
        la=build_module_lock_v2({"math.util":a}); lb=build_module_lock_v2({"math.util":b})
        ma=la["modules"][0]; mb=lb["modules"][0]
        self.assertEqual(ma["module_semantic_hash"],mb["module_semantic_hash"])
        self.assertEqual(ma["export_surface_hash"],mb["export_surface_hash"])
        self.assertNotEqual(ma["source_sha256"],mb["source_sha256"])
        self.assertNotEqual(la["lock_hash"],lb["lock_hash"])

    def test_independent_import_order_is_surface_only(self):
        modules={
            "a.one":"module a.one version \"2.0.0\"; export fn one(x:Int)->Int=x+1;",
            "b.two":"module b.two version \"2.0.0\"; export fn two(x:Int)->Int=x+2;",
        }
        body="fn solve(x:Int)->Int=a.one(b.two(x)); entry main:Int=solve(1);"
        p1="script App version \"2.0.0\"; import a.one as a; import b.two as b; "+body
        p2="script App version \"2.0.0\"; import b.two as b; import a.one as a; "+body
        l1=compile_program_with_modules_v2(p1,modules); l2=compile_program_with_modules_v2(p2,modules)
        self.assertEqual(l1.dependency_lock_hash,l2.dependency_lock_hash)
        self.assertEqual(l1.compiled.semantic_hash,l2.compiled.semantic_hash)
        self.assertEqual(run_program_v2(l1.compiled).result_encoded,{"$int":"4"})

    def test_module_bundle_roundtrips_detached_and_compiles_without_source_files(self):
        modules={"math.util":self.UTIL}
        bundle=build_module_bundle_v2(modules)
        detached=json.loads(json.dumps(bundle))
        validated=validate_module_bundle_v2(detached)
        self.assertEqual(validated['bundle_hash'],bundle['bundle_hash'])
        self.assertEqual(module_sources_from_bundle_v2(detached),modules)
        linked=compile_program_from_module_bundle_v2(self.APP,detached)
        self.assertEqual(run_program_v2(linked.compiled).result_encoded,{"$int":"7"})
        ir=export_program_ir_v4_pure(linked.compiled)
        self.assertEqual(run_program_ir_v4(json.loads(json.dumps(ir))).result_encoded,{"$int":"7"})

    def test_module_bundle_source_or_lock_tamper_is_rejected(self):
        bundle=build_module_bundle_v2({"math.util":self.UTIL})
        source_tamper=copy.deepcopy(bundle); source_tamper['modules'][0]['source'] += '\n// tamper'
        with self.assertRaises(TevScriptError) as captured:
            validate_module_bundle_v2(source_tamper)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_MODULE_BUNDLE_SOURCE_HASH')
        lock_tamper=copy.deepcopy(bundle); lock_tamper['lock']['modules'][0]['module_semantic_hash']='0'*64
        with self.assertRaises(TevScriptError) as captured:
            validate_module_bundle_v2(lock_tamper)
        self.assertEqual(captured.exception.diagnostic.code,'TEVS_V2_MODULE_BUNDLE_LOCK')

    def test_exact_lock_tamper_is_rejected(self):
        modules={"math.util":self.UTIL}; lock=build_module_lock_v2(modules); tampered=copy.deepcopy(lock)
        tampered["modules"][0]["source_sha256"]="0"*64
        with self.assertRaises(TevScriptError) as captured:
            validate_module_lock_v2(tampered,modules)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_MODULE_LOCK_MISMATCH")
        with self.assertRaises(TevScriptError):
            compile_program_with_modules_v2(self.APP,modules,expected_lock=tampered)

    def test_cycle_is_rejected_before_program_compile(self):
        modules={
            "a.mod":"module a.mod version \"2.0.0\"; import b.mod as b; export fn a(x:Int)->Int=b.b(x);",
            "b.mod":"module b.mod version \"2.0.0\"; import a.mod as a; export fn b(x:Int)->Int=a.a(x);",
        }
        with self.assertRaises(TevScriptError) as captured:
            build_module_lock_v2(modules)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_MODULE_CYCLE")

    def test_private_function_is_not_visible_through_alias(self):
        modules={"m.lib":"module m.lib version \"2.0.0\"; fn hidden(x:Int)->Int=x+1; export fn shown(x:Int)->Int=hidden(x);"}
        app="script App version \"2.0.0\"; import m.lib as m; fn solve(x:Int)->Int=m.hidden(x); entry main:Int=solve(1);"
        with self.assertRaises(TevScriptError) as captured:
            compile_program_with_modules_v2(app,modules)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_MODULE_EXPORT")

    def test_missing_dependency_duplicate_alias_and_duplicate_module_import_fail_closed(self):
        with self.assertRaises(TevScriptError) as captured:
            build_module_lock_v2({"m.lib":"module m.lib version \"2.0.0\"; import missing.mod as x; export fn f(x:Int)->Int=x;"})
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_MODULE_MISSING")
        modules={"a.one":"module a.one version \"2.0.0\"; export fn f(x:Int)->Int=x;","b.two":"module b.two version \"2.0.0\"; export fn g(x:Int)->Int=x;"}
        app_alias="script App version \"2.0.0\"; import a.one as x; import b.two as x; fn solve(v:Int)->Int=x.f(v); entry main:Int=solve(1);"
        with self.assertRaises(TevScriptError) as captured:
            compile_program_with_modules_v2(app_alias,modules)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_MODULE_ALIAS")
        app_dup="script App version \"2.0.0\"; import a.one as x; import a.one as y; fn solve(v:Int)->Int=x.f(v); entry main:Int=solve(1);"
        with self.assertRaises(TevScriptError) as captured:
            compile_program_with_modules_v2(app_dup,modules)
        self.assertEqual(captured.exception.diagnostic.code,"TEVS_V2_MODULE_IMPORT")

    def test_module_profile_rejects_records_and_recursion(self):
        bad_record="module x.r version \"2.0.0\"; generic record Box<T>{value:T;} export fn f(x:Int)->Int=x;"
        with self.assertRaises(TevScriptError): parse_pure_module_v2(bad_record)
        bad_rec="module x.r version \"2.0.0\"; export fn f(x:Int)->Int=x; recursive fn r(n:Int)->Int decreases n max_depth 2 = if n==0 then 0 else self(n-1);"
        with self.assertRaises(TevScriptError): parse_pure_module_v2(bad_rec)


    def test_linked_program_preserves_concrete_method_and_rewrites_import_in_body(self):
        modules={"lib.num":"module lib.num version \"2.0.0\"; export fn bump(x:Int)->Int=x+1;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Box<T>{value:T;}\n"
            "generic fn box<T>(x:T)->Box<T>=Box(value=x);\n"
            "impl Box<Int>{fn bumped(self)->Int=n.bump(self.value);}\n"
            "entry main:Int=box<Int>(4).bumped();"
        )
        linked=compile_program_with_modules_v2(app,modules)
        self.assertEqual(run_program_v2(linked.compiled).result_encoded,{"$int":"5"})
        detached=json.loads(json.dumps(export_program_ir_v4_pure(linked.compiled)))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"5"})
        self.assertNotIn("module",json.dumps(detached).lower())

    def test_linked_program_preserves_protocol_associated_binding_and_constrained_call(self):
        modules={"lib.num":"module lib.num version \"2.0.0\"; export fn bump(x:Int)->Int=x+1;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Box<T>{value:T;}\n"
            "generic fn box<T>(x:T)->Box<T>=Box(value=x);\n"
            "protocol Iterable{type Item;fn first(self)->Self::Item;}\n"
            "impl Box<Int>:Iterable{type Item=Int;fn first(self)->Int=n.bump(self.value);}\n"
            "generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();\n"
            "entry main:Int=first_of<Box<Int>>(box<Int>(4));"
        )
        linked=compile_program_with_modules_v2(app,modules)
        compiled=linked.compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"5"})
        self.assertEqual(len(compiled.protocol_witnesses),1)
        self.assertEqual(compiled.protocol_witnesses[0].associated_types,(("Item","Int","Int"),))
        self.assertEqual(len(compiled.constrained_function_specializations),1)

    def test_linked_program_preserves_generic_protocol_impl_and_rewrites_import_in_body(self):
        modules={"lib.id":"module lib.id version \"2.0.0\"; export generic fn identity<T>(x:T)->T=x;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.id as ids;\n"
            "generic record Box<T>{value:T;}\n"
            "generic fn box<T>(x:T)->Box<T>=Box(value=x);\n"
            "protocol Iterable{type Item;fn first(self)->Self::Item;}\n"
            "generic impl<T> Box<T>:Iterable{type Item=T;fn first(self)->T=ids.identity<T>(self.value);}\n"
            "generic fn first_of<T:Iterable>(x:T)->T::Item=x.first();\n"
            "entry main:Int=first_of<Box<Int>>(box<Int>(7));"
        )
        linked=compile_program_with_modules_v2(app,modules)
        compiled=linked.compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"7"})
        self.assertEqual(len(compiled.generic_protocol_impl_templates),1)
        self.assertEqual(len(compiled.generic_protocol_impl_specializations),1)
        self.assertEqual(compiled.generic_protocol_impl_specializations[0].receiver_source_type,"Box<Int>")
        self.assertEqual(len(compiled.protocol_witnesses),1)
        detached=json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"7"})
        self.assertNotIn("generic_protocol_impl",json.dumps(detached).lower())

    def test_linked_program_keeps_generic_impl_template_lazy_without_demand(self):
        modules={"lib.id":"module lib.id version \"2.0.0\"; export generic fn identity<T>(x:T)->T=x;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.id as ids;\n"
            "generic record Box<T>{value:T;}\n"
            "protocol Iterable{type Item;fn first(self)->Self::Item;}\n"
            "generic impl<T> Box<T>:Iterable{type Item=T;fn first(self)->T=ids.identity<T>(self.value);}\n"
            "entry main:Int=0;"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(len(compiled.generic_protocol_impl_templates),1)
        self.assertEqual(compiled.generic_protocol_impl_specializations,())
        self.assertEqual(compiled.protocol_witnesses,())
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"0"})


    def test_linked_constrained_generic_impl_preserves_prerequisite_and_import_rewrite(self):
        modules={"lib.num":"module lib.num version \"2.0.0\"; export fn bump(x:Int)->Int=x+1;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Box<T>{value:T;}\n"
            "generic record Wrap<T>{value:T;}\n"
            "generic fn box<T>(x:T)->Box<T>=Box(value=x);\n"
            "generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);\n"
            "protocol P{fn p(self)->Int;}\n"
            "protocol Q{fn q(self)->Int;}\n"
            "impl Box<Int>:P{fn p(self)->Int=self.value;}\n"
            "generic impl<T:P> Wrap<T>:Q{fn q(self)->Int=n.bump(self.value.p());}\n"
            "entry main:Int=wrap<Box<Int>>(box<Int>(5)).q();"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"6"})
        self.assertEqual(len(compiled.generic_protocol_impl_specializations),1)
        spec=compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(spec.receiver_source_type,"Wrap<Box<Int>>")
        self.assertEqual(len(spec.prerequisite_witnesses),1)



    def test_linked_constrained_generic_impl_projects_prerequisite_associated_type(self):
        modules={"lib.id":"module lib.id version \"2.0.0\"; export generic fn identity<T>(x:T)->T=x;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.id as ids;\n"
            "generic record Box<T>{value:T;}\n"
            "generic record Wrap<T>{value:T;}\n"
            "generic fn box<T>(x:T)->Box<T>=Box(value=x);\n"
            "generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);\n"
            "protocol P{type Item;fn first(self)->Self::Item;}\n"
            "protocol Q{type Out;fn get(self)->Self::Out;}\n"
            "impl Box<Int>:P{type Item=Int;fn first(self)->Int=self.value;}\n"
            "generic impl<T:P> Wrap<T>:Q{type Out=T::Item;fn get(self)->T::Item=ids.identity<T::Item>(self.value.first());}\n"
            "entry main:Int=wrap<Box<Int>>(box<Int>(12)).get();"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"12"})
        q_witness=[w for w in compiled.protocol_witnesses if w.protocol_name=="Q"][0]
        self.assertEqual(q_witness.associated_types,(("Out","Int","Int"),))
        detached=json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn("::",json.dumps(detached,sort_keys=True))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"12"})


    def test_linked_dependent_associated_constraint_survives_import_rewrite(self):
        modules={"lib.num":"module lib.num version \"2.0.0\"; export fn bump(x:Int)->Int=x+1;"}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Left<T>{value:T;}\n"
            "generic record Right<T>{value:T;}\n"
            "generic fn left<T>(x:T)->Left<T>=Left(value=x);\n"
            "generic fn right<T>(x:T)->Right<T>=Right(value=x);\n"
            "protocol P{type Item;fn first(self)->Self::Item;}\n"
            "protocol Q{type Item;fn size(self)->Int;}\n"
            "impl Left<Int>:P{type Item=Int;fn first(self)->Int=self.value;}\n"
            "impl Right<Text>:Q{type Item=Int;fn size(self)->Int=2;}\n"
            "generic fn same<A:P,B:Q<Item=A::Item>>(a:A,b:B)->Int=n.bump(b.size());\n"
            "entry main:Int=same<Left<Int>,Right<Text>>(left<Int>(7),right<Text>(\"x\"));"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"3"})
        spec=[x for x in compiled.constrained_function_specializations if x.function_name=="same"][0]
        self.assertEqual(spec.associated_constraint_bindings,(("B","Item","Int"),))
        detached=json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn("A::Item",json.dumps(detached,sort_keys=True))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"3"})

    def test_linked_nested_generic_impl_pattern_preserves_import_rewrite(self):
        modules={"lib.num":'''module lib.num version "2.0.0"; export fn bump(x:Int)->Int=x+1;'''}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Wrap<T>{value:T;}\n"
            "generic fn wrap<T>(x:T)->Wrap<T>=Wrap(value=x);\n"
            "protocol P{fn p(self)->Int;}\n"
            "generic impl<T> Wrap<Option<T>>:P{fn p(self)->Int=n.bump(0);}\n"
            "entry main:Int=wrap<Option<Int>>(Some(7)).p();"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"1"})
        spec=compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(spec.receiver_source_type,"Wrap<Option<Int>>")
        self.assertEqual(spec.type_argument_ids,("Int",))
        detached=json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn("Wrap<Option<T>>",json.dumps(detached,sort_keys=True))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"1"})

    def test_linked_nonlinear_generic_impl_pattern_preserves_import_rewrite(self):
        modules={"lib.num":'''module lib.num version "2.0.0"; export fn bump(x:Int)->Int=x+1;'''}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Pair<A,B>{left:A;right:B;}\n"
            "generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);\n"
            "protocol P{fn p(self)->Int;}\n"
            "generic impl<T> Pair<T,T>:P{fn p(self)->Int=n.bump(0);}\n"
            "entry main:Int=pair<Int,Int>(1,2).p();"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"1"})
        spec=compiled.generic_protocol_impl_specializations[0]
        self.assertEqual(spec.receiver_source_type,"Pair<Int,Int>")
        self.assertEqual(spec.type_argument_ids,("Int",))
        detached=json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn("Pair<T,T>",json.dumps(detached,sort_keys=True))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"1"})


    def test_linked_associated_receiver_pattern_preserves_import_rewrite_and_evidence(self):
        modules={"lib.num":'''module lib.num version "2.0.0"; export fn bump(x:Int)->Int=x+1;'''}
        app = (
            "script App version \"2.0.0\";\n"
            "import lib.num as n;\n"
            "generic record Box<T>{value:T;}\n"
            "generic record Pair<A,B>{left:A;right:B;}\n"
            "generic fn box<T>(x:T)->Box<T>=Box(value=x);\n"
            "generic fn pair<A,B>(a:A,b:B)->Pair<A,B>=Pair(left=a,right=b);\n"
            "protocol P{type Item;fn first(self)->Self::Item;}\n"
            "protocol Q{fn q(self)->Int;}\n"
            "generic impl<T> Box<T>:P{type Item=T;fn first(self)->T=self.value;}\n"
            "generic impl<T:P> Pair<T,T::Item>:Q{fn q(self)->Int=n.bump(0);}\n"
            "entry main:Int=pair<Box<Int>,Int>(box<Int>(2),3).q();"
        )
        compiled=compile_program_with_modules_v2(app,modules).compiled
        self.assertEqual(run_program_v2(compiled).result_encoded,{"$int":"1"})
        q_spec=[x for x in compiled.generic_protocol_impl_specializations if x.protocol_name=="Q"][0]
        q_witness=[x for x in compiled.protocol_witnesses if x.protocol_name=="Q"][0]
        self.assertEqual(q_spec.receiver_associated_projections,(("T","Item","Int"),))
        self.assertEqual(q_witness.receiver_associated_projections,(("T","Item","Int"),))
        detached=json.loads(json.dumps(export_program_ir_v4_pure(compiled)))
        self.assertNotIn("T::Item",json.dumps(detached,sort_keys=True))
        self.assertEqual(run_program_ir_v4(detached).result_encoded,{"$int":"1"})



if __name__ == "__main__": unittest.main()
