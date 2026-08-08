from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.linker_v1 import SourceInputV1, link_v1_sources
from tev_script.static_semantics_v1 import analyze_v1_static_semantics


def analyze(source: str):
    plan = link_v1_sources([SourceInputV1("stress.tevs", source.encode())])
    return analyze_v1_static_semantics(plan)


class V1HostStackIndependenceTests(unittest.TestCase):
    def test_one_thousand_function_chain_fails_normative_depth_not_recursionerror(self) -> None:
        functions = ['fn f0(x: Int) -> Int = x;']
        for index in range(1, 1000):
            functions.append(
                f'fn f{index}(x: Int) -> Int = f{index - 1}(x);'
            )
        source = (
            'script DeepFunctions version "1.0.0"; '
            + ' '.join(functions)
            + ' entity E { state out: Int = 0; on update { out = f999(1); } }'
        )
        try:
            analyze(source)
        except RecursionError as exc:  # pragma: no cover - this is the failure mode under test.
            self.fail(f"V1 function graph leaked Python recursion limit: {exc}")
        except TevScriptError as exc:
            self.assertEqual(exc.diagnostic.code, "TEVS_V1_PURITY_CALL_DEPTH")
        else:
            self.fail("1000-function chain must exceed the normative V1 call depth")

    def test_one_thousand_acyclic_record_dependencies_do_not_use_python_recursion(self) -> None:
        records = ['record R0 { value: Int; }']
        for index in range(1, 1000):
            records.append(f'record R{index} {{ child: R{index - 1}; }}')
        source = (
            'script DeepRecords version "1.0.0"; '
            + ' '.join(records)
            + ' entity E { on start { return; } }'
        )
        try:
            semantics = analyze(source)
        except RecursionError as exc:  # pragma: no cover
            self.fail(f"V1 record graph leaked Python recursion limit: {exc}")
        self.assertEqual(len(semantics.types.records), 1000)


if __name__ == "__main__":
    unittest.main()
