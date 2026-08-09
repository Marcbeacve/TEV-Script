from __future__ import annotations

import copy
import json
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script.canonical import canonical_hash
from tev_script.diagnostics import TevScriptError
from tev_script.ir_v3_values import RecordValueV3, VariantValueV3
from tev_script.runtime_v3 import ScriptRuntimeV3

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text()
)["valid_program"]


def rehash(program: dict) -> dict:
    result = copy.deepcopy(program)
    result["debug_hash"] = canonical_hash(result["debug"])
    semantic = {
        key: value
        for key, value in result.items()
        if key not in {"semantic_hash", "debug", "debug_hash"}
    }
    result["semantic_hash"] = canonical_hash(semantic)
    return result


class IrV3RuntimeStateTests(unittest.TestCase):
    def test_new_algebraic_opcodes_mutate_state_deterministically(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE), expected_source_semantic_hash="1" * 64)
        emitted = runtime.invoke("E", "start")
        self.assertEqual(emitted, ())
        state = runtime.state("E")
        self.assertEqual(state["count"], 7)
        self.assertEqual(
            state["pair"],
            RecordValueV3("Root.Pair", (("a", 2), ("b", Fraction(3, 1)))),
        )
        self.assertEqual(state["kind"], VariantValueV3("Root.Kind", "B"))
        self.assertEqual(state["opt"], VariantValueV3("Option<Int>", "Some", 7))
        self.assertEqual(
            state["result"],
            VariantValueV3("Result<Int,Text>", "Err", "bad"),
        )

    def test_canonical_state_uses_portable_recursive_encoding(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        runtime.invoke("E", "start")
        state = runtime.canonical_state("E")
        self.assertEqual(state["count"], {"$int": "7"})
        self.assertEqual(
            state["pair"],
            {
                "$record": {
                    "type": "Root.Pair",
                    "fields": [
                        {"name": "a", "value": {"$int": "2"}},
                        {"name": "b", "value": {"$rat": ["3", "1"]}},
                    ],
                }
            },
        )
        self.assertEqual(
            state["opt"],
            {"$option": {"type": "Option<Int>", "variant": "Some", "value": {"$int": "7"}}},
        )


class IrV3RuntimeCapabilityTests(unittest.TestCase):
    def test_capability_can_return_canonical_record_and_effect_receives_semantic_record(self) -> None:
        observed: list[RecordValueV3] = []

        def read_pair():
            return {
                "$record": {
                    "type": "Root.Pair",
                    "fields": [
                        {"name": "a", "value": {"$int": "10"}},
                        {"name": "b", "value": {"$rat": ["1", "2"]}},
                    ],
                }
            }

        def write_pair(value):
            observed.append(value)

        runtime = ScriptRuntimeV3(
            copy.deepcopy(BASE),
            {"world.read": read_pair, "sink.write": write_pair},
        )
        runtime.invoke("E", "pulse")
        pair = runtime.state("E")["pair"]
        self.assertEqual(
            pair,
            RecordValueV3("Root.Pair", (("a", 10), ("b", Fraction(1, 2)))),
        )
        self.assertEqual(observed, [pair])

    def test_capability_composite_type_tampering_fails_before_state_mutation(self) -> None:
        before = BASE["entities"][0]["states"][3]["initial"]

        def bad_read():
            value = copy.deepcopy(before)
            value["$record"]["type"] = "Other.Pair"
            return value

        runtime = ScriptRuntimeV3(copy.deepcopy(BASE), {"world.read": bad_read})
        with self.assertRaises(TevScriptError) as captured:
            runtime.invoke("E", "pulse")
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_VALUE_INVALID")
        self.assertEqual(runtime.canonical_state("E")["pair"], before)


class IrV3RuntimeEventTests(unittest.TestCase):
    def test_emitted_algebraic_event_has_type_and_canonical_value_witness(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        emitted = runtime.invoke("E", "update")
        self.assertEqual(len(emitted), 1)
        event = emitted[0]
        self.assertEqual(event.event_id, "changed")
        self.assertEqual(event.argument_types, ("Root.Pair", "Option<Int>"))
        encoded = event.canonical_arguments(runtime.type_table)
        self.assertEqual(encoded[0], BASE["entities"][0]["states"][3]["initial"])
        self.assertEqual(encoded[1], BASE["entities"][0]["states"][2]["initial"])


class IrV3RuntimeFaultTests(unittest.TestCase):
    def test_wrong_variant_unwrap_is_deterministic_runtime_fault(self) -> None:
        program = copy.deepcopy(BASE)
        start = program["entities"][0]["handlers"][1]
        start["locals"] = []
        start["instructions"] = [
            {"op":"LOAD_STATE","name":"opt","type":"Option<Int>"},
            {"op":"LOAD_VARIANT_PAYLOAD","type":"Option<Int>","variant":"Some","payload_type":"Int"},
            {"op":"STORE_STATE","name":"count","type":"Int"},
            {"op":"RETURN"},
        ]
        start["instruction_budget"] = 4
        runtime = ScriptRuntimeV3(rehash(program))
        with self.assertRaises(TevScriptError) as captured:
            runtime.invoke("E", "start")
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_VARIANT_UNWRAP")
        self.assertEqual(runtime.state("E")["count"], 0)

    def test_missing_capability_fails_closed(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        with self.assertRaises(TevScriptError) as captured:
            runtime.invoke("E", "pulse")
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_CAPABILITY_MISSING")

    def test_noncanonical_invocation_identifier_is_rejected(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        with self.assertRaises(TevScriptError) as captured:
            runtime.invoke("E", "bad.event")
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_INVOCATION_ID")


if __name__ == "__main__":
    unittest.main()
