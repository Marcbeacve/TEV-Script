from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

from tev_script.canonical import canonical_hash
from tools import tevprober_omega0 as probe

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_BRANCH = "agent/tev-script-omega-kernel-v1"
BASE_SHA = probe.BASE_SHA
BASE_TREE = probe.BASE_TREE
RECEIPT_SCHEMA = "TEV_SCRIPT_OMEGA0_CERTIFY_RECEIPT_V1"
DESIGN_PATH = "docs/superpowers/specs/2026-08-15-tev-script-omega-master-design.md"
PLAN_PATH = "docs/superpowers/plans/2026-08-15-tev-script-omega0-kernel-contract.md"
OMEGA_TEST_MODULES = (
    "tests.test_omega_kernel_v1",
    "tests.test_omega_v2_adapter_v1",
    "tests.test_tevprober_omega0",
    "tests.test_omega0_certify",
)
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_SHA256_PREFIXED = re.compile(r"^sha256:[0-9a-f]{64}$")
_RAN = re.compile(r"Ran\s+(\d+)\s+tests?\s+in\s+")
_SKIPPED = re.compile(r"skipped=(\d+)")


class Omega0CertificationFailure(RuntimeError):
    pass


def _canonical_body(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(value)


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be non-empty text")
    return value


def _require_sha40(value: Any, name: str) -> str:
    text = _require_text(value, name)
    if _SHA40.fullmatch(text) is None:
        raise ValueError(f"{name} must be lowercase 40-hex git id")
    return text


def _require_sha64(value: Any, name: str) -> str:
    text = _require_text(value, name)
    if _SHA64.fullmatch(text) is None:
        raise ValueError(f"{name} must be lowercase sha256 hex")
    return text


def _require_prefixed_sha256(value: Any, name: str) -> str:
    text = _require_text(value, name)
    if _SHA256_PREFIXED.fullmatch(text) is None:
        raise ValueError(f"{name} must be sha256:<lowercase-64-hex>")
    return text


def _require_count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def build_receipt_body(
    *,
    repository: str,
    branch: str,
    commit_sha: str,
    tree_sha: str,
    base_sha: str,
    base_tree_sha: str,
    omega_master_design_sha256: str,
    omega_plan_sha256: str,
    omega_frontier_plan_hash: str,
    omega_test_count: int,
    omega_skipped_tests: int,
    full_test_count: int,
    full_skipped_tests: int,
    v2_governed_files_unchanged: bool,
    v2_authority_validation: str,
) -> dict[str, Any]:
    if v2_governed_files_unchanged is not True:
        raise ValueError("v2_governed_files_unchanged must be True")
    if v2_authority_validation != "PASS":
        raise ValueError("v2_authority_validation must be PASS")
    return {
        "schema": RECEIPT_SCHEMA,
        "repository": _require_text(repository, "repository"),
        "branch": _require_text(branch, "branch"),
        "commit_sha": _require_sha40(commit_sha, "commit_sha"),
        "tree_sha": _require_sha40(tree_sha, "tree_sha"),
        "base_sha": _require_sha40(base_sha, "base_sha"),
        "base_tree_sha": _require_sha40(base_tree_sha, "base_tree_sha"),
        "omega_master_design_sha256": _require_sha64(
            omega_master_design_sha256, "omega_master_design_sha256"
        ),
        "omega_plan_sha256": _require_sha64(omega_plan_sha256, "omega_plan_sha256"),
        "omega_frontier_plan_hash": _require_prefixed_sha256(
            omega_frontier_plan_hash, "omega_frontier_plan_hash"
        ),
        "omega_test_count": _require_count(omega_test_count, "omega_test_count"),
        "omega_skipped_tests": _require_count(omega_skipped_tests, "omega_skipped_tests"),
        "full_test_count": _require_count(full_test_count, "full_test_count"),
        "full_skipped_tests": _require_count(full_skipped_tests, "full_skipped_tests"),
        "v2_governed_files_unchanged": True,
        "v2_authority_validation": "PASS",
        "promotion_authority": False,
        "language_stable": False,
        "certify_full": True,
    }


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _canonical_body(body)
    if "receipt_hash" in candidate:
        raise ValueError("receipt body must not already contain receipt_hash")
    _validate_receipt_body(candidate)
    return {**candidate, "receipt_hash": canonical_hash(candidate)}


def verify_receipt(receipt: Mapping[str, Any]) -> bool:
    try:
        candidate = dict(receipt)
        embedded = candidate.pop("receipt_hash")
        _validate_receipt_body(candidate)
        return bool(
            isinstance(embedded, str)
            and _SHA64.fullmatch(embedded) is not None
            and embedded == canonical_hash(candidate)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _validate_receipt_body(body: Mapping[str, Any]) -> None:
    expected = {
        "schema",
        "repository",
        "branch",
        "commit_sha",
        "tree_sha",
        "base_sha",
        "base_tree_sha",
        "omega_master_design_sha256",
        "omega_plan_sha256",
        "omega_frontier_plan_hash",
        "omega_test_count",
        "omega_skipped_tests",
        "full_test_count",
        "full_skipped_tests",
        "v2_governed_files_unchanged",
        "v2_authority_validation",
        "promotion_authority",
        "language_stable",
        "certify_full",
    }
    if set(body) != expected:
        raise ValueError("Omega0 receipt body field set mismatch")
    if body.get("schema") != RECEIPT_SCHEMA:
        raise ValueError("Omega0 receipt schema mismatch")
    _require_text(body.get("repository"), "repository")
    _require_text(body.get("branch"), "branch")
    _require_sha40(body.get("commit_sha"), "commit_sha")
    _require_sha40(body.get("tree_sha"), "tree_sha")
    _require_sha40(body.get("base_sha"), "base_sha")
    _require_sha40(body.get("base_tree_sha"), "base_tree_sha")
    _require_sha64(body.get("omega_master_design_sha256"), "omega_master_design_sha256")
    _require_sha64(body.get("omega_plan_sha256"), "omega_plan_sha256")
    _require_prefixed_sha256(body.get("omega_frontier_plan_hash"), "omega_frontier_plan_hash")
    _require_count(body.get("omega_test_count"), "omega_test_count")
    _require_count(body.get("omega_skipped_tests"), "omega_skipped_tests")
    _require_count(body.get("full_test_count"), "full_test_count")
    _require_count(body.get("full_skipped_tests"), "full_skipped_tests")
    if body.get("v2_governed_files_unchanged") is not True:
        raise ValueError("Omega0 receipt requires unchanged V2 governed files")
    if body.get("v2_authority_validation") != "PASS":
        raise ValueError("Omega0 receipt requires V2 authority validation PASS")
    if body.get("promotion_authority") is not False:
        raise ValueError("Omega0 receipt cannot claim promotion authority")
    if body.get("language_stable") is not False:
        raise ValueError("Omega0 receipt cannot claim language stability")
    if body.get("certify_full") is not True:
        raise ValueError("Omega0 receipt requires certify_full=True")


def validate_external_receipt_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    root = ROOT.resolve()
    if candidate == root or root in candidate.parents:
        raise ValueError("Omega0 receipt path must be outside repository")
    if candidate.exists():
        raise ValueError("Omega0 receipt path is create-once and already exists")
    if not candidate.parent.exists() or not candidate.parent.is_dir():
        raise ValueError("Omega0 receipt parent must already exist and be a directory")
    return candidate


def _run(arguments: Sequence[str], *, timeout: int = 7200) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            tuple(arguments),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise Omega0CertificationFailure(
            "command timed out: " + repr(tuple(arguments))
        ) from error
    if completed.returncode != 0:
        combined = (completed.stdout + "\n" + completed.stderr)[-32768:]
        raise Omega0CertificationFailure(
            f"command failed exit={completed.returncode}: {tuple(arguments)!r}; output={combined}"
        )
    return completed


def _git(*arguments: str) -> str:
    return _run(("git", *arguments), timeout=60).stdout.strip()


def _sha256_file(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise Omega0CertificationFailure("missing certification input: " + relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_unittest_counts(completed: subprocess.CompletedProcess[str]) -> tuple[int, int]:
    combined = completed.stdout + "\n" + completed.stderr
    matches = _RAN.findall(combined)
    if len(matches) != 1:
        raise Omega0CertificationFailure("cannot determine unittest count")
    skipped_matches = _SKIPPED.findall(combined)
    skipped = int(skipped_matches[-1]) if skipped_matches else 0
    return int(matches[0]), skipped


def _run_omega_tests() -> tuple[int, int]:
    completed = _run((sys.executable, "-m", "unittest", "-v", *OMEGA_TEST_MODULES))
    return _parse_unittest_counts(completed)


def _run_full_regression() -> tuple[int, int]:
    completed = _run(
        (
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test*.py",
            "-v",
        )
    )
    return _parse_unittest_counts(completed)


def _v2_governed_paths() -> tuple[str, ...]:
    try:
        matrix = json.loads(
            (ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Omega0CertificationFailure("cannot load V2 feature matrix") from error
    if not isinstance(matrix, dict):
        raise Omega0CertificationFailure("V2 feature matrix must be an object")
    paths: set[str] = {"CANONICAL_INDEX.json", "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json"}
    for key in ("authority_files", "stable_tooling_authority"):
        values = matrix.get(key, [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise Omega0CertificationFailure("malformed V2 matrix path inventory: " + key)
        paths.update(values)
    governed = matrix.get("governed_paths")
    if not isinstance(governed, dict):
        raise Omega0CertificationFailure("missing V2 governed_paths")
    for group, values in governed.items():
        if not isinstance(group, str) or not isinstance(values, list) or any(
            not isinstance(item, str) for item in values
        ):
            raise Omega0CertificationFailure("malformed V2 governed path group")
        paths.update(values)
    return tuple(sorted(paths))


def _require_v2_governed_files_unchanged(head: str) -> None:
    for relative in _v2_governed_paths():
        base_row = _git("ls-tree", BASE_SHA, "--", relative)
        head_row = _git("ls-tree", head, "--", relative)
        if not base_row or base_row != head_row:
            raise Omega0CertificationFailure(
                "V2 governed file changed or missing: " + relative
            )


def _require_git_identity(expected_base: str) -> tuple[str, str, str]:
    if expected_base != BASE_SHA:
        raise Omega0CertificationFailure(
            f"expected base mismatch: expected={BASE_SHA} observed={expected_base}"
        )
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise Omega0CertificationFailure(
            f"Omega0 branch mismatch: expected={EXPECTED_BRANCH} observed={branch}"
        )
    dirty = _git("status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise Omega0CertificationFailure("Omega0 certification requires clean worktree")
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    base_tree = _git("rev-parse", BASE_SHA + "^{tree}")
    if base_tree != BASE_TREE:
        raise Omega0CertificationFailure("stable V2 base tree mismatch")
    ancestor = subprocess.run(
        ("git", "merge-base", "--is-ancestor", BASE_SHA, head),
        cwd=ROOT,
        check=False,
        capture_output=True,
        timeout=60,
    )
    if ancestor.returncode != 0:
        raise Omega0CertificationFailure("stable V2 base is not an ancestor of Omega0 head")
    origin_main = _git("rev-parse", "refs/remotes/origin/main")
    if origin_main != BASE_SHA:
        raise Omega0CertificationFailure(
            f"origin/main moved during Omega0 campaign: {origin_main}"
        )
    return branch, head, tree


def _require_frontier() -> dict[str, Any]:
    changed = probe.resolve_changed_paths()
    value = probe.plan(changed)
    if value.get("status") != "READY" or not probe.verify_plan(value):
        raise Omega0CertificationFailure("Omega0 causal frontier is not READY")
    return value


def certify(*, expected_base: str, receipt_out: str | Path) -> dict[str, Any]:
    output = validate_external_receipt_path(receipt_out)
    branch, head, tree = _require_git_identity(expected_base)
    frontier = _require_frontier()
    _require_v2_governed_files_unchanged(head)

    omega_count, omega_skips = _run_omega_tests()
    full_count, full_skips = _run_full_regression()
    if omega_skips != 0 or full_skips != 0:
        raise Omega0CertificationFailure(
            f"Omega0 certification requires zero skips: omega={omega_skips} full={full_skips}"
        )

    body = build_receipt_body(
        repository=REPOSITORY,
        branch=branch,
        commit_sha=head,
        tree_sha=tree,
        base_sha=BASE_SHA,
        base_tree_sha=BASE_TREE,
        omega_master_design_sha256=_sha256_file(DESIGN_PATH),
        omega_plan_sha256=_sha256_file(PLAN_PATH),
        omega_frontier_plan_hash=str(frontier["plan_hash"]),
        omega_test_count=omega_count,
        omega_skipped_tests=omega_skips,
        full_test_count=full_count,
        full_skipped_tests=full_skips,
        v2_governed_files_unchanged=True,
        v2_authority_validation="PASS",
    )
    receipt = seal_receipt(body)
    if not verify_receipt(receipt):
        raise Omega0CertificationFailure("generated Omega0 receipt failed self-verification")
    try:
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            stream.write("\n")
    except OSError as error:
        raise Omega0CertificationFailure("cannot write Omega0 receipt") from error
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEV Script Omega0 technical certification")
    parser.add_argument("--expected-base", required=True)
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = certify(expected_base=args.expected_base, receipt_out=args.receipt_out)
    except Exception as error:  # noqa: BLE001
        print("OMEGA0_CERTIFY_FULL=FAIL")
        print("OMEGA0_CERTIFY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print("OMEGA0_CERTIFY_FULL=PASS")
    print("OMEGA0_V2_GOVERNED_FILES_UNCHANGED=PASS")
    print("OMEGA0_PROMOTION_AUTHORITY=NO")
    print("OMEGA0_LANGUAGE_STABLE=NO")
    print("OMEGA0_RECEIPT_HASH=" + receipt["receipt_hash"])
    print("OMEGA0_RECEIPT_PATH=" + str(Path(args.receipt_out).expanduser().resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
