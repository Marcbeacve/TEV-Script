from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
OMEGA0_BASE_SHA = "35046a16b2787438f03cffd0d376fbb68d63a5df"
OMEGA0_BASE_TREE = "60267f52b41886d41c39d52ee866a1672e6fedd3"
V2_BASE_SHA = "2bdb047dcad41f9d112219bd65925c25668c02e0"
PLAN_SCHEMA = "tev-script-max-v3-basis-frontier/v1"

MAX_V3_BASIS_FRONTIER = (
    "RUN_TEV_SCRIPT_MAX_V3_BASIS_CERTIFY.py",
    "docs/superpowers/plans/2026-08-16-tevscript-max-v3-primitive-basis.md",
    "docs/superpowers/specs/2026-08-16-tevscript-max-v3-primitive-basis-design.md",
    "schemas/tev-script-max-v3-basis-certify-receipt.schema.json",
    "tests/test_max_v3_basis_certify.py",
    "tests/test_omega_semantic_basis_v1.py",
    "tests/test_tevprober_max_basis_v1.py",
    "tev_script/omega_semantic_basis_v1.py",
    "tools/tevprober_max_basis_v1.py",
    "tools/tevprober_max_v3_basis_frontier.py",
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
        raise ValueError("max_v3_basis_changed_paths_sequence_required")
    normalized: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            raise ValueError("max_v3_basis_changed_path_must_be_text")
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
            raise ValueError("max_v3_basis_changed_path_invalid")
        normalized.append(value)
    return tuple(sorted(dict.fromkeys(normalized)))


def plan(changed_paths: Sequence[str]) -> dict[str, Any]:
    paths = normalize_paths(changed_paths)
    expected = set(MAX_V3_BASIS_FRONTIER)
    observed = set(paths)
    unknown = sorted(observed - expected)
    missing = sorted(expected - observed)
    ready = not unknown and not missing
    reasons = (
        [
            "exact_max_v3_primitive_basis_frontier",
            "omega0_base_bound",
            "v2_authority_immutable",
            "omega0_authority_immutable",
            "non_promotional_candidate_phase",
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
        "mode": "MAX_V3_PRIMITIVE_BASIS" if ready else "HOLD",
        "omega0_base_sha": OMEGA0_BASE_SHA,
        "omega0_base_tree": OMEGA0_BASE_TREE,
        "v2_base_sha": V2_BASE_SHA,
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
        "PATH", "HOME", "TMP", "TEMP", "SYSTEMROOT", "WINDIR", "COMSPEC",
        "PATHEXT", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
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
    if _git("merge-base", "--is-ancestor", OMEGA0_BASE_SHA, "HEAD").returncode != 0:
        raise ValueError("max_v3_basis_omega0_base_not_ancestor")
    committed = _git("diff", "--name-only", OMEGA0_BASE_SHA + "...HEAD", "--")
    pending = _git("status", "--porcelain=v1", "--untracked-files=all")
    if committed.returncode != 0 or pending.returncode != 0:
        raise ValueError("max_v3_basis_git_delta_unreadable")
    values = list(committed.stdout.splitlines())
    for line in pending.stdout.splitlines():
        if len(line) >= 4:
            values.append(line[3:].split(" -> ", 1)[-1])
    return normalize_paths(values)


__all__ = [
    "MAX_V3_BASIS_FRONTIER",
    "OMEGA0_BASE_SHA",
    "OMEGA0_BASE_TREE",
    "V2_BASE_SHA",
    "normalize_paths",
    "plan",
    "resolve_changed_paths",
    "verify_plan",
]
