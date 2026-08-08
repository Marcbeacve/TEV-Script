from __future__ import annotations

import unittest

from tev_script.linked_program_v1 import emit_linked_program_v1
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics


class V1LinkedProgramUnitKindRegressionTests(unittest.TestCase):
    def test_multi_module_normalization_uses_unit_index_kind_contract(self) -> None:
        plan = link_v1_sources(
            [
                SourceInputV1(
                    "root.tevs",
                    b'script Root version "1.0.0"; import math; entity E { state out: Int = 0; on update { out = math.twice(out); } }',
                ),
                SourceInputV1(
                    "math.tevs",
                    b'module math version "1.0.0"; export fn twice(value: Int) -> Int = value * 2;',
                ),
            ]
        )
        module_unit = next(unit for unit in plan.units if unit.kind == "module")
        self.assertEqual(module_unit.unit_id, "math")
        self.assertFalse(hasattr(module_unit, "unit_kind"))

        semantics = analyze_v1_static_semantics(plan)
        bundle = emit_linked_program_v1(semantics)

        self.assertEqual(
            [module["module_id"] for module in bundle.program["modules"]],
            ["math"],
        )
        self.assertEqual(bundle.program["modules"][0]["version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
