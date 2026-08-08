from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V0_2_ORACLE = "6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5"
PRECERTIFY_RECEIPT_SCHEMA = "TEV_SCRIPT_V1_PRECERTIFY_RECEIPT_V5"
CERTIFY_RECEIPT_SCHEMA = "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V1"


def run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def abort(label: str, message: str, completed: subprocess.CompletedProcess[str] | None = None) -> None:
    print(label + "=FAIL " + message)
    if completed is not None:
        if completed.stdout:
            print(label + "_STDOUT=" + completed.stdout[-16000:].replace("\n", "\\n"))
        if completed.stderr:
            print(label + "_STDERR=" + completed.stderr[-16000:].replace("\n", "\\n"))
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


def single_marker(stdout: str, prefix: str) -> str:
    values = [line[len(prefix):] for line in stdout.splitlines() if line.startswith(prefix)]
    if len(values) != 1:
        abort("V1_CERTIFY_FULL_PRECERTIFY_RECEIPT", f"EXPECTED_ONE_{prefix!r}_OBSERVED={values!r}")
    return values[0]


def require_equal(label: str, observed: object, expected: object) -> None:
    if observed != expected:
        abort(label, f"EXPECTED={expected!r} OBSERVED={observed!r}")
    print(label + "=PASS")


def validate_authority_metadata() -> tuple[str, str, str]:
    canonical_path = ROOT / "CANONICAL_INDEX.json"
    matrix_path = ROOT / "spec" / "TEV_SCRIPT_V1_FEATURE_MATRIX.json"
    state_path = ROOT / "PROJECT_STATE.md"

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))

    require_equal("V1_CERTIFY_FULL_CANONICAL_INDEX_SCHEMA", canonical.get("schema"), "TEV_SCRIPT_CANONICAL_INDEX_V1")
    require_equal("V1_CERTIFY_FULL_REPOSITORY_STABLE_FALSE", canonical.get("stable"), False)

    targets = [
        item
        for item in canonical.get("candidate_language_targets", [])
        if item.get("language_version") == "1.0.0"
    ]
    if len(targets) != 1:
        abort("V1_CERTIFY_FULL_CANONICAL_TARGET", f"EXPECTED_ONE_V1_TARGET OBSERVED={len(targets)}")
    target = targets[0]
    require_equal(
        "V1_CERTIFY_FULL_CANONICAL_TARGET_STATUS",
        target.get("status"),
        "FULL_IMPLEMENTATION_CANDIDATE_PRECERTIFY_REQUIRED",
    )
    require_equal("V1_CERTIFY_FULL_CANONICAL_TARGET_STABLE_FALSE", target.get("stable"), False)
    require_equal(
        "V1_CERTIFY_FULL_CANONICAL_CERTIFY_GATE",
        target.get("gates", {}).get("certify_full"),
        "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py",
    )

    require_equal("V1_CERTIFY_FULL_MATRIX_SCHEMA", matrix.get("schema"), "TEV_SCRIPT_V1_FEATURE_MATRIX_V5")
    require_equal("V1_CERTIFY_FULL_MATRIX_TARGET", matrix.get("target_language_version"), "1.0.0")
    require_equal("V1_CERTIFY_FULL_MATRIX_STABLE_AUTH_FALSE", matrix.get("stable_release_authorized"), False)
    require_equal(
        "V1_CERTIFY_FULL_MATRIX_STATUS",
        matrix.get("certification_status"),
        "FULL_IMPLEMENTATION_CANDIDATE_PRECERTIFY_REQUIRED",
    )

    return (
        file_sha256("CANONICAL_INDEX.json"),
        file_sha256("spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json"),
        hashlib.sha256(state_path.read_bytes()).hexdigest(),
    )


def main() -> int:
    require_clean("CERTIFY_BEFORE")
    head = git_text("rev-parse", "HEAD")
    tree = git_text("rev-parse", "HEAD^{tree}")
    branch = git_text("rev-parse", "--abbrev-ref", "HEAD")

    ancestry = run(["git", "merge-base", "--is-ancestor", V0_2_ORACLE, "HEAD"])
    if ancestry.returncode != 0:
        abort("V1_CERTIFY_FULL_V0_2_ANCESTRY", "FAIL", ancestry)
    print("V1_CERTIFY_FULL_V0_2_ANCESTRY=PASS")

    canonical_sha, matrix_sha, project_state_sha = validate_authority_metadata()

    precertify = run([sys.executable, str(ROOT / "RUN_TEV_SCRIPT_V1_PRECERTIFY.py")])
    if precertify.returncode != 0:
        abort("V1_CERTIFY_FULL_PRECERTIFY", "COMMAND_FAILED", precertify)
    if "V1_PRECERTIFY=PASS" not in precertify.stdout.splitlines():
        abort("V1_CERTIFY_FULL_PRECERTIFY", "PASS_WITNESS_MISSING", precertify)
    if "SKIPPED_" in precertify.stdout:
        abort("V1_CERTIFY_FULL_PRECERTIFY", "UNEXPECTED_SKIP", precertify)
    print("V1_CERTIFY_FULL_PRECERTIFY=PASS")

    receipt_json = single_marker(precertify.stdout, "V1_PRECERTIFY_RECEIPT=")
    receipt_sha = single_marker(precertify.stdout, "V1_PRECERTIFY_RECEIPT_SHA256=")
    observed_receipt_sha = hashlib.sha256(receipt_json.encode("utf-8")).hexdigest()
    require_equal("V1_CERTIFY_FULL_PRECERTIFY_RECEIPT_HASH", observed_receipt_sha, receipt_sha)

    try:
        receipt = json.loads(receipt_json)
    except json.JSONDecodeError as error:
        abort("V1_CERTIFY_FULL_PRECERTIFY_RECEIPT_JSON", type(error).__name__ + ":" + str(error))

    require_equal("V1_CERTIFY_FULL_PRECERTIFY_SCHEMA", receipt.get("schema"), PRECERTIFY_RECEIPT_SCHEMA)
    require_equal("V1_CERTIFY_FULL_PRECERTIFY_BRANCH", receipt.get("branch"), branch)
    require_equal("V1_CERTIFY_FULL_PRECERTIFY_COMMIT", receipt.get("commit"), head)
    require_equal("V1_CERTIFY_FULL_PRECERTIFY_TREE", receipt.get("tree"), tree)
    require_equal("V1_CERTIFY_FULL_PRECERTIFY_ORACLE", receipt.get("v0_2_oracle"), V0_2_ORACLE)

    mandatory = {
        "v1_governance": "PASS",
        "v1_python_gate": "PASS",
        "ir_v3_csharp_v0_2_assembly_isolation": "PASS",
        "ir_v3_csharp_runtime_assembly": "PASS_NET8_DEPENDENCY_FREE",
        "ir_v3_csharp_aot_json": "PASS_REFLECTION_FREE",
        "ir_v3_python_js_csharp_parity": "PASS",
        "checkpoint_v2_cross_host": "PASS",
        "browser_wasm_v3": "PASS",
        "wasi_v3": "PASS_FRESH_RESTORE",
        "signed_update_v3_host": "PASS",
        "signed_update_v3_browser_wasm": "PASS",
        "signed_update_v3_wasi": "PASS_FRESH_RESTORE",
        "v0_2_portable_regression": "PASS",
        "certify_full": False,
        "language_stable": False,
    }
    for key, expected in mandatory.items():
        require_equal("V1_CERTIFY_FULL_EVIDENCE_" + key.upper(), receipt.get(key), expected)

    require_clean("CERTIFY_AFTER_PRECERTIFY")
    head_after = git_text("rev-parse", "HEAD")
    tree_after = git_text("rev-parse", "HEAD^{tree}")
    require_equal("V1_CERTIFY_FULL_HEAD_STABLE", head_after, head)
    require_equal("V1_CERTIFY_FULL_TREE_STABLE", tree_after, tree)

    require_equal("V1_CERTIFY_FULL_CANONICAL_INDEX_STABLE", file_sha256("CANONICAL_INDEX.json"), canonical_sha)
    require_equal(
        "V1_CERTIFY_FULL_FEATURE_MATRIX_STABLE",
        file_sha256("spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json"),
        matrix_sha,
    )
    require_equal("V1_CERTIFY_FULL_PROJECT_STATE_STABLE", file_sha256("PROJECT_STATE.md"), project_state_sha)

    certificate = {
        "schema": CERTIFY_RECEIPT_SCHEMA,
        "branch": branch,
        "commit": head,
        "tree": tree,
        "v0_2_oracle": V0_2_ORACLE,
        "precertify_receipt_sha256": receipt_sha,
        "tracked_index_manifest_sha256": receipt["tracked_index_manifest_sha256"],
        "canonical_index_sha256": canonical_sha,
        "feature_matrix_sha256": matrix_sha,
        "project_state_sha256": project_state_sha,
        "certified_scope": [
            "V1_GOVERNANCE_AND_AUTHORITY_BINDINGS",
            "V1_REFERENCE_FRONTEND_AND_STATIC_SEMANTICS",
            "V1_LINKED_CANONICAL_PROGRAM",
            "V1_TO_IR_V2_ERASABLE_PROFILE",
            "V1_TO_IR_V3_FULL_ALGEBRAIC_PROFILE",
            "IR_V3_PYTHON_JAVASCRIPT_CSHARP_BYTE_LOCK",
            "RUNTIME_CHECKPOINT_V2_CROSS_HOST_RESTART",
            "IR_V3_BROWSER_WASM_AOT",
            "IR_V3_WASI_FRESH_RESTORE",
            "SIGNED_UPDATE_V3_HOST",
            "SIGNED_UPDATE_V3_BROWSER_WASM",
            "SIGNED_UPDATE_V3_WASI_FRESH_RESTORE",
            "V0_2_PORTABLE_NON_REGRESSION",
        ],
        "certify_full": True,
        "language_stable": False,
    }
    certificate_json = json.dumps(
        certificate,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    certificate_sha = hashlib.sha256(certificate_json.encode("utf-8")).hexdigest()

    print("V1_CERTIFY_FULL_RECEIPT=" + certificate_json)
    print("V1_CERTIFY_FULL_RECEIPT_SHA256=" + certificate_sha)
    print("CERTIFY_FULL=PASS")
    print("LANGUAGE_STABLE=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
