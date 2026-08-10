from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"


def main() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(TEST_ROOT), pattern="test_host_realization_v1.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"R1_HOST_REALIZATION_TEST_COUNT={result.testsRun}")
    print(f"R1_HOST_REALIZATION_TESTS={'PASS' if result.wasSuccessful() else 'FAIL'}")
    if not result.wasSuccessful():
        print("TEV_SCRIPT_HOST_REALIZATION_R1=FAIL")
        return 1

    validator = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_host_realization_v1.py")],
        cwd=ROOT,
        text=True,
    )
    print(f"R1_HOST_REALIZATION_AUTHORITY={'PASS' if validator.returncode == 0 else 'FAIL'}")
    if validator.returncode != 0:
        print("TEV_SCRIPT_HOST_REALIZATION_R1=FAIL")
        return 2

    print("FULL_UNIT_REGRESSION=DEFERRED_BY_DESIGN")
    print("CERTIFY_FULL=DEFERRED_BY_DESIGN")
    print("PYTHON_CERTIFY_FULL=DEFERRED_BY_DESIGN")
    print("TEV_SCRIPT_HOST_REALIZATION_R1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
