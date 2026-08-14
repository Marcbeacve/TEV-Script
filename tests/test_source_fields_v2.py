import copy
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.program_ir_v4 import export_program_ir_v4_pure, run_program_ir_v4_pure
from tev_script.source_program_v2 import (
    compile_and_run_program_v2,
    compile_program_v2,
    parse_expression_v2,
    tokenize_source_v2,
)


def _field_nodes(value):
    found=[]
    stack=[value]
    while stack:
        node=stack.pop()
        if isinstance(node,dict):
            if node.get("op")=="FIELD":
                found.append(node)
            stack.extend(node.values())
        elif isinstance(node,list):
            stack.extend(node)
    return found


class SourceFieldsV2Tests(unittest.TestCase):
    def test_generic_parameter_field_access_runs(self):
        source='''script Demo version "2.0.0";
        generic record Pair<T>{left:T;right:T;}
        generic fn make<T>(x:T,y:T)->Pair<T>=Pair(left=x,right=y);
        generic fn first<T>(p:Pair<T>)->T=p.left;
        fn main_value()->Int=first<Int>(make<Int>(2,3));
        entry main:Int=main_value();'''
        compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"2"})
        fields=_field_nodes(export_program_ir_v4_pure(compiled)["entry"]["body"])
        self.assertEqual(len(fields),1)
        self.assertEqual(fields[0]["field"],"left")
        self.assertTrue(fields[0]["record_type"].startswith("Demo.Pair__g_"))
        self.assertNotEqual(fields[0]["record_type"],"Pair<Int>")

    def test_postfix_field_on_call_result_runs(self):
        source='''script Demo version "2.0.0";
        generic record Pair<T>{left:T;right:T;}
        generic fn make<T>(x:T,y:T)->Pair<T>=Pair(left=x,right=y);
        fn main_value()->Int=make<Int>(4,5).right;
        entry main:Int=main_value();'''
        _compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"5"})

    def test_nested_generic_field_chain_runs(self):
        source='''script Demo version "2.0.0";
        generic record Box<T>{value:T;}
        generic record Wrap<T>{box:Box<T>;}
        generic fn wrap<T>(x:T)->Wrap<T>=Wrap(box=Box(value=x));
        generic fn unwrap<T>(w:Wrap<T>)->T=w.box.value;
        fn main_value()->Int=unwrap<Int>(wrap<Int>(9));
        entry main:Int=main_value();'''
        _compiled,receipt=compile_and_run_program_v2(source)
        self.assertEqual(receipt.result_encoded,{"$int":"9"})

    def test_missing_field_fails_closed(self):
        source='''script Demo version "2.0.0";
        generic record Pair<T>{left:T;right:T;}
        fn bad(p:Pair<Int>)->Int=p.missing;
        entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_FIELD")

    def test_non_record_field_receiver_fails_closed(self):
        source='''script Demo version "2.0.0";
        fn bad(x:Int)->Int=x.value;
        entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_FIELD")

    def test_field_result_type_is_checked(self):
        source='''script Demo version "2.0.0";
        generic record Pair<T>{left:T;right:T;}
        fn bad(p:Pair<Int>)->Text=p.left;
        entry main:Int=0;'''
        with self.assertRaises(TevScriptError) as ctx:
            compile_program_v2(source)
        self.assertEqual(ctx.exception.diagnostic.code,"TEVS_V2_PROGRAM_TYPE")

    def test_qualified_builtin_call_remains_call(self):
        expr=parse_expression_v2("list.get(xs,0)")
        self.assertEqual(expr.kind,"call")
        self.assertEqual(expr.value[0],"list.get")
        tokens=tokenize_source_v2("sensor.read(x)")
        self.assertEqual(tokens[0].kind,"IDENT")
        self.assertEqual(tokens[0].text,"sensor.read")

    def test_detached_program_ir_preserves_field_receipt(self):
        source='''script Demo version "2.0.0";
        generic record Box<T>{value:T;}
        generic fn box<T>(x:T)->Box<T>=Box(value=x);
        generic fn get<T>(x:Box<T>)->T=x.value;
        fn main_value()->Int=get<Int>(box<Int>(13));
        entry main:Int=main_value();'''
        compiled,source_receipt=compile_and_run_program_v2(source)
        detached=copy.deepcopy(export_program_ir_v4_pure(compiled))
        portable=run_program_ir_v4_pure(detached)
        self.assertEqual(portable.result_encoded,source_receipt.result_encoded)
        self.assertEqual(portable.result_hash,source_receipt.result_hash)
        fields=_field_nodes(detached["entry"]["body"])
        self.assertEqual(len(fields),1)
        self.assertTrue(fields[0]["record_type"].startswith("Demo.Box__g_"))


if __name__=="__main__":
    unittest.main()
