from __future__ import annotations

import copy
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from tev_script import ScriptRuntime, TevScriptError, compile_bytes, compile_path
from tev_script.canonical import canonical_hash

ROOT = Path(__file__).resolve().parents[1]


class CompilerTests(unittest.TestCase):
    def test_player_compiles_deterministically(self) -> None:
        first = compile_path(ROOT / "examples" / "Player.tevs")
        second = compile_path(ROOT / "examples" / "Player.tevs")
        self.assertEqual(first.canonical_json, second.canonical_json)
        self.assertEqual(first.ir["semantic_hash"], second.ir["semantic_hash"])
        self.assertEqual(first.ir["schema"], "TEV_SCRIPT_PROGRAM_IR_V2")

    def test_decimal_is_exact_rational(self) -> None:
        source = b'''script Exact version "0.2.0";
entity E { state speed: Rat = 0.1; on start { return; } }
'''
        ir = compile_bytes("Exact.tevs", source).ir
        initial = ir["entities"][0]["states"][0]["initial"]
        self.assertEqual(initial, {"$rat": ["1", "10"]})

    def test_type_error_has_source_span(self) -> None:
        source = b'''script Bad version "0.2.0";
entity E { state health: Int = 10; on update { health = "bad"; } }
'''
        with self.assertRaises(TevScriptError) as captured:
            compile_bytes("Bad.tevs", source)
        self.assertEqual(captured.exception.diagnostic.code, "TEVS_COMPILE_TYPE_MISMATCH")
        self.assertEqual(captured.exception.diagnostic.span.path, "Bad.tevs")

    def test_unknown_capability_is_rejected(self) -> None:
        source = b'''script Bad version "0.2.0";
entity E { on start { call unity.magic(); } }
'''
        with self.assertRaisesRegex(TevScriptError, "TEVS_COMPILE_CALL_UNKNOWN"):
            compile_bytes("Bad.tevs", source)

    def test_tampered_semantic_hash_is_rejected(self) -> None:
        ir = compile_path(ROOT / "examples" / "Door.tevs").ir
        tampered = copy.deepcopy(ir)
        tampered["entities"][0]["states"][0]["initial"] = True
        with self.assertRaisesRegex(TevScriptError, "TEVS_RUNTIME_SEMANTIC_HASH"):
            ScriptRuntime(tampered)


    def test_source_path_does_not_change_compiled_bytes(self) -> None:
        source = (ROOT / "examples" / "Player.tevs").read_bytes()
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first_path = Path(first_dir) / "Player.tevs"
            second_path = Path(second_dir) / "Player.tevs"
            first_path.write_bytes(source)
            second_path.write_bytes(source)
            first = compile_path(first_path)
            second = compile_path(second_path)
        self.assertEqual(first.canonical_json, second.canonical_json)
        self.assertEqual(first.ir["debug_hash"], second.ir["debug_hash"])

    def test_branch_local_declaration_is_rejected(self) -> None:
        source = b'''script Scoped version "0.2.0";
entity E {
    state out: Int = 0;
    on process(flag: Bool) {
        if flag { let x: Int = 1; }
        out = x;
    }
}
'''
        with self.assertRaisesRegex(TevScriptError, "TEVS_COMPILE_LOCAL_CONTROL_SCOPE"):
            compile_bytes("Scoped.tevs", source)

    def test_parameter_cannot_shadow_state(self) -> None:
        source = b'''script Shadow version "0.2.0";
entity E {
    state value: Int = 0;
    on update(value: Int) { return; }
}
'''
        with self.assertRaisesRegex(TevScriptError, "TEVS_COMPILE_PARAMETER_SHADOWS_STATE"):
            compile_bytes("Shadow.tevs", source)

    def test_tampered_debug_hash_is_rejected(self) -> None:
        ir = compile_path(ROOT / "examples" / "Door.tevs").ir
        tampered = copy.deepcopy(ir)
        tampered["debug"]["source_path"] = "forged.tevs"
        with self.assertRaisesRegex(TevScriptError, "TEVS_RUNTIME_DEBUG_HASH"):
            ScriptRuntime(tampered)

    def test_enabled_boundary_is_rejected_even_with_valid_semantic_hash(self) -> None:
        ir = compile_path(ROOT / "examples" / "Door.tevs").ir
        tampered = copy.deepcopy(ir)
        tampered["boundary"]["dynamic_code"] = True
        semantic = {
            key: value
            for key, value in tampered.items()
            if key not in {"semantic_hash", "debug", "debug_hash"}
        }
        tampered["semantic_hash"] = canonical_hash(semantic)
        with self.assertRaisesRegex(TevScriptError, "TEVS_RUNTIME_BOUNDARY"):
            ScriptRuntime(tampered)

    def test_runtime_owns_a_deep_copy_of_ir(self) -> None:
        ir = compile_path(ROOT / "examples" / "Player.tevs").ir
        runtime = ScriptRuntime(ir)
        ir["entities"][0]["states"][0]["initial"] = {"$rat": ["999", "1"]}
        self.assertEqual(runtime.state("Player")["speed"], Fraction(5, 1))


class RuntimeTests(unittest.TestCase):
    def test_damage_mutates_state_and_emits_died(self) -> None:
        ir = compile_path(ROOT / "examples" / "Player.tevs").ir
        runtime = ScriptRuntime(ir)
        emitted = runtime.invoke("Player", "damage", 100)
        self.assertEqual(runtime.state("Player")["health"], 0)
        self.assertEqual([item.event_id for item in emitted], ["died"])

    def test_update_calls_movement_and_animation_capabilities(self) -> None:
        ir = compile_path(ROOT / "examples" / "Player.tevs").ir
        calls: list[tuple[str, object]] = []
        runtime = ScriptRuntime(
            ir,
            capabilities={
                "input.move2d": lambda: (Fraction(1), Fraction(0)),
                "motion.move2d": lambda value: calls.append(("move", value)),
                "animation.play": lambda value: calls.append(("animate", value)),
                "debug.log": lambda value: calls.append(("log", value)),
            },
        )
        runtime.invoke("Player", "update")
        self.assertEqual(calls[0], ("move", (Fraction(5), Fraction(0))))
        self.assertEqual(calls[1], ("animate", "Walk"))

    def test_start_logs(self) -> None:
        ir = compile_path(ROOT / "examples" / "Player.tevs").ir
        logs: list[str] = []
        runtime = ScriptRuntime(ir, {"debug.log": logs.append})
        runtime.invoke("Player", "start")
        self.assertEqual(logs, ["Player ready"])

    def test_missing_capability_fails_closed(self) -> None:
        ir = compile_path(ROOT / "examples" / "Player.tevs").ir
        runtime = ScriptRuntime(ir)
        with self.assertRaisesRegex(TevScriptError, "TEVS_RUNTIME_CAPABILITY_MISSING"):
            runtime.invoke("Player", "update")


if __name__ == "__main__":
    unittest.main()
