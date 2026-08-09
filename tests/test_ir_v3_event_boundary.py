from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tev_script.diagnostics import TevScriptError
from tev_script.runtime_v3 import ScriptRuntimeV3

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text()
)["valid_program"]


class IrV3UnhandledEventBoundaryTests(unittest.TestCase):
    def test_unhandled_zero_argument_event_is_observable_without_host_type_inference(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        emitted = runtime.invoke("E", "external")
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].event_id, "external")
        self.assertEqual(emitted[0].argument_types, ())
        self.assertEqual(emitted[0].arguments, ())

    def test_unhandled_event_with_unknown_argument_signature_fails_closed(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        with self.assertRaises(TevScriptError) as captured:
            runtime.invoke("E", "external", 1)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_IR_V3_EVENT_SIGNATURE_UNKNOWN",
        )

    def test_unhandled_declared_event_uses_declared_algebraic_signature(self) -> None:
        program = copy.deepcopy(BASE)
        # `changed` is declared in emitted_events and has no local handler.
        runtime = ScriptRuntimeV3(program)
        pair = program["entities"][0]["states"][3]["initial"]
        option = program["entities"][0]["states"][2]["initial"]
        emitted = runtime.invoke("E", "changed", pair, option)
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0].argument_types, ("Root.Pair", "Option<Int>"))
        self.assertEqual(
            emitted[0].canonical_arguments(runtime.type_table),
            (pair, option),
        )


if __name__ == "__main__":
    unittest.main()
