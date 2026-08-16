from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

from tools import tevprober_max_v3_basis_frontier as frontier
from tools.tevprober_max_basis_v1 import evaluate_basis, verify_basis_report

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_BRANCH = "agent/tev-script-omega-kernel-v1"
LANGUAGE_VERSION = "3.0.0"
SCHEMA = "TEV_SCRIPT_MAX_V3_BASIS_CERTIFY_RECEIPT_V1"
OMEGA0_BASE_SHA = frontier.OMEGA0_BASE_SHA
OMEGA0_BASE_TREE = frontier.OMEGA0_BASE_TREE
V2_BASE_SHA = frontier.V2_BASE_SHA
V2_AUTHORITY_PROFILE = "stable"
DESIGN_PATH = "docs/superpowers/specs/2026-08-16-tevscript-max-v3-primitive-basis-design.md"
PLAN_PATH = "docs/superpowers/plans/2026-08-16-tevscript-max-v3-primitive-basis.md"

OMEGA0_PATHS = (
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
BASIS_TEST_MODULES = (
    "tests.test_omega_semantic_basis_v1",
    "tests.test_tevprober_max_basis_v1",
    "tests.test_max_v3_basis_certify",
)
OMEGA0_TEST_MODULES = (
    "tests.test_omega_kernel_v1",
    "tests.test_omega_v2_adapter_v1",
    "tests.test_tevprober_omega0",
    "tests.test_omega0_certify",
)
_RAN = re.compile(r"Ran\s+(\d+)\s+tests?")
_SKIPPED = re.compile(r"skipped=(\d+)")
_HEX = frozenset("0123456789abcdef")


class MaxV3BasisCertificationFailure(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _hash_body(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(dict(value))).hexdigest()


def _sha40(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(char not in _HEX for char in value):
        raise ValueError(name + " must be lowercase 40-hex")
    return value


def _sha64(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        raise ValueError(name + " must be lowercase 64-hex")
    return value


def _prefixed_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError(name + " must be sha256-prefixed")
    _sha64(value.removeprefix("sha256:"), name)
    return value


def _positive_count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(name + " must be a positive integer")
    return value


def build_receipt_body(
    *,
    repository: str,
    branch: str,
    commit_sha: str,
    tree_sha: str,
    omega0_base_sha: str,
    omega0_base_tree_sha: str,
    v2_base_sha: str,
    design_sha256: str,
    plan_sha256: str,
    frontier_plan_hash: str,
    basis_report_hash: str,
    basis_test_count: int,
    basis_skipped_tests: int,
    omega0_test_count: int,
    omega0_skipped_tests: int,
    full_test_count: int,
    full_skipped_tests: int,
    v2_governed_files_unchanged: bool,
    omega0_files_unchanged: bool,
    v2_authority_validation: str,
) -> dict[str, Any]:
    if repository != REPOSITORY:
        raise ValueError("repository identity mismatch")
    if branch != EXPECTED_BRANCH:
        raise ValueError("branch identity mismatch")
    if omega0_base_sha != OMEGA0_BASE_SHA or omega0_base_tree_sha != OMEGA0_BASE_TREE:
        raise ValueError("Omega0 base identity mismatch")
    if v2_base_sha != V2_BASE_SHA:
        raise ValueError("V2 base identity mismatch")
    if basis_skipped_tests != 0 or omega0_skipped_tests != 0 or full_skipped_tests != 0:
        raise ValueError("MAX V3 basis certification requires zero skips")
    if v2_governed_files_unchanged is not True or omega0_files_unchanged is not True:
        raise ValueError("MAX V3 basis certification requires immutable V2 and Omega0 authorities")
    if v2_authority_validation != "PASS":
        raise ValueError("MAX V3 basis certification requires V2 authority PASS")
    return {
        "schema": SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "repository": repository,
        "branch": branch,
        "commit_sha": _sha40(commit_sha, "commit_sha"),
        "tree_sha": _sha40(tree_sha, "tree_sha"),
        "omega0_base_sha": omega0_base_sha,
        "omega0_base_tree_sha": omega0_base_tree_sha,
        "v2_base_sha": v2_base_sha,
        "design_sha256": _sha64(design_sha256, "design_sha256"),
        "plan_sha256": _sha64(plan_sha256, "plan_sha256"),
        "frontier_plan_hash": _prefixed_sha256(frontier_plan_hash, "frontier_plan_hash"),
        "basis_report_hash": _sha64(basis_report_hash, "basis_report_hash"),
        "basis_test_count": _positive_count(basis_test_count, "basis_test_count"),
        "basis_skipped_tests": 0,
        "omega0_test_count": _positive_count(omega0_test_count, "omega0_test_count"),
        "omega0_skipped_tests": 0,
        "full_test_count": _positive_count(full_test_count, "full_test_count"),
        "full_skipped_tests": 0,
        "v2_governed_files_unchanged": True,
        "omega0_files_unchanged": True,
        "v2_authority_validation": "PASS",
        "promotion_authority": False,
        "language_stable": False,
        "certify_full": True,
    }


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    stable = dict(body)
    if "receipt_hash" in stable:
        raise ValueError("receipt body must not already contain receipt_hash")
    return {**stable, "receipt_hash": _hash_body(stable)}


def verify_receipt(value: Mapping[str, Any]) -> bool:
    try:
        observed = dict(value)
        receipt_hash = observed.pop("receipt_hash")
        if not isinstance(receipt_hash, str) or not hmac.compare_digest(receipt_hash, _hash_body(observed)):
            return False
        expected = build_receipt_body(
            repository=observed["repository"],
            branch=observed["branch"],
            commit_sha=observed["commit_sha"],
            tree_sha=observed["tree_sha"],
            omega0_base_sha=observed["omega0_base_sha"],
            omega0_base_tree_sha=observed["omega0_base_tree_sha"],
            v2_base_sha=observed["v2_base_sha"],
            design_sha256=observed["design_sha256"],
            plan_sha256=observed["plan_sha256"],
            frontier_plan_hash=observed["frontier_plan_hash"],
            basis_report_hash=observed["basis_report_hash"],
            basis_test_count=observed["basis_test_count"],
            basis_skipped_tests=observed["basis_skipped_tests"],
            omega0_test_count=observed["omega0_test_count"],
            omega0_skipped_tests=observed["omega0_skipped_tests"],
            full_test_count=observed["full_test_count"],
            full_skipped_tests=observed["full_skipped_tests"],
            v2_governed_files_unchanged=observed["v2_governed_files_unchanged"],
            omega0_files_unchanged=observed["omega0_files_unchanged"],
            v2_authority_validation=observed["v2_authority_validation"],
        )
        return _canonical_bytes(observed) == _canonical_bytes(expected)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def validate_external_receipt_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    root = ROOT.resolve()
    if candidate == root or root in candidate.parents:
        raise ValueError("MAX V3 basis receipt path must be outside repository")
    if candidate.exists():
        raise ValueError("MAX V3 basis receipt path is create-once and already exists")
    if not candidate.parent.exists() or not candidate.parent.is_dir():
        raise ValueError("MAX V3 basis receipt parent must already exist")
    return candidate


def _run(arguments: Sequence[str], *, timeout: int = 7200) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            tuple(arguments), cwd=ROOT, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise MaxV3BasisCertificationFailure("command timed out: " + repr(tuple(arguments))) from error
    if completed.returncode != 0:
        output = (completed.stdout + "\n" + completed.stderr)[-32768:]
        raise MaxV3BasisCertificationFailure(
            f"command failed exit={completed.returncode}: {tuple(arguments)!r}; output={output}"
        )
    return completed


def _git(*arguments: str) -> str:
    return _run(("git", *arguments), timeout=60).stdout.strip()


def _sha256_file(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise MaxV3BasisCertificationFailure("missing certification input: " + relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_unittest_counts(completed: subprocess.CompletedProcess[str]) -> tuple[int, int]:
    combined = completed.stdout + "\n" + completed.stderr
    matches = _RAN.findall(combined)
    if len(matches) != 1:
        raise MaxV3BasisCertificationFailure("cannot determine unittest count")
    skipped_matches = _SKIPPED.findall(combined)
    skipped = int(skipped_matches[-1]) if skipped_matches else 0
    return int(matches[0]), skipped


def _run_unittest_modules(modules: Sequence[str]) -> tuple[int, int]:
    return _parse_unittest_counts(
        _run((sys.executable, "-m", "unittest", "-v", *tuple(modules)))
    )


def _run_full_regression() -> tuple[int, int]:
    return _parse_unittest_counts(
        _run((sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py", "-v"))
    )


def _v2_governed_paths() -> tuple[str, ...]:
    try:
        matrix = json.loads((ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MaxV3BasisCertificationFailure("cannot load V2 feature matrix") from error
    if not isinstance(matrix, dict):
        raise MaxV3BasisCertificationFailure("V2 feature matrix must be an object")
    paths: set[str] = {"CANONICAL_INDEX.json", "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json"}
    for key in ("authority_files", "stable_tooling_authority"):
        values = matrix.get(key, [])
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise MaxV3BasisCertificationFailure("malformed V2 matrix path inventory: " + key)
        paths.update(values)
    governed = matrix.get("governed_paths")
    if not isinstance(governed, dict):
        raise MaxV3BasisCertificationFailure("missing V2 governed_paths")
    for values in governed.values():
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise MaxV3BasisCertificationFailure("malformed V2 governed path group")
        paths.update(values)
    return tuple(sorted(paths))


def _require_paths_unchanged(base: str, head: str, paths: Sequence[str], label: str) -> None:
    for relative in paths:
        base_row = _git("ls-tree", base, "--", relative)
        head_row = _git("ls-tree", head, "--", relative)
        if not base_row or base_row != head_row:
            raise MaxV3BasisCertificationFailure(f"{label} changed or missing: {relative}")


def _require_git_identity(expected_omega0_base: str) -> tuple[str, str, str]:
    if expected_omega0_base != OMEGA0_BASE_SHA:
        raise MaxV3BasisCertificationFailure("expected Omega0 base mismatch")
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise MaxV3BasisCertificationFailure(f"branch mismatch: {branch}")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise MaxV3BasisCertificationFailure("certification requires clean worktree")
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    if _git("rev-parse", OMEGA0_BASE_SHA + "^{tree}") != OMEGA0_BASE_TREE:
        raise MaxV3BasisCertificationFailure("Omega0 base tree mismatch")
    ancestor = subprocess.run(
        ("git", "merge-base", "--is-ancestor", OMEGA0_BASE_SHA, head),
        cwd=ROOT, check=False, capture_output=True, timeout=60,
    )
    if ancestor.returncode != 0:
        raise MaxV3BasisCertificationFailure("Omega0 base is not ancestor")
    origin_main = _git("rev-parse", "refs/remotes/origin/main")
    if origin_main != V2_BASE_SHA:
        raise MaxV3BasisCertificationFailure("origin/main moved; rebase/review required")
    return branch, head, tree


def certify(*, expected_omega0_base: str, receipt_out: str | Path) -> dict[str, Any]:
    output = validate_external_receipt_path(receipt_out)
    branch, head, tree = _require_git_identity(expected_omega0_base)
    changed = frontier.resolve_changed_paths()
    frontier_report = frontier.plan(changed)
    if frontier_report.get("status") != "READY" or not frontier.verify_plan(frontier_report):
        raise MaxV3BasisCertificationFailure("MAX V3 basis frontier is not READY")

    _require_paths_unchanged(V2_BASE_SHA, head, _v2_governed_paths(), "V2 governed file")
    _require_paths_unchanged(OMEGA0_BASE_SHA, head, OMEGA0_PATHS, "Omega0 file")

    basis_report = evaluate_basis()
    if basis_report.get("status") != "PASS" or not verify_basis_report(basis_report):
        raise MaxV3BasisCertificationFailure("primitive basis probe did not PASS")

    basis_count, basis_skips = _run_unittest_modules(BASIS_TEST_MODULES)
    omega_count, omega_skips = _run_unittest_modules(OMEGA0_TEST_MODULES)
    _run((sys.executable, "tools/validate_v2_authority.py", "--profile", V2_AUTHORITY_PROFILE), timeout=1800)
    full_count, full_skips = _run_full_regression()
    if basis_skips or omega_skips or full_skips:
        raise MaxV3BasisCertificationFailure(
            f"zero skips required: basis={basis_skips} omega0={omega_skips} full={full_skips}"
        )

    body = build_receipt_body(
        repository=REPOSITORY,
        branch=branch,
        commit_sha=head,
        tree_sha=tree,
        omega0_base_sha=OMEGA0_BASE_SHA,
        omega0_base_tree_sha=OMEGA0_BASE_TREE,
        v2_base_sha=V2_BASE_SHA,
        design_sha256=_sha256_file(DESIGN_PATH),
        plan_sha256=_sha256_file(PLAN_PATH),
        frontier_plan_hash=str(frontier_report["plan_hash"]),
        basis_report_hash=str(basis_report["report_hash"]),
        basis_test_count=basis_count,
        basis_skipped_tests=basis_skips,
        omega0_test_count=omega_count,
        omega0_skipped_tests=omega_skips,
        full_test_count=full_count,
        full_skipped_tests=full_skips,
        v2_governed_files_unchanged=True,
        omega0_files_unchanged=True,
        v2_authority_validation="PASS",
    )
    receipt = seal_receipt(body)
    if not verify_receipt(receipt):
        raise MaxV3BasisCertificationFailure("generated receipt failed self-verification")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        stream.write("\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEVScript MAX V3 primitive basis technical certification")
    parser.add_argument("--expected-omega0-base", required=True)
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = certify(
            expected_omega0_base=args.expected_omega0_base,
            receipt_out=args.receipt_out,
        )
    except Exception as error:  # noqa: BLE001
        print("MAX_V3_BASIS_CERTIFY_FULL=FAIL")
        print("MAX_V3_BASIS_CERTIFY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print("MAX_V3_BASIS_CERTIFY_FULL=PASS")
    print("MAX_V3_BASIS_V2_UNCHANGED=PASS")
    print("MAX_V3_BASIS_OMEGA0_UNCHANGED=PASS")
    print("MAX_V3_BASIS_PROMOTION_AUTHORITY=NO")
    print("MAX_V3_BASIS_LANGUAGE_STABLE=NO")
    print("MAX_V3_BASIS_RECEIPT_HASH=" + receipt["receipt_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
