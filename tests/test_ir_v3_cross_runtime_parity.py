from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IrV3CrossRuntimeParityTests(unittest.TestCase):
    def test_python_javascript_csharp_receipts_are_byte_identical(self) -> None:
        missing = [name for name in ("node", "dotnet") if shutil.which(name) is None]
        if missing:
            self.skipTest(
                "cross-runtime parity is not claimed; missing tool(s): " + ", ".join(missing)
            )
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "validate_ir_v3_cross_runtime_parity.py"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            self.fail(
                "IR V3 cross-runtime parity failed:\n"
                + completed.stdout[-12000:]
                + "\n"
                + completed.stderr[-12000:]
            )
        self.assertIn(
            "TEV_SCRIPT_IR_V3_CROSS_RUNTIME_PARITY=PASS",
            completed.stdout,
        )
        self.assertIn(
            "TEV_SCRIPT_IR_V3_CSHARP_SELF_TEST=PASS",
            completed.stdout,
        )
        self.assertIn(
            "TEV_SCRIPT_IR_V3_NODE_TESTS=PASS",
            completed.stdout,
        )


if __name__ == "__main__":
    unittest.main()
