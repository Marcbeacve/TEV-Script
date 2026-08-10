from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

ACTION_LOOP_TESTS = (
    "tests.test_realization_execution_observation_v0",
    "tests.test_execution_grounded_discovery_v0",
)


def run(command: list[str]) -> int:
    completed = subprocess.run(command, cwd=ROOT, text=True)
    return completed.returncode


def run_tests() -> tuple[bool, int]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for module in ACTION_LOOP_TESTS:
        suite.addTests(loader.loadTestsFromName(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful(), result.testsRun


def main() -> int:
    if run([sys.executable, str(ROOT / "tests" / "run_realization_semantics_campaign.py")]):
        print("R0_ACTION_LOOP_CORE_FOCAL=FAIL")
        print("TEV_SCRIPT_REALIZATION_ACTION_LOOP_V0=FAIL")
        return 1
    print("R0_ACTION_LOOP_CORE_FOCAL=PASS")

    tests_ok, count = run_tests()
    print(f"R0_ACTION_LOOP_TEST_COUNT={count}")
    print(f"R0_ACTION_LOOP_TESTS={'PASS' if tests_ok else 'FAIL'}")
    if not tests_ok:
        print("TEV_SCRIPT_REALIZATION_ACTION_LOOP_V0=FAIL")
        return 2

    if run([sys.executable, str(ROOT / "tools" / "validate_realization_action_loop_v0.py")]):
        print("R0_ACTION_LOOP_AUTHORITY=FAIL")
        print("TEV_SCRIPT_REALIZATION_ACTION_LOOP_V0=FAIL")
        return 3
    print("R0_ACTION_LOOP_AUTHORITY=PASS")

    print("LONG_REPOSITORY_VALIDATION=DEFERRED_BY_DESIGN")
    print("TEV_SCRIPT_REALIZATION_ACTION_LOOP_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
