from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"

TEST_FILES = (
    "test_realization_semantics_v0.py",
    "test_realization_identity_invariants_v0.py",
    "test_discovery_realization_v0.py",
    "test_realization_composition_v0.py",
    "test_realization_placement_v0.py",
)


def run_tests() -> tuple[bool, int]:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for file_name in TEST_FILES:
        suite.addTests(loader.discover(str(TEST_ROOT), pattern=file_name))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful(), result.testsRun


def run_authority_validator() -> bool:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "validate_realization_semantics_v0.py")],
        cwd=ROOT,
        text=True,
    )
    return completed.returncode == 0


def main() -> int:
    tests_ok, count = run_tests()
    print(f"REALIZATION_SEMANTICS_FOCAL_TEST_COUNT={count}")
    print(f"REALIZATION_SEMANTICS_FOCAL_TESTS={'PASS' if tests_ok else 'FAIL'}")
    if not tests_ok:
        print("TEV_SCRIPT_REALIZATION_SEMANTICS_V0=FAIL")
        return 1

    authority_ok = run_authority_validator()
    print(f"REALIZATION_SEMANTICS_AUTHORITY_GATE={'PASS' if authority_ok else 'FAIL'}")
    if not authority_ok:
        print("TEV_SCRIPT_REALIZATION_SEMANTICS_V0=FAIL")
        return 1

    print("LONG_REPOSITORY_VALIDATION=DEFERRED_BY_DESIGN")
    print("TEV_SCRIPT_REALIZATION_SEMANTICS_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
