from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_program_v2 import compile_program_v2


class UnusedConcreteSignatureClosureV2Tests(unittest.TestCase):
    def assert_compile_rejects(self, source: str, code: str) -> None:
        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)
        self.assertEqual(captured.exception.diagnostic.code, code)

    def test_unused_concrete_collection_parameter_rejects_unit_storage(self) -> None:
        self.assert_compile_rejects(
            '''
            script Demo version "2.0.0";
            fn bad(m: Map<Unit,Int,4>) -> Int = 0;
            entry main: Int = 0;
            ''',
            "TEVS_V2_TYPE_NOT_STORABLE",
        )

    def test_unused_concrete_collection_return_rejects_unit_storage(self) -> None:
        self.assert_compile_rejects(
            '''
            script Demo version "2.0.0";
            fn bad() -> List<Unit,4> = [];
            entry main: Int = 0;
            ''',
            "TEVS_V2_TYPE_NOT_STORABLE",
        )

    def test_unused_generic_function_rejects_concrete_invalid_subtype(self) -> None:
        self.assert_compile_rejects(
            '''
            script Demo version "2.0.0";
            generic fn bad<T>(m: Map<Unit,T,4>) -> Int = 0;
            entry main: Int = 0;
            ''',
            "TEVS_V2_TYPE_NOT_STORABLE",
        )

    def test_unused_generic_record_rejects_concrete_invalid_field_subtype(self) -> None:
        self.assert_compile_rejects(
            '''
            script Demo version "2.0.0";
            generic record Bad<T> { items: Map<Unit,T,4>; }
            generic fn identity<T>(x:T)->T=x;
            entry main: Int = identity<Int>(1);
            ''',
            "TEVS_V2_TYPE_NOT_STORABLE",
        )

    def test_unused_concrete_signature_rejects_unknown_nominal_type(self) -> None:
        self.assert_compile_rejects(
            '''
            script Demo version "2.0.0";
            fn bad(x: Missing) -> Int = 0;
            entry main: Int = 0;
            ''',
            "TEVS_V2_GENERIC_NOMINAL",
        )

    def test_valid_unused_concrete_signature_is_validated_without_materialization(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn unused(m: Map<List<Int,4>,Int,4>) -> Int = 0;
        entry main: Int = 0;
        '''
        compiled = compile_program_v2(source)
        emitted = {item["type_id"] for item in compiled.type_descriptors}
        self.assertNotIn("List<Int,4>", emitted)
        self.assertNotIn("Map<List<Int,4>,Int,4>", emitted)


if __name__ == "__main__":
    unittest.main()
