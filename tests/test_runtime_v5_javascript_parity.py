from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tev_script.program_ir_v5_semantic import (
    checkpoint_to_object,
    initial_process_checkpoint,
    program_to_object,
)
from tev_script.runtime_v5_semantic import run_semantic_quantum
from tev_script.source_semantic_process_v3 import compile_semantic_process_v3

ROOT = Path(__file__).resolve().parents[1]
JS_RUNTIME = ROOT / "runtime-js" / "v3" / "runtime_v5_semantic.mjs"

HALT_SOURCE = '''
process Halt version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 2;
fact alive = proc.state ["alive"];
field process = [alive];
label done = halt;
entry done;
'''

APPLY_SOURCE = '''
process Door version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["closed"];
fact opened = door.state ["open"];
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


def _canonicalize(value):
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))


class JavaScriptRuntimeV5ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        node = shutil.which("node")
        if node is None:
            raise AssertionError("Node.js is a required V3 independent-runtime certification dependency")
        cls.node = node
        if not JS_RUNTIME.is_file():
            raise AssertionError(f"missing independent V3 JavaScript runtime: {JS_RUNTIME}")

    def _run_node(self, program, checkpoint=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program_path = root / "program.json"
            program_path.write_text(
                json.dumps(program_to_object(program), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
                encoding="utf-8",
            )
            argv = [self.node, str(JS_RUNTIME), "--program", str(program_path)]
            if checkpoint is not None:
                checkpoint_path = root / "checkpoint.json"
                checkpoint_path.write_text(
                    json.dumps(checkpoint_to_object(checkpoint, program), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
                    encoding="utf-8",
                )
                argv.extend(("--checkpoint", str(checkpoint_path)))
            completed = subprocess.run(argv, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(completed.stdout)

    def _assert_parity(self, source: str) -> None:
        program = compile_semantic_process_v3(source)
        checkpoint = initial_process_checkpoint(program)
        python_result = run_semantic_quantum(program, checkpoint)
        js_result = self._run_node(program, checkpoint)
        self.assertEqual(js_result, _canonicalize(asdict(python_result)))

    def test_halt_quantum_matches_python_exactly(self) -> None:
        self._assert_parity(HALT_SOURCE)

    def test_apply_profile_transition_matches_python_exactly(self) -> None:
        program = compile_semantic_process_v3(APPLY_SOURCE)
        checkpoint = initial_process_checkpoint(program)
        python_result = run_semantic_quantum(program, checkpoint)
        js_result = self._run_node(program, checkpoint)
        self.assertEqual(js_result, _canonicalize(asdict(python_result)))
        self.assertEqual(js_result["field"]["profile"], "world")
        self.assertEqual(js_result["steps_used"], 2)

    def test_two_suspended_epochs_preserve_exact_continuation_chain(self) -> None:
        program = compile_semantic_process_v3(CYCLE_SOURCE)
        checkpoint0 = initial_process_checkpoint(program)
        python0 = run_semantic_quantum(program, checkpoint0)
        js0 = self._run_node(program, checkpoint0)
        self.assertEqual(js0, _canonicalize(asdict(python0)))
        python1 = run_semantic_quantum(program, python0.next_checkpoint)
        js1 = self._run_node(program, python0.next_checkpoint)
        self.assertEqual(js1, _canonicalize(asdict(python1)))
        self.assertEqual(js1["continuation"]["previous_continuation_hash"], js0["continuation"]["continuation_hash"])

    def _run_raw_program(self, raw: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "program.json"
            path.write_text(raw, encoding="utf-8")
            return subprocess.run(
                [self.node, str(JS_RUNTIME), "--program", str(path)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )

    def test_strict_json_and_tamper_negatives_fail_before_execution(self) -> None:
        program = compile_semantic_process_v3(HALT_SOURCE)
        canonical = json.dumps(program_to_object(program), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        duplicate = canonical.replace("{", '{"schema":"duplicate",', 1)
        floating = canonical.replace('"entry_pc":0', '"entry_pc":0.0')
        negative_zero = canonical.replace('"entry_pc":0', '"entry_pc":-0')
        unsafe = canonical.replace('"entry_pc":0', '"entry_pc":9007199254740992')
        tampered = canonical.replace(program.program_hash, "0" * 64, 1)
        for raw, marker in (
            (duplicate, "TEVS_JS_JSON_DUPLICATE_KEY"),
            (floating, "TEVS_JS_JSON_FLOAT"),
            (negative_zero, "TEVS_JS_JSON_NEGATIVE_ZERO"),
            (unsafe, "TEVS_JS_JSON_NUMBER_RANGE"),
            (tampered, "TEVS_JS_PROGRAM_HASH"),
        ):
            with self.subTest(marker=marker):
                completed = self._run_raw_program(raw)
                self.assertEqual(completed.returncode, 2)
                self.assertIn(marker, completed.stderr)


if __name__ == "__main__":
    unittest.main()
