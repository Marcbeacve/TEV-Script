from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable, Mapping
import xml.etree.ElementTree as ET

RegressionRunner = Callable[[Path, Path], int]
IdentityResolver = Callable[[Path], tuple[str, str]]
WorktreeCleanResolver = Callable[[Path], bool]

_FULL_REGRESSION_FIELDS = frozenset(
    {
        "schema",
        "status",
        "reason",
        "error",
        "source_commit",
        "source_tree",
        "identity_stable",
        "worktree_clean_before",
        "worktree_clean_after",
        "returncode",
        "test_count",
        "failure_count",
        "error_count",
        "skipped_count",
        "junit_sha256",
        "receipt_sha256",
    }
)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _is_sha(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError("git source identity unavailable")
    return completed.stdout.strip()


def _default_identity(root: Path) -> tuple[str, str]:
    return _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")


def _default_worktree_clean(root: Path) -> bool:
    return _git(root, "status", "--porcelain=v1", "--untracked-files=all") == ""


def _is_git_sha(value: object) -> bool:
    return _is_sha(value, 40)


def _default_runner(root: Path, junit_path: Path) -> int:
    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--disable-warnings",
            f"--junitxml={junit_path}",
        ),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return int(completed.returncode)


def _integer_attribute(node: ET.Element, name: str) -> int:
    raw = node.attrib.get(name, "0")
    value = int(raw, 10)
    if value < 0:
        raise ValueError(f"negative JUnit count: {name}")
    return value


def _junit_counts(path: Path) -> tuple[int, int, int, int]:
    document = ET.parse(path)
    root = document.getroot()
    names = ("tests", "failures", "errors", "skipped")
    if root.tag in {"testsuite", "testsuites"} and all(
        name in root.attrib for name in names
    ):
        values = tuple(_integer_attribute(root, name) for name in names)
        return values[0], values[1], values[2], values[3]

    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("JUnit result has no test suites")
    totals = [0, 0, 0, 0]
    for suite in suites:
        for index, name in enumerate(names):
            totals[index] += _integer_attribute(suite, name)
    return totals[0], totals[1], totals[2], totals[3]


def verify_full_regression_receipt(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    receipt = dict(value)
    if set(receipt) - _FULL_REGRESSION_FIELDS:
        return False
    observed_hash = receipt.pop("receipt_sha256", None)
    if not _is_sha(observed_hash, 64):
        return False
    if hashlib.sha256(_canonical_json_bytes(receipt)).hexdigest() != observed_hash:
        return False
    if receipt.get("schema") != "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2":
        return False
    status = receipt.get("status")
    if status not in {"PASS", "FAIL"}:
        return False
    if not isinstance(receipt.get("reason"), str):
        return False
    if "error" in receipt and not isinstance(receipt.get("error"), str):
        return False
    for name in ("identity_stable", "worktree_clean_before", "worktree_clean_after"):
        if not isinstance(receipt.get(name), bool):
            return False
    returncode = receipt.get("returncode")
    if not isinstance(returncode, int) or isinstance(returncode, bool):
        return False
    for name in ("test_count", "failure_count", "error_count", "skipped_count"):
        count = receipt.get(name)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return False
    source_commit = receipt.get("source_commit")
    source_tree = receipt.get("source_tree")
    if source_commit != "" and not _is_git_sha(source_commit):
        return False
    if source_tree != "" and not _is_git_sha(source_tree):
        return False
    junit_sha = receipt.get("junit_sha256")
    if junit_sha != "" and not _is_sha(junit_sha, 64):
        return False
    if status == "PASS":
        return bool(
            receipt.get("reason") == ""
            and _is_git_sha(source_commit)
            and _is_git_sha(source_tree)
            and receipt.get("identity_stable") is True
            and receipt.get("worktree_clean_before") is True
            and receipt.get("worktree_clean_after") is True
            and returncode == 0
            and receipt.get("test_count", 0) > 0
            and receipt.get("failure_count") == 0
            and receipt.get("error_count") == 0
            and receipt.get("skipped_count") == 0
            and _is_sha(junit_sha, 64)
        )
    return True


def run_full_regression(
    root: Path | str,
    *,
    runner: RegressionRunner | None = None,
    identity_resolver: IdentityResolver | None = None,
    worktree_clean_resolver: WorktreeCleanResolver | None = None,
) -> dict[str, object]:
    root = Path(root)
    execute = _default_runner if runner is None else runner
    resolve_identity = _default_identity if identity_resolver is None else identity_resolver
    resolve_clean = (
        _default_worktree_clean
        if worktree_clean_resolver is None
        else worktree_clean_resolver
    )
    body: dict[str, object]
    try:
        source_before = resolve_identity(root)
        if not all(_is_git_sha(value) for value in source_before):
            raise ValueError("invalid Git source identity")
        clean_before = bool(resolve_clean(root))
        if not clean_before:
            body = {
                "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2",
                "status": "FAIL",
                "reason": "SOURCE_IDENTITY_NOT_STABLE",
                "source_commit": source_before[0],
                "source_tree": source_before[1],
                "identity_stable": False,
                "worktree_clean_before": False,
                "worktree_clean_after": False,
                "returncode": -1,
                "test_count": 0,
                "failure_count": 0,
                "error_count": 0,
                "skipped_count": 0,
                "junit_sha256": "",
            }
        else:
            with tempfile.TemporaryDirectory(prefix="tevscript-full-regression-") as temporary:
                junit_path = Path(temporary) / "pytest-junit.xml"
                returncode = int(execute(root, junit_path))
                source_after = resolve_identity(root)
                if not all(_is_git_sha(value) for value in source_after):
                    raise ValueError("invalid Git source identity after regression")
                clean_after = bool(resolve_clean(root))
                identity_stable = source_after == source_before

                if not junit_path.is_file():
                    body = {
                        "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2",
                        "status": "FAIL",
                        "reason": "JUNIT_RESULT_MISSING",
                        "source_commit": source_before[0],
                        "source_tree": source_before[1],
                        "identity_stable": identity_stable,
                        "worktree_clean_before": clean_before,
                        "worktree_clean_after": clean_after,
                        "returncode": returncode,
                        "test_count": 0,
                        "failure_count": 0,
                        "error_count": 0,
                        "skipped_count": 0,
                        "junit_sha256": "",
                    }
                else:
                    junit_bytes = junit_path.read_bytes()
                    tests, failures, errors, skipped = _junit_counts(junit_path)
                    test_clean = (
                        returncode == 0
                        and tests > 0
                        and failures == 0
                        and errors == 0
                        and skipped == 0
                    )
                    source_clean = clean_before and clean_after and identity_stable
                    passed = test_clean and source_clean
                    reason = ""
                    if not source_clean:
                        reason = "SOURCE_IDENTITY_NOT_STABLE"
                    elif not test_clean:
                        reason = "FULL_REGRESSION_NOT_CLEAN"
                    body = {
                        "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2",
                        "status": "PASS" if passed else "FAIL",
                        "reason": reason,
                        "source_commit": source_before[0],
                        "source_tree": source_before[1],
                        "identity_stable": identity_stable,
                        "worktree_clean_before": clean_before,
                        "worktree_clean_after": clean_after,
                        "returncode": returncode,
                        "test_count": tests,
                        "failure_count": failures,
                        "error_count": errors,
                        "skipped_count": skipped,
                        "junit_sha256": hashlib.sha256(junit_bytes).hexdigest(),
                    }
    except (
        OSError,
        ValueError,
        RuntimeError,
        ET.ParseError,
        subprocess.SubprocessError,
    ) as error:
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V2",
            "status": "FAIL",
            "reason": "FULL_REGRESSION_EXECUTION_ERROR",
            "error": f"{type(error).__name__}: {error}",
            "source_commit": "",
            "source_tree": "",
            "identity_stable": False,
            "worktree_clean_before": False,
            "worktree_clean_after": False,
            "returncode": -1,
            "test_count": 0,
            "failure_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "junit_sha256": "",
        }
    return {
        **body,
        "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


__all__ = [
    "IdentityResolver",
    "RegressionRunner",
    "WorktreeCleanResolver",
    "run_full_regression",
    "verify_full_regression_receipt",
]
