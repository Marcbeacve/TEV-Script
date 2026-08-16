from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import unittest

from tev_script.canonical import canonical_json
from tev_script.program_ir_v5_semantic import checkpoint_to_object, initial_process_checkpoint, program_to_object
from tev_script.runtime_v5_semantic import run_semantic_quantum
from tev_script.source_semantic_process_v3 import compile_semantic_process_v3

ROOT = Path(__file__).resolve().parents[1]
JS_RUNTIME = ROOT / "runtime_js_v3" / "runtime_v5_semantic.mjs"

PROFILE_SOURCE = '''
process UnicodeDoor version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["café","😀"];
fact opened = door.state ["ouvert","😀"];
field theory = [closed];
transform realize effects 1111111111111111111111111111111111111111111111111111111111111111 resources 2222222222222222222222222222222222222222222222222222222222222222 profile world remove [closed] add [opened];
label start = apply realize done;
label done = halt;
entry start;
'''

CYCLE_SOURCE = '''
process Cycle version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 3;
fact alive = proc.state ["alive"];
field process = [alive];
label loop = jump loop;
entry loop;
'''


class JavaScriptRuntimeV5ParityTests(unittest.TestCase):
    maxDiff = None

    def _js(self, program, checkpoint):
        request = {"program": program_to_object(program), "checkpoint": checkpoint_to_object(checkpoint, program)}
        completed = subprocess.run(
            ("node", str(JS_RUNTIME)), input=canonical_json(request), text=True,
            capture_output=True, cwd=ROOT, timeout=30, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    @staticmethod
    def _python_bytes(result) -> str:
        return canonical_json(asdict(result)) + "\n"

    def test_unicode_profile_transition_is_byte_identical(self) -> None:
        program = compile_semantic_process_v3(PROFILE_SOURCE)
        checkpoint = initial_process_checkpoint(program)
        expected = run_semantic_quantum(program, checkpoint)
        self.assertEqual(expected.field.profile, "world")
        self.assertEqual(self._js(program, checkpoint), self._python_bytes(expected))

    def test_two_epoch_cycle_matches_continuation_and_checkpoint_bytes(self) -> None:
        program = compile_semantic_process_v3(CYCLE_SOURCE)
        checkpoint = initial_process_checkpoint(program)
        first = run_semantic_quantum(program, checkpoint)
        js_first_text = self._js(program, checkpoint)
        self.assertEqual(js_first_text, self._python_bytes(first))
        js_first = json.loads(js_first_text)
        second = run_semantic_quantum(program, first.next_checkpoint)
        completed = subprocess.run(
            ("node", str(JS_RUNTIME)),
            input=canonical_json({"program": program_to_object(program), "checkpoint": js_first["next_checkpoint"]}),
            text=True, capture_output=True, cwd=ROOT, timeout=30, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, self._python_bytes(second))
        self.assertEqual(json.loads(completed.stdout)["continuation"]["previous_continuation_hash"], first.continuation.continuation_hash)

    def test_object_keys_with_proto_spelling_remain_plain_canonical_data(self) -> None:
        source = r'''
process ProtoData version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 1;
fact alive = proc.state [{"__proto__":{"x":1},"constructor":"data"}];
field process = [alive];
label done = halt;
entry done;
'''
        program = compile_semantic_process_v3(source)
        checkpoint = initial_process_checkpoint(program)
        expected = run_semantic_quantum(program, checkpoint)
        self.assertEqual(self._js(program, checkpoint), self._python_bytes(expected))

    def test_tampered_program_hash_fails_before_execution(self) -> None:
        program = compile_semantic_process_v3(CYCLE_SOURCE)
        checkpoint = initial_process_checkpoint(program)
        raw = program_to_object(program); raw["program_hash"] = "0" * 64
        completed = subprocess.run(
            ("node", str(JS_RUNTIME)),
            input=canonical_json({"program": raw, "checkpoint": checkpoint_to_object(checkpoint, program)}),
            text=True, capture_output=True, cwd=ROOT, timeout=30, check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("PROGRAM_HASH", completed.stderr)

    def test_duplicate_json_member_is_rejected(self) -> None:
        completed = subprocess.run(
            ("node", str(JS_RUNTIME)), input='{"program":null,"program":null,"checkpoint":null}',
            text=True, capture_output=True, cwd=ROOT, timeout=30, check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("JSON_DUPLICATE_KEY", completed.stderr)


if __name__ == "__main__":
    unittest.main()
