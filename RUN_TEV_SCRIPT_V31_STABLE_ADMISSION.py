from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence
import venv

import RUN_TEV_SCRIPT_V31_CERTIFY_FULL as technical
from tev_script.descriptor_v31 import v31_descriptor, verify_v31_descriptor
from tev_script import release_metadata_v31 as release


ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_BRANCH = "agent/tevscript-max-3-1-total-core-v1"
SCHEMA = "TEV_SCRIPT_V31_STABLE_ADMISSION_RECEIPT_V1"
V31_WHEEL_SOURCE_DATE_EPOCH = "1700000000"
RELEASE_DIFF_WHITELIST = tuple(
    sorted(
        (
            "CANONICAL_INDEX.json",
            "CHANGELOG.md",
            "README.md",
            "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json",
            "tev_script/release_metadata_v31.py",
        )
    )
)
_HEX = frozenset("0123456789abcdef")
_PASSED = re.compile(r"(?P<count>[0-9]+)\s+passed\b")
_SKIPPED = re.compile(r"(?P<count>[0-9]+)\s+skipped\b")


class V31StableAdmissionFailure(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _hash_body(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


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


def verify_release_diff_paths(paths: Sequence[str]) -> bool:
    try:
        if isinstance(paths, (str, bytes)):
            return False
        original = tuple(paths)
        normalized = tuple(
            sorted(dict.fromkeys(str(path).replace("\\", "/") for path in original))
        )
        return normalized == RELEASE_DIFF_WHITELIST and len(normalized) == len(original)
    except Exception:
        return False


def build_receipt_body(
    *,
    repository: str,
    branch: str,
    technical_parent_commit: str,
    technical_parent_receipt_sha256: str,
    release_commit_sha: str,
    release_tree_sha: str,
    release_diff_hash: str,
    descriptor_hash: str,
    full_test_count: int,
    full_skipped_tests: int,
    wheel_filename: str,
    wheel_sha256: str,
    wheel_reproducible: bool,
    installed_v31_smoke: str,
    installed_v3_compatibility: str,
    installed_v2_compatibility: str,
) -> dict[str, Any]:
    if repository != REPOSITORY or branch != EXPECTED_BRANCH:
        raise ValueError("repository/branch identity mismatch")
    if full_skipped_tests != 0:
        raise ValueError("zero skips required")
    if wheel_reproducible is not True:
        raise ValueError("wheel reproducibility required")
    expected_wheel = "tev_script_portable_reference-3.1.0-py3-none-any.whl"
    if wheel_filename != expected_wheel:
        raise ValueError("wheel filename mismatch")
    for name, value in (
        ("installed_v31_smoke", installed_v31_smoke),
        ("installed_v3_compatibility", installed_v3_compatibility),
        ("installed_v2_compatibility", installed_v2_compatibility),
    ):
        if value != "PASS":
            raise ValueError(name + " must be PASS")

    return {
        "schema": SCHEMA,
        "language_version": "3.1.0",
        "repository": repository,
        "branch": branch,
        "technical_parent_commit": _sha40(
            technical_parent_commit, "technical_parent_commit"
        ),
        "technical_parent_receipt_sha256": _sha64(
            technical_parent_receipt_sha256,
            "technical_parent_receipt_sha256",
        ),
        "release_commit_sha": _sha40(release_commit_sha, "release_commit_sha"),
        "release_tree_sha": _sha40(release_tree_sha, "release_tree_sha"),
        "release_diff_hash": _sha64(release_diff_hash, "release_diff_hash"),
        "descriptor_hash": _sha64(descriptor_hash, "descriptor_hash"),
        "full_test_count": _count(full_test_count, "full_test_count"),
        "full_skipped_tests": 0,
        "wheel_filename": expected_wheel,
        "wheel_sha256": _sha64(wheel_sha256, "wheel_sha256"),
        "wheel_reproducible": True,
        "installed_v31_smoke": "PASS",
        "installed_v3_compatibility": "PASS",
        "installed_v2_compatibility": "PASS",
        "stable_admission": True,
        "language_stable": True,
        "publication_eligible": True,
        "publication_authorized": False,
        "merge_authorized": False,
    }


def seal_receipt(body: Mapping[str, Any]) -> dict[str, Any]:
    stable = dict(body)
    if "receipt_hash" in stable:
        raise ValueError("receipt_hash already present")
    return {**stable, "receipt_hash": _hash_body(stable)}


def verify_receipt(value: Mapping[str, Any]) -> bool:
    try:
        body = dict(value)
        digest = body.pop("receipt_hash")
        if not isinstance(digest, str) or not hmac.compare_digest(digest, _hash_body(body)):
            return False
        expected = build_receipt_body(
            repository=body["repository"],
            branch=body["branch"],
            technical_parent_commit=body["technical_parent_commit"],
            technical_parent_receipt_sha256=body["technical_parent_receipt_sha256"],
            release_commit_sha=body["release_commit_sha"],
            release_tree_sha=body["release_tree_sha"],
            release_diff_hash=body["release_diff_hash"],
            descriptor_hash=body["descriptor_hash"],
            full_test_count=body["full_test_count"],
            full_skipped_tests=body["full_skipped_tests"],
            wheel_filename=body["wheel_filename"],
            wheel_sha256=body["wheel_sha256"],
            wheel_reproducible=body["wheel_reproducible"],
            installed_v31_smoke=body["installed_v31_smoke"],
            installed_v3_compatibility=body["installed_v3_compatibility"],
            installed_v2_compatibility=body["installed_v2_compatibility"],
        )
        return _canonical_bytes(body) == _canonical_bytes(expected)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def validate_artifact_dir(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    root = ROOT.resolve()
    if candidate == root or root in candidate.parents:
        raise ValueError("artifact dir must be outside repository")
    if not candidate.is_dir():
        raise ValueError("artifact dir must exist")
    if any(candidate.iterdir()):
        raise ValueError("artifact dir must be empty")
    return candidate


def _environment(*, include_repo: bool) -> dict[str, str]:
    env = os.environ.copy()
    if include_repo:
        existing = env.get("PYTHONPATH", "")
        root = str(ROOT.resolve())
        env["PYTHONPATH"] = root if not existing else root + os.pathsep + existing
    else:
        env.pop("PYTHONPATH", None)
    return env


def _run(
    args: Sequence[str],
    *,
    timeout: int = 7200,
    cwd: Path | None = None,
    include_repo: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            tuple(args),
            cwd=ROOT if cwd is None else cwd,
            env=_environment(include_repo=include_repo),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise V31StableAdmissionFailure("command timeout") from error
    if result.returncode != 0:
        raise V31StableAdmissionFailure(
            "command failed: "
            + repr(tuple(args))
            + "; output="
            + (result.stdout + "\n" + result.stderr)[-32768:]
        )
    return result


def _git(*args: str) -> str:
    return _run(("git", *args), timeout=120).stdout.strip()


def _parse_pytest_counts(result: subprocess.CompletedProcess[str]) -> tuple[int, int]:
    text = result.stdout + "\n" + result.stderr
    passed = [int(match.group("count")) for match in _PASSED.finditer(text)]
    if not passed:
        raise V31StableAdmissionFailure("cannot parse pytest count")
    skipped = [int(match.group("count")) for match in _SKIPPED.finditer(text)]
    return passed[-1], skipped[-1] if skipped else 0


def _load_technical_certificate(path: Path) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    file_sha = hashlib.sha256(data).hexdigest()
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise V31StableAdmissionFailure("technical certificate invalid JSON") from error
    if not isinstance(value, dict) or not technical.verify_receipt(value):
        raise V31StableAdmissionFailure("technical certificate verification failed")
    return value, file_sha


def _require_release_identity(parent: str) -> tuple[str, str, tuple[str, ...]]:
    branch = _git("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise V31StableAdmissionFailure("branch mismatch")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise V31StableAdmissionFailure("clean worktree required")
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    if _git("rev-parse", "HEAD^") != parent:
        raise V31StableAdmissionFailure("release commit must be direct child of technical parent")
    paths = tuple(
        sorted(
            filter(
                None,
                _git("diff", "--name-only", parent + "..HEAD", "--").splitlines(),
            )
        )
    )
    if not verify_release_diff_paths(paths):
        raise V31StableAdmissionFailure("release diff whitelist mismatch")
    remote = _git("ls-remote", "origin", "refs/heads/" + EXPECTED_BRANCH)
    rows = [line.split() for line in remote.splitlines() if line.strip()]
    if len(rows) != 1 or rows[0][0] != head:
        raise V31StableAdmissionFailure("release branch is not pushed at exact HEAD")
    return head, tree, paths


def _load_backend():
    path = ROOT / "packaging/v31/tools/tev_script_build_backend_v31.py"
    spec = importlib.util.spec_from_file_location(
        "tev_script_build_backend_v31_stable",
        path,
    )
    if spec is None or spec.loader is None:
        raise V31StableAdmissionFailure("cannot load V31 backend")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if getattr(module, "BACKEND_SCHEMA", None) != "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V31":
        raise V31StableAdmissionFailure("V31 backend identity mismatch")
    return module


def _build_final_wheel(artifact_dir: Path) -> tuple[Path, str]:
    backend = _load_backend()
    old = os.environ.get("SOURCE_DATE_EPOCH")
    os.environ["SOURCE_DATE_EPOCH"] = V31_WHEEL_SOURCE_DATE_EPOCH
    try:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            name1 = backend.build_wheel(first)
            name2 = backend.build_wheel(second)
            left = (Path(first) / name1).read_bytes()
            right = (Path(second) / name2).read_bytes()
            if name1 != name2 or left != right:
                raise V31StableAdmissionFailure("final wheel is not reproducible")
            target = artifact_dir / name1
            target.write_bytes(left)
            return target, hashlib.sha256(left).hexdigest()
    finally:
        if old is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = old


def _installed_smoke(wheel: Path) -> tuple[str, str, str]:
    with tempfile.TemporaryDirectory() as directory:
        workspace = Path(directory)
        env_root = workspace / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_root)
        python = env_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _run(
            (str(python), "-m", "pip", "install", "--no-deps", str(wheel)),
            timeout=1800,
            cwd=workspace,
            include_repo=False,
        )
        _run(
            (str(python), "-m", "pip", "check"),
            timeout=120,
            cwd=workspace,
            include_repo=False,
        )

        v31 = _run(
            (str(python), "-m", "tev_script.describe_v31"),
            timeout=120,
            cwd=workspace,
            include_repo=False,
        )
        descriptor = json.loads(v31.stdout)
        if descriptor.get("language_version") != "3.1.0" or descriptor.get("stable") is not True:
            raise V31StableAdmissionFailure("installed V31 descriptor is not stable")

        process_path = workspace / "process.tevs"
        unit_path = workspace / "calc.tevs"
        program_path = workspace / "program.json"
        process_path.write_text(
            "\n".join(
                (
                    'process StableSmoke version "3.1.0";',
                    "authority " + "a" * 64 + ";",
                    "quantum_steps 8;",
                    "unit Calc profile pure;",
                    "field actual = [];",
                    "label Start = invoke_v4 Calc result tev.stable.smoke End;",
                    "label End = halt;",
                    "entry Start;",
                    "",
                )
            ),
            encoding="utf-8",
        )
        unit_path.write_text(
            'script Calc version "2.0.0"; fn add1(x:Int)->Int=x+1; entry main:Int=add1(4);\n',
            encoding="utf-8",
        )
        _run(
            (
                str(python),
                "-m",
                "tev_script.cli_v31",
                "compile-total",
                str(process_path),
                "--unit",
                "Calc=" + str(unit_path),
                "--output",
                str(program_path),
            ),
            timeout=120,
            cwd=workspace,
            include_repo=False,
        )
        run = _run(
            (
                str(python),
                "-m",
                "tev_script.cli_v31",
                "run-total",
                str(program_path),
            ),
            timeout=120,
            cwd=workspace,
            include_repo=False,
        )
        run_result = json.loads(run.stdout)
        if run_result.get("status") != "HALTED":
            raise V31StableAdmissionFailure("installed V31 Total-Core smoke did not halt")

        v3 = _run(
            (str(python), "-m", "tev_script.describe_v3"),
            timeout=120,
            cwd=workspace,
            include_repo=False,
        )
        v3_descriptor = json.loads(v3.stdout)
        if v3_descriptor.get("language_version") != "3.0.0" or v3_descriptor.get("stable") is not True:
            raise V31StableAdmissionFailure("installed V3 compatibility failed")

        v2 = _run(
            (str(python), "-m", "tev_script.describe_v2"),
            timeout=120,
            cwd=workspace,
            include_repo=False,
        )
        v2_descriptor = json.loads(v2.stdout)
        if v2_descriptor.get("language_version") != "2.0.0" or v2_descriptor.get("stable") is not True:
            raise V31StableAdmissionFailure("installed V2 compatibility failed")

        return "PASS", "PASS", "PASS"


def _validate_stable_schema() -> None:
    path = ROOT / "schemas/tev-script-v31-stable-admission-receipt.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    if (
        schema.get("$id") != SCHEMA
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        raise V31StableAdmissionFailure("stable receipt schema invalid")


def certify(
    *,
    technical_parent_certificate: str | Path,
    artifact_out_dir: str | Path,
) -> dict[str, Any]:
    artifacts = validate_artifact_dir(artifact_out_dir)
    metadata = release.validate_release_metadata_v31()
    if (
        metadata["release_profile"] != "stable_request"
        or metadata["release_status"] != "STABLE_ADMISSION_REQUESTED"
        or metadata["stable"] is not True
        or metadata["publication_authority"] is not False
        or metadata["merge_authority"] is not False
    ):
        raise V31StableAdmissionFailure("stable-request release metadata required")

    certificate_path = Path(technical_parent_certificate).expanduser().resolve()
    technical_receipt, certificate_sha = _load_technical_certificate(certificate_path)
    if technical_receipt["commit_sha"] != release.TECHNICAL_PARENT_COMMIT:
        raise V31StableAdmissionFailure("technical parent commit mismatch")
    if certificate_sha != release.TECHNICAL_PARENT_RECEIPT_SHA256:
        raise V31StableAdmissionFailure("technical parent certificate file hash mismatch")

    head, tree, paths = _require_release_identity(release.TECHNICAL_PARENT_COMMIT)
    descriptor = v31_descriptor()
    if not verify_v31_descriptor(descriptor) or descriptor["stable"] is not True:
        raise V31StableAdmissionFailure("stable V31 descriptor invalid")
    matrix_report = technical.validate_v31_matrix(
        technical.load_feature_matrix(ROOT),
        descriptor,
    )
    if matrix_report["status"] != "PASS" or matrix_report["language_stable"] is not True:
        raise V31StableAdmissionFailure("stable V31 feature matrix invalid")

    _validate_stable_schema()
    full = _run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
        )
    )
    full_count, full_skips = _parse_pytest_counts(full)
    if full_skips:
        raise V31StableAdmissionFailure("zero skips required")

    wheel, wheel_sha = _build_final_wheel(artifacts)
    v31_smoke, v3_smoke, v2_smoke = _installed_smoke(wheel)
    diff_hash = hashlib.sha256(_canonical_bytes(list(paths))).hexdigest()
    body = build_receipt_body(
        repository=REPOSITORY,
        branch=EXPECTED_BRANCH,
        technical_parent_commit=release.TECHNICAL_PARENT_COMMIT,
        technical_parent_receipt_sha256=certificate_sha,
        release_commit_sha=head,
        release_tree_sha=tree,
        release_diff_hash=diff_hash,
        descriptor_hash=str(descriptor["descriptor_hash"]),
        full_test_count=full_count,
        full_skipped_tests=full_skips,
        wheel_filename=wheel.name,
        wheel_sha256=wheel_sha,
        wheel_reproducible=True,
        installed_v31_smoke=v31_smoke,
        installed_v3_compatibility=v3_smoke,
        installed_v2_compatibility=v2_smoke,
    )
    receipt = seal_receipt(body)
    if not verify_receipt(receipt):
        raise V31StableAdmissionFailure("stable receipt self-verification failed")

    receipt_path = artifacts / "TEV_SCRIPT_V31_STABLE_ADMISSION_RECEIPT_V1.json"
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEVScript MAX 3.1 Stable Admission")
    parser.add_argument("--technical-parent-certificate", required=True)
    parser.add_argument("--artifact-out-dir", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = certify(
            technical_parent_certificate=args.technical_parent_certificate,
            artifact_out_dir=args.artifact_out_dir,
        )
    except Exception as error:  # noqa: BLE001
        print("V31_STABLE_ADMISSION=FAIL")
        print("V31_STABLE_ADMISSION_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1

    print("V31_STABLE_ADMISSION=PASS")
    print("V31_LANGUAGE_STABLE=YES")
    print("V31_PUBLICATION_ELIGIBLE=YES")
    print("V31_PUBLICATION_AUTHORIZED=NO")
    print("V31_MERGE_AUTHORIZED=NO")
    print("V31_STABLE_RECEIPT_HASH=" + receipt["receipt_hash"])
    print("V31_WHEEL_FILENAME=" + receipt["wheel_filename"])
    print("V31_WHEEL_SHA256=" + receipt["wheel_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
