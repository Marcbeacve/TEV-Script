from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tev_script.canonical import canonical_json
from tev_script.pipeline_v1 import compile_v1_mapping_to_ir_v3
from tev_script.runtime_cli_v3 import main


SOURCE = b'''script RuntimeTool version "1.0.0";
entity E {
  state count: Int = 0;
  on tick {
    count = count + 1;
  }
}
'''


class V1RuntimeCliV3Tests(unittest.TestCase):
    def invoke(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def fixture(self, root: Path) -> tuple[Path, Path, dict[str, object]]:
        compiled = compile_v1_mapping_to_ir_v3({"RuntimeTool.tevs": SOURCE})
        ir = compiled.target.ir
        ir_path = root / "program.ir.json"
        scenario_path = root / "scenario.json"
        ir_path.write_text(compiled.target.canonical_json + "\n", encoding="utf-8")
        scenario = {
            "schema": "TEV_SCRIPT_IR_V3_SCENARIO_V1",
            "scenario_id": "runtime-cli-v3",
            "program_semantic_hash": ir["semantic_hash"],
            "source_semantic_hash": ir["source_semantic_hash"],
            "capabilities": [],
            "steps": [
                {
                    "entity_id": "E",
                    "event_id": "tick",
                    "arguments": [],
                }
            ],
        }
        scenario_path.write_text(canonical_json(scenario) + "\n", encoding="utf-8")
        return ir_path, scenario_path, ir

    def test_describe_validates_and_reports_compact_surface(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ir_path, _scenario_path, ir = self.fixture(Path(directory))
            code, stdout, stderr = self.invoke(["describe", str(ir_path)])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["schema"], "TEV_SCRIPT_IR_V3_DESCRIPTION_V1")
            self.assertEqual(result["program_id"], "RuntimeTool")
            self.assertEqual(result["semantic_hash"], ir["semantic_hash"])
            self.assertEqual(result["entity_count"], 1)
            self.assertEqual(result["state_count"], 1)
            self.assertEqual(result["handler_count"], 1)
            self.assertEqual(result["capability_ids"], [])
            self.assertIs(result["host_object_references"], False)

    def test_validate_can_pin_expected_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ir_path, _scenario_path, ir = self.fixture(Path(directory))
            code, stdout, stderr = self.invoke(
                ["validate", str(ir_path), "--source-hash", str(ir["source_semantic_hash"])]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["schema"], "TEV_SCRIPT_IR_V3_VALIDATION_RESULT_V1")
            self.assertEqual(result["status"], "PASS_CANDIDATE")

    def test_validate_rejects_wrong_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ir_path, _scenario_path, _ir = self.fixture(Path(directory))
            code, stdout, stderr = self.invoke(
                ["validate", str(ir_path), "--source-hash", "0" * 64]
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            result = json.loads(stderr)
            self.assertEqual(result["status"], "FAIL")

    def test_conformance_emits_receipt_and_compact_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ir_path, scenario_path, ir = self.fixture(root)
            receipt_path = root / "receipt.json"
            code, stdout, stderr = self.invoke(
                [
                    "conformance",
                    str(ir_path),
                    str(scenario_path),
                    "--output",
                    str(receipt_path),
                ]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["schema"], "TEV_SCRIPT_IR_V3_CONFORMANCE_RUN_RESULT_V1")
            self.assertEqual(result["program_semantic_hash"], ir["semantic_hash"])
            self.assertRegex(result["receipt_hash"], r"^[0-9a-f]{64}$")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["receipt_hash"], result["receipt_hash"])
            self.assertEqual(receipt["steps"][0]["event_id"], "tick")

    def test_conformance_print_receipt_uses_two_canonical_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ir_path, scenario_path, _ir = self.fixture(Path(directory))
            code, stdout, stderr = self.invoke(
                [
                    "conformance",
                    str(ir_path),
                    str(scenario_path),
                    "--print-receipt",
                ]
            )
            self.assertEqual(code, 0, stderr)
            lines = stdout.splitlines()
            self.assertEqual(len(lines), 2)
            summary = json.loads(lines[0])
            receipt = json.loads(lines[1])
            self.assertEqual(receipt["receipt_hash"], summary["receipt_hash"])
            self.assertEqual(lines[0], canonical_json(summary))
            self.assertEqual(lines[1], canonical_json(receipt))


if __name__ == "__main__":
    unittest.main()
