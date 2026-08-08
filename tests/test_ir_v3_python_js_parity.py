from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IrV3PythonJavaScriptParityGateTests(unittest.TestCase):
    def test_python_and_javascript_emit_identical_canonical_receipt_bytes(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is unavailable; cross-runtime parity is not claimed")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "validate_ir_v3_python_js_parity.py")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            self.fail(
                "Python/JavaScript IR V3 parity gate failed:\n"
                + completed.stdout[-6000:]
                + "\n"
                + completed.stderr[-6000:]
            )
        self.assertIn("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=PASS", completed.stdout)
        receipt_line = next(
            line
            for line in completed.stdout.splitlines()
            if line.startswith("TEV_SCRIPT_IR_V3_PYTHON_JS_RECEIPT_HASH=")
        )
        receipt_hash = receipt_line.split("=", 1)[1]
        self.assertRegex(receipt_hash, r"^[0-9a-f]{64}$")

    def test_node_conformance_module_imports_without_package_export_dependency(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable")
        script = (
            "import('./javascript/src/ir-v3-conformance.mjs')"
            ".then(m=>{if(typeof m.runIrV3Conformance!=='function')process.exit(3)})"
        )
        completed = subprocess.run(
            [node, "--input-type=module", "--eval", script],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=completed.stdout + "\n" + completed.stderr,
        )


if __name__ == "__main__":
    unittest.main()
