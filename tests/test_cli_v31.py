from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tev_script.cli_v31 import main


AUTHORITY = "a" * 64


PURE_PROCESS = f'''
process Demo version "3.1.0";
authority {AUTHORITY};
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.total.result End;
label End = halt;
entry Start;
'''

PURE_UNIT = 'script Calc version "2.0.0"; fn add1(x:Int)->Int=x+1; entry main:Int=add1(4);'

LOOP_PROCESS = f'''
process Loop version "3.1.0";
authority {AUTHORITY};
quantum_steps 1;
field actual = [];
label Start = jump Start;
entry Start;
'''


class CLIV31Tests(unittest.TestCase):
    def run_cli(self, argv: list[str]) -> tuple[int, dict, str]:
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(argv)
        payload = json.loads(out.getvalue()) if out.getvalue().strip() else {}
        return code, payload, err.getvalue()

    def test_descriptor_command_matches_v31_surface(self) -> None:
        code, payload, err = self.run_cli(["descriptor"])
        self.assertEqual(code, 0, err)
        self.assertEqual(payload["language_version"], "3.1.0")
        self.assertEqual(payload["profiles"], ["total_core"])

    def test_check_total_compiles_current_source_without_artifact_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = root / "program.tevs"
            unit = root / "calc.tevs"
            process.write_text(PURE_PROCESS, encoding="utf-8")
            unit.write_text(PURE_UNIT, encoding="utf-8")

            code, checked, err = self.run_cli([
                "check-total",
                str(process),
                "--unit", f"Calc={unit}",
            ])
            self.assertEqual(code, 0, err)
            self.assertEqual(checked["status"], "PASS")
            self.assertEqual(checked["language_version"], "3.1.0")
            self.assertEqual(checked["profile"], "total_core")
            self.assertEqual(list(root.glob("*.json")), [])

    def test_compile_validate_and_run_total_use_shared_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = root / "program.tevs"
            unit = root / "calc.tevs"
            artifact = root / "program.json"
            process.write_text(PURE_PROCESS, encoding="utf-8")
            unit.write_text(PURE_UNIT, encoding="utf-8")

            code, compiled, err = self.run_cli([
                "compile-total",
                str(process),
                "--unit", f"Calc={unit}",
                "--output", str(artifact),
            ])
            self.assertEqual(code, 0, err)
            self.assertEqual(compiled["status"], "PASS")
            self.assertEqual(compiled["language_version"], "3.1.0")
            self.assertTrue(artifact.is_file())

            code, validated, err = self.run_cli(["validate-total", str(artifact)])
            self.assertEqual(code, 0, err)
            self.assertEqual(validated["status"], "PASS")
            self.assertEqual(validated["program_ir_hash"], compiled["program_ir_hash"])

            code, result, err = self.run_cli(["run-total", str(artifact)])
            self.assertEqual(code, 0, err)
            self.assertEqual(result["status"], "HALTED")
            self.assertEqual(result["program_ir_hash"], compiled["program_ir_hash"])
            self.assertEqual(result["epochs_executed"], 1)

    def test_run_and_resume_total_chain_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = root / "loop.tevs"
            artifact = root / "loop.json"
            checkpoint = root / "checkpoint.json"
            checkpoint2 = root / "checkpoint2.json"
            process.write_text(LOOP_PROCESS, encoding="utf-8")

            code, compiled, err = self.run_cli([
                "compile-total", str(process), "--output", str(artifact)
            ])
            self.assertEqual(code, 0, err)

            code, first, err = self.run_cli([
                "run-total",
                str(artifact),
                "--checkpoint-output", str(checkpoint),
            ])
            self.assertEqual(code, 0, err)
            self.assertEqual(first["status"], "SUSPENDED")
            self.assertTrue(checkpoint.is_file())

            code, second, err = self.run_cli([
                "resume-total",
                str(artifact),
                "--checkpoint", str(checkpoint),
                "--checkpoint-output", str(checkpoint2),
            ])
            self.assertEqual(code, 0, err)
            self.assertEqual(second["status"], "SUSPENDED")
            self.assertEqual(second["last_epoch_index"], first["last_epoch_index"] + 1)
            self.assertNotEqual(second["continuation_hash"], first["continuation_hash"])
            self.assertTrue(checkpoint2.is_file())

    def test_compile_total_rejects_duplicate_unit_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            process = root / "program.tevs"
            unit = root / "calc.tevs"
            artifact = root / "program.json"
            process.write_text(PURE_PROCESS, encoding="utf-8")
            unit.write_text(PURE_UNIT, encoding="utf-8")
            code, _payload, err = self.run_cli([
                "compile-total", str(process),
                "--unit", f"Calc={unit}",
                "--unit", f"Calc={unit}",
                "--output", str(artifact),
            ])
            self.assertEqual(code, 2)
            diagnostic = json.loads(err)
            self.assertEqual(diagnostic["status"], "FAIL")

    def test_compile_total_supports_external_proof_admission_file(self) -> None:
        parser_help = io.StringIO()
        with redirect_stdout(parser_help):
            code = main(["compile-total", "--help"])
        self.assertEqual(code, 0)
        text = parser_help.getvalue()
        self.assertIn("--proof-admission", text)
        self.assertIn("--effect-input", text)


if __name__ == "__main__":
    unittest.main()