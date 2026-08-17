from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from typing import Callable, Mapping, Sequence

EXPECTED_INVARIANTS = frozenset(
    {
        "DETERMINISM",
        "CAPABILITY_NON_ESCALATION",
        "BOUNDED_EXECUTION",
        "CANONICAL_IDENTITY",
        "CHECKPOINT_REPLAY_EQUIVALENCE",
        "CROSS_RUNTIME_EQUIVALENCE",
        "UPGRADE_NO_FORK",
    }
)

_V31_INVARIANT_BLOB = "d12e6940e1507c5394e1a21695048a0fb78cac34"
DEFAULT_WITNESSES: dict[str, dict[str, object]] = {
    "DETERMINISM": {
        "kind": "pytest",
        "target": (
            "tests/test_platform_invariants_v31.py::"
            "test_total_core_determinism_same_input_same_canonical_result"
        ),
        "git_blob_sha1": _V31_INVARIANT_BLOB,
        "required_tools": ["python"],
    },
    "CAPABILITY_NON_ESCALATION": {
        "kind": "pytest",
        "target": (
            "tests/test_platform_invariants_v31.py::"
            "test_total_core_capability_non_escalation_requires_external_effect_input"
        ),
        "git_blob_sha1": _V31_INVARIANT_BLOB,
        "required_tools": ["python"],
    },
    "BOUNDED_EXECUTION": {
        "kind": "pytest",
        "target": (
            "tests/test_platform_invariants_v31.py::"
            "test_total_core_bounded_execution_suspends_exactly_at_quantum_limit"
        ),
        "git_blob_sha1": _V31_INVARIANT_BLOB,
        "required_tools": ["python"],
    },
    "CANONICAL_IDENTITY": {
        "kind": "pytest",
        "target": (
            "tests/test_platform_invariants_v31.py::"
            "test_total_core_canonical_identity_rejects_program_hash_tamper"
        ),
        "git_blob_sha1": _V31_INVARIANT_BLOB,
        "required_tools": ["python"],
    },
    "CHECKPOINT_REPLAY_EQUIVALENCE": {
        "kind": "pytest",
        "target": (
            "tests/test_platform_invariants_v31.py::"
            "test_total_core_checkpoint_replay_is_canonically_equivalent"
        ),
        "git_blob_sha1": _V31_INVARIANT_BLOB,
        "required_tools": ["python"],
    },
    "CROSS_RUNTIME_EQUIVALENCE": {
        "kind": "pytest",
        "target": "tests/test_runtime_v5_total_js_parity.py",
        "git_blob_sha1": "fe6bbac0efa7460031845d2fa5bd2431bff04ecf",
        "required_tools": ["python", "node"],
    },
    "UPGRADE_NO_FORK": {
        "kind": "python_script",
        "target": "tools/validate_hot_update_batch_5c_5e.py",
        "git_blob_sha1": "3ce43b78d25805c8f0d76cb671dcc4035bacd485",
        "required_tools": ["python"],
    },
}

Executor = Callable[[Sequence[str], Path], int]
ToolResolver = Callable[[str], str | None]


def _git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _safe_target(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError("witness target must be text")
    file_part = raw.split("::", 1)[0]
    path = PurePosixPath(file_part)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe witness target: {raw}")
    return raw


def _default_executor(command: Sequence[str], cwd: Path) -> int:
    result = subprocess.run(
        tuple(command),
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return int(result.returncode)


def validate_platform_invariants(
    root: Path,
    *,
    witnesses: Mapping[str, Mapping[str, object]] | None = None,
    executor: Executor | None = None,
    tool_resolver: ToolResolver | None = None,
    python_executable: str = sys.executable,
) -> dict[str, object]:
    root = Path(root)
    selected = (
        DEFAULT_WITNESSES
        if witnesses is None
        else {name: dict(value) for name, value in witnesses.items()}
    )
    execute = _default_executor if executor is None else executor
    resolve = shutil.which if tool_resolver is None else tool_resolver
    missing = sorted(EXPECTED_INVARIANTS - set(selected))
    extra = sorted(set(selected) - EXPECTED_INVARIANTS)
    if missing or extra:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_INVARIANTS_V2",
            "status": "FAIL",
            "missing_witnesses": missing,
            "extra_witnesses": extra,
            "witnesses": {},
        }
    outcomes: dict[str, dict[str, object]] = {}
    try:
        for name in sorted(EXPECTED_INVARIANTS):
            witness = selected[name]
            kind = witness.get("kind")
            target = _safe_target(witness.get("target"))
            expected_blob = witness.get("git_blob_sha1")
            tools = witness.get("required_tools", ["python"])
            if not isinstance(tools, list) or any(
                not isinstance(tool, str) or not tool for tool in tools
            ):
                raise ValueError(f"invalid tools for {name}")
            file_part = target.split("::", 1)[0]
            observed_blob = _git_blob_sha1((root / Path(file_part)).read_bytes())
            if not isinstance(expected_blob, str) or observed_blob != expected_blob:
                outcomes[name] = {
                    "status": "FAIL",
                    "reason": "TARGET_IDENTITY_MISMATCH",
                }
                continue
            unavailable = [
                tool for tool in tools if tool != "python" and resolve(tool) is None
            ]
            if unavailable:
                outcomes[name] = {
                    "status": "HOLD",
                    "reason": "MISSING_TOOL",
                    "tools": sorted(unavailable),
                }
                continue
            if kind == "pytest":
                command = (python_executable, "-m", "pytest", target, "-q")
            elif kind == "python_script":
                command = (python_executable, target)
            else:
                raise ValueError(f"unsupported witness kind for {name}")
            returncode = execute(command, root)
            outcomes[name] = {
                "status": "PASS" if returncode == 0 else "FAIL",
                "returncode": returncode,
                "target": target,
            }
        failures = sorted(
            name for name, row in outcomes.items() if row["status"] == "FAIL"
        )
        holds = sorted(
            name for name, row in outcomes.items() if row["status"] == "HOLD"
        )
        status = "FAIL" if failures else ("HOLD" if holds else "PASS")
        return {
            "schema": "TEV_SCRIPT_PLATFORM_INVARIANTS_V2",
            "status": status,
            "missing_witnesses": [],
            "extra_witnesses": [],
            "failed_witnesses": failures,
            "hold_witnesses": holds,
            "witnesses": outcomes,
        }
    except (OSError, UnicodeError, ValueError) as error:
        return {
            "schema": "TEV_SCRIPT_PLATFORM_INVARIANTS_V2",
            "status": "FAIL",
            "missing_witnesses": [],
            "extra_witnesses": [],
            "witnesses": outcomes,
            "error": str(error),
        }


__all__ = [
    "DEFAULT_WITNESSES",
    "EXPECTED_INVARIANTS",
    "validate_platform_invariants",
]
