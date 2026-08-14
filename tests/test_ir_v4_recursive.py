from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.ir_v4_recursive import evaluate_recursive_v4, validate_recursive_v4
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


class IrV4RecursiveKernelTests(unittest.TestCase):
    def _kernel_from_source(self, source: str):
        compiled = compile_program_v2(source)
        inst = compiled.entry.instantiation
        contract = validate_recursive_v4(
            inst.body,
            compiled.types.table,
            inst.parameter_names,
            inst.parameter_type_ids,
            inst.return_type_id,
            measure_parameter=inst.measure_parameter,
            max_depth=inst.max_depth,
            maximum_steps=inst.maximum_steps,
        )
        return compiled, inst, contract

    def test_factorial_matches_existing_recursive_runtime_exact_result(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
        entry main:Int=factorial(5);
        '''
        compiled, old = compile_and_run_program_v2(source)
        _compiled, _inst, contract = self._kernel_from_source(source)
        new = evaluate_recursive_v4(contract, compiled.types.table, compiled.entry.arguments)
        self.assertEqual(new.result_type, old.result_type)
        self.assertEqual(new.result_encoded, old.result_encoded)
        self.assertEqual(new.result_hash, old.result_hash)
        self.assertEqual(new.result_encoded, {"$int":"120"})

    def test_generic_recursive_list_matches_existing_runtime(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn repeat<T>(n:Int,x:T,acc:List<T,4>)->List<T,4> decreases n max_depth 4 = if n==0 then acc else self(n-1,x,list.push(acc,x));
        entry main:List<Int,4>=repeat<Int>(3,7,[]);
        '''
        compiled, old = compile_and_run_program_v2(source)
        _compiled, _inst, contract = self._kernel_from_source(source)
        new = evaluate_recursive_v4(contract, compiled.types.table, compiled.entry.arguments)
        self.assertEqual(new.result_encoded, old.result_encoded)
        self.assertEqual(new.result_hash, old.result_hash)

    def test_contract_recomputes_same_bounds_as_instantiation(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn down(n:Int)->Int decreases n max_depth 8 = if n==0 then 0 else self(n-1);
        entry main:Int=down(4);
        '''
        _compiled, inst, contract = self._kernel_from_source(source)
        self.assertEqual(contract.measure_index, inst.measure_index)
        self.assertEqual(contract.local_static_step_upper_bound, inst.local_static_step_upper_bound)
        self.assertEqual(contract.recursive_static_step_upper_bound, inst.recursive_static_step_upper_bound)

    def test_depth_is_runtime_authority(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn down(n:Int)->Int decreases n max_depth 3 = if n==0 then 0 else self(n-1);
        entry main:Int=down(4);
        '''
        compiled = compile_program_v2(source)
        inst = compiled.entry.instantiation
        contract = validate_recursive_v4(
            inst.body, compiled.types.table, inst.parameter_names, inst.parameter_type_ids, inst.return_type_id,
            measure_parameter=inst.measure_parameter, max_depth=inst.max_depth, maximum_steps=inst.maximum_steps,
        )
        with self.assertRaises(TevScriptError) as captured:
            evaluate_recursive_v4(contract, compiled.types.table, compiled.entry.arguments)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_RECURSIVE_DEPTH_EXHAUSTED")

    def test_non_decreasing_measure_is_rejected_by_kernel(self) -> None:
        source = '''
        script Demo version "2.0.0";
        recursive fn down(n:Int)->Int decreases n max_depth 8 = if n==0 then 0 else self(n-1);
        entry main:Int=down(2);
        '''
        compiled, inst, _contract = self._kernel_from_source(source)
        body = dict(inst.body)
        # Replace the sole SELF_CALL argument n-1 with n.
        def mutate(value):
            if isinstance(value, dict):
                if value.get("op") == "SELF_CALL":
                    value["arguments"][0] = {"op":"PARAM","name":"n","type":"Int"}
                    return True
                return any(mutate(v) for v in value.values())
            if isinstance(value, list): return any(mutate(v) for v in value)
            return False
        self.assertTrue(mutate(body))
        contract = validate_recursive_v4(
            body, compiled.types.table, inst.parameter_names, inst.parameter_type_ids, inst.return_type_id,
            measure_parameter="n", max_depth=8, maximum_steps=inst.maximum_steps,
        )
        with self.assertRaises(TevScriptError) as captured:
            evaluate_recursive_v4(contract, compiled.types.table, compiled.entry.arguments)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V4_RECURSIVE_MEASURE_NOT_DECREASING")


if __name__ == "__main__":
    unittest.main()
