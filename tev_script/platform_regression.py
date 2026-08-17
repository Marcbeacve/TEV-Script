from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Callable
import xml.etree.ElementTree as ET

RegressionRunner = Callable[[Path, Path], int]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


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
        return tuple(_integer_attribute(root, name) for name in names)  # type: ignore[return-value]

    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("JUnit result has no test suites")
    totals = [0, 0, 0, 0]
    for suite in suites:
        for index, name in enumerate(names):
            totals[index] += _integer_attribute(suite, name)
    return totals[0], totals[1], totals[2], totals[3]


def run_full_regression(
    root: Path | str,
    *,
    runner: RegressionRunner | None = None,
) -> dict[str, object]:
    root = Path(root)
    execute = _default_runner if runner is None else runner
    body: dict[str, object]
    try:
        with tempfile.TemporaryDirectory(prefix="tevscript-full-regression-") as temporary:
            junit_path = Path(temporary) / "pytest-junit.xml"
            returncode = int(execute(root, junit_path))
            if not junit_path.is_file():
                body = {
                    "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V1",
                    "status": "FAIL",
                    "reason": "JUNIT_RESULT_MISSING",
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
                clean = (
                    returncode == 0
                    and tests > 0
                    and failures == 0
                    and errors == 0
                    and skipped == 0
                )
                body = {
                    "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V1",
                    "status": "PASS" if clean else "FAIL",
                    "reason": "" if clean else "FULL_REGRESSION_NOT_CLEAN",
                    "returncode": returncode,
                    "test_count": tests,
                    "failure_count": failures,
                    "error_count": errors,
                    "skipped_count": skipped,
                    "junit_sha256": hashlib.sha256(junit_bytes).hexdigest(),
                }
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_FULL_REGRESSION_V1",
            "status": "FAIL",
            "reason": "FULL_REGRESSION_EXECUTION_ERROR",
            "error": f"{type(error).__name__}: {error}",
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


__all__ = ["RegressionRunner", "run_full_regression"]
