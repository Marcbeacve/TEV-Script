from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.cli_v1 import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "v1"


class V1CliTargetTests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_auto_selects_ir_v2_for_erasable_program(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.json"
            code, stdout, stderr = self.invoke(
                [
                    "compile",
                    str(EXAMPLES / "ErasableToIrV2.tevs"),
                    "--target",
                    "auto",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["target_ir_schema"], "TEV_SCRIPT_PROGRAM_IR_V2")
            self.assertEqual(json.loads(output.read_text())["schema"], "TEV_SCRIPT_PROGRAM_IR_V2")

    def test_auto_selects_ir_v3_for_algebraic_program(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.json"
            code, stdout, stderr = self.invoke(
                [
                    "compile",
                    str(EXAMPLES / "AlgebraicCapability.tevs"),
                    "--target",
                    "auto",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["target_ir_schema"], "TEV_SCRIPT_PROGRAM_IR_V3")
            self.assertEqual(json.loads(output.read_text())["schema"], "TEV_SCRIPT_PROGRAM_IR_V3")

    def test_explicit_ir_v3_compiles_erasable_program_without_changing_source_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.json"
            code, stdout, stderr = self.invoke(
                [
                    "compile",
                    str(EXAMPLES / "ErasableToIrV2.tevs"),
                    "--target",
                    "irv3",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["target_ir_schema"], "TEV_SCRIPT_PROGRAM_IR_V3")
            self.assertRegex(result["linked_semantic_hash"], r"^[0-9a-f]{64}$")
            self.assertRegex(result["target_ir_semantic_hash"], r"^[0-9a-f]{64}$")

    def test_forcing_ir_v2_on_algebraic_program_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "program.json"
            code, stdout, stderr = self.invoke(
                [
                    "compile",
                    str(EXAMPLES / "AlgebraicCapability.tevs"),
                    "--target",
                    "irv2",
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            diagnostic = json.loads(stderr)
            self.assertEqual(diagnostic["status"], "FAIL")
            self.assertFalse(output.exists())

    def test_multifile_check_accepts_explicit_finite_source_set(self) -> None:
        sources = [
            str(EXAMPLES / "ecosystem" / "main.tevs"),
            str(EXAMPLES / "ecosystem" / "model.tevs"),
            str(EXAMPLES / "ecosystem" / "rules.tevs"),
            str(EXAMPLES / "ecosystem" / "storage.tevs"),
        ]
        code, stdout, stderr = self.invoke(["check", *sources])
        self.assertEqual(code, 0, stderr)
        result = json.loads(stdout)
        self.assertEqual(result["program_id"], "Ecosystem")
        self.assertEqual(result["default_target_ir"], "TEV_SCRIPT_PROGRAM_IR_V3")
        self.assertFalse(result["ir_v2_lowerable"])


if __name__ == "__main__":
    unittest.main()
