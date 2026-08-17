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
V31_INDEX_AUTHORITY_FILES = tuple(
    sorted(
        (
            "schemas/tev-script-program-ir-v5-total-core.schema.json",
            "schemas/tev-script-v31-certify-full-receipt.schema.json",
            "schemas/tev-script-v31-descriptor.schema.json",
            "schemas/tev-script-v31-stable-admission-receipt.schema.json",
            "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json",
            "spec/TEV_SCRIPT_V31_TOTAL_CORE.md",
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


def expected_v31_index_target() -> dict[str, Any]:
    return {
        "language_version": "3.1.0",
        "status": "STABLE_ADMISSION_REQUESTED",
        "stable": True,
        "publication_authorized": False,
        "merge_authorized": False,
        "authority_files": list(V31_INDEX_AUTHORITY_FILES),
        "introspection_surface": {
            "schema": "schemas/tev-script-v31-descriptor.schema.json",
            "generator": "tev_script/descriptor_v31.py",
            "module_cli": "tev_script/describe_v31.py",
            "installed_cli": "tev-script-v31-describe",
            "stable_claim": True,
        },
        "stable_release_surface": {
            "release_metadata": "tev_script/release_metadata_v31.py",
            "admission_gate": "RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py",
            "receipt_schema": "TEV_SCRIPT_V31_STABLE_ADMISSION_RECEIPT_V1",
            "exact_parent_certificate_required": True,
            "release_diff_whitelist_required": True,
            "artifact_byte_identity_required": True,
            "stable_claim": True,
        },
        "gates": {
            "certify_full": "RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py",
            "stable_admission": "RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py",
        },
        "public_interfaces": {
            "python_package": "tev_script",
            "v31_cli": "tev-script-v31",
            "v31_descriptor_cli": "tev-script-v31-describe",
            "v31_module_cli": "python -m tev_script.cli_v31",
        },
    }


def validate_v31_index_target(value: Mapping[str, Any]) -> bool:
    try:
        return _canonical_bytes(dict(value)) == _canonical_bytes(expected_v31_index_target())
    except (TypeError, ValueError):
        return False


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


def validate_finalization_root(path: str | Path) -> Path:
    candidate = validate_artifact_dir(path)
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


def _remote_branch_sha() -> str:
    raw = _git("ls-remote", "origin", "refs/heads/" + EXPECTED_BRANCH)
    rows = [line.split() for line in raw.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2:
        raise V31StableAdmissionFailure("cannot resolve exact candidate branch")
    return rows[0][0]


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
    if _remote_branch_sha() != parent:
        raise V31StableAdmissionFailure(
            "remote branch must remain at technical parent until Stable Admission PASS"
        )
    return head, tree, paths


def _require_v31_index_target() -> None:
    try:
        index = json.loads((ROOT / "CANONICAL_INDEX.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V31StableAdmissionFailure("canonical index invalid JSON") from error
    if not isinstance(index, dict):
        raise V31StableAdmissionFailure("canonical index root must be object")
    targets = index.get("candidate_language_targets")
    if not isinstance(targets, list):
        raise V31StableAdmissionFailure("canonical index target list missing")
    matches = [
        item
        for item in targets
        if isinstance(item, Mapping) and item.get("language_version") == "3.1.0"
    ]
    if len(matches) != 1 or not validate_v31_index_target(matches[0]):
        raise V31StableAdmissionFailure("canonical V31 target is missing or malformed")


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

        v31 = json.loads(
            _run(
                (str(python), "-m", "tev_script.describe_v31"),
                timeout=120,
                cwd=workspace,
                include_repo=False,
            ).stdout
        )
        if v31.get("language_version") != "3.1.0" or v31.get("stable") is not True:
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
        result = json.loads(
            _run(
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
            ).stdout
        )
        if result.get("status") != "HALTED":
            raise V31StableAdmissionFailure("installed V31 Total-Core smoke did not halt")

        v3 = json.loads(
            _run(
                (str(python), "-m", "tev_script.describe_v3"),
                timeout=120,
                cwd=workspace,
                include_repo=False,
            ).stdout
        )
        if v3.get("language_version") != "3.0.0" or v3.get("stable") is not True:
            raise V31StableAdmissionFailure("installed V3 compatibility failed")

        v2 = json.loads(
            _run(
                (str(python), "-m", "tev_script.describe_v2"),
                timeout=120,
                cwd=workspace,
                include_repo=False,
            ).stdout
        )
        if v2.get("language_version") != "2.0.0" or v2.get("stable") is not True:
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
    _require_v31_index_target()
    predecessor = technical.require_predecessor_byte_identity(ROOT)
    if (
        predecessor["v3_byte_identity"] != "PASS"
        or predecessor["v2_byte_identity"] != "PASS"
        or predecessor["canonical_index_predecessor_identity"] != "PASS"
    ):
        raise V31StableAdmissionFailure("predecessor identity failed after release shaping")

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


def _stable_release_metadata_text(parent: str, certificate_sha: str) -> str:
    return f'''from __future__ import annotations

LANGUAGE_VERSION = "3.1.0"
RELEASE_PROFILE = "stable_request"
RELEASE_STATUS = "STABLE_ADMISSION_REQUESTED"
STABLE = True
PUBLICATION_AUTHORITY = False
MERGE_AUTHORITY = False
TECHNICAL_PARENT_COMMIT = "{parent}"
TECHNICAL_PARENT_RECEIPT_SHA256 = "{certificate_sha}"


def _is_sha(value: str, length: int) -> bool:
    return len(value) == length and all(c in "0123456789abcdef" for c in value)


def validate_release_metadata_v31() -> dict[str, object]:
    if LANGUAGE_VERSION != "3.1.0":
        raise RuntimeError("TEVS_V31_RELEASE_LANGUAGE_VERSION")
    if RELEASE_PROFILE == "candidate":
        if RELEASE_STATUS != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED":
            raise RuntimeError("TEVS_V31_RELEASE_CANDIDATE_STATUS")
        if STABLE or PUBLICATION_AUTHORITY or MERGE_AUTHORITY:
            raise RuntimeError("TEVS_V31_RELEASE_CANDIDATE_AUTHORITY")
        if TECHNICAL_PARENT_COMMIT or TECHNICAL_PARENT_RECEIPT_SHA256:
            raise RuntimeError("TEVS_V31_RELEASE_CANDIDATE_PARENT")
    elif RELEASE_PROFILE == "stable_request":
        if RELEASE_STATUS != "STABLE_ADMISSION_REQUESTED":
            raise RuntimeError("TEVS_V31_RELEASE_STABLE_STATUS")
        if not STABLE or PUBLICATION_AUTHORITY or MERGE_AUTHORITY:
            raise RuntimeError("TEVS_V31_RELEASE_STABLE_AUTHORITY")
        if not _is_sha(TECHNICAL_PARENT_COMMIT, 40):
            raise RuntimeError("TEVS_V31_RELEASE_PARENT_COMMIT")
        if not _is_sha(TECHNICAL_PARENT_RECEIPT_SHA256, 64):
            raise RuntimeError("TEVS_V31_RELEASE_PARENT_RECEIPT")
    else:
        raise RuntimeError("TEVS_V31_RELEASE_PROFILE")
    return {{
        "language_version": LANGUAGE_VERSION,
        "release_profile": RELEASE_PROFILE,
        "release_status": RELEASE_STATUS,
        "stable": STABLE,
        "publication_authority": PUBLICATION_AUTHORITY,
        "merge_authority": MERGE_AUTHORITY,
        "technical_parent_commit": TECHNICAL_PARENT_COMMIT,
        "technical_parent_receipt_sha256": TECHNICAL_PARENT_RECEIPT_SHA256,
    }}


__all__ = [
    "LANGUAGE_VERSION",
    "MERGE_AUTHORITY",
    "PUBLICATION_AUTHORITY",
    "RELEASE_PROFILE",
    "RELEASE_STATUS",
    "STABLE",
    "TECHNICAL_PARENT_COMMIT",
    "TECHNICAL_PARENT_RECEIPT_SHA256",
    "validate_release_metadata_v31",
]
'''


def _append_release_note(path: Path, parent: str, certificate_sha: str) -> None:
    marker = "## TEVScript MAX 3.1.0 Total-Core — Stable Admission Request"
    text = path.read_text(encoding="utf-8")
    if marker in text:
        raise V31StableAdmissionFailure("release marker already present: " + path.name)
    if text and not text.endswith("\n"):
        text += "\n"
    block = f'''\n{marker}\n\n- Language/package version: `3.1.0`\n- Technical parent: `{parent}`\n- Technical certificate file SHA-256: `{certificate_sha}`\n- Program IR: V5 Total-Core\n- Independent JavaScript parity: required\n- Stable Admission: requested on this exact release-shaped commit\n- Publication eligibility depends on Stable Admission.\n- Publication authority: **not granted**.\n- Merge authority: **not granted**.\n'''
    path.write_text(text + block, encoding="utf-8", newline="\n")


def _shape_release(parent: str, certificate_sha: str) -> None:
    metadata = release.validate_release_metadata_v31()
    if metadata["release_profile"] != "candidate" or metadata["stable"] is not False:
        raise V31StableAdmissionFailure("release shaping requires candidate metadata")

    (ROOT / "tev_script/release_metadata_v31.py").write_text(
        _stable_release_metadata_text(parent, certificate_sha),
        encoding="utf-8",
        newline="\n",
    )

    matrix_path = ROOT / "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    if (
        matrix.get("status") != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED"
        or matrix.get("stable") is not False
        or matrix.get("language_stable") is not False
    ):
        raise V31StableAdmissionFailure("candidate feature matrix required")
    matrix["status"] = "STABLE_ADMISSION_REQUESTED"
    matrix["stable"] = True
    matrix["language_stable"] = True
    matrix["publication_authorized"] = False
    matrix["merge_authorized"] = False
    matrix_path.write_text(
        json.dumps(matrix, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    index_path = ROOT / "CANONICAL_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    targets = index.get("candidate_language_targets")
    if not isinstance(targets, list):
        raise V31StableAdmissionFailure("canonical index target list missing")
    if any(
        isinstance(item, Mapping) and item.get("language_version") == "3.1.0"
        for item in targets
    ):
        raise V31StableAdmissionFailure("canonical index already has V31 target")
    targets.append(expected_v31_index_target())
    index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    _append_release_note(ROOT / "CHANGELOG.md", parent, certificate_sha)
    _append_release_note(ROOT / "README.md", parent, certificate_sha)

    paths = tuple(
        sorted(filter(None, _git("diff", "--name-only", "HEAD", "--").splitlines()))
    )
    if not verify_release_diff_paths(paths):
        raise V31StableAdmissionFailure("release shaping changed wrong paths")
    _run(("git", "diff", "--check"), timeout=120)


def _release_focal() -> None:
    command = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        "tests/test_v31_authority.py",
        "tests/test_v31_certify_full.py",
        "tests/test_v31_descriptor.py",
        "tests/test_v31_packaging.py",
        "tests/test_v31_stable_admission.py",
    )
    result = _run(command, timeout=3600)
    _count_value, skips = _parse_pytest_counts(result)
    if skips:
        raise V31StableAdmissionFailure("release focal requires zero skips")

    descriptor = v31_descriptor()
    report = technical.validate_v31_matrix(technical.load_feature_matrix(ROOT), descriptor)
    if report["status"] != "PASS" or report["language_stable"] is not True:
        raise V31StableAdmissionFailure("release focal matrix/descriptor mismatch")
    identity = technical.require_predecessor_byte_identity(ROOT)
    if identity["canonical_index_predecessor_identity"] != "PASS":
        raise V31StableAdmissionFailure("release focal predecessor index mismatch")
    _require_v31_index_target()


def _run_release_focal_fresh() -> None:
    command = (
        sys.executable,
        "-c",
        (
            "import RUN_TEV_SCRIPT_V31_STABLE_ADMISSION as gate; "
            "gate._release_focal(); "
            "print('V31_RELEASE_FOCAL=PASS')"
        ),
    )
    result = _run(command, timeout=3600)
    if "V31_RELEASE_FOCAL=PASS" not in result.stdout:
        raise V31StableAdmissionFailure(
            "fresh release focal did not report PASS"
        )


def _run_stable_certify_fresh(
    *,
    technical_parent_certificate: Path,
    artifact_out_dir: Path,
) -> dict[str, Any]:
    command = (
        sys.executable,
        str(ROOT / "RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py"),
        "--technical-parent-certificate",
        str(technical_parent_certificate),
        "--artifact-out-dir",
        str(artifact_out_dir),
    )
    result = _run(command, timeout=7200)
    if "V31_STABLE_ADMISSION=PASS" not in result.stdout:
        raise V31StableAdmissionFailure(
            "fresh Stable Admission subprocess did not report PASS"
        )

    receipt_path = (
        artifact_out_dir / "TEV_SCRIPT_V31_STABLE_ADMISSION_RECEIPT_V1.json"
    )
    if not receipt_path.is_file():
        raise V31StableAdmissionFailure(
            "fresh Stable Admission did not emit receipt"
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V31StableAdmissionFailure(
            "fresh Stable Admission receipt is invalid JSON"
        ) from error
    if not isinstance(receipt, dict) or not verify_receipt(receipt):
        raise V31StableAdmissionFailure(
            "fresh Stable Admission receipt failed verification"
        )
    return receipt


def _commit_release(parent: str) -> tuple[str, str]:
    if _remote_branch_sha() != parent:
        raise V31StableAdmissionFailure("remote branch moved before release commit")
    _run(("git", "add", *RELEASE_DIFF_WHITELIST), timeout=120)
    staged = tuple(
        sorted(filter(None, _git("diff", "--cached", "--name-only").splitlines()))
    )
    if staged != RELEASE_DIFF_WHITELIST:
        raise V31StableAdmissionFailure("staged release diff mismatch")
    _run(
        (
            "git",
            "-c",
            "user.name=MCBA",
            "-c",
            "user.email=benaventmarcamaya@gmail.com",
            "commit",
            "-m",
            "release(v31): request stable admission for Total-Core 3.1.0",
        ),
        timeout=120,
    )
    head = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    if _git("rev-parse", "HEAD^") != parent:
        raise V31StableAdmissionFailure("release commit parent mismatch")
    return head, tree


def finalize_candidate(finalization_root: str | Path) -> dict[str, Any]:
    output = validate_finalization_root(finalization_root)
    candidate = release.validate_release_metadata_v31()
    if candidate["release_profile"] != "candidate" or candidate["stable"] is not False:
        raise V31StableAdmissionFailure("finalization requires candidate release metadata")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise V31StableAdmissionFailure("finalization requires clean candidate checkout")

    parent = _git("rev-parse", "HEAD")
    parent_tree = _git("rev-parse", "HEAD^{tree}")
    if _remote_branch_sha() != parent:
        raise V31StableAdmissionFailure("local candidate is not exact remote candidate")

    technical_receipt_path = output / "TEV_SCRIPT_V31_CERTIFY_FULL_RECEIPT.json"
    technical_receipt = technical.certify(receipt_out=technical_receipt_path)
    if technical_receipt["commit_sha"] != parent or technical_receipt["tree_sha"] != parent_tree:
        raise V31StableAdmissionFailure("technical certificate identity mismatch")
    certificate_sha = hashlib.sha256(technical_receipt_path.read_bytes()).hexdigest()

    _shape_release(parent, certificate_sha)
    _run_release_focal_fresh()
    release_head, release_tree = _commit_release(parent)

    stable_artifacts = output / "stable-artifacts"
    stable_artifacts.mkdir()
    stable_receipt = _run_stable_certify_fresh(
        technical_parent_certificate=technical_receipt_path,
        artifact_out_dir=stable_artifacts,
    )
    if stable_receipt["release_commit_sha"] != release_head:
        raise V31StableAdmissionFailure("stable receipt release commit mismatch")
    if stable_receipt["release_tree_sha"] != release_tree:
        raise V31StableAdmissionFailure("stable receipt release tree mismatch")

    if _remote_branch_sha() != parent:
        raise V31StableAdmissionFailure("remote branch moved during Stable Admission")
    _run(("git", "push", "origin", "HEAD:refs/heads/" + EXPECTED_BRANCH), timeout=1800)
    if _remote_branch_sha() != release_head:
        raise V31StableAdmissionFailure("release push verification failed")
    if _git("status", "--porcelain=v1", "--untracked-files=all"):
        raise V31StableAdmissionFailure("final release checkout is dirty")

    wheel = stable_artifacts / stable_receipt["wheel_filename"]
    stable_receipt_path = stable_artifacts / "TEV_SCRIPT_V31_STABLE_ADMISSION_RECEIPT_V1.json"
    return {
        "technical_parent_head": parent,
        "technical_parent_tree": parent_tree,
        "technical_receipt_path": technical_receipt_path.resolve().as_posix(),
        "technical_receipt_file_sha256": certificate_sha,
        "release_head": release_head,
        "release_tree": release_tree,
        "stable_receipt_path": stable_receipt_path.resolve().as_posix(),
        "stable_receipt_file_sha256": hashlib.sha256(stable_receipt_path.read_bytes()).hexdigest(),
        "wheel_path": wheel.resolve().as_posix(),
        "wheel_sha256": stable_receipt["wheel_sha256"],
        "language_stable": True,
        "publication_eligible": True,
        "publication_authorized": False,
        "merge_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEVScript MAX 3.1 Stable Admission")
    parser.add_argument("--technical-parent-certificate")
    parser.add_argument("--artifact-out-dir")
    parser.add_argument("--finalize-candidate-root")
    args = parser.parse_args(argv)
    try:
        if args.finalize_candidate_root:
            if args.technical_parent_certificate or args.artifact_out_dir:
                raise ValueError("finalize mode is exclusive")
            result = finalize_candidate(args.finalize_candidate_root)
            print("TEVSCRIPT_V31_STABLE_CLOSURE=PASS")
            print("V31_CERTIFY_FULL=PASS")
            print("V31_STABLE_ADMISSION=PASS")
            print("V31_LANGUAGE_STABLE=YES")
            print("V31_PUBLICATION_ELIGIBLE=YES")
            print("V31_PUBLICATION_AUTHORIZED=NO")
            print("V31_MERGE_AUTHORIZED=NO")
            for key, value in result.items():
                print("V31_FINAL_" + key.upper() + "=" + str(value))
            return 0

        if not args.technical_parent_certificate or not args.artifact_out_dir:
            raise ValueError("technical certificate and artifact dir are required")
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
