from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"

FOCAL_TEST_FILES = (
    "test_v1_frontend.py",
    "test_v1_linked_program.py",
    "test_v1_irv3_lowering.py",
    "test_v1_irv3_lowering_receipt.py",
    "test_ir_v3_validation.py",
    "test_ir_v3_runtime.py",
    "test_realization_semantics_v0.py",
    "test_realization_selection_v0.py",
    "test_realization_resolution_v0.py",
    "test_realization_search_v0.py",
    "test_host_realization_v1.py",
    "test_execution_request_v0.py",
    "test_realization_activation_v0.py",
    "test_realization_execution_observation_v0.py",
    "test_execution_grounded_discovery_v0.py",
    "test_system_integration_receipt_v0.py",
    "test_system_api_v0.py",
)


def run_tests() -> tuple[bool, int, int, int]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for file_name in FOCAL_TEST_FILES:
        suite.addTests(loader.discover(str(TEST_ROOT), pattern=file_name, top_level_dir=str(ROOT)))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful(), result.testsRun, len(result.failures), len(result.errors)


def main() -> int:
    ok, count, failures, errors = run_tests()
    print(f"SYSTEM_INTEGRATION_FOCAL_TEST_COUNT={count}")
    print(f"SYSTEM_INTEGRATION_FOCAL_FAILURES={failures}")
    print(f"SYSTEM_INTEGRATION_FOCAL_ERRORS={errors}")
    print(f"SYSTEM_INTEGRATION_FOCAL_TESTS={'PASS' if ok else 'FAIL'}")
    if not ok:
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=FAIL")
        return 1

    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_system_integration_v0.py")],
        cwd=ROOT,
        text=True,
    )
    if completed.returncode:
        print("SYSTEM_INTEGRATION_STATIC_AUTHORITY=FAIL")
        print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=FAIL")
        return 2
    print("SYSTEM_INTEGRATION_STATIC_AUTHORITY=PASS")

    print("SYSTEM_LANGUAGE_TO_IR_V3=PASS")
    print("SYSTEM_IR_V3_RUNTIME=PASS")
    print("SYSTEM_REALIZATION_ADMISSION=PASS")
    print("SYSTEM_GOVERNED_SELECTION_RESOLUTION=PASS")
    print("SYSTEM_HOST_REALIZATION_EVIDENCE=PASS")
    print("SYSTEM_EXECUTION_OBSERVATION_LOOP=PASS")
    print("SYSTEM_INTEGRATION_RECEIPT_BINDING=PASS")
    print("CERTIFY_FULL=DEFERRED_BY_DESIGN")
    print("PYTHON_CERTIFY_FULL=DEFERRED_BY_DESIGN")
    print("UNITY_VALIDATION=DEFERRED_BY_PRIORITY")
    print("TEV_SCRIPT_SYSTEM_INTEGRATION_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
