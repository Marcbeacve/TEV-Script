from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STABLE_RECEIPT_SCHEMA = "TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_V1"
GLOBAL_CERT_SCHEMA = "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2"
PYTHON_CERT_SCHEMA = "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V2"
STABLE_VERSION = "1.0.0"

# A stable-shaped commit may change release metadata and distribution-facing
# documentation only. Runtime/compiler/gate changes require a new technical
# candidate and must be certified before another stable attempt.
ALLOWED_RELEASE_PATHS = {
    "CANONICAL_INDEX.json",
    "CHANGELOG.md",
    "PROJECT_STATE.md",
    "README.md",
    "javascript/package.json",
    "pyproject.toml",
    "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
    "tev_script/release_metadata_v1.py",
}


def run(
    arguments: list[str],
    *,
    cwd: Path = ROOT,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def fail(label: str, message: str, completed: subprocess.CompletedProcess[str] | None = None) -> None:
    print(label + "=FAIL " + message)
    if completed is not None:
        if completed.stdout:
            print(label + "_STDOUT=" + completed.stdout[-20000:].replace("\n", "\\n"))
        if completed.stderr:
            print(label + "_STDERR=" + completed.stderr[-20000:].replace("\n", "\\n"))
    print("STABLE_ADMISSION=FAIL")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    raise SystemExit(1)


def git_text(*arguments: str) -> str:
    completed = run(["git", *arguments])
    if completed.returncode != 0:
        fail("STABLE_GIT_" + arguments[0].upper().replace("-", "_"), "COMMAND_FAILED", completed)
    return completed.stdout.strip()


def require_clean(stage: str) -> None:
    completed = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if completed.returncode != 0:
        fail("STABLE_GIT_STATUS_" + stage, "COMMAND_FAILED", completed)
    if completed.stdout:
        fail("STABLE_GIT_CLEAN_" + stage, "DIRTY=" + completed.stdout.replace("\n", "\\n"))
    print("STABLE_GIT_CLEAN_" + stage + "=PASS")


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def single_marker(stdout: str, prefix: str, label: str) -> str:
    values = [line[len(prefix):] for line in stdout.splitlines() if line.startswith(prefix)]
    if len(values) != 1:
        fail(label, f"EXPECTED_ONE_{prefix!r}_OBSERVED={values!r}")
    return values[0]


def require_equal(label: str, observed: object, expected: object) -> None:
    if observed != expected:
        fail(label, f"EXPECTED={expected!r} OBSERVED={observed!r}")
    print(label + "=PASS")


def prepare_artifact_root(raw: str) -> Path:
    destination = Path(raw).expanduser().resolve()
    try:
        destination.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        fail("STABLE_ARTIFACT_ROOT", "MUST_BE_OUTSIDE_REPOSITORY")
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        fail("STABLE_ARTIFACT_ROOT", "MUST_BE_EMPTY=" + str(destination))
    return destination


def parse_json_marker(stdout: str, prefix: str, hash_prefix: str, label: str) -> tuple[dict[str, object], str]:
    payload = single_marker(stdout, prefix, label)
    external_hash = single_marker(stdout, hash_prefix, label)
    observed_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    require_equal(label + "_HASH", observed_hash, external_hash)
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        fail(label + "_JSON", type(error).__name__ + ":" + str(error))
    if not isinstance(value, dict):
        fail(label + "_JSON", "ROOT_NOT_OBJECT")
    return value, external_hash


def validate_release_diff(parent: str, head: str) -> list[str]:
    ancestry = run(["git", "merge-base", "--is-ancestor", parent, head])
    if ancestry.returncode != 0:
        fail("STABLE_TECHNICAL_PARENT_ANCESTRY", "PARENT_NOT_ANCESTOR", ancestry)
    changed = git_text("diff", "--name-only", parent + ".." + head).splitlines()
    changed = [item for item in changed if item]
    if not changed:
        fail("STABLE_RELEASE_DIFF", "NO_RELEASE_CHANGES")
    forbidden = sorted(set(changed) - ALLOWED_RELEASE_PATHS)
    if forbidden:
        fail("STABLE_RELEASE_DIFF", "FORBIDDEN_PATHS=" + ",".join(forbidden))
    print("STABLE_RELEASE_DIFF=PASS files=" + str(len(changed)))
    return sorted(changed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEV Script V1 stable release admission")
    parser.add_argument("--artifact-out-dir", required=True)
    args = parser.parse_args(argv)

    if shutil.which("git") is None:
        fail("STABLE_TOOL_GIT", "MISSING")
    if shutil.which("npm") is None:
        fail("STABLE_TOOL_NPM", "MISSING")

    artifact_root = prepare_artifact_root(args.artifact_out_dir)
    python_artifacts = artifact_root / "python"
    javascript_artifacts = artifact_root / "javascript"
    javascript_artifacts.mkdir()

    require_clean("BEFORE")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD")

    sys.path.insert(0, str(ROOT))
    from tev_script.descriptor_v1 import v1_descriptor  # noqa: E402
    from tev_script.release_metadata_v1 import (  # noqa: E402
        RELEASE_PROFILE,
        TECHNICAL_PARENT_CERTIFICATE_SHA256,
        TECHNICAL_PARENT_COMMIT,
        validate_release_metadata,
    )

    validate_release_metadata()
    require_equal("STABLE_RELEASE_PROFILE", RELEASE_PROFILE, "stable")
    parent = TECHNICAL_PARENT_COMMIT
    parent_certificate = TECHNICAL_PARENT_CERTIFICATE_SHA256
    changed_files = validate_release_diff(parent, head)

    stable_governance = run(
        [sys.executable, str(ROOT / "tools" / "validate_v1_stable_governance.py")]
    )
    if stable_governance.returncode != 0:
        fail("STABLE_GOVERNANCE", "COMMAND_FAILED", stable_governance)
    if "TEV_SCRIPT_V1_STABLE_GOVERNANCE=PASS" not in stable_governance.stdout.splitlines():
        fail("STABLE_GOVERNANCE", "PASS_WITNESS_MISSING", stable_governance)
    print("STABLE_GOVERNANCE=PASS")

    global_cert = run(
        [
            sys.executable,
            str(ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py"),
            "--profile",
            "stable",
        ]
    )
    if global_cert.returncode != 0:
        fail("STABLE_GLOBAL_CERTIFY_FULL", "COMMAND_FAILED", global_cert)
    if "CERTIFY_FULL=PASS" not in global_cert.stdout.splitlines():
        fail("STABLE_GLOBAL_CERTIFY_FULL", "PASS_WITNESS_MISSING", global_cert)
    if "LANGUAGE_STABLE=NO" not in global_cert.stdout.splitlines():
        fail("STABLE_GLOBAL_CERTIFY_FULL", "TECHNICAL_GATE_MUST_NOT_SELF_PROMOTE", global_cert)
    global_receipt, global_receipt_hash = parse_json_marker(
        global_cert.stdout,
        "V1_CERTIFY_FULL_RECEIPT=",
        "V1_CERTIFY_FULL_RECEIPT_SHA256=",
        "STABLE_GLOBAL_CERTIFY_RECEIPT",
    )
    require_equal("STABLE_GLOBAL_CERT_SCHEMA", global_receipt.get("schema"), GLOBAL_CERT_SCHEMA)
    require_equal("STABLE_GLOBAL_CERT_PROFILE", global_receipt.get("admission_profile"), "stable")
    require_equal("STABLE_GLOBAL_CERT_COMMIT", global_receipt.get("commit"), head)
    require_equal("STABLE_GLOBAL_CERT_TREE", global_receipt.get("tree"), tree)
    require_equal("STABLE_GLOBAL_CERT_FLAG", global_receipt.get("certify_full"), True)
    require_equal("STABLE_GLOBAL_CERT_LANGUAGE_FLAG", global_receipt.get("language_stable"), False)

    python_cert = run(
        [
            sys.executable,
            str(ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py"),
            "--profile",
            "stable",
            "--artifact-out-dir",
            str(python_artifacts),
        ]
    )
    if python_cert.returncode != 0:
        fail("STABLE_PYTHON_CERTIFY_FULL", "COMMAND_FAILED", python_cert)
    if "PYTHON_CERTIFY_FULL=PASS" not in python_cert.stdout.splitlines():
        fail("STABLE_PYTHON_CERTIFY_FULL", "PASS_WITNESS_MISSING", python_cert)
    if "LANGUAGE_STABLE=NO" not in python_cert.stdout.splitlines():
        fail("STABLE_PYTHON_CERTIFY_FULL", "PYTHON_GATE_MUST_NOT_SELF_PROMOTE", python_cert)
    python_receipt, python_receipt_hash = parse_json_marker(
        python_cert.stdout,
        "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT=",
        "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_SHA256=",
        "STABLE_PYTHON_CERTIFY_RECEIPT",
    )
    require_equal("STABLE_PYTHON_CERT_SCHEMA", python_receipt.get("schema"), PYTHON_CERT_SCHEMA)
    require_equal("STABLE_PYTHON_CERT_PROFILE", python_receipt.get("admission_profile"), "stable")
    require_equal("STABLE_PYTHON_CERT_COMMIT", python_receipt.get("commit"), head)
    require_equal("STABLE_PYTHON_PACKAGE_VERSION", python_receipt.get("package_version"), STABLE_VERSION)

    wheels = sorted(python_artifacts.glob("*.whl"))
    if len(wheels) != 1:
        fail("STABLE_PYTHON_ARTIFACT", "EXPECTED_ONE_WHEEL observed=" + str(len(wheels)))
    wheel = wheels[0]
    wheel_hash = sha256_file(wheel)
    require_equal("STABLE_PYTHON_ARTIFACT_HASH", wheel_hash, python_receipt.get("wheel_sha256"))
    require_equal("STABLE_PYTHON_ARTIFACT_NAME", wheel.name, python_receipt.get("wheel_filename"))

    npm_test = run(["npm", "test"], cwd=ROOT / "javascript")
    if npm_test.returncode != 0:
        fail("STABLE_JAVASCRIPT_TEST", "COMMAND_FAILED", npm_test)
    print("STABLE_JAVASCRIPT_TEST=PASS")

    npm_pack = run(
        [
            "npm",
            "pack",
            "--json",
            "--pack-destination",
            str(javascript_artifacts),
        ],
        cwd=ROOT / "javascript",
    )
    if npm_pack.returncode != 0:
        fail("STABLE_JAVASCRIPT_PACK", "COMMAND_FAILED", npm_pack)
    try:
        pack_result = json.loads(npm_pack.stdout)
    except json.JSONDecodeError as error:
        fail("STABLE_JAVASCRIPT_PACK", "INVALID_JSON=" + str(error), npm_pack)
    if not isinstance(pack_result, list) or len(pack_result) != 1 or not isinstance(pack_result[0], dict):
        fail("STABLE_JAVASCRIPT_PACK", "EXPECTED_ONE_PACK_RESULT")
    package_info = pack_result[0]
    package_name = package_info.get("filename")
    if not isinstance(package_name, str) or not package_name:
        fail("STABLE_JAVASCRIPT_PACK", "FILENAME_MISSING")
    package_path = javascript_artifacts / package_name
    if not package_path.is_file():
        fail("STABLE_JAVASCRIPT_PACK", "ARTIFACT_MISSING=" + package_name)
    package_hash = sha256_file(package_path)
    declared_integrity = package_info.get("integrity")
    package_json = json.loads((ROOT / "javascript" / "package.json").read_text(encoding="utf-8"))
    require_equal("STABLE_JAVASCRIPT_VERSION", package_json.get("version"), STABLE_VERSION)
    print("STABLE_JAVASCRIPT_PACK=PASS")

    descriptor = v1_descriptor()
    descriptor_hash = descriptor.get("descriptor_hash")
    if not isinstance(descriptor_hash, str) or len(descriptor_hash) != 64:
        fail("STABLE_DESCRIPTOR_HASH", "INVALID=" + repr(descriptor_hash))

    require_clean("AFTER")
    require_equal("STABLE_HEAD_UNCHANGED", git_text("rev-parse", "HEAD"), head)
    require_equal("STABLE_TREE_UNCHANGED", git_text("rev-parse", "HEAD^{tree}"), tree)

    receipt = {
        "schema": STABLE_RECEIPT_SCHEMA,
        "branch": branch,
        "commit": head,
        "tree": tree,
        "language_version": STABLE_VERSION,
        "technical_parent_commit": parent,
        "technical_parent_certificate_sha256": parent_certificate,
        "release_changed_paths": changed_files,
        "global_certify_full_receipt_sha256": global_receipt_hash,
        "python_certify_full_receipt_sha256": python_receipt_hash,
        "python_package_name": python_receipt["package_name"],
        "python_package_version": python_receipt["package_version"],
        "python_wheel_filename": wheel.name,
        "python_wheel_sha256": wheel_hash,
        "javascript_package_name": package_json["name"],
        "javascript_package_version": package_json["version"],
        "javascript_package_filename": package_path.name,
        "javascript_package_sha256": package_hash,
        "javascript_npm_integrity": declared_integrity,
        "descriptor_hash": descriptor_hash,
        "canonical_index_sha256": sha256_file(ROOT / "CANONICAL_INDEX.json"),
        "feature_matrix_sha256": sha256_file(ROOT / "spec" / "TEV_SCRIPT_V1_FEATURE_MATRIX.json"),
        "certify_full": True,
        "stable_admission": True,
        "language_stable": True,
    }
    receipt_json = canonical_json(receipt)
    receipt_hash = hashlib.sha256(receipt_json.encode("utf-8")).hexdigest()
    receipt_path = artifact_root / "tev-script-v1-stable-admission.receipt.json"
    receipt_path.write_text(receipt_json + "\n", encoding="utf-8", newline="\n")

    print("TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT=" + receipt_json)
    print("TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_SHA256=" + receipt_hash)
    print("TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_FILE=" + str(receipt_path))
    print("CERTIFY_FULL=PASS")
    print("STABLE_ADMISSION=PASS")
    print("LANGUAGE_STABLE=YES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
