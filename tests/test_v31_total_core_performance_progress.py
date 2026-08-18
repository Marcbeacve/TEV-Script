from __future__ import annotations

from contextlib import redirect_stderr
import io
import unittest

from RUN_TEV_SCRIPT_V31_TOTAL_CORE_PERFORMANCE import _progress


class V31TotalCorePerformanceProgressTests(unittest.TestCase):
    def test_progress_is_emitted_to_stderr(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            _progress("fresh run 2/3 benchmark")
        self.assertEqual(
            stderr.getvalue().strip(),
            "[PERFORMANCE] fresh run 2/3 benchmark",
        )


if __name__ == "__main__":
    unittest.main()
