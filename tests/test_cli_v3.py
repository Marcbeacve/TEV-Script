from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v3 import main
from tev_script.descriptor_v3 import v3_descriptor, verify_v3_descriptor
from tev_script.json_io import load_strict_json
from tev_script.program_ir_v5_semantic import validate_semantic_process_program

SOURCE = '''
process Door version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["closed"];
fact opened = door.state ["open"];
field actual = [closed];
transform open effects 1111111111111111111111111111111111111111111111111111111111111111 resources 2222222222222222222222222222222222222222222222222222222222222222 remove [closed] add [opened];
label start = apply open done;
label done = halt;
entry start;
'''

CYCLE = '''
process Cycle version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 2;
fact alive = proc.state ["alive"];
field process = [alive];
label loop = jump loop;
entry loop;
'''


class DescriptorV3Tests(unittest.TestCase):
    def test_descriptor_is_self_hashed_non_promotional(self) -> None:
        value = v3_descriptor()
        self.assertEqual(value["language_version"], "3.0.0")
        self.assertFalse(value["stable"])
        self.assertFalse(value["promotion_authority"])
        self.assertIn("semantic_process", value["source_profiles"])
        self.assertTrue(verify_v3_descriptor(value))
        tampered = dict(value)
        tampered["stable"] = True
        self.assertFalse(verify_v3_descriptor(tampered))


class CliV3Tests(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out = io.StringIO(); err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_describe_and_check(self) -> None:
        code, out, err = self._run(["describe"])
        self.assertEqual(code, 0, err)
        self.assertTrue(verify_v3_descriptor(json.loads(out)))
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "door.tevs"
            source.write_text(SOURCE, encoding="utf-8")
            code, out, err = self._run(["check", str(source)])
            self.assertEqual(code, 0, err)
            payload = json.loads(out)
            self.assertEqual(payload["status"], "PASS_CANDIDATE")
            self.assertEqual(payload["language_version"], "3.0.0")
            self.assertEqual(payload["program_ir_schema"], "TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1")

    def test_compile_writes_valid_ir_v5(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "door.tevs"; target = Path(directory) / "door.ir.json"
            source.write_text(SOURCE, encoding="utf-8")
            code, out, err = self._run(["compile", str(source), "-o", str(target)])
            self.assertEqual(code, 0, err)
            program = validate_semantic_process_program(load_strict_json(target))
            self.assertEqual(program.language_version, "3.0.0")
            self.assertEqual(json.loads(out)["program_ir_hash"], program.program_hash)

    def test_run_halts_and_cycle_remains_cli_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for stem, text in (("door", SOURCE), ("cycle", CYCLE)):
                src = root / f"{stem}.tevs"; ir = root / f"{stem}.json"; cp = root / f"{stem}.checkpoint.json"
                src.write_text(text, encoding="utf-8")
                self.assertEqual(self._run(["compile", str(src), "-o", str(ir)])[0], 0)
                code, out, err = self._run(["run", str(ir), "--epochs", "2", "--checkpoint-output", str(cp)])
                self.assertEqual(code, 0, err)
                payload = json.loads(out)
                if stem == "door":
                    self.assertEqual(payload["status"], "HALTED")
                    self.assertEqual(payload["epochs_executed"], 1)
                else:
                    self.assertEqual(payload["status"], "SUSPENDED")
                    self.assertEqual(payload["epochs_executed"], 2)
                self.assertTrue(cp.is_file())

    def test_invalid_source_and_unbounded_epoch_request_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bad.tevs"
            source.write_text(SOURCE.replace('version "3.0.0"', 'version "9.0.0"'), encoding="utf-8")
            code, _out, err = self._run(["check", str(source)])
            self.assertEqual(code, 2)
            self.assertIn("TEVS_V3_SOURCE_VERSION", err)
            source.write_text(SOURCE, encoding="utf-8")
            target = Path(directory) / "p.json"
            self.assertEqual(self._run(["compile", str(source), "-o", str(target)])[0], 0)
            code, _out, err = self._run(["run", str(target), "--epochs", "0"])
            self.assertEqual(code, 2)
            self.assertIn("epochs", err)


if __name__ == "__main__":
    unittest.main()
