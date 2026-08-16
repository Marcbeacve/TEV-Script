from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence
import venv

import RUN_TEV_SCRIPT_V3_CERTIFY_FULL as technical
from tev_script.descriptor_v3 import v3_descriptor, verify_v3_descriptor
from tev_script import release_metadata_v3 as release

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_BRANCH = "agent/tev-script-omega-kernel-v1"
V2_AUTHORITY_PROFILE = technical.V2_AUTHORITY_PROFILE
SCHEMA = "TEV_SCRIPT_V3_STABLE_ADMISSION_RECEIPT_V1"
RELEASE_DIFF_WHITELIST = tuple(sorted((
    "CANONICAL_INDEX.json",
    "CHANGELOG.md",
    "README.md",
    "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json",
    "tev_script/release_metadata_v3.py",
)))
_HEX = frozenset("0123456789abcdef")

class V3StableAdmissionFailure(RuntimeError): pass

def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")

def _hash_body(value: Mapping[str, Any]) -> str: return hashlib.sha256(_canonical_bytes(dict(value))).hexdigest()
def _sha40(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in _HEX for c in value): raise ValueError(name)
    return value
def _sha64(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value): raise ValueError(name)
    return value
def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1: raise ValueError(name)
    return value

def verify_release_diff_paths(paths: Sequence[str]) -> bool:
    try:
        if isinstance(paths, (str, bytes)): return False
        observed = tuple(sorted(dict.fromkeys(str(p).replace("\\", "/") for p in paths)))
        return observed == RELEASE_DIFF_WHITELIST and len(observed) == len(tuple(paths))
    except Exception:
        return False

def build_receipt_body(
    *, repository: str, branch: str, technical_parent_commit: str,
    technical_parent_receipt_sha256: str, release_commit_sha: str, release_tree_sha: str,
    release_diff_hash: str, descriptor_hash: str, v3_test_count: int,
    v3_skipped_tests: int, full_test_count: int, full_skipped_tests: int,
    wheel_filename: str, wheel_sha256: str, wheel_reproducible: bool,
    installed_v3_smoke: str, installed_v2_compatibility: str,
) -> dict[str, Any]:
    if repository != REPOSITORY or branch != EXPECTED_BRANCH: raise ValueError("identity")
    if v3_skipped_tests or full_skipped_tests: raise ValueError("zero skips required")
    if wheel_reproducible is not True: raise ValueError("wheel reproducibility")
    if not isinstance(wheel_filename, str) or not wheel_filename.endswith("-3.0.0-py3-none-any.whl"): raise ValueError("wheel filename")
    if installed_v3_smoke != "PASS" or installed_v2_compatibility != "PASS": raise ValueError("installed smoke")
    return {
        "schema": SCHEMA, "language_version": "3.0.0", "repository": repository, "branch": branch,
        "technical_parent_commit": _sha40(technical_parent_commit, "technical_parent_commit"),
        "technical_parent_receipt_sha256": _sha64(technical_parent_receipt_sha256, "technical_parent_receipt_sha256"),
        "release_commit_sha": _sha40(release_commit_sha, "release_commit_sha"),
        "release_tree_sha": _sha40(release_tree_sha, "release_tree_sha"),
        "release_diff_hash": _sha64(release_diff_hash, "release_diff_hash"),
        "descriptor_hash": _sha64(descriptor_hash, "descriptor_hash"),
        "v3_test_count": _count(v3_test_count, "v3_test_count"), "v3_skipped_tests": 0,
        "full_test_count": _count(full_test_count, "full_test_count"), "full_skipped_tests": 0,
        "wheel_filename": wheel_filename, "wheel_sha256": _sha64(wheel_sha256, "wheel_sha256"),
        "wheel_reproducible": True, "installed_v3_smoke": "PASS", "installed_v2_compatibility": "PASS",
        "stable_admission": True, "language_stable": True, "publication_authorized": True,
        "merge_authority": False,
    }

def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    stable = dict(body)
    if "receipt_hash" in stable: raise ValueError("receipt_hash already present")
    return {**stable, "receipt_hash": _hash_body(stable)}
def verify_receipt(value: Mapping[str, Any]) -> bool:
    try:
        body = dict(value); digest = body.pop("receipt_hash")
        if not isinstance(digest, str) or not hmac.compare_digest(digest, _hash_body(body)): return False
        expected = build_receipt_body(
            repository=body["repository"], branch=body["branch"], technical_parent_commit=body["technical_parent_commit"],
            technical_parent_receipt_sha256=body["technical_parent_receipt_sha256"], release_commit_sha=body["release_commit_sha"],
            release_tree_sha=body["release_tree_sha"], release_diff_hash=body["release_diff_hash"], descriptor_hash=body["descriptor_hash"],
            v3_test_count=body["v3_test_count"], v3_skipped_tests=body["v3_skipped_tests"], full_test_count=body["full_test_count"],
            full_skipped_tests=body["full_skipped_tests"], wheel_filename=body["wheel_filename"], wheel_sha256=body["wheel_sha256"],
            wheel_reproducible=body["wheel_reproducible"], installed_v3_smoke=body["installed_v3_smoke"],
            installed_v2_compatibility=body["installed_v2_compatibility"],
        )
        return _canonical_bytes(body) == _canonical_bytes(expected)
    except (KeyError, TypeError, ValueError, OverflowError): return False

def validate_artifact_dir(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(); root = ROOT.resolve()
    if candidate == root or root in candidate.parents: raise ValueError("artifact dir must be outside repository")
    if not candidate.is_dir(): raise ValueError("artifact dir must exist")
    if any(candidate.iterdir()): raise ValueError("artifact dir must be empty")
    return candidate

def _run(args: Sequence[str], *, timeout: int = 7200, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    try: result = subprocess.run(tuple(args), cwd=ROOT if cwd is None else cwd, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc: raise V3StableAdmissionFailure("command timeout") from exc
    if result.returncode != 0: raise V3StableAdmissionFailure((result.stdout + "\n" + result.stderr)[-32768:])
    return result
def _git(*args: str) -> str: return _run(("git", *args), timeout=60).stdout.strip()
def _parse_counts(result: subprocess.CompletedProcess[str]) -> tuple[int, int]:
    import re
    text = result.stdout + "\n" + result.stderr
    ran = re.findall(r"Ran\s+(\d+)\s+tests?", text); skipped = re.findall(r"skipped=(\d+)", text)
    if len(ran) != 1: raise V3StableAdmissionFailure("cannot parse test count")
    return int(ran[0]), int(skipped[-1]) if skipped else 0

def _load_technical_certificate(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes(); file_sha = hashlib.sha256(data).hexdigest()
    try: value = json.loads(data.decode("utf-8"))
    except Exception as exc: raise V3StableAdmissionFailure("technical certificate invalid JSON") from exc
    if not isinstance(value, dict) or not technical.verify_receipt(value): raise V3StableAdmissionFailure("technical certificate verification failed")
    return value, file_sha

def _require_release_identity(parent: str) -> tuple[str, str, tuple[str, ...]]:
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH: raise V3StableAdmissionFailure("branch mismatch")
    if _git("status", "--porcelain=v1", "--untracked-files=all"): raise V3StableAdmissionFailure("clean worktree required")
    head, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    if _git("rev-parse", "HEAD^") != parent: raise V3StableAdmissionFailure("release commit must be direct child of technical parent")
    paths = tuple(sorted(filter(None, _git("diff", "--name-only", parent + "..HEAD", "--").splitlines())))
    if not verify_release_diff_paths(paths): raise V3StableAdmissionFailure("release diff whitelist mismatch")
    return head, tree, paths

def _load_backend():
    path = ROOT / "packaging/v3/tools/tev_script_build_backend_v3.py"
    spec = importlib.util.spec_from_file_location("tev_script_build_backend_v3_stable", path)
    if spec is None or spec.loader is None: raise V3StableAdmissionFailure("cannot load V3 backend")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def _build_final_wheel(artifact_dir: Path) -> tuple[Path, str]:
    backend = _load_backend(); old = os.environ.get("SOURCE_DATE_EPOCH"); os.environ["SOURCE_DATE_EPOCH"] = technical.V3_WHEEL_SOURCE_DATE_EPOCH
    try:
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            n1, n2 = backend.build_wheel(a), backend.build_wheel(b)
            left, right = (Path(a)/n1).read_bytes(), (Path(b)/n2).read_bytes()
            if n1 != n2 or left != right: raise V3StableAdmissionFailure("final wheel is not reproducible")
            target = artifact_dir / n1; target.write_bytes(left)
            return target, hashlib.sha256(left).hexdigest()
    finally:
        if old is None: os.environ.pop("SOURCE_DATE_EPOCH", None)
        else: os.environ["SOURCE_DATE_EPOCH"] = old

def _installed_smoke(wheel: Path) -> tuple[str, str]:
    with tempfile.TemporaryDirectory() as directory:
        env = Path(directory) / "venv"; venv.EnvBuilder(with_pip=True, clear=True).create(env)
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _run((str(python), "-m", "pip", "install", "--no-deps", str(wheel)), timeout=1800)
        v3 = _run((str(python), "-m", "tev_script.describe_v3"), timeout=120)
        descriptor = json.loads(v3.stdout)
        if descriptor.get("language_version") != "3.0.0" or descriptor.get("stable") is not True: raise V3StableAdmissionFailure("installed V3 descriptor not stable")
        _run((str(python), "-m", "tev_script.cli_v2", "descriptor"), timeout=120)
        return "PASS", "PASS"
def certify(*, technical_parent_certificate: str | Path, artifact_out_dir: str | Path) -> dict[str, Any]:
    artifacts = validate_artifact_dir(artifact_out_dir)
    metadata = release.validate_release_metadata_v3()
    if metadata["release_profile"] != "stable_request" or metadata["stable"] is not True: raise V3StableAdmissionFailure("stable-request metadata required")
    cert_path = Path(technical_parent_certificate).expanduser().resolve(); tech, file_sha = _load_technical_certificate(cert_path)
    if tech["commit_sha"] != release.TECHNICAL_PARENT_COMMIT: raise V3StableAdmissionFailure("technical parent commit mismatch")
    if file_sha != release.TECHNICAL_PARENT_RECEIPT_SHA256: raise V3StableAdmissionFailure("technical parent certificate file hash mismatch")
    head, tree, paths = _require_release_identity(release.TECHNICAL_PARENT_COMMIT)
    descriptor = v3_descriptor()
    if not verify_v3_descriptor(descriptor) or descriptor["stable"] is not True: raise V3StableAdmissionFailure("stable descriptor invalid")
    v3_result = _run((sys.executable, "-m", "unittest", "-v", *technical.V3_TEST_MODULES)); v3_count, v3_skips = _parse_counts(v3_result)
    full_result = _run((sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py", "-v")); full_count, full_skips = _parse_counts(full_result)
    if v3_skips or full_skips: raise V3StableAdmissionFailure("zero skips required")
    _run((sys.executable, "tools/validate_v2_authority.py", "--profile", V2_AUTHORITY_PROFILE), timeout=1800)
    wheel, wheel_sha = _build_final_wheel(artifacts)
    v3_smoke, v2_smoke = _installed_smoke(wheel)
    diff_hash = hashlib.sha256(_canonical_bytes(list(paths))).hexdigest()
    body = build_receipt_body(
        repository=REPOSITORY, branch=EXPECTED_BRANCH, technical_parent_commit=release.TECHNICAL_PARENT_COMMIT,
        technical_parent_receipt_sha256=file_sha, release_commit_sha=head, release_tree_sha=tree,
        release_diff_hash=diff_hash, descriptor_hash=str(descriptor["descriptor_hash"]), v3_test_count=v3_count,
        v3_skipped_tests=v3_skips, full_test_count=full_count, full_skipped_tests=full_skips,
        wheel_filename=wheel.name, wheel_sha256=wheel_sha, wheel_reproducible=True,
        installed_v3_smoke=v3_smoke, installed_v2_compatibility=v2_smoke,
    )
    receipt = seal_receipt(body)
    if not verify_receipt(receipt): raise V3StableAdmissionFailure("stable receipt self-verification failed")
    receipt_path = artifacts / "TEV_SCRIPT_V3_STABLE_ADMISSION_RECEIPT_V1.json"
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)+"\n", encoding="utf-8")
    return receipt

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="TEVScript MAX V3 Stable Admission")
    parser.add_argument("--technical-parent-certificate", required=True); parser.add_argument("--artifact-out-dir", required=True)
    args=parser.parse_args(argv)
    try: receipt=certify(technical_parent_certificate=args.technical_parent_certificate, artifact_out_dir=args.artifact_out_dir)
    except Exception as error:
        print("V3_STABLE_ADMISSION=FAIL"); print("V3_STABLE_ADMISSION_ERROR="+type(error).__name__+":"+str(error)); return 1
    print("V3_STABLE_ADMISSION=PASS"); print("V3_LANGUAGE_STABLE=YES"); print("V3_PUBLICATION_AUTHORIZED=YES"); print("V3_MERGE_AUTHORITY=NO"); print("V3_STABLE_RECEIPT_HASH="+receipt["receipt_hash"]); return 0
if __name__ == "__main__": raise SystemExit(main())
