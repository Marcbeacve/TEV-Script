from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class BrowserWitnessAuthorityTests(unittest.TestCase):
    def _assert_managed_authority(
        self,
        *,
        js_relative: str,
        cs_relative: str,
        report_name: str,
        missing_report_marker: str,
    ) -> None:
        js = (ROOT / js_relative).read_text(encoding="utf-8")
        cs = (ROOT / cs_relative).read_text(encoding="utf-8")

        self.assertIn(f"globalThis.{report_name} =", js)
        self.assertIn("managedReportReceived", js)
        self.assertIn(missing_report_marker, js)
        self.assertEqual(js.count("emitWitness('PASS'"), 1)

        append_start = js.index("function append(value)")
        report_start = js.index(f"globalThis.{report_name} =")
        console_start = js.index("console.log =", report_start)
        append_block = js[append_start:report_start]
        report_block = js[report_start:console_start]

        self.assertNotIn("emitWitness('PASS'", append_block)
        self.assertNotIn("startsWith('TEV_SCRIPT_", append_block)
        self.assertNotIn("includes('TEV_SCRIPT_", append_block)
        self.assertIn("emitWitness('PASS'", report_block)

        self.assertIn("using System.Runtime.InteropServices.JavaScript;", cs)
        self.assertIn(f'[JSImport("globalThis.{report_name}")]', cs)
        self.assertIn('BrowserWitness.Report("PASS"', cs)
        self.assertIn('BrowserWitness.Report("FAIL"', cs)

    def test_ir_v3_browser_witness_is_managed_authoritative(self) -> None:
        self._assert_managed_authority(
            js_relative="runtimes/csharp/TevScript.V3BrowserWasmGate/main.mjs",
            cs_relative="runtimes/csharp/TevScript.V3BrowserWasmGate/Program.cs",
            report_name="tevIrV3BrowserReport",
            missing_report_marker="DOTNET_EXITED_WITHOUT_MANAGED_REPORT",
        )

    def test_signed_update_browser_witness_is_managed_authoritative(self) -> None:
        self._assert_managed_authority(
            js_relative="runtimes/csharp/TevScript.V3BrowserSignedUpdateGate/main.mjs",
            cs_relative="runtimes/csharp/TevScript.V3BrowserSignedUpdateGate/Program.cs",
            report_name="tevIrV3SignedBrowserReport",
            missing_report_marker="DOTNET_EXITED_WITHOUT_MANAGED_REPORT",
        )


if __name__ == "__main__":
    unittest.main()
