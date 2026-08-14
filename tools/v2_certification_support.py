from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import subprocess
from typing import Callable

_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


class V2CertificationFailure(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitIdentity:
    branch: str
    commit_sha: str
    tree_sha: str
    base_sha: str


def bounded(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return text[-12000:].replace("\r", "\\r").replace("\n", "\\n")


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise V2CertificationFailure(
            f"git {' '.join(arguments)} failed exit={completed.returncode}; "
            f"stdout={bounded(completed.stdout)}; stderr={bounded(completed.stderr)}"
        )
    return completed.stdout.strip()


def require_git_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or _GIT_SHA.fullmatch(value) is None:
        raise V2CertificationFailure(f"invalid {label}: {value!r}")
    return value


def collect_git_identity(
    root: Path,
    expected_base: str,
    *,
    git: Callable[..., str] | None = None,
) -> GitIdentity:
    base_sha = require_git_sha(expected_base, "expected base")
    git_fn = _git if git is None else git
    dirty = git_fn(root, "status", "--porcelain")
    if dirty:
        raise V2CertificationFailure("dirty worktree is not certifiable: " + bounded(dirty))
    branch = git_fn(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch.startswith("agent/"):
        raise V2CertificationFailure(
            f"V2 certification requires an agent/ branch, observed={branch!r}"
        )
    commit_sha = require_git_sha(
        git_fn(root, "rev-parse", "--verify", "HEAD"),
        "HEAD Git identity",
    )
    tree_sha = require_git_sha(
        git_fn(root, "rev-parse", "--verify", "HEAD^{tree}"),
        "tree Git identity",
    )
    observed_origin_main = git_fn(root, "rev-parse", "--verify", "origin/main")
    if observed_origin_main != base_sha:
        raise V2CertificationFailure(
            "origin/main drift from expected V2 base: "
            f"expected={base_sha} observed={observed_origin_main}"
        )
    git_fn(root, "merge-base", "--is-ancestor", base_sha, "HEAD")
    return GitIdentity(branch, commit_sha, tree_sha, base_sha)


def _outside_repository(root: Path, raw: Path, label: str) -> Path:
    root_resolved = root.resolve()
    selected = raw.expanduser().resolve()
    try:
        selected.relative_to(root_resolved)
    except ValueError:
        return selected
    raise V2CertificationFailure(f"{label} must be outside the repository")


def require_external_output_path(root: Path, raw: Path) -> Path:
    selected = _outside_repository(root, raw, "V2 certification output")
    if selected.exists() and selected.is_dir():
        raise V2CertificationFailure("V2 certification output path is a directory")
    return selected


def require_external_input_file(root: Path, raw: Path) -> Path:
    selected = _outside_repository(root, raw, "V2 certification input")
    if not selected.is_file():
        raise V2CertificationFailure(f"V2 certification input file is missing: {selected}")
    return selected


def require_external_empty_dir(root: Path, raw: Path) -> Path:
    selected = _outside_repository(root, raw, "V2 certification artifact directory")
    if selected.exists() and not selected.is_dir():
        raise V2CertificationFailure("V2 certification artifact path is not a directory")
    selected.mkdir(parents=True, exist_ok=True)
    if any(selected.iterdir()):
        raise V2CertificationFailure(
            f"V2 certification artifact directory must be empty: {selected}"
        )
    return selected


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
