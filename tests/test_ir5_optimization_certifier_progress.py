from __future__ import annotations

from contextlib import redirect_stderr
import io
import sys
import unittest

from RUN_TEV_SCRIPT_V31_IR5_OPTIMIZATION_CERTIFY import _run


class Ir5OptimizationCertifierProgressTests(unittest.TestCase):
    def test_run_streams_gate_progress_and_preserves_captured_output(self) -> None:
        stderr = io.StringIO()
        command = (
            sys.executable,
            "-c",
            (
                "import sys; "
                "print('child-out', flush=True); "
                "print('child-err', file=sys.stderr, flush=True)"
            ),
        )

        with redirect_stderr(stderr):
            result = _run("SMOKE", command, index=2, total=9)

        observed = stderr.getvalue()
        self.assertIn("[2/9] SMOKE", observed)
        self.assertIn("[SMOKE] child-out", observed)
        self.assertIn("[SMOKE] child-err", observed)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["stdout"].strip(), "child-out")
        self.assertEqual(result["stderr"].strip(), "child-err")


if __name__ == "__main__":
    unittest.main()
