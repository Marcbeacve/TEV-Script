from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.source_program_v2 import compile_program_v2


class UnusedConcreteSignatureClosureV2Tests(unittest.TestCase):
    def test_unused_concrete_collection_signature_rejects_unit_storage(self) -> None:
        source = '''
        script Demo version "2.0.0";
        fn bad(m: Map<Unit,Int,4>) -> Int = 0;
        entry main: Int = 0;
        '''

        with self.assertRaises(TevScriptError) as captured:
            compile_program_v2(source)

        self.assertEqual(captured.exception.diagnostic.code, "TEVS_V2_TYPE_NOT_STORABLE")


if __name__ == "__main__":
    unittest.main()
