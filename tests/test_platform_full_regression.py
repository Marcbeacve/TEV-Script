from __future__ import annotations

from pathlib import Path

from tev_script.platform_regression import run_full_regression


def _runner(
    *,
    returncode: int = 0,
    tests: int = 3,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
):
    def run(root: Path, junit_path: Path) -> int:
        del root
        junit_path.write_text(
            (
                f'<testsuites tests="{tests}" failures="{failures}" '
                f'errors="{errors}" skipped="{skipped}">'
                f'<testsuite tests="{tests}" failures="{failures}" '
                f'errors="{errors}" skipped="{skipped}" />'
                '</testsuites>'
            ),
            encoding="utf-8",
        )
        return returncode

    return run


def test_full_regression_pass_requires_nonempty_zero_skip_suite(tmp_path: Path) -> None:
    receipt = run_full_regression(tmp_path, runner=_runner(tests=17))
    assert receipt["status"] == "PASS"
    assert receipt["test_count"] == 17
    assert receipt["failure_count"] == 0
    assert receipt["error_count"] == 0
    assert receipt["skipped_count"] == 0
    assert len(receipt["junit_sha256"]) == 64


def test_any_skip_blocks_full_regression(tmp_path: Path) -> None:
    receipt = run_full_regression(tmp_path, runner=_runner(tests=17, skipped=1))
    assert receipt["status"] == "FAIL"
    assert receipt["skipped_count"] == 1
    assert receipt["reason"] == "FULL_REGRESSION_NOT_CLEAN"


def test_any_failure_or_error_blocks_full_regression(tmp_path: Path) -> None:
    for field, runner in (
        ("failure_count", _runner(returncode=1, failures=1)),
        ("error_count", _runner(returncode=1, errors=1)),
    ):
        receipt = run_full_regression(tmp_path, runner=runner)
        assert receipt["status"] == "FAIL"
        assert receipt[field] == 1


def test_zero_collected_tests_cannot_pass(tmp_path: Path) -> None:
    receipt = run_full_regression(tmp_path, runner=_runner(returncode=5, tests=0))
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "FULL_REGRESSION_NOT_CLEAN"


def test_missing_junit_fails_closed(tmp_path: Path) -> None:
    receipt = run_full_regression(
        tmp_path,
        runner=lambda root, junit_path: 0,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "JUNIT_RESULT_MISSING"
