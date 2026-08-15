from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "2bdb047dcad41f9d112219bd65925c25668c02e0"
BASE_TREE = "aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8"
PLAN_SCHEMA = "tev-script-omega0-plan/v1"

OMEGA0_FRONTIER = (
    "RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py",
    "docs/superpowers/plans/2026-08-15-tev-script-omega0-kernel-contract.md",
    "docs/superpowers/specs/2026-08-15-tev-script-omega-master-design.md",
    "schemas/tev-script-omega0-certify-receipt.schema.json",
    "tests/test_omega0_certify.py",
    "tests/test_omega_kernel_v1.py",
    "tests/test_omega_v2_adapter_v1.py",
    "tests/test_tevprober_omega0.py",
    "tev_script/omega_kernel_v1.py",
    "tev_script/omega_v2_adapter_v1.py",
    "tools/tevprober_omega0.py",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def normalize_paths(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("omega0_changed_paths_sequence_required")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError("omega0_changed_path_must_be_text")
        value = raw.strip().replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if (
            not value
            or value.startswith("/")
            or value.startswith("../")
            or "/../" in value
            or value.endswith("/..")
            or "\x00" in value
            or "\n" in value
            or "\r" in value
        ):
            raise ValueError("omega0_changed_path_invalid")
        normalized.append(value)
    return tuple(sorted(dict.fromkeys(normalized)))


def plan(changed_paths: Sequence[str]) -> dict[str, Any]:
    paths = normalize_paths(changed_paths)
    expected = set(OMEGA0_FRONTIER)
    observed = set(paths)
    unknown = sorted(observed - expected)
    missing = sorted(expected - observed)
    ready = not unknown and not missing
    reasons = (
        [
            "exact_omega0_frontier",
            "stable_v2_base_bound",
            "v2_semantic_authority_unchanged",
            "non_promotional_research_track",
        ]
        if ready
        else [
            *("out_of_frontier:" + value for value in unknown),
            *("missing_frontier:" + value for value in missing),
        ]
    )
    body = {
        "schema": PLAN_SCHEMA,
        "status": "READY" if ready else "HOLD",
        "mode": "OMEGA0_KERNEL_EXTRACTION" if ready else "HOLD",
        "base_sha": BASE_SHA,
        "base_tree": BASE_TREE,
        "changed_paths": list(paths),
        "reasons": reasons,
        "promotion_authority_bool": False,
        "language_stable_claim_bool": False,
    }
    return {**body, "plan_hash": _hash(body)}


def verify_plan(value: Mapping[str, Any]) -> bool:
    try:
        changed = value.get("changed_paths")
        if not isinstance(changed, list) or any(not isinstance(item, str) for item in changed):
            return False
        expected = plan(changed)
        observed_hash = value.get("plan_hash")
        return bool(
            isinstance(observed_hash, str)
            and hmac.compare_digest(observed_hash, expected["plan_hash"])
            and _canonical_bytes(dict(value)) == _canonical_bytes(expected)
        )
    except (TypeError, ValueError, OverflowError):
        return False


def _environment() -> dict[str, str]:
    keep = {
        "PATH",
        "HOME",
        "TMP",
        "TEMP",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "USERPROFILE",
        "LOCALAPPDATA",
        "APPDATA",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in keep}
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
        }
    )
    return env


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=ROOT,
        env=_environment(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )


def resolve_changed_paths() -> tuple[str, ...]:
    ancestor = _git("merge-base", "--is-ancestor", BASE_SHA, "HEAD")
    if ancestor.returncode != 0:
        raise ValueError("omega0_base_not_ancestor")
    committed = _git("diff", "--name-only", BASE_SHA + "...HEAD", "--")
    pending = _git("status", "--porcelain=v1", "--untracked-files=all")
    if committed.returncode != 0 or pending.returncode != 0:
        raise ValueError("omega0_git_delta_unreadable")
    values = list(committed.stdout.splitlines())
    for line in pending.stdout.splitlines():
        if len(line) >= 4:
            values.append(line[3:].split(" -> ", 1)[-1])
    return normalize_paths(values)


def main() -> int:
    try:
        changed = resolve_changed_paths()
        value = plan(changed)
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_OMEGA0_PROBE=FAIL")
        print("TEV_SCRIPT_OMEGA0_PROBE_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    print("TEV_SCRIPT_OMEGA0_PROBE=" + value["status"])
    return 0 if value["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
