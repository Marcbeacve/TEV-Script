from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator

from tev_script.canonical import canonical_hash, canonical_json
from tev_script.descriptor_v2 import v2_descriptor
from tev_script import release_metadata_v2 as release_metadata
from tools import v2_certification_support as support

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
RECEIPT_SCHEMA = "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1"
GitIdentity = support.GitIdentity
V2StableAdmissionFailure = support.V2CertificationFailure
REQUIRED_RELEASE_PATHS = {
    "CANONICAL_INDEX.json",
    "CHANGELOG.md",
    "PROJECT_STATE.md",
    "README.md",
    "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
    "tev_script/release_metadata_v2.py",
}
ALLOWED_RELEASE_PATHS = frozenset(REQUIRED_RELEASE_PATHS)


def run(
    arguments: list[str],
    *,
    timeout: int = 7200,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            arguments,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise V2StableAdmissionFailure(
            f"command timed out: {arguments!r}; "
            f"stdout={support.bounded(error.stdout)}; "
            f"stderr={support.bounded(error.stderr)}"
        ) from error
    if completed.returncode != 0:
        raise V2StableAdmissionFailure(
            f"command failed exit={completed.returncode}: {arguments!r}; "
            f"stdout={support.bounded(completed.stdout)}; "
            f"stderr={support.bounded(completed.stderr)}"
        )
    return completed


def git_text(*arguments: str) -> str:
    return run(["git", *arguments]).stdout.strip()


def _require_release_path_modes(head: str, paths: list[str]) -> None:
    for relative in paths:
        row = git_text("ls-tree", head, "--", relative)
        prefix = "100644 blob "
        suffix = "\t" + relative
        object_id = (
            row[len(prefix) :].split("\t", 1)[0]
            if row.startswith(prefix)
            else ""
        )
        if (
            not row.startswith(prefix)
            or not row.endswith(suffix)
            or len(object_id) != 40
            or any(char not in "0123456789abcdef" for char in object_id)
        ):
            raise V2StableAdmissionFailure(
                "V2_STABLE_RELEASE_PATH_NOT_REGULAR_BLOB:"
                + relative
                + ":"
                + row
            )


def validate_release_diff(parent: str, head: str) -> list[str]:
    git_text("merge-base", "--is-ancestor", parent, head)
    changed = sorted(
        item
        for item in git_text(
            "diff", "--name-only", parent + ".." + head
        ).splitlines()
        if item
    )
    changed_set = set(changed)
    forbidden = sorted(changed_set - ALLOWED_RELEASE_PATHS)
    if forbidden:
        raise V2StableAdmissionFailure(
            "V2_STABLE_RELEASE_DIFF_FORBIDDEN:" + ",".join(forbidden)
        )
    missing = sorted(REQUIRED_RELEASE_PATHS - changed_set)
    if missing:
        raise V2StableAdmissionFailure(
            "V2_STABLE_RELEASE_DIFF_MISSING:" + ",".join(missing)
        )
    if changed_set != set(REQUIRED_RELEASE_PATHS):
        raise V2StableAdmissionFailure("V2_STABLE_RELEASE_DIFF_NOT_EXACT")
    _require_release_path_modes(head, changed)
    return changed


def load_parent_certificate(
    path: Path,
    parent: str,
    expected_hash: str,
) -> tuple[dict[str, object], str]:
    selected = support.require_external_input_file(ROOT, path)
    try:
        receipt = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2StableAdmissionFailure(
            f"cannot load V2 technical parent certificate: {error}"
        ) from error
    if not isinstance(receipt, dict):
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate root must be an object"
        )
    schema = json.loads(
        (
            ROOT
            / "schemas"
            / "tev-script-v2-certify-full-receipt-v2.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(receipt)
    body = dict(receipt)
    embedded = body.pop("receipt_hash", None)
    observed = canonical_hash(body)
    if embedded != observed or observed != expected_hash:
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate hash mismatch: "
            f"embedded={embedded} observed={observed} expected={expected_hash}"
        )
    if receipt.get("admission_profile") != "candidate":
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate must use candidate profile"
        )
    if receipt.get("commit_sha") != parent:
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate commit mismatch"
        )
    if receipt.get("base_sha") != parent:
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate base mismatch"
        )
    parent_tree = git_text("rev-parse", parent + "^{tree}")
    if receipt.get("tree_sha") != parent_tree:
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate tree mismatch"
        )
    if (
        receipt.get("dirty") is not False
        or receipt.get("certify_full") is not True
        or receipt.get("language_stable") is not False
    ):
        raise V2StableAdmissionFailure(
            "V2 technical parent certificate claims are invalid"
        )
    return receipt, observed


def _load_receipt(path: Path, schema_name: str) -> dict[str, object]:
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2StableAdmissionFailure(
            f"cannot load generated receipt {path}: {error}"
        ) from error
    if not isinstance(receipt, dict) or receipt.get("schema") != schema_name:
        raise V2StableAdmissionFailure(
            f"generated receipt schema mismatch: {path}"
        )
    return receipt


def _embedded_hash(receipt: dict[str, object]) -> str:
    body = dict(receipt)
    embedded = body.pop("receipt_hash", None)
    observed = canonical_hash(body)
    if embedded != observed:
        raise V2StableAdmissionFailure("generated receipt self-hash mismatch")
    return observed


def _single_marker(stdout: str, prefix: str, label: str) -> str:
    values = [
        line[len(prefix) :]
        for line in stdout.splitlines()
        if line.startswith(prefix)
    ]
    if len(values) != 1:
        raise V2StableAdmissionFailure(
            f"{label} expected one {prefix!r} marker, observed={values!r}"
        )
    return values[0]


def _require_v2_technical_receipt(
    receipt: dict[str, object],
    announced_hash: str,
    identity: GitIdentity,
) -> str:
    observed = _embedded_hash(receipt)
    if observed != announced_hash:
        raise V2StableAdmissionFailure(
            "V2 technical receipt announced hash mismatch"
        )
    if (
        receipt.get("admission_profile") != "stable"
        or receipt.get("branch") != identity.branch
        or receipt.get("commit_sha") != identity.commit_sha
        or receipt.get("tree_sha") != identity.tree_sha
        or receipt.get("base_sha") != identity.base_sha
        or receipt.get("dirty") is not False
        or receipt.get("certify_full") is not True
        or receipt.get("language_stable") is not False
    ):
        raise V2StableAdmissionFailure(
            "V2 technical receipt identity/claims mismatch"
        )
    return observed


def _require_v1_receipt(
    receipt: dict[str, object],
    announced_hash: str,
    identity: GitIdentity,
) -> str:
    observed = canonical_hash(receipt)
    if observed != announced_hash:
        raise V2StableAdmissionFailure("V1 receipt announced hash mismatch")
    if (
        receipt.get("admission_profile") != "stable"
        or receipt.get("branch") != identity.branch
        or receipt.get("commit") != identity.commit_sha
        or receipt.get("tree") != identity.tree_sha
        or receipt.get("certify_full") is not True
        or receipt.get("language_stable") is not False
    ):
        raise V2StableAdmissionFailure("V1 receipt identity/claims mismatch")
    return observed


def _require_v2_python_receipt(
    receipt: dict[str, object],
    announced_hash: str,
    identity: GitIdentity,
) -> str:
    observed = _embedded_hash(receipt)
    if observed != announced_hash:
        raise V2StableAdmissionFailure(
            "V2 Python receipt announced hash mismatch"
        )
    if (
        receipt.get("admission_profile") != "stable"
        or receipt.get("branch") != identity.branch
        or receipt.get("commit_sha") != identity.commit_sha
        or receipt.get("tree_sha") != identity.tree_sha
        or receipt.get("base_sha") != identity.base_sha
        or receipt.get("dirty") is not False
        or receipt.get("python_v2_certify_full") is not True
        or receipt.get("language_stable") is not False
    ):
        raise V2StableAdmissionFailure(
            "V2 Python receipt identity/claims mismatch"
        )
    return observed


def _file_sha256(path: Path) -> str:
    return support.sha256_file(path)


def build_receipt(
    identity: GitIdentity,
    *,
    parent: str,
    parent_tree: str,
    parent_certificate_sha256: str,
    changed_paths: list[str],
    v2_technical_receipt_sha256: str,
    v1_receipt_sha256: str,
    v2_python_receipt_sha256: str,
    wheel_filename: str,
    wheel_sha256: str,
    descriptor_hash: str,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "commit_sha": identity.commit_sha,
        "tree_sha": identity.tree_sha,
        "branch": identity.branch,
        "language_version": "2.0.0",
        "python_package_version": "1.0.0",
        "technical_parent_commit": parent,
        "technical_parent_tree": parent_tree,
        "technical_parent_certificate_sha256": parent_certificate_sha256,
        "release_changed_paths": changed_paths,
        "v2_technical_receipt_sha256": v2_technical_receipt_sha256,
        "v1_receipt_sha256": v1_receipt_sha256,
        "v2_python_receipt_sha256": v2_python_receipt_sha256,
        "python_wheel_filename": wheel_filename,
        "python_wheel_sha256": wheel_sha256,
        "descriptor_hash": descriptor_hash,
        "canonical_index_sha256": _file_sha256(ROOT / "CANONICAL_INDEX.json"),
        "feature_matrix_sha256": _file_sha256(
            ROOT / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json"
        ),
        "certify_full": True,
        "stable_admission": True,
        "language_stable": True,
    }
    return {**body, "receipt_hash": canonical_hash(body)}


def _validate_receipt(receipt: dict[str, object]) -> None:
    schema = json.loads(
        (
            ROOT
            / "schemas"
            / "tev-script-v2-stable-admission-receipt.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(receipt)


def _write_stable_receipt(
    path: Path,
    receipt: dict[str, object],
) -> Path:
    return support.write_external_bytes_once(
        ROOT,
        path,
        (canonical_json(receipt) + "\n").encode("utf-8"),
    )


def certify(
    *,
    technical_parent_certificate: Path,
    artifact_out_dir: Path,
) -> tuple[dict[str, object], Path]:
    try:
        release_metadata.validate_release_metadata()
    except RuntimeError as error:
        raise V2StableAdmissionFailure(
            "stable release metadata invalid: " + str(error)
        ) from error
    if release_metadata.RELEASE_PROFILE != "stable":
        raise V2StableAdmissionFailure(
            "V2 Stable Admission requires stable release profile"
        )
    parent = support.require_git_sha(
        release_metadata.TECHNICAL_PARENT_COMMIT,
        "technical parent",
    )
    parent_certificate_hash = str(
        release_metadata.TECHNICAL_PARENT_CERTIFICATE_SHA256
    )
    if (
        len(parent_certificate_hash) != 64
        or any(
            char not in "0123456789abcdef"
            for char in parent_certificate_hash
        )
    ):
        raise V2StableAdmissionFailure(
            "invalid technical parent certificate SHA-256"
        )

    artifact_root = support.require_external_empty_dir(
        ROOT, artifact_out_dir
    )
    initial = support.collect_git_identity(ROOT, parent)
    _, observed_parent_hash = load_parent_certificate(
        technical_parent_certificate,
        parent,
        parent_certificate_hash,
    )
    changed = validate_release_diff(parent, initial.commit_sha)

    governance = run(
        [
            sys.executable,
            str(ROOT / "tools" / "validate_v2_stable_governance.py"),
        ]
    )
    if (
        "TEV_SCRIPT_V2_STABLE_GOVERNANCE=PASS"
        not in governance.stdout.splitlines()
    ):
        raise V2StableAdmissionFailure(
            "V2 stable governance PASS witness missing"
        )

    v2_technical_path = artifact_root / "v2-technical.json"
    technical = run(
        [
            sys.executable,
            str(ROOT / "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py"),
            "--profile",
            "stable",
            "--expected-base",
            parent,
            "--receipt-out",
            str(v2_technical_path),
        ]
    )
    technical_lines = set(technical.stdout.splitlines())
    if (
        "CERTIFY_V2=PASS" not in technical_lines
        or "LANGUAGE_STABLE=NO" not in technical_lines
    ):
        raise V2StableAdmissionFailure(
            "V2 technical recertification witnesses missing"
        )
    v2_technical = _load_receipt(
        v2_technical_path,
        "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2",
    )
    v2_technical_hash = _require_v2_technical_receipt(
        v2_technical,
        _single_marker(
            technical.stdout,
            "TEV_SCRIPT_V2_RECEIPT_SHA256=",
            "V2 technical recertification",
        ),
        initial,
    )

    v1_path = artifact_root / "v1-global.json"
    v1 = run(
        [
            sys.executable,
            str(ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py"),
            "--profile",
            "stable",
            "--receipt-out",
            str(v1_path),
        ]
    )
    v1_lines = set(v1.stdout.splitlines())
    if (
        "CERTIFY_FULL=PASS" not in v1_lines
        or "LANGUAGE_STABLE=NO" not in v1_lines
    ):
        raise V2StableAdmissionFailure(
            "V1 non-regression witnesses missing"
        )
    v1_receipt = _load_receipt(
        v1_path,
        "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2",
    )
    v1_hash = _require_v1_receipt(
        v1_receipt,
        _single_marker(
            v1.stdout,
            "V1_CERTIFY_FULL_RECEIPT_SHA256=",
            "V1 non-regression",
        ),
        initial,
    )

    python_dir = artifact_root / "python"
    python_receipt_path = artifact_root / "v2-python.json"
    python_cert = run(
        [
            sys.executable,
            str(ROOT / "RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py"),
            "--profile",
            "stable",
            "--expected-base",
            parent,
            "--artifact-out-dir",
            str(python_dir),
            "--receipt-out",
            str(python_receipt_path),
        ]
    )
    python_lines = set(python_cert.stdout.splitlines())
    if (
        "PYTHON_V2_CERTIFY_FULL=PASS" not in python_lines
        or "LANGUAGE_STABLE=NO" not in python_lines
    ):
        raise V2StableAdmissionFailure(
            "V2 Python certification witnesses missing"
        )
    python_receipt = _load_receipt(
        python_receipt_path,
        "TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL_RECEIPT_V1",
    )
    python_receipt_hash = _require_v2_python_receipt(
        python_receipt,
        _single_marker(
            python_cert.stdout,
            "TEV_SCRIPT_V2_PYTHON_RECEIPT_SHA256=",
            "V2 Python certification",
        ),
        initial,
    )
    wheel_filename = str(python_receipt.get("wheel_filename"))
    wheel_sha256 = str(python_receipt.get("wheel_sha256"))
    wheel = python_dir / wheel_filename
    if (
        not wheel.is_file()
        or support.sha256_file(wheel) != wheel_sha256
    ):
        raise V2StableAdmissionFailure(
            "V2 Python wheel byte identity mismatch"
        )

    descriptor = v2_descriptor()
    descriptor_hash = descriptor.get("descriptor_hash")
    if (
        not isinstance(descriptor_hash, str)
        or len(descriptor_hash) != 64
    ):
        raise V2StableAdmissionFailure(
            "V2 stable descriptor hash is invalid"
        )
    final = support.collect_git_identity(ROOT, parent)
    if final != initial:
        raise V2StableAdmissionFailure(
            "Git identity changed during V2 Stable Admission: "
            f"{initial!r} -> {final!r}"
        )
    parent_tree = git_text("rev-parse", parent + "^{tree}")
    receipt = build_receipt(
        final,
        parent=parent,
        parent_tree=parent_tree,
        parent_certificate_sha256=observed_parent_hash,
        changed_paths=changed,
        v2_technical_receipt_sha256=v2_technical_hash,
        v1_receipt_sha256=v1_hash,
        v2_python_receipt_sha256=python_receipt_hash,
        wheel_filename=wheel_filename,
        wheel_sha256=wheel_sha256,
        descriptor_hash=descriptor_hash,
    )
    _validate_receipt(receipt)
    receipt_path = _write_stable_receipt(
        artifact_root / "tev-script-v2-stable-admission.receipt.json",
        receipt,
    )
    return receipt, receipt_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="TEV Script V2 stable release admission"
    )
    parser.add_argument(
        "--technical-parent-certificate", type=Path, required=True
    )
    parser.add_argument("--artifact-out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        receipt, receipt_path = certify(
            technical_parent_certificate=args.technical_parent_certificate,
            artifact_out_dir=args.artifact_out_dir,
        )
    except Exception as error:  # noqa: BLE001
        print("STABLE_ADMISSION=FAIL")
        print("CERTIFY_FULL=NO")
        print("LANGUAGE_STABLE=NO")
        print(
            "TEV_SCRIPT_V2_STABLE_ADMISSION_ERROR="
            + type(error).__name__
            + ":"
            + str(error)
        )
        return 1
    print(
        "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT="
        + canonical_json(receipt)
    )
    print(
        "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_SHA256="
        + str(receipt["receipt_hash"])
    )
    print(
        "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_FILE="
        + str(receipt_path)
    )
    print("CERTIFY_FULL=PASS")
    print("STABLE_ADMISSION=PASS")
    print("LANGUAGE_STABLE=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
