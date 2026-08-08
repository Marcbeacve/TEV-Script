from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tev_script.canonical import canonical_json
from tev_script.compiler import compile_bytes
from tev_script.diagnostics import TevScriptError
from tev_script.lift_ir_v2_to_v3 import lift_ir_v2_to_v3
from tev_script.runtime_checkpoint_v2 import RuntimeCheckpointV2
from tev_script.runtime_v3 import ScriptRuntimeV3

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text()
)["valid_program"]


class RuntimeCheckpointV2RoundtripTests(unittest.TestCase):
    def test_capture_parse_restore_continue_is_exact_for_algebraic_state(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        runtime.invoke("E", "start")
        checkpoint = RuntimeCheckpointV2.capture(runtime)
        text = checkpoint.to_canonical_json()
        parsed = RuntimeCheckpointV2.parse(text)
        restored = parsed.restore_exact(copy.deepcopy(BASE))

        self.assertEqual(restored.canonical_state("E"), runtime.canonical_state("E"))
        self.assertEqual(parsed.checkpoint_hash, checkpoint.checkpoint_hash)

        left_events = runtime.invoke("E", "update")
        right_events = restored.invoke("E", "update")
        self.assertEqual(runtime.canonical_state("E"), restored.canonical_state("E"))
        self.assertEqual(
            [event.canonical_arguments(runtime.type_table) for event in left_events],
            [event.canonical_arguments(restored.type_table) for event in right_events],
        )

    def test_checkpoint_text_must_be_exact_canonical_json(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        checkpoint = RuntimeCheckpointV2.capture(runtime)
        pretty = json.dumps(checkpoint.to_object(), indent=2)
        with self.assertRaises(TevScriptError) as captured:
            RuntimeCheckpointV2.parse(pretty)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_CHECKPOINT_V2_CANONICAL")

    def test_checkpoint_schema_accepts_captured_object_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema dependency unavailable")
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        checkpoint = RuntimeCheckpointV2.capture(runtime)
        schema = json.loads(
            (ROOT / "schemas" / "tev_script_runtime_checkpoint_v2.schema.json").read_text()
        )
        jsonschema.Draft202012Validator(schema).validate(checkpoint.to_object())


class RuntimeCheckpointV2TamperTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime = ScriptRuntimeV3(copy.deepcopy(BASE))
        runtime.invoke("E", "start")
        self.checkpoint = RuntimeCheckpointV2.capture(runtime)

    def _parse_object(self, obj: dict) -> RuntimeCheckpointV2:
        return RuntimeCheckpointV2.parse(canonical_json(obj))

    def test_ir_semantic_hash_tamper_prevents_restore(self) -> None:
        obj = self.checkpoint.to_object()
        obj["semantic_hash"] = "0" * 64
        parsed = self._parse_object(obj)
        with self.assertRaises(TevScriptError) as captured:
            parsed.restore_exact(copy.deepcopy(BASE))
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_CHECKPOINT_V2_SEMANTIC_HASH")

    def test_state_type_tamper_prevents_restore(self) -> None:
        obj = self.checkpoint.to_object()
        obj["entities"][0]["state"]["pair"]["type"] = "Root.Kind"
        parsed = self._parse_object(obj)
        with self.assertRaises(TevScriptError) as captured:
            parsed.restore_exact(copy.deepcopy(BASE))
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_CHECKPOINT_V2_STATE_TYPE")

    def test_nested_record_type_tamper_is_rejected_by_v3_codec(self) -> None:
        obj = self.checkpoint.to_object()
        obj["entities"][0]["state"]["pair"]["value"]["$record"]["type"] = "Other.Pair"
        parsed = self._parse_object(obj)
        with self.assertRaises(TevScriptError) as captured:
            parsed.restore_exact(copy.deepcopy(BASE))
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_VALUE_INVALID")

    def test_source_semantic_hash_tamper_prevents_target_validation(self) -> None:
        obj = self.checkpoint.to_object()
        obj["source_semantic_hash"] = "2" * 64
        parsed = self._parse_object(obj)
        with self.assertRaises(TevScriptError) as captured:
            parsed.restore_exact(copy.deepcopy(BASE))
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_IR_V3_SOURCE_HASH")


class RuntimeCheckpointV2CompatibilityTests(unittest.TestCase):
    def test_lifted_v2_program_checkpoint_preserves_v2_source_provenance(self) -> None:
        source = b'''script LiftCheckpoint version "0.2.0";
entity E { state x: Int = 0; on update { x = x + 1; } }
'''
        v2 = compile_bytes("LiftCheckpoint.tevs", source)
        lifted = lift_ir_v2_to_v3(v2.ir)
        runtime = ScriptRuntimeV3(lifted.ir)
        runtime.invoke("E", "update")
        checkpoint = RuntimeCheckpointV2.capture(runtime)
        self.assertEqual(checkpoint.source_schema, "TEV_SCRIPT_PROGRAM_IR_V2")
        self.assertEqual(checkpoint.source_semantic_hash, v2.ir["semantic_hash"])
        restored = RuntimeCheckpointV2.parse(checkpoint.to_canonical_json()).restore_exact(lifted.ir)
        restored.invoke("E", "update")
        self.assertEqual(restored.state("E")["x"], 2)


if __name__ == "__main__":
    unittest.main()
