from __future__ import annotations

import copy
from pathlib import Path

from tev_script.platform_regression import run_full_regression, verify_full_regression_receipt


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


def _identity(root: Path) -> tuple[str, str]:
    del root
    return "a" * 40, "b" * 40


def _run(root: Path, **kwargs):
    return run_full_regression(
        root,
        identity_resolver=kwargs.pop("identity_resolver", _identity),
        worktree_clean_resolver=kwargs.pop("worktree_clean_resolver", lambda root: True),
        **kwargs,
    )


def test_full_regression_pass_requires_nonempty_zero_skip_suite(tmp_path: Path) -> None:
    receipt = _run(tmp_path, runner=_runner(tests=17))
    assert receipt["status"] == "PASS"
    assert receipt["test_count"] == 17
    assert receipt["failure_count"] == 0
    assert receipt["error_count"] == 0
    assert receipt["skipped_count"] == 0
    assert receipt["source_commit"] == "a" * 40
    assert receipt["source_tree"] == "b" * 40
    assert receipt["identity_stable"] is True
    assert receipt["worktree_clean_before"] is True
    assert receipt["worktree_clean_after"] is True
    assert len(receipt["junit_sha256"]) == 64
    assert verify_full_regression_receipt(receipt)


def test_full_regression_receipt_tamper_is_rejected(tmp_path: Path) -> None:
    receipt = _run(tmp_path, runner=_runner(tests=17))
    tampered = copy.deepcopy(receipt)
    tampered["test_count"] = 18
    assert not verify_full_regression_receipt(tampered)
    tampered = copy.deepcopy(receipt)
    tampered["source_commit"] = "c" * 40
    assert not verify_full_regression_receipt(tampered)


def test_any_skip_blocks_full_regression(tmp_path: Path) -> None:
    receipt = _run(tmp_path, runner=_runner(tests=17, skipped=1))
    assert receipt["status"] == "FAIL"
    assert receipt["skipped_count"] == 1
    assert receipt["reason"] == "FULL_REGRESSION_NOT_CLEAN"
    assert verify_full_regression_receipt(receipt)


def test_any_failure_or_error_blocks_full_regression(tmp_path: Path) -> None:
    for field, runner in (
        ("failure_count", _runner(returncode=1, failures=1)),
        ("error_count", _runner(returncode=1, errors=1)),
    ):
        receipt = _run(tmp_path, runner=runner)
        assert receipt["status"] == "FAIL"
        assert receipt[field] == 1
        assert verify_full_regression_receipt(receipt)


def test_zero_collected_tests_cannot_pass(tmp_path: Path) -> None:
    receipt = _run(tmp_path, runner=_runner(returncode=5, tests=0))
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "FULL_REGRESSION_NOT_CLEAN"
    assert verify_full_regression_receipt(receipt)


def test_missing_junit_fails_closed(tmp_path: Path) -> None:
    receipt = _run(
        tmp_path,
        runner=lambda root, junit_path: 0,
    )
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "JUNIT_RESULT_MISSING"
    assert verify_full_regression_receipt(receipt)


def test_dirty_worktree_before_or_after_blocks_regression(tmp_path: Path) -> None:
    states = iter((True, False))
    receipt = _run(
        tmp_path,
        runner=_runner(),
        worktree_clean_resolver=lambda root: next(states),
    )
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "SOURCE_IDENTITY_NOT_STABLE"
    assert receipt["worktree_clean_after"] is False
    assert verify_full_regression_receipt(receipt)


def test_head_or_tree_drift_blocks_regression(tmp_path: Path) -> None:
    identities = iter((("a" * 40, "b" * 40), ("c" * 40, "d" * 40)))
    receipt = _run(
        tmp_path,
        runner=_runner(),
        identity_resolver=lambda root: next(identities),
    )
    assert receipt["status"] == "FAIL"
    assert receipt["reason"] == "SOURCE_IDENTITY_NOT_STABLE"
    assert receipt["identity_stable"] is False
    assert verify_full_regression_receipt(receipt)
