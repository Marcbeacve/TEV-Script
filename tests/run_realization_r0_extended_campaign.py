from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"

EXTENDED_TEST_FILES = (
    "test_commit_outcome_v0.py",
    "test_delivery_guarantee_v0.py",
    "test_delivery_plan_v0.py",
    "test_delivery_satisfaction_v0.py",
    "test_dispatch_consumption_v0.py",
    "test_execution_request_v0.py",
    "test_prepared_execution_v0.py",
    "test_realization_cost_model_v0.py",
    "test_realization_cost_model_update_v0.py",
    "test_realization_cost_prediction_v0.py",
    "test_realization_dispatch_loop_v0.py",
    "test_realization_execution_authority_v0.py",
    "test_realization_receipt_validity_dispatch_v0.py",
    "test_realization_resource_measurement_v0.py",
    "test_realization_resource_calibration_v0.py",
    "test_realization_search_v0.py",
    "test_realization_selection_v0.py",
)


def run(command: list[str]) -> int:
    return subprocess.run(command, cwd=ROOT, text=True).returncode


def run_tests() -> tuple[bool, int]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for file_name in EXTENDED_TEST_FILES:
        suite.addTests(loader.discover(str(TEST_ROOT), pattern=file_name))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful(), result.testsRun


def main() -> int:
    if run([sys.executable, str(ROOT / "tests" / "run_realization_action_loop_campaign.py")]):
        print("R0_EXTENDED_ACTION_LOOP_BASE=FAIL")
        print("TEV_SCRIPT_REALIZATION_R0_EXTENDED=FAIL")
        return 1
    print("R0_EXTENDED_ACTION_LOOP_BASE=PASS")

    tests_ok, count = run_tests()
    print(f"R0_EXTENDED_TEST_COUNT={count}")
    print(f"R0_EXTENDED_TESTS={'PASS' if tests_ok else 'FAIL'}")
    if not tests_ok:
        print("TEV_SCRIPT_REALIZATION_R0_EXTENDED=FAIL")
        return 2

    if run([sys.executable, str(ROOT / "tools" / "validate_realization_r0_extended_v0.py")]):
        print("R0_EXTENDED_AUTHORITY=FAIL")
        print("TEV_SCRIPT_REALIZATION_R0_EXTENDED=FAIL")
        return 3
    print("R0_EXTENDED_AUTHORITY=PASS")

    print("FULL_UNIT_REGRESSION=DEFERRED_BY_DESIGN")
    print("CERTIFY_FULL=DEFERRED_BY_DESIGN")
    print("PYTHON_CERTIFY_FULL=DEFERRED_BY_DESIGN")
    print("TEV_SCRIPT_REALIZATION_R0_EXTENDED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
