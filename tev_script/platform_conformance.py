from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from typing import Callable, Sequence

from .version import CURRENT_LANGUAGE_VERSION

MANIFEST_PATH = Path("conformance/v31-platform-manifest.json")
MANIFEST_SCHEMA = "TEV_SCRIPT_PLATFORM_CONFORMANCE_MANIFEST_V1"

Executor = Callable[[Sequence[str], Path], int]
ToolResolver = Callable[[str], str | None]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _default_executor(command: Sequence[str], cwd: Path) -> int:
    completed = subprocess.run(
        tuple(command),
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return int(completed.returncode)


def _target_file(target: str) -> str:
    raw = target.split("::", 1)[0]
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or "." in path.parts or not raw:
        raise ValueError(f"unsafe conformance target: {target}")
    return path.as_posix()


def load_platform_manifest(root: Path) -> dict[str, object]:
    value = json.loads((Path(root) / MANIFEST_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("platform conformance manifest must be an object")
    return value


def run_platform_conformance(
    root: Path,
    *,
    executor: Executor | None = None,
    tool_resolver: ToolResolver | None = None,
    python_executable: str = sys.executable,
) -> dict[str, object]:
    root = Path(root)
    execute = _default_executor if executor is None else executor
    resolve = shutil.which if tool_resolver is None else tool_resolver
    outcomes: list[dict[str, object]] = []
    try:
        manifest = load_platform_manifest(root)
        if manifest.get("schema") != MANIFEST_SCHEMA:
            raise ValueError("platform conformance manifest schema mismatch")
        if manifest.get("language_version") != CURRENT_LANGUAGE_VERSION:
            raise ValueError("platform conformance language version mismatch")
        cases = manifest.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("platform conformance cases missing")
        seen: set[str] = set()
        for raw in cases:
            if not isinstance(raw, dict):
                raise ValueError("platform conformance case must be an object")
            case_id = raw.get("case_id")
            kind = raw.get("kind")
            target = raw.get("target")
            tools = raw.get("required_tools", ["python"])
            expected_blob = raw.get("git_blob_sha1")
            if not isinstance(case_id, str) or not case_id or case_id in seen:
                raise ValueError("invalid or duplicate conformance case_id")
            seen.add(case_id)
            if kind != "pytest" or not isinstance(target, str):
                raise ValueError(f"unsupported conformance case kind: {case_id}")
            if not isinstance(tools, list) or any(
                not isinstance(tool, str) or not tool for tool in tools
            ):
                raise ValueError(f"invalid tool list: {case_id}")
            file_path = _target_file(target)
            data = (root / Path(file_path)).read_bytes()
            observed_blob = _git_blob_sha1(data)
            if not isinstance(expected_blob, str) or observed_blob != expected_blob:
                outcomes.append(
                    {
                        "case_id": case_id,
                        "status": "FAIL",
                        "reason": "TARGET_IDENTITY_MISMATCH",
                    }
                )
                continue
            unavailable = [
                tool for tool in tools if tool != "python" and resolve(tool) is None
            ]
            if unavailable:
                outcomes.append(
                    {
                        "case_id": case_id,
                        "status": "HOLD",
                        "reason": "MISSING_TOOL",
                        "tools": sorted(unavailable),
                    }
                )
                continue
            returncode = execute(
                (python_executable, "-m", "pytest", target, "-q"),
                root,
            )
            outcomes.append(
                {
                    "case_id": case_id,
                    "status": "PASS" if returncode == 0 else "FAIL",
                    "returncode": returncode,
                }
            )
        failed = sorted(
            str(row["case_id"]) for row in outcomes if row["status"] == "FAIL"
        )
        hold = sorted(
            str(row["case_id"]) for row in outcomes if row["status"] == "HOLD"
        )
        status = "FAIL" if failed else ("HOLD" if hold else "PASS")
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_CONFORMANCE_RECEIPT_V1",
            "language_version": CURRENT_LANGUAGE_VERSION,
            "status": status,
            "outcomes": sorted(outcomes, key=lambda row: str(row["case_id"])),
            "failed_cases": failed,
            "hold_cases": hold,
        }
        return {
            **body,
            "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
        }
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_CONFORMANCE_RECEIPT_V1",
            "language_version": CURRENT_LANGUAGE_VERSION,
            "status": "FAIL",
            "outcomes": outcomes,
            "failed_cases": [],
            "hold_cases": [],
            "error": str(error),
        }
        return {
            **body,
            "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
        }


__all__ = [
    "MANIFEST_PATH",
    "MANIFEST_SCHEMA",
    "load_platform_manifest",
    "run_platform_conformance",
]
