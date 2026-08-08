from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
V0_2_ORACLE = "6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5"
PRODUCTION_RECEIPT_SCHEMA = "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_V2"
CERTIFY_RECEIPT_SCHEMA = "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_V2"
EXPECTED_SOAK_EVENTS = 10_000


def run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def abort(
    label: str,
    message: str,
    completed: subprocess.CompletedProcess[str] | None = None,
) -> None:
    print(label + "=FAIL " + message)
    if completed is not None:
        if completed.stdout:
            print(label + "_STDOUT=" + completed.stdout[-16000:].replace("\n", "\\n"))
        if completed.stderr:
            print(label + "_STDERR=" + completed.stderr[-16000:].replace("\n", "\\n"))
    print("PYTHON_CERTIFY_FULL=NO")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    raise SystemExit(1)


def git_text(*arguments: str) -> str:
    completed = run(["git", *arguments])
    if completed.returncode != 0:
        abort("GIT_" + arguments[0].upper().replace("-", "_"), "COMMAND_FAILED", completed)
    return completed.stdout.strip()


def require_clean(stage: str) -> None:
    completed = run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
    if completed.returncode != 0:
        abort("GIT_STATUS_" + stage, "COMMAND_FAILED", completed)
    if completed.stdout:
        abort("GIT_CLEAN_" + stage, "DIRTY=" + completed.stdout.replace("\n", "\\n"))
    print("GIT_CLEAN_" + stage + "=PASS")


def file_sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def single_marker(stdout: str, prefix: str) -> str:
    values = [line[len(prefix):] for line in stdout.splitlines() if line.startswith(prefix)]
    if len(values) != 1:
        abort(
            "V1_PYTHON_CERTIFY_FULL_PRODUCTION_RECEIPT",
            f"EXPECTED_ONE_{prefix!r}_OBSERVED={values!r}",
        )
    return values[0]


def require_equal(label: str, observed: object, expected: object) -> None:
    if observed != expected:
        abort(label, f"EXPECTED={expected!r} OBSERVED={observed!r}")
    print(label + "=PASS")


def validate_authority_metadata(profile: str) -> tuple[str, str]:
    canonical = json.loads((ROOT / "CANONICAL_INDEX.json").read_text(encoding="utf-8"))
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_CANONICAL_INDEX_SCHEMA",
        canonical.get("schema"),
        "TEV_SCRIPT_CANONICAL_INDEX_V1",
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_V0_2_TOP_LEVEL_STABLE_FALSE",
        canonical.get("stable"),
        False,
    )
    targets = [
        item
        for item in canonical.get("candidate_language_targets", [])
        if isinstance(item, dict) and item.get("language_version") == "1.0.0"
    ]
    if len(targets) != 1:
        abort(
            "V1_PYTHON_CERTIFY_FULL_CANONICAL_TARGET",
            f"EXPECTED_ONE_V1_TARGET OBSERVED={len(targets)}",
        )
    target = targets[0]
    expected_stable = profile == "stable"
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_TARGET_STABLE",
        target.get("stable"),
        expected_stable,
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PRODUCTION_GATE_BINDING",
        target.get("gates", {}).get("python_production"),
        "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py",
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_GATE_BINDING",
        target.get("gates", {}).get("python_certify_full"),
        "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
    )
    surface = target.get("python_production_surface", {})
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_RUNTIME_SOURCE_FALSE",
        surface.get("runtime_accepts_source"),
        False,
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_LEAST_AUTHORITY_DEFAULT",
        surface.get("least_authority_default"),
        True,
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_SERIALIZED_HOST_ACCESS",
        surface.get("serialized_host_access"),
        True,
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_SURFACE_STABLE",
        surface.get("stable_claim"),
        expected_stable,
    )
    return (
        file_sha256("CANONICAL_INDEX.json"),
        file_sha256("PROJECT_STATE.md"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TEV Script V1 Python technical certification")
    parser.add_argument("--profile", choices=("candidate", "stable"), default="candidate")
    parser.add_argument("--artifact-out-dir")
    args = parser.parse_args(argv)
    profile = args.profile
    expected_stable = profile == "stable"
    print("V1_PYTHON_CERTIFY_FULL_PROFILE=" + profile)

    require_clean("PYTHON_CERTIFY_BEFORE")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD")

    ancestry = run(["git", "merge-base", "--is-ancestor", V0_2_ORACLE, "HEAD"])
    if ancestry.returncode != 0:
        abort("V1_PYTHON_CERTIFY_FULL_V0_2_ANCESTRY", "FAIL", ancestry)
    print("V1_PYTHON_CERTIFY_FULL_V0_2_ANCESTRY=PASS")

    canonical_sha, project_state_sha = validate_authority_metadata(profile)

    production_arguments = [
        sys.executable,
        str(ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py"),
        "--profile",
        profile,
    ]
    if args.artifact_out_dir:
        production_arguments.extend(["--artifact-out-dir", args.artifact_out_dir])
    production = run(production_arguments)
    if production.returncode != 0:
        abort("V1_PYTHON_CERTIFY_FULL_PRODUCTION", "COMMAND_FAILED", production)
    expected_witness = (
        "TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_STABLE_CANDIDATE"
        if expected_stable
        else "TEV_SCRIPT_V1_PYTHON_PRODUCTION=PASS_CANDIDATE"
    )
    if expected_witness not in production.stdout.splitlines():
        abort("V1_PYTHON_CERTIFY_FULL_PRODUCTION", "PASS_WITNESS_MISSING", production)
    if "SKIPPED_" in production.stdout or "skipped=" in production.stdout.lower():
        abort("V1_PYTHON_CERTIFY_FULL_PRODUCTION", "UNEXPECTED_SKIP", production)
    print("V1_PYTHON_CERTIFY_FULL_PRODUCTION=PASS")

    receipt_json = single_marker(
        production.stdout,
        "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_JSON=",
    )
    receipt_sha = single_marker(
        production.stdout,
        "TEV_SCRIPT_V1_PYTHON_PRODUCTION_RECEIPT_SHA256=",
    )
    try:
        receipt = json.loads(receipt_json)
    except json.JSONDecodeError as error:
        abort(
            "V1_PYTHON_CERTIFY_FULL_PRODUCTION_RECEIPT_JSON",
            type(error).__name__ + ":" + str(error),
        )
    if not isinstance(receipt, dict):
        abort("V1_PYTHON_CERTIFY_FULL_PRODUCTION_RECEIPT_JSON", "ROOT_NOT_OBJECT")

    embedded_hash = receipt.pop("receipt_hash", None)
    observed_hash = hashlib.sha256(canonical_json(receipt).encode("utf-8")).hexdigest()
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PRODUCTION_RECEIPT_MARKER_HASH",
        receipt_sha,
        observed_hash,
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PRODUCTION_RECEIPT_EMBEDDED_HASH",
        embedded_hash,
        observed_hash,
    )

    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PRODUCTION_SCHEMA",
        receipt.get("schema"),
        PRODUCTION_RECEIPT_SCHEMA,
    )
    require_equal("V1_PYTHON_CERTIFY_FULL_PRODUCTION_PROFILE", receipt.get("admission_profile"), profile)
    require_equal("V1_PYTHON_CERTIFY_FULL_PRODUCTION_BRANCH", receipt.get("branch"), branch)
    require_equal("V1_PYTHON_CERTIFY_FULL_PRODUCTION_COMMIT", receipt.get("commit"), head)
    require_equal("V1_PYTHON_CERTIFY_FULL_PRODUCTION_TREE", receipt.get("tree"), tree)
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PRODUCTION_ORACLE",
        receipt.get("v0_2_oracle"),
        V0_2_ORACLE,
    )

    mandatory = {
        "runtime_dependency_count": 0,
        "wheel_portable_tag": "py3-none-any",
        "v1_governance": "PASS",
        "frontend_closure": "PASS",
        "wheel_reproducible": True,
        "isolated_install": "PASS",
        "installed_module_origin": "VENV",
        "installed_console_scripts": "PASS",
        "installed_ir_v3_compile": "PASS",
        "installed_runtime_host": "PASS",
        "least_authority": "PASS",
        "reentrant_access_rejected": "PASS",
        "concurrent_access_rejected": "PASS",
        "typed_capability": "PASS",
        "checkpoint_restart_continuation": "PASS",
        "soak_events": EXPECTED_SOAK_EVENTS,
        "soak_result": "PASS",
        "certify_full": False,
        "language_stable": False,
    }
    for key, expected in mandatory.items():
        require_equal(
            "V1_PYTHON_CERTIFY_FULL_EVIDENCE_" + key.upper(),
            receipt.get(key),
            expected,
        )

    for key in (
        "python_version",
        "pip_version_witness",
        "setuptools_version",
        "package_name",
        "package_version",
        "wheel_filename",
        "wheel_sha256",
    ):
        value = receipt.get(key)
        if not isinstance(value, str) or not value:
            abort(
                "V1_PYTHON_CERTIFY_FULL_EVIDENCE_" + key.upper(),
                f"EXPECTED_NON_EMPTY_STRING OBSERVED={value!r}",
            )
        print("V1_PYTHON_CERTIFY_FULL_EVIDENCE_" + key.upper() + "=PASS")

    expected_version = "1.0.0" if expected_stable else "0.2.0"
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PACKAGE_VERSION",
        receipt.get("package_version"),
        expected_version,
    )

    wheel_sha256 = str(receipt["wheel_sha256"])
    if len(wheel_sha256) != 64 or any(char not in "0123456789abcdef" for char in wheel_sha256):
        abort(
            "V1_PYTHON_CERTIFY_FULL_WHEEL_SHA256",
            "INVALID_SHA256=" + wheel_sha256,
        )
    print("V1_PYTHON_CERTIFY_FULL_WHEEL_SHA256=PASS")

    require_clean("PYTHON_CERTIFY_AFTER_PRODUCTION")
    require_equal("V1_PYTHON_CERTIFY_FULL_HEAD_STABLE", git_text("rev-parse", "HEAD"), head)
    require_equal("V1_PYTHON_CERTIFY_FULL_TREE_STABLE", git_text("rev-parse", "HEAD^{tree}"), tree)
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_CANONICAL_INDEX_STABLE",
        file_sha256("CANONICAL_INDEX.json"),
        canonical_sha,
    )
    require_equal(
        "V1_PYTHON_CERTIFY_FULL_PROJECT_STATE_STABLE",
        file_sha256("PROJECT_STATE.md"),
        project_state_sha,
    )

    certificate = {
        "schema": CERTIFY_RECEIPT_SCHEMA,
        "admission_profile": profile,
        "branch": branch,
        "commit": head,
        "tree": tree,
        "v0_2_oracle": V0_2_ORACLE,
        "python_production_receipt_sha256": receipt_sha,
        "canonical_index_sha256": canonical_sha,
        "project_state_sha256": project_state_sha,
        "python_version": receipt["python_version"],
        "pip_version_witness": receipt["pip_version_witness"],
        "setuptools_version": receipt["setuptools_version"],
        "package_name": receipt["package_name"],
        "package_version": receipt["package_version"],
        "wheel_filename": receipt["wheel_filename"],
        "wheel_sha256": receipt["wheel_sha256"],
        "certified_scope": [
            "V1_PYTHON_REFERENCE_FRONTEND",
            "V1_PYTHON_SOURCE_TO_IR_V3",
            "V1_PYTHON_IR_V3_VALIDATION_AND_RUNTIME",
            "V1_PYTHON_IR_ONLY_PRODUCTION_HOST",
            "V1_PYTHON_LEAST_AUTHORITY_CAPABILITY_PREFLIGHT",
            "V1_PYTHON_SERIALIZED_HOST_ACCESS_GUARD",
            "V1_PYTHON_TYPED_CAPABILITY_EXECUTION",
            "V1_PYTHON_RUNTIME_CHECKPOINT_V2_RESTART",
            "V1_PYTHON_ZERO_RUNTIME_DEPENDENCIES",
            "V1_PYTHON_REPRODUCIBLE_PORTABLE_WHEEL",
            "V1_PYTHON_ISOLATED_WHEEL_INSTALL_AND_MODULE_ORIGIN",
            "V1_PYTHON_10000_EVENT_SEMANTIC_SOAK",
            "V0_2_PYTHON_NON_REGRESSION",
        ],
        "python_certify_full": True,
        "global_certify_full": False,
        "language_stable": False,
        "stable_release_authorized": False,
    }
    certificate_json = canonical_json(certificate)
    certificate_sha = hashlib.sha256(certificate_json.encode("utf-8")).hexdigest()

    print("TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT=" + certificate_json)
    print("TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_SHA256=" + certificate_sha)
    print("PYTHON_CERTIFY_FULL=PASS")
    print("CERTIFY_FULL=NO")
    print("LANGUAGE_STABLE=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
