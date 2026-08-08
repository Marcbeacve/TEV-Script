from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tev_script.canonical import canonical_hash, canonical_json
from tev_script.diagnostics import TevScriptError
from tev_script.ir_v3_conformance import run_ir_v3_conformance

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text()
)
SCENARIO = json.loads(
    (ROOT / "conformance" / "ir-v3-portable.scenario.json").read_text()
)
PROGRAM = CASES["valid_program"]


class IrV3ConformanceReceiptTests(unittest.TestCase):
    def test_portable_scenario_produces_self_consistent_receipt(self) -> None:
        bundle = run_ir_v3_conformance(copy.deepcopy(PROGRAM), copy.deepcopy(SCENARIO))
        receipt = bundle.receipt
        self.assertEqual(receipt["schema"], "TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1")
        self.assertEqual(receipt["scenario_id"], "algebraic_roundtrip")
        self.assertEqual(receipt["scenario_hash"], canonical_hash(SCENARIO))
        self.assertEqual(receipt["program_semantic_hash"], PROGRAM["semantic_hash"])
        self.assertEqual(receipt["source_semantic_hash"], "1" * 64)
        body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
        self.assertEqual(receipt["receipt_hash"], canonical_hash(body))
        self.assertEqual(bundle.canonical_json, canonical_json(receipt))
        self.assertEqual(bundle.receipt_hash, receipt["receipt_hash"])

    def test_receipt_records_intermediate_state_and_typed_event_witnesses(self) -> None:
        receipt = run_ir_v3_conformance(
            copy.deepcopy(PROGRAM), copy.deepcopy(SCENARIO)
        ).receipt
        steps = receipt["steps"]
        self.assertEqual([step["event_id"] for step in steps], ["start", "update", "pulse"])
        self.assertEqual(steps[0]["state_hash"], steps[1]["state_hash"])
        self.assertNotEqual(steps[1]["state_hash"], steps[2]["state_hash"])

        self.assertEqual(steps[0]["emitted"], [])
        self.assertEqual(len(steps[1]["emitted"]), 1)
        changed = steps[1]["emitted"][0]
        self.assertEqual((changed["entity_id"], changed["event_id"]), ("E", "changed"))
        self.assertEqual(
            [item["type"] for item in changed["arguments"]],
            ["Root.Pair", "Option<Int>"],
        )
        self.assertEqual(
            changed["arguments"][0]["value"],
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
            changed["arguments"][1]["value"],
            {
                "$option": {
                    "type": "Option<Int>",
                    "variant": "Some",
                    "value": {"$int": "7"},
                }
            },
        )

    def test_capability_transcript_uses_execution_order_not_script_declaration_order(self) -> None:
        receipt = run_ir_v3_conformance(
            copy.deepcopy(PROGRAM), copy.deepcopy(SCENARIO)
        ).receipt
        transcript = receipt["capability_calls"]
        self.assertEqual(
            [item["capability_id"] for item in transcript],
            ["world.read", "sink.write"],
        )
        self.assertEqual([item["index"] for item in transcript], [0, 1])
        self.assertEqual(transcript[0]["arguments"], [])
        self.assertEqual(transcript[0]["return"]["type"], "Root.Pair")
        self.assertEqual(transcript[1]["arguments"], [transcript[0]["return"]])
        self.assertNotIn("return", transcript[1])

    def test_final_state_contains_scripted_capability_record(self) -> None:
        receipt = run_ir_v3_conformance(
            copy.deepcopy(PROGRAM), copy.deepcopy(SCENARIO)
        ).receipt
        final_entity = receipt["final_state"][0]
        self.assertEqual(final_entity["entity_id"], "E")
        pair = final_entity["state"]["pair"]
        self.assertEqual(pair["type"], "Root.Pair")
        self.assertEqual(
            pair["value"],
            SCENARIO["capabilities"][1]["calls"][0]["return"]["value"],
        )
        self.assertEqual(
            receipt["final_state_hash"],
            canonical_hash(receipt["final_state"]),
        )

    def test_scenario_and_receipt_schemas_accept_outputs_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency unavailable")
        scenario_schema = json.loads(
            (ROOT / "schemas" / "tev_script_ir_v3_scenario_v1.schema.json").read_text()
        )
        receipt_schema = json.loads(
            (ROOT / "schemas" / "tev_script_ir_v3_conformance_receipt_v1.schema.json").read_text()
        )
        bundle = run_ir_v3_conformance(copy.deepcopy(PROGRAM), copy.deepcopy(SCENARIO))
        jsonschema.Draft202012Validator(scenario_schema).validate(SCENARIO)
        jsonschema.Draft202012Validator(receipt_schema).validate(bundle.receipt)


class IrV3ConformanceNegativeTests(unittest.TestCase):
    def test_scenario_program_hash_tamper_fails_before_execution(self) -> None:
        scenario = copy.deepcopy(SCENARIO)
        scenario["program_semantic_hash"] = "0" * 64
        with self.assertRaises(TevScriptError) as captured:
            run_ir_v3_conformance(copy.deepcopy(PROGRAM), scenario)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_IR_V3_CONFORMANCE_PROGRAM_HASH",
        )

    def test_scripted_capability_argument_mismatch_detects_execution_divergence(self) -> None:
        scenario = copy.deepcopy(SCENARIO)
        scenario["capabilities"][0]["calls"][0]["arguments"][0]["value"]["$record"]["fields"][0]["value"] = {"$int": "99"}
        with self.assertRaises(TevScriptError) as captured:
            run_ir_v3_conformance(copy.deepcopy(PROGRAM), scenario)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ARGUMENTS",
        )

    def test_extra_scripted_capability_call_fails_after_steps(self) -> None:
        scenario = copy.deepcopy(SCENARIO)
        scenario["capabilities"][1]["calls"].append(
            copy.deepcopy(scenario["capabilities"][1]["calls"][0])
        )
        with self.assertRaises(TevScriptError) as captured:
            run_ir_v3_conformance(copy.deepcopy(PROGRAM), scenario)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_UNDERFLOW",
        )

    def test_missing_scripted_capability_call_fails_when_runtime_invokes_it(self) -> None:
        scenario = copy.deepcopy(SCENARIO)
        scenario["capabilities"][1]["calls"].clear()
        with self.assertRaises(TevScriptError) as captured:
            run_ir_v3_conformance(copy.deepcopy(PROGRAM), scenario)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_IR_V3_CONFORMANCE_CAPABILITY_CALL_OVERFLOW",
        )

    def test_capability_scripts_must_be_canonically_sorted(self) -> None:
        scenario = copy.deepcopy(SCENARIO)
        scenario["capabilities"].reverse()
        with self.assertRaises(TevScriptError) as captured:
            run_ir_v3_conformance(copy.deepcopy(PROGRAM), scenario)
        self.assertEqual(
            captured.exception.diagnostic.code,
            "TEVS_IR_V3_CONFORMANCE_CAPABILITY_ORDER",
        )


if __name__ == "__main__":
    unittest.main()
