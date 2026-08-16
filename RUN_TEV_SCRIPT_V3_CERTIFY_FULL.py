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

from tev_script.descriptor_v3 import v3_descriptor, verify_v3_descriptor
from tev_script.release_metadata_v3 import validate_release_metadata_v3
from tools.tevprober_max_basis_v1 import evaluate_basis, verify_basis_report

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_BRANCH = "agent/tev-script-omega-kernel-v1"
V2_BASE_SHA = "2bdb047dcad41f9d112219bd65925c25668c02e0"
LANGUAGE_VERSION = "3.0.0"
SCHEMA = "TEV_SCRIPT_V3_CERTIFY_FULL_RECEIPT_V1"
FEATURE_MATRIX_PATH = "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json"
V3_TEST_MODULES = (
    "tests.test_omega_semantic_basis_v1",
    "tests.test_omega_type_effect_v1",
    "tests.test_program_ir_v5_semantic",
    "tests.test_runtime_v5_semantic",
    "tests.test_semantic_stdlib_v1",
    "tests.test_source_semantic_process_v3",
    "tests.test_translation_validation_v3",
    "tests.test_cli_v3",
    "tests.test_tevprober_max_basis_v1",
    "tests.test_v3_schemas_metadata",
    "tests.test_v3_certify_full",
)
_RAN = re.compile(r"Ran\s+(\d+)\s+tests?")
_SKIPPED = re.compile(r"skipped=(\d+)")
_HEX = frozenset("0123456789abcdef")


class V3CertificationFailure(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _hash_body(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(dict(value))).hexdigest()


def _sha40(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in _HEX for c in value):
        raise ValueError(name + " must be lowercase 40-hex")
    return value


def _sha64(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise ValueError(name + " must be lowercase 64-hex")
    return value


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(name + " must be positive integer")
    return value


def build_receipt_body(
    *, repository: str, branch: str, commit_sha: str, tree_sha: str,
    v2_base_sha: str, feature_matrix_sha256: str, descriptor_hash: str,
    basis_report_hash: str, v3_test_count: int, v3_skipped_tests: int,
    full_test_count: int, full_skipped_tests: int,
    schema_validation: str, v2_authority_validation: str,
) -> dict[str, Any]:
    if repository != REPOSITORY or branch != EXPECTED_BRANCH:
        raise ValueError("repository/branch identity mismatch")
    if v2_base_sha != V2_BASE_SHA:
        raise ValueError("V2 base identity mismatch")
    if v3_skipped_tests != 0 or full_skipped_tests != 0:
        raise ValueError("V3 certification requires zero skips")
    if schema_validation != "PASS" or v2_authority_validation != "PASS":
        raise ValueError("V3 certification requires schema and V2 authority PASS")
    return {
        "schema": SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "repository": repository,
        "branch": branch,
        "commit_sha": _sha40(commit_sha, "commit_sha"),
        "tree_sha": _sha40(tree_sha, "tree_sha"),
        "v2_base_sha": v2_base_sha,
        "feature_matrix_sha256": _sha64(feature_matrix_sha256, "feature_matrix_sha256"),
        "descriptor_hash": _sha64(descriptor_hash, "descriptor_hash"),
        "basis_report_hash": _sha64(basis_report_hash, "basis_report_hash"),
        "v3_test_count": _count(v3_test_count, "v3_test_count"),
        "v3_skipped_tests": 0,
        "full_test_count": _count(full_test_count, "full_test_count"),
        "full_skipped_tests": 0,
        "schema_validation": "PASS",
        "v2_authority_validation": "PASS",
        "package_release_shape": "DEFERRED_TO_STABLE_ADMISSION",
        "promotion_authority": False,
        "language_stable": False,
        "certify_full": True,
    }


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    stable = dict(body)
    if "receipt_hash" in stable:
        raise ValueError("receipt body already contains receipt_hash")
    return {**stable, "receipt_hash": _hash_body(stable)}


def verify_receipt(value: Mapping[str, Any]) -> bool:
    try:
        observed = dict(value)
        digest = observed.pop("receipt_hash")
        if not isinstance(digest, str) or not hmac.compare_digest(digest, _hash_body(observed)):
            return False
        expected = build_receipt_body(
            repository=observed["repository"], branch=observed["branch"],
            commit_sha=observed["commit_sha"], tree_sha=observed["tree_sha"],
            v2_base_sha=observed["v2_base_sha"], feature_matrix_sha256=observed["feature_matrix_sha256"],
            descriptor_hash=observed["descriptor_hash"], basis_report_hash=observed["basis_report_hash"],
            v3_test_count=observed["v3_test_count"], v3_skipped_tests=observed["v3_skipped_tests"],
            full_test_count=observed["full_test_count"], full_skipped_tests=observed["full_skipped_tests"],
            schema_validation=observed["schema_validation"], v2_authority_validation=observed["v2_authority_validation"],
        )
        return _canonical_bytes(observed) == _canonical_bytes(expected)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def validate_external_receipt_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    root = ROOT.resolve()
    if candidate == root or root in candidate.parents:
        raise ValueError("V3 certification receipt must be outside repository")
    if candidate.exists():
        raise ValueError("V3 certification receipt is create-once")
    if not candidate.parent.exists() or not candidate.parent.is_dir():
        raise ValueError("V3 certification receipt parent must exist")
    return candidate


def _run(arguments: Sequence[str], *, timeout: int = 7200) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(tuple(arguments), cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise V3CertificationFailure("command timed out: " + repr(tuple(arguments))) from error
    if completed.returncode != 0:
        output = (completed.stdout + "\n" + completed.stderr)[-32768:]
        raise V3CertificationFailure(f"command failed exit={completed.returncode}: {tuple(arguments)!r}; output={output}")
    return completed


def _git(*arguments: str) -> str:
    return _run(("git", *arguments), timeout=60).stdout.strip()


def _parse_counts(completed: subprocess.CompletedProcess[str]) -> tuple[int, int]:
    text = completed.stdout + "\n" + completed.stderr
    matches = _RAN.findall(text)
    if len(matches) != 1:
        raise V3CertificationFailure("cannot determine unittest count")
    skipped_matches = _SKIPPED.findall(text)
    skipped = int(skipped_matches[-1]) if skipped_matches else 0
    return int(matches[0]), skipped


def _run_modules(modules: Sequence[str]) -> tuple[int, int]:
    return _parse_counts(_run((sys.executable, "-m", "unittest", "-v", *tuple(modules))))


def _run_full() -> tuple[int, int]:
    return _parse_counts(_run((sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py", "-v")))


def _require_git_identity() -> tuple[str, str, str]:
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise V3CertificationFailure("branch mismatch: " + branch)
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise V3CertificationFailure("certification requires clean worktree")
    head, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    if subprocess.run(("git", "merge-base", "--is-ancestor", V2_BASE_SHA, head), cwd=ROOT, check=False, capture_output=True, timeout=60).returncode != 0:
        raise V3CertificationFailure("V2 base is not ancestor")
    origin_main = _git("rev-parse", "refs/remotes/origin/main")
    if origin_main != V2_BASE_SHA:
        raise V3CertificationFailure("origin/main moved; review/rebase required")
    return branch, head, tree


def _sha256_file(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise V3CertificationFailure("missing certification input: " + relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certify(*, receipt_out: str | Path) -> dict[str, Any]:
    output = validate_external_receipt_path(receipt_out)
    metadata = validate_release_metadata_v3()
    if metadata["release_profile"] != "candidate" or metadata["stable"] is not False:
        raise V3CertificationFailure("technical certification requires candidate release metadata")
    branch, head, tree = _require_git_identity()
    descriptor = v3_descriptor()
    if not verify_v3_descriptor(descriptor) or descriptor["stable"] is not False:
        raise V3CertificationFailure("V3 descriptor candidate contract invalid")
    basis = evaluate_basis()
    if basis.get("status") != "PASS" or not verify_basis_report(basis):
        raise V3CertificationFailure("MAX primitive basis probe did not PASS")
    v3_count, v3_skips = _run_modules(V3_TEST_MODULES)
    _run((sys.executable, "tools/validate_v2_authority.py"), timeout=1800)
    full_count, full_skips = _run_full()
    if v3_skips or full_skips:
        raise V3CertificationFailure(f"zero skips required: v3={v3_skips} full={full_skips}")
    body = build_receipt_body(
        repository=REPOSITORY, branch=branch, commit_sha=head, tree_sha=tree,
        v2_base_sha=V2_BASE_SHA,
        feature_matrix_sha256=_sha256_file(FEATURE_MATRIX_PATH),
        descriptor_hash=str(descriptor["descriptor_hash"]),
        basis_report_hash=str(basis["report_hash"]),
        v3_test_count=v3_count, v3_skipped_tests=v3_skips,
        full_test_count=full_count, full_skipped_tests=full_skips,
        schema_validation="PASS", v2_authority_validation="PASS",
    )
    receipt = seal_receipt(body)
    if not verify_receipt(receipt):
        raise V3CertificationFailure("generated receipt failed self-verification")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        stream.write("\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEVScript MAX V3 technical certification")
    parser.add_argument("--receipt-out", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = certify(receipt_out=args.receipt_out)
    except Exception as error:  # noqa: BLE001
        print("V3_CERTIFY_FULL=FAIL")
        print("V3_CERTIFY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print("V3_CERTIFY_FULL=PASS")
    print("V3_LANGUAGE_STABLE=NO")
    print("V3_PROMOTION_AUTHORITY=NO")
    print("V3_RECEIPT_HASH=" + receipt["receipt_hash"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
