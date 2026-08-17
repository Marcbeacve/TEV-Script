from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence

from tev_script.descriptor_v2 import v2_descriptor
from tev_script.descriptor_v31 import v31_descriptor, verify_v31_descriptor


ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_BRANCH = "agent/tevscript-max-3-1-total-core-v1"
LANGUAGE_VERSION = "3.1.0"
PROFILE = "total_core"
SCHEMA = "TEV_SCRIPT_V31_CERTIFY_FULL_RECEIPT_V1"

V3_STABLE_TAG = "v3.0.0"
V3_STABLE_SHA = "edd868cf481c358a2b435eb014af8dfee7ab7417"
V3_STABLE_TREE = "5c17d42967965e4f6ec5316bb84d41a75f141edc"

FEATURE_MATRIX_PATH = "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json"
CONFORMANCE_MATRIX_PATH = "conformance/v31-total-core-parity.json"
CERTIFICATION_SCHEMA_PATH = "schemas/tev-script-v31-certify-full-receipt.schema.json"

TECHNICAL_REQUIRED_PATHS = frozenset({
    "RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py",
    "conformance/v31-total-core-parity.json",
    "docs/superpowers/plans/2026-08-16-tevscript-max-3-1-total-core.md",
    "docs/superpowers/specs/2026-08-16-tevscript-max-3-1-total-core-design.md",
    "docs/superpowers/specs/2026-08-16-tevscript-max-3-1-total-core-effect-input-amendment.md",
    "docs/superpowers/specs/2026-08-16-tevscript-max-3-1-total-core-js-parity-amendment.md",
    "runtime_js_v31/core.mjs",
    "runtime_js_v31/runtime_v5_total.mjs",
    "runtime_js_v31/v4_governed.mjs",
    "schemas/tev-script-program-ir-v5-total-core.schema.json",
    "schemas/tev-script-v31-certify-full-receipt.schema.json",
    "schemas/tev-script-v31-descriptor.schema.json",
    "spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json",
    "spec/TEV_SCRIPT_V31_TOTAL_CORE.md",
    "tests/test_cli_v31.py",
    "tests/test_program_ir_v5_total.py",
    "tests/test_runtime_v5_total.py",
    "tests/test_runtime_v5_total_js_parity.py",
    "tests/test_runtime_v5_total_proof.py",
    "tests/test_source_total_core_v31.py",
    "tests/test_v31_authority.py",
    "tests/test_v31_certify_full.py",
    "tests/test_v31_descriptor.py",
    "tev_script/__init__.py",
    "tev_script/cli_v31.py",
    "tev_script/describe_v31.py",
    "tev_script/descriptor_v31.py",
    "tev_script/program_ir_v5_total.py",
    "tev_script/runtime_v5_total.py",
    "tev_script/source_total_core_v31.py",
})

POST_CERT_ALLOWED_PATHS = frozenset({
    "CANONICAL_INDEX.json",
    "CHANGELOG.md",
    "README.md",
    "RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py",
    "packaging/v31/pyproject.toml",
    "packaging/v31/tools/tev_script_build_backend_v31.py",
    "schemas/tev-script-v31-stable-admission-receipt.schema.json",
    "tests/test_v31_packaging.py",
    "tests/test_v31_stable_admission.py",
})

REQUIRED_FEATURES = frozenset({
    "TOTAL_CORE_CANONICAL_IR",
    "EXACT_V4_CHILD_IDENTITY",
    "CANONICAL_V4_RESULT_BRIDGE",
    "EXTERNAL_PROOF_ADMISSION",
    "BOUNDED_QUANTA_OMEGA_CONTINUATION",
    "UNIFIED_V31_SOURCE",
    "V31_CLI_DESCRIPTOR",
    "INDEPENDENT_JAVASCRIPT_TOTAL_CORE",
    "EFFECT_EVIDENCE_SEPARATION",
    "PHYSICAL_COMMIT_EXTERNAL",
})

PRODUCTION_GATES = [
    "V31_MATRIX_PASS",
    "V31_DESCRIPTOR_PASS",
    "V31_CORE_ZERO_SKIP_PASS",
    "V31_JS_PARITY_ZERO_SKIP_PASS",
    "V3_BYTE_IDENTITY_PASS",
    "V2_BYTE_IDENTITY_PASS",
    "MINIMALITY_PASS",
    "V3_AUTHORITY_REGRESSION_PASS",
    "V2_AUTHORITY_REGRESSION_PASS",
    "PREDECESSOR_TESTS_PASS",
    "V31_CERTIFY_FULL_PASS",
]

V31_CORE_TESTS = (
    "tests/test_program_ir_v5_total.py",
    "tests/test_runtime_v5_total.py",
    "tests/test_runtime_v5_total_proof.py",
    "tests/test_source_total_core_v31.py",
    "tests/test_cli_v31.py",
    "tests/test_v31_descriptor.py",
    "tests/test_v31_authority.py",
    "tests/test_v31_certify_full.py",
)

JS_PARITY_TESTS = (
    "tests/test_runtime_v5_total_js_parity.py",
)

PREDECESSOR_TESTS = (
    "tests/test_program_ir_v4.py",
    "tests/test_program_ir_v4_recursive.py",
    "tests/test_program_ir_v4_effects.py",
    "tests/test_ir_v4_effects.py",
    "tests/test_program_ir_v5_semantic.py",
    "tests/test_runtime_v5_semantic.py",
    "tests/test_runtime_v5_js_parity.py",
    "tests/test_omega_kernel_v1.py",
    "tests/test_omega_semantic_basis_v1.py",
    "tests/test_source_program_v2.py",
    "tests/test_source_effect_program_v2.py",
    "tests/test_source_semantic_process_v3.py",
    "tests/test_cli_v3.py",
    "tests/test_v3_descriptor_runtime_targets.py",
)

_PASSED = re.compile(r"(?P<count>[0-9]+)\s+passed\b")
_SKIPPED = re.compile(r"(?P<count>[0-9]+)\s+skipped\b")
_HEX = frozenset("0123456789abcdef")


class V31CertificationFailure(RuntimeError):
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


def _positive_count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(name + " must be a positive integer")
    return value


def _zero_skip(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != 0:
        raise ValueError(name + " must be exactly zero")
    return 0


def _pass(value: Any, name: str) -> str:
    if value != "PASS":
        raise ValueError(name + " must be PASS")
    return "PASS"


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(name + " must be non-empty text")
    return value


def _list_text(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return tuple(value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V31CertificationFailure("cannot load JSON: " + path.as_posix()) from error
    if not isinstance(value, dict):
        raise V31CertificationFailure("JSON root must be object: " + path.as_posix())
    return value


def load_feature_matrix(root: Path = ROOT) -> dict[str, Any]:
    return _load_json(root / FEATURE_MATRIX_PATH)


def validate_v31_matrix(
    matrix: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if (
        matrix.get("schema") != "TEV_SCRIPT_V31_FEATURE_MATRIX_V1"
        or matrix.get("language_version") != LANGUAGE_VERSION
        or matrix.get("program_ir_version") != 5
        or matrix.get("profile") != PROFILE
    ):
        errors.append("matrix_identity")
    if (
        matrix.get("status") != "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED"
        or matrix.get("stable") is not False
        or matrix.get("publication_authorized") is not False
        or matrix.get("merge_authorized") is not False
        or matrix.get("language_stable") is not False
    ):
        errors.append("candidate_authority")
    if matrix.get("predecessor_v3") != {
        "tag": V3_STABLE_TAG,
        "commit_sha": V3_STABLE_SHA,
        "tree_sha": V3_STABLE_TREE,
        "language_version": "3.0.0",
    }:
        errors.append("predecessor_v3")
    if matrix.get("compatibility") != {
        "v3_semantics_reinterpreted": False,
        "v2_semantics_reinterpreted": False,
        "v4_child_artifacts_reinterpreted": False,
    }:
        errors.append("compatibility")

    feature_map: dict[str, str] = {}
    features = matrix.get("required_features")
    if not isinstance(features, list):
        errors.append("required_features_shape")
    else:
        for row in features:
            if (
                not isinstance(row, Mapping)
                or set(row) != {"id", "status"}
                or not isinstance(row.get("id"), str)
                or not isinstance(row.get("status"), str)
            ):
                errors.append("required_features_shape")
                continue
            feature_id = str(row["id"])
            if feature_id in feature_map:
                errors.append("required_features_duplicate")
            feature_map[feature_id] = str(row["status"])
        if frozenset(feature_map) != REQUIRED_FEATURES:
            errors.append("required_features_inventory")
        if any(status != "CLOSED" for status in feature_map.values()):
            errors.append("required_features_not_closed")

    technical = _list_text(matrix.get("technical_governed_paths"))
    if (
        technical is None
        or frozenset(technical) != TECHNICAL_REQUIRED_PATHS
        or len(technical) != len(set(technical))
        or tuple(sorted(technical)) != technical
    ):
        errors.append("technical_governed_paths")
        technical_report: list[str] = []
    else:
        technical_report = list(technical)

    post_cert = _list_text(matrix.get("post_cert_allowed_paths"))
    if (
        post_cert is None
        or frozenset(post_cert) != POST_CERT_ALLOWED_PATHS
        or len(post_cert) != len(set(post_cert))
        or tuple(sorted(post_cert)) != post_cert
    ):
        errors.append("post_cert_allowed_paths")
        post_cert_report: list[str] = []
    else:
        post_cert_report = list(post_cert)

    if TECHNICAL_REQUIRED_PATHS.intersection(POST_CERT_ALLOWED_PATHS):
        errors.append("governed_path_overlap")
    if matrix.get("production_gates") != PRODUCTION_GATES:
        errors.append("production_gates")
    if (
        descriptor.get("language_version") != LANGUAGE_VERSION
        or descriptor.get("program_ir_version") != 5
        or descriptor.get("profiles") != ["total_core"]
        or descriptor.get("stable") is not False
        or descriptor.get("promotion_authority") is not False
        or descriptor.get("proof_admission_external_only") is not True
        or descriptor.get("physical_effect_commit_inside_runtime") is not False
        or not verify_v31_descriptor(descriptor)
    ):
        errors.append("descriptor_binding")

    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "all_required_features_closed": not any(
            error.startswith("required_features") for error in errors
        ),
        "technical_governed_paths": technical_report,
        "post_cert_allowed_paths": post_cert_report,
        "publication_authorized": False,
        "merge_authorized": False,
        "language_stable": False,
    }


def _subprocess_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    root_text = str(root.resolve())
    env["PYTHONPATH"] = root_text if not existing else root_text + os.pathsep + existing
    return env


def _run(
    arguments: Sequence[str],
    *,
    root: Path = ROOT,
    timeout: int = 7200,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            tuple(arguments),
            cwd=root,
            env=_subprocess_environment(root),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise V31CertificationFailure("command timed out: " + repr(tuple(arguments))) from error
    if completed.returncode != 0:
        output = (completed.stdout + "\n" + completed.stderr)[-32768:]
        raise V31CertificationFailure(
            "command failed exit="
            + str(completed.returncode)
            + ": "
            + repr(tuple(arguments))
            + "; output="
            + output
        )
    return completed


def _git(root: Path, *arguments: str) -> str:
    return _run(("git", *arguments), root=root, timeout=120).stdout.strip()


def _git_bytes(root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=root,
            env=_subprocess_environment(root),
            check=False,
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as error:
        raise V31CertificationFailure("git command timed out") from error
    if completed.returncode != 0:
        raise V31CertificationFailure(
            "git failed: "
            + " ".join(arguments)
            + ": "
            + completed.stderr.decode("utf-8", "replace")[-4096:]
        )
    return completed.stdout


def _git_show_json(root: Path, ref: str, relative: str) -> dict[str, Any]:
    raw = _git_bytes(root, "show", f"{ref}:{relative}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise V31CertificationFailure(
            "cannot decode JSON from git object " + ref + ":" + relative
        ) from error
    if not isinstance(value, dict):
        raise V31CertificationFailure("git JSON root is not object: " + relative)
    return value


def _matrix_paths(matrix: Mapping[str, Any], *, include_index: bool) -> tuple[str, ...]:
    paths: set[str] = set()
    if include_index:
        paths.add("CANONICAL_INDEX.json")
    for key in ("authority_files", "stable_tooling_authority"):
        values = matrix.get(key)
        if values is None:
            continue
        checked = _list_text(values)
        if checked is None:
            raise V31CertificationFailure("malformed predecessor path list: " + key)
        paths.update(checked)
    governed = matrix.get("governed_paths")
    if not isinstance(governed, Mapping):
        raise V31CertificationFailure("predecessor governed_paths missing")
    for values in governed.values():
        checked = _list_text(values)
        if checked is None:
            raise V31CertificationFailure("malformed predecessor governed path group")
        paths.update(checked)
    return tuple(sorted(paths))


def _require_snapshot_bytes(
    root: Path,
    *,
    snapshot_ref: str,
    paths: Sequence[str],
    label: str,
) -> None:
    for relative in paths:
        path = root / relative
        if not path.is_file():
            raise V31CertificationFailure(label + " path missing: " + relative)
        expected = _git_bytes(root, "show", f"{snapshot_ref}:{relative}")
        if path.read_bytes() != expected:
            raise V31CertificationFailure(label + " byte identity changed: " + relative)


def require_predecessor_byte_identity(root: Path = ROOT) -> dict[str, Any]:
    v3_matrix = _git_show_json(
        root, V3_STABLE_SHA, "spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json"
    )
    v3_paths = set(_matrix_paths(v3_matrix, include_index=False))
    v3_paths.add("spec/TEV_SCRIPT_V3_FEATURE_MATRIX.json")
    _require_snapshot_bytes(
        root,
        snapshot_ref=V3_STABLE_SHA,
        paths=tuple(sorted(v3_paths)),
        label="V3",
    )

    v2_matrix = _git_show_json(
        root, V3_STABLE_SHA, "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json"
    )
    v2_paths = set(_matrix_paths(v2_matrix, include_index=True))
    v2_paths.add("spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json")
    _require_snapshot_bytes(
        root,
        snapshot_ref=V3_STABLE_SHA,
        paths=tuple(sorted(v2_paths)),
        label="inherited V2",
    )

    body = {
        "schema": "TEV_SCRIPT_V31_PREDECESSOR_BYTE_IDENTITY_V1",
        "status": "PASS",
        "v3_snapshot_sha": V3_STABLE_SHA,
        "v3_governed_path_count": len(v3_paths),
        "v2_inherited_snapshot_sha": V3_STABLE_SHA,
        "v2_governed_path_count": len(v2_paths),
        "v3_byte_identity": "PASS",
        "v2_byte_identity": "PASS",
    }
    return {**body, "report_hash": _hash_body(body)}


def evaluate_minimality(root: Path = ROOT) -> dict[str, Any]:
    changed_raw = _git(root, "diff", "--name-only", V3_STABLE_SHA, "--")
    changed = {
        item.strip().replace("\\", "/")
        for item in changed_raw.splitlines()
        if item.strip()
    }
    allowed = TECHNICAL_REQUIRED_PATHS | POST_CERT_ALLOWED_PATHS
    unexpected = sorted(changed - allowed)
    missing = sorted(TECHNICAL_REQUIRED_PATHS - changed)
    body = {
        "schema": "TEV_SCRIPT_V31_MINIMALITY_REPORT_V1",
        "base_sha": V3_STABLE_SHA,
        "changed_paths": sorted(changed),
        "unexpected_paths": unexpected,
        "missing_technical_paths": missing,
        "status": "PASS" if not unexpected and not missing else "FAIL",
    }
    return {**body, "report_hash": _hash_body(body)}


def _sha256_file(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise V31CertificationFailure("missing certification input: " + relative)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_certification_schema(root: Path = ROOT) -> None:
    schema = _load_json(root / CERTIFICATION_SCHEMA_PATH)
    if (
        schema.get("$id") != SCHEMA
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
    ):
        raise V31CertificationFailure("V31 certification receipt schema identity is invalid")
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        raise V31CertificationFailure("V31 certification receipt schema shape is invalid")
    if set(required) != set(properties):
        raise V31CertificationFailure(
            "V31 certification receipt schema required/property set mismatch"
        )
    for field, expected in (
        ("publication_authorized", False),
        ("merge_authorized", False),
        ("language_stable", False),
        ("certify_full", True),
    ):
        node = properties.get(field)
        if not isinstance(node, Mapping) or node.get("const") is not expected:
            raise V31CertificationFailure(
                "V31 certification schema authority field mismatch: " + field
            )


def _governed_manifest(root: Path) -> tuple[dict[str, str], str]:
    manifest = {
        relative: _sha256_file(root, relative)
        for relative in sorted(TECHNICAL_REQUIRED_PATHS)
    }
    body = {
        "schema": "TEV_SCRIPT_V31_GOVERNED_PATH_MANIFEST_V1",
        "paths": manifest,
    }
    return manifest, _hash_body(body)


def _require_git_identity(root: Path) -> tuple[str, str, str]:
    branch = _git(root, "branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise V31CertificationFailure("branch mismatch: " + branch)
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise V31CertificationFailure("certification requires clean worktree")

    head = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    if subprocess.run(
        ("git", "merge-base", "--is-ancestor", V3_STABLE_SHA, head),
        cwd=root,
        env=_subprocess_environment(root),
        check=False,
        capture_output=True,
        timeout=120,
    ).returncode != 0:
        raise V31CertificationFailure("V3 stable release is not an ancestor")

    remote_main = _git(root, "ls-remote", "origin", "refs/heads/main")
    rows = [line.split() for line in remote_main.splitlines() if line.strip()]
    if len(rows) != 1 or len(rows[0]) != 2 or rows[0][1] != "refs/heads/main":
        raise V31CertificationFailure(
            "cannot resolve exact origin/main through remote authority"
        )
    if rows[0][0] != V3_STABLE_SHA:
        raise V31CertificationFailure(
            "origin/main moved; expected V3 stable "
            + V3_STABLE_SHA
            + " observed "
            + rows[0][0]
        )

    tag_commit = _git(root, "rev-parse", V3_STABLE_TAG + "^{commit}")
    if tag_commit != V3_STABLE_SHA:
        raise V31CertificationFailure("V3 stable tag does not resolve to pinned commit")
    stable_tree = _git(root, "rev-parse", V3_STABLE_SHA + "^{tree}")
    if stable_tree != V3_STABLE_TREE:
        raise V31CertificationFailure("V3 stable tree mismatch")
    return branch, head, tree


def _parse_pytest_counts(completed: subprocess.CompletedProcess[str]) -> tuple[int, int]:
    text = completed.stdout + "\n" + completed.stderr
    passed = [int(match.group("count")) for match in _PASSED.finditer(text)]
    if not passed:
        raise V31CertificationFailure("cannot determine pytest passed count")
    skipped = [int(match.group("count")) for match in _SKIPPED.finditer(text)]
    return passed[-1], (skipped[-1] if skipped else 0)


def _gate_hash(
    name: str,
    command: Sequence[str],
    completed: subprocess.CompletedProcess[str],
) -> str:
    return _hash_body(
        {
            "schema": "TEV_SCRIPT_V31_GATE_TRANSCRIPT_V1",
            "name": name,
            "command": list(command),
            "returncode": completed.returncode,
            "stdout_sha256": hashlib.sha256(
                completed.stdout.encode("utf-8")
            ).hexdigest(),
            "stderr_sha256": hashlib.sha256(
                completed.stderr.encode("utf-8")
            ).hexdigest(),
        }
    )


def _run_pytest_gate(name: str, targets: Sequence[str]) -> tuple[int, int, str]:
    command = (
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "-o",
        "addopts=",
        *tuple(targets),
    )
    completed = _run(command)
    count, skips = _parse_pytest_counts(completed)
    if skips != 0:
        raise V31CertificationFailure(name + " requires zero skips")
    return count, skips, _gate_hash(name, command, completed)


def _run_v3_authority_gate() -> str:
    command = (sys.executable, "tools/validate_v3_authority.py", "--no-git")
    completed = _run(command, timeout=1800)
    if "V3_AUTHORITY=PASS" not in completed.stdout:
        raise V31CertificationFailure("V3 authority gate did not report PASS")
    return _gate_hash("v3_authority", command, completed)


def _evaluate_v2_authority(root: Path = ROOT) -> dict[str, Any]:
    descriptor = v2_descriptor()
    matrix = _load_json(root / "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json")
    errors: list[str] = []
    certification = descriptor.get("certification")
    if (
        descriptor.get("language_version") != "2.0.0"
        or descriptor.get("stable") is not True
        or not isinstance(certification, Mapping)
        or certification.get("publication_authorized") is not False
        or certification.get("merge_authorized") is not False
    ):
        errors.append("descriptor")
    if (
        matrix.get("schema") != "TEV_SCRIPT_V2_FEATURE_MATRIX_V1"
        or matrix.get("language_version") != "2.0.0"
        or matrix.get("stable") is not True
        or matrix.get("publication_authorized") is not False
        or matrix.get("merge_authorized") is not False
    ):
        errors.append("matrix")
    identity = require_predecessor_byte_identity(root)
    if identity["v2_byte_identity"] != "PASS":
        errors.append("byte_identity")
    body = {
        "schema": "TEV_SCRIPT_V31_V2_AUTHORITY_REGRESSION_V1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "descriptor_hash": str(descriptor.get("descriptor_hash")),
        "feature_matrix_sha256": _sha256_file(
            root, "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json"
        ),
        "v2_byte_identity": identity["v2_byte_identity"],
    }
    report = {**body, "report_hash": _hash_body(body)}
    if report["status"] != "PASS":
        raise V31CertificationFailure(
            "V2 authority regression failed: " + ",".join(errors)
        )
    return report


def build_receipt_body(
    *,
    repository: str,
    branch: str,
    commit_sha: str,
    tree_sha: str,
    v3_stable_sha: str,
    v3_stable_tree: str,
    feature_matrix_sha256: str,
    descriptor_hash: str,
    conformance_matrix_sha256: str,
    certification_schema_sha256: str,
    python_version: str,
    node_version: str,
    v31_core_test_count: int,
    v31_core_skipped_tests: int,
    js_parity_test_count: int,
    js_parity_skipped_tests: int,
    predecessor_test_count: int,
    predecessor_skipped_tests: int,
    v31_core_gate_hash: str,
    js_parity_gate_hash: str,
    predecessor_gate_hash: str,
    v3_authority_gate_hash: str,
    v2_authority_gate_hash: str,
    predecessor_identity_hash: str,
    minimality_report_hash: str,
    governed_path_count: int,
    changed_path_count: int,
    v3_byte_identity: str,
    v2_byte_identity: str,
    minimality: str,
    js_parity: str,
    governed_path_manifest_hash: str | None = None,
) -> dict[str, Any]:
    if repository != REPOSITORY:
        raise ValueError("repository identity mismatch")
    if branch != EXPECTED_BRANCH:
        raise ValueError("branch identity mismatch")
    if v3_stable_sha != V3_STABLE_SHA or v3_stable_tree != V3_STABLE_TREE:
        raise ValueError("V3 stable predecessor identity mismatch")
    _zero_skip(v31_core_skipped_tests, "v31_core_skipped_tests")
    _zero_skip(js_parity_skipped_tests, "js_parity_skipped_tests")
    _zero_skip(predecessor_skipped_tests, "predecessor_skipped_tests")
    _pass(v3_byte_identity, "v3_byte_identity")
    _pass(v2_byte_identity, "v2_byte_identity")
    _pass(minimality, "minimality")
    _pass(js_parity, "js_parity")

    governed_count = _positive_count(governed_path_count, "governed_path_count")
    if governed_count != len(TECHNICAL_REQUIRED_PATHS):
        raise ValueError("governed_path_count mismatch")
    changed_count = _positive_count(changed_path_count, "changed_path_count")
    if changed_count < governed_count:
        raise ValueError("changed_path_count cannot be below governed path count")
    manifest_hash = (
        _sha64(governed_path_manifest_hash, "governed_path_manifest_hash")
        if governed_path_manifest_hash is not None
        else _sha64(minimality_report_hash, "minimality_report_hash")
    )

    return {
        "schema": SCHEMA,
        "language_version": LANGUAGE_VERSION,
        "profile": PROFILE,
        "repository": repository,
        "branch": branch,
        "commit_sha": _sha40(commit_sha, "commit_sha"),
        "tree_sha": _sha40(tree_sha, "tree_sha"),
        "v3_stable_sha": V3_STABLE_SHA,
        "v3_stable_tree": V3_STABLE_TREE,
        "feature_matrix_sha256": _sha64(
            feature_matrix_sha256, "feature_matrix_sha256"
        ),
        "descriptor_hash": _sha64(descriptor_hash, "descriptor_hash"),
        "conformance_matrix_sha256": _sha64(
            conformance_matrix_sha256, "conformance_matrix_sha256"
        ),
        "certification_schema_sha256": _sha64(
            certification_schema_sha256, "certification_schema_sha256"
        ),
        "python_version": _text(python_version, "python_version"),
        "node_version": _text(node_version, "node_version"),
        "v31_core_test_count": _positive_count(
            v31_core_test_count, "v31_core_test_count"
        ),
        "v31_core_skipped_tests": 0,
        "js_parity_test_count": _positive_count(
            js_parity_test_count, "js_parity_test_count"
        ),
        "js_parity_skipped_tests": 0,
        "predecessor_test_count": _positive_count(
            predecessor_test_count, "predecessor_test_count"
        ),
        "predecessor_skipped_tests": 0,
        "v31_core_gate_hash": _sha64(v31_core_gate_hash, "v31_core_gate_hash"),
        "js_parity_gate_hash": _sha64(js_parity_gate_hash, "js_parity_gate_hash"),
        "predecessor_gate_hash": _sha64(
            predecessor_gate_hash, "predecessor_gate_hash"
        ),
        "v3_authority_gate_hash": _sha64(
            v3_authority_gate_hash, "v3_authority_gate_hash"
        ),
        "v2_authority_gate_hash": _sha64(
            v2_authority_gate_hash, "v2_authority_gate_hash"
        ),
        "predecessor_identity_hash": _sha64(
            predecessor_identity_hash, "predecessor_identity_hash"
        ),
        "minimality_report_hash": _sha64(
            minimality_report_hash, "minimality_report_hash"
        ),
        "governed_path_manifest_hash": manifest_hash,
        "governed_path_count": governed_count,
        "changed_path_count": changed_count,
        "v3_byte_identity": "PASS",
        "v2_byte_identity": "PASS",
        "minimality": "PASS",
        "js_parity": "PASS",
        "package_release_shape": "V31_3_1_0_TOTAL_CORE_TECHNICAL_CANDIDATE",
        "publication_authorized": False,
        "merge_authorized": False,
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
        if not isinstance(digest, str) or not hmac.compare_digest(
            digest, _hash_body(observed)
        ):
            return False
        expected = build_receipt_body(
            repository=observed["repository"],
            branch=observed["branch"],
            commit_sha=observed["commit_sha"],
            tree_sha=observed["tree_sha"],
            v3_stable_sha=observed["v3_stable_sha"],
            v3_stable_tree=observed["v3_stable_tree"],
            feature_matrix_sha256=observed["feature_matrix_sha256"],
            descriptor_hash=observed["descriptor_hash"],
            conformance_matrix_sha256=observed["conformance_matrix_sha256"],
            certification_schema_sha256=observed["certification_schema_sha256"],
            python_version=observed["python_version"],
            node_version=observed["node_version"],
            v31_core_test_count=observed["v31_core_test_count"],
            v31_core_skipped_tests=observed["v31_core_skipped_tests"],
            js_parity_test_count=observed["js_parity_test_count"],
            js_parity_skipped_tests=observed["js_parity_skipped_tests"],
            predecessor_test_count=observed["predecessor_test_count"],
            predecessor_skipped_tests=observed["predecessor_skipped_tests"],
            v31_core_gate_hash=observed["v31_core_gate_hash"],
            js_parity_gate_hash=observed["js_parity_gate_hash"],
            predecessor_gate_hash=observed["predecessor_gate_hash"],
            v3_authority_gate_hash=observed["v3_authority_gate_hash"],
            v2_authority_gate_hash=observed["v2_authority_gate_hash"],
            predecessor_identity_hash=observed["predecessor_identity_hash"],
            minimality_report_hash=observed["minimality_report_hash"],
            governed_path_manifest_hash=observed["governed_path_manifest_hash"],
            governed_path_count=observed["governed_path_count"],
            changed_path_count=observed["changed_path_count"],
            v3_byte_identity=observed["v3_byte_identity"],
            v2_byte_identity=observed["v2_byte_identity"],
            minimality=observed["minimality"],
            js_parity=observed["js_parity"],
        )
        return _canonical_bytes(observed) == _canonical_bytes(expected)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def validate_external_receipt_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve()
    root = ROOT.resolve()
    if candidate == root or root in candidate.parents:
        raise ValueError("V31 certification receipt must be outside repository")
    if candidate.exists():
        raise ValueError("V31 certification receipt is create-once")
    if not candidate.parent.exists() or not candidate.parent.is_dir():
        raise ValueError("V31 certification receipt parent must exist")
    return candidate


def certify(*, receipt_out: str | Path) -> dict[str, Any]:
    output = validate_external_receipt_path(receipt_out)
    branch, head, tree = _require_git_identity(ROOT)
    _validate_certification_schema(ROOT)

    descriptor = v31_descriptor()
    matrix_report = validate_v31_matrix(load_feature_matrix(ROOT), descriptor)
    if matrix_report["status"] != "PASS":
        raise V31CertificationFailure(
            "V31 feature matrix invalid: " + ",".join(matrix_report["errors"])
        )

    minimality_report = evaluate_minimality(ROOT)
    if minimality_report["status"] != "PASS":
        raise V31CertificationFailure(
            "minimality gate failed: "
            + json.dumps(minimality_report, sort_keys=True)
        )

    predecessor_identity = require_predecessor_byte_identity(ROOT)
    if (
        predecessor_identity["v3_byte_identity"] != "PASS"
        or predecessor_identity["v2_byte_identity"] != "PASS"
    ):
        raise V31CertificationFailure("predecessor byte identity failed")

    manifest, manifest_hash = _governed_manifest(ROOT)
    if len(manifest) != len(TECHNICAL_REQUIRED_PATHS):
        raise V31CertificationFailure("governed manifest path count mismatch")

    core_count, core_skips, core_hash = _run_pytest_gate(
        "v31_core", V31_CORE_TESTS
    )
    js_count, js_skips, js_hash = _run_pytest_gate(
        "v31_js_parity", JS_PARITY_TESTS
    )
    predecessor_count, predecessor_skips, predecessor_hash = _run_pytest_gate(
        "predecessor", PREDECESSOR_TESTS
    )
    v3_authority_hash = _run_v3_authority_gate()
    v2_authority = _evaluate_v2_authority(ROOT)

    node_version = _run(("node", "--version"), timeout=120).stdout.strip()
    if not node_version:
        raise V31CertificationFailure("cannot determine Node.js version")

    body = build_receipt_body(
        repository=REPOSITORY,
        branch=branch,
        commit_sha=head,
        tree_sha=tree,
        v3_stable_sha=V3_STABLE_SHA,
        v3_stable_tree=V3_STABLE_TREE,
        feature_matrix_sha256=_sha256_file(ROOT, FEATURE_MATRIX_PATH),
        descriptor_hash=str(descriptor["descriptor_hash"]),
        conformance_matrix_sha256=_sha256_file(ROOT, CONFORMANCE_MATRIX_PATH),
        certification_schema_sha256=_sha256_file(ROOT, CERTIFICATION_SCHEMA_PATH),
        python_version=platform.python_version(),
        node_version=node_version,
        v31_core_test_count=core_count,
        v31_core_skipped_tests=core_skips,
        js_parity_test_count=js_count,
        js_parity_skipped_tests=js_skips,
        predecessor_test_count=predecessor_count,
        predecessor_skipped_tests=predecessor_skips,
        v31_core_gate_hash=core_hash,
        js_parity_gate_hash=js_hash,
        predecessor_gate_hash=predecessor_hash,
        v3_authority_gate_hash=v3_authority_hash,
        v2_authority_gate_hash=v2_authority["report_hash"],
        predecessor_identity_hash=predecessor_identity["report_hash"],
        minimality_report_hash=minimality_report["report_hash"],
        governed_path_manifest_hash=manifest_hash,
        governed_path_count=len(manifest),
        changed_path_count=len(minimality_report["changed_paths"]),
        v3_byte_identity=predecessor_identity["v3_byte_identity"],
        v2_byte_identity=predecessor_identity["v2_byte_identity"],
        minimality=minimality_report["status"],
        js_parity="PASS",
    )
    receipt = seal_receipt(body)
    if not verify_receipt(receipt):
        raise V31CertificationFailure("generated receipt failed self-verification")

    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(
            receipt,
            stream,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        stream.write("\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="TEVScript MAX 3.1 Total-Core technical certification"
    )
    parser.add_argument("--receipt-out")
    arguments = parser.parse_args(argv)
    output = (
        Path(arguments.receipt_out)
        if arguments.receipt_out
        else ROOT.parent / "TEV_SCRIPT_V31_CERTIFY_FULL_RECEIPT.json"
    )
    try:
        receipt = certify(receipt_out=output)
    except Exception as error:  # noqa: BLE001
        print("V31_CERTIFY_FULL=FAIL")
        print("V31_CERTIFY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1

    print("V31_CERTIFY_FULL=PASS")
    print("V31_LANGUAGE_STABLE=NO")
    print("V31_PUBLICATION_AUTHORIZED=NO")
    print("V31_MERGE_AUTHORIZED=NO")
    print("V31_RECEIPT_HASH=" + receipt["receipt_hash"])
    print("V31_RECEIPT_PATH=" + output.resolve().as_posix())
    print("V31_HEAD=" + receipt["commit_sha"])
    print("V31_TREE=" + receipt["tree_sha"])
    print("V31_CORE_TEST_COUNT=" + str(receipt["v31_core_test_count"]))
    print("V31_JS_PARITY_TEST_COUNT=" + str(receipt["js_parity_test_count"]))
    print("V31_PREDECESSOR_TEST_COUNT=" + str(receipt["predecessor_test_count"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
