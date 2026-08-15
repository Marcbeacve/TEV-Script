from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Sequence

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator  # noqa: E402

from tev_script.canonical import canonical_hash, canonical_json  # noqa: E402
from tev_script.descriptor_v2 import V2_CERTIFIED_BASE_SHA as CERTIFIED_BASE_SHA  # noqa: E402
from tools import v2_certification_support as certification_support  # noqa: E402

REPOSITORY = "Marcbeacve/TEV-Script"
GitIdentity = certification_support.GitIdentity
V2CertificationFailure = certification_support.V2CertificationFailure


def _git(root: Path, *arguments: str) -> str:
    return certification_support._git(root, *arguments)


def collect_git_identity(
    root: Path,
    expected_base: str = CERTIFIED_BASE_SHA,
) -> GitIdentity:
    return certification_support.collect_git_identity(
        root,
        expected_base,
        git=_git,
    )


def require_external_receipt_path(root: Path, raw: Path) -> Path:
    return certification_support.require_external_output_path(root, raw)


def _bounded(value: str | bytes | None) -> str:
    return certification_support.bounded(value)


def v2_test_modules(root: Path) -> tuple[str, ...]:
    try:
        matrix = json.loads(
            (
                root / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json"
            ).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2CertificationFailure(
            f"cannot load V2 test inventory: {error}"
        ) from error
    paths = matrix.get("governed_paths", {}).get("tests")
    if not isinstance(paths, list) or not paths:
        raise V2CertificationFailure("V2 test inventory is empty")
    modules: list[str] = []
    for relative in paths:
        if relative in {
            "tests/test_v2_certify_full.py",
            "tests/test_v2_certify_full_v2.py",
        }:
            continue
        if (
            not isinstance(relative, str)
            or not relative.startswith("tests/")
            or not relative.endswith(".py")
        ):
            raise V2CertificationFailure(
                f"invalid V2 test path: {relative!r}"
            )
        if not (root / relative).is_file():
            raise V2CertificationFailure(
                f"missing V2 test path: {relative}"
            )
        modules.append(relative[:-3].replace("/", "."))
    if len(modules) != len(set(modules)):
        raise V2CertificationFailure(
            "V2 test inventory contains duplicate modules"
        )
    return tuple(modules)


def run_checked(
    label: str,
    arguments: Sequence[str],
    required_witnesses: Sequence[str],
    *,
    timeout: int = 1800,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(arguments),
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise V2CertificationFailure(
            f"{label} timed out after {timeout}s; "
            f"stdout={_bounded(error.stdout)}; "
            f"stderr={_bounded(error.stderr)}"
        ) from error
    combined = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0:
        raise V2CertificationFailure(
            f"{label} failed exit={completed.returncode}; "
            f"stdout={_bounded(completed.stdout)}; "
            f"stderr={_bounded(completed.stderr)}"
        )
    for witness in required_witnesses:
        if witness not in combined:
            raise V2CertificationFailure(
                f"{label} missing required witness {witness!r}; "
                f"stdout={_bounded(completed.stdout)}; "
                f"stderr={_bounded(completed.stderr)}"
            )
    return completed


def _run_v2_regression() -> int:
    import re

    modules = v2_test_modules(ROOT)
    completed = run_checked(
        "V2 governed regression",
        [sys.executable, "-m", "unittest", "-v", *modules],
        ("OK",),
    )
    combined = completed.stdout + "\n" + completed.stderr
    if "skipped=" in combined.lower() or "skipped '" in combined.lower():
        raise V2CertificationFailure(
            "V2 governed regression contains a skip"
        )
    matches = re.findall(r"Ran ([0-9]+) tests? in ", combined)
    if len(matches) != 1 or int(matches[0]) <= 0:
        raise V2CertificationFailure(
            "V2 governed regression test count is missing or ambiguous"
        )
    return int(matches[0])


def _single_marker(stdout: str, prefix: str, label: str) -> str:
    values = [
        line[len(prefix) :]
        for line in stdout.splitlines()
        if line.startswith(prefix)
    ]
    if len(values) != 1:
        raise V2CertificationFailure(
            f"{label} expected one {prefix!r} marker, "
            f"observed={values!r}"
        )
    return values[0]


def _require_v1_non_regression_receipt(
    receipt: dict[str, object],
    announced_hash: str,
    identity: GitIdentity,
) -> str:
    observed = canonical_hash(receipt)
    if observed != announced_hash:
        raise V2CertificationFailure(
            "V1 non-regression receipt announced hash mismatch"
        )
    if (
        receipt.get("schema")
        != "TEV_SCRIPT_V1_CERTIFY_FULL_RECEIPT_V2"
        or receipt.get("admission_profile") != "stable"
        or receipt.get("commit") != identity.commit_sha
        or receipt.get("tree") != identity.tree_sha
        or receipt.get("certify_full") is not True
        or receipt.get("language_stable") is not False
    ):
        raise V2CertificationFailure(
            "V1 non-regression receipt identity/claims mismatch"
        )
    return observed


def _run_v1_non_regression(identity: GitIdentity) -> str:
    with tempfile.TemporaryDirectory(prefix="tev_v2_v1_cert_") as raw:
        receipt = Path(raw) / "v1-certify-full.json"
        completed = run_checked(
            "V1 non-regression certification",
            [
                sys.executable,
                str(ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py"),
                "--profile",
                "stable",
                "--receipt-out",
                str(receipt),
            ],
            ("CERTIFY_FULL=PASS", "LANGUAGE_STABLE=NO"),
            timeout=3600,
        )
        try:
            parsed = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise V2CertificationFailure(
                f"cannot load fresh V1 receipt: {error}"
            ) from error
        if not isinstance(parsed, dict):
            raise V2CertificationFailure(
                "fresh V1 receipt root must be an object"
            )
        return _require_v1_non_regression_receipt(
            parsed,
            _single_marker(
                completed.stdout,
                "V1_CERTIFY_FULL_RECEIPT_SHA256=",
                "V1 non-regression certification",
            ),
            identity,
        )


def _gate_receipt_fields() -> dict[str, str]:
    return {
        "authority_inventory": "PASS",
        "schemas_contracts": "PASS",
        "cli_v2": "PASS",
        "source_static": "PASS",
        "program_ir_v4": "PASS",
        "filesystem_safety": "PASS",
        "toctou_closure": "PASS",
        "one_mib_pre_admission": "PASS",
        "v2_negative_campaign": "PASS",
        "v2_regression": "PASS",
        "v1_certify_full": "PASS",
    }


def _gate_receipt_fields_v2() -> dict[str, str]:
    return {
        **_gate_receipt_fields(),
        "stable_tooling_authority": "PASS",
    }


def build_receipt(
    identity: GitIdentity,
    *,
    python_version: str,
    v2_test_count: int,
    v1_receipt_sha256: str,
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1",
        "repository": REPOSITORY,
        "commit_sha": identity.commit_sha,
        "tree_sha": identity.tree_sha,
        "base_sha": identity.base_sha,
        "branch": identity.branch,
        "dirty": False,
        "python_version": python_version,
        "gates": _gate_receipt_fields(),
        "v2_test_count": v2_test_count,
        "v2_skipped_tests": 0,
        "v1_receipt_sha256": v1_receipt_sha256,
    }
    return {**body, "receipt_hash": canonical_hash(body)}


def build_receipt_v2(
    identity: GitIdentity,
    *,
    admission_profile: str,
    python_version: str,
    v2_test_count: int,
    v1_receipt_sha256: str,
) -> dict[str, object]:
    if admission_profile not in {"candidate", "stable"}:
        raise V2CertificationFailure(
            f"unsupported V2 admission profile: {admission_profile!r}"
        )
    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2",
        "admission_profile": admission_profile,
        "repository": REPOSITORY,
        "commit_sha": identity.commit_sha,
        "tree_sha": identity.tree_sha,
        "base_sha": identity.base_sha,
        "branch": identity.branch,
        "dirty": False,
        "python_version": python_version,
        "gates": _gate_receipt_fields_v2(),
        "v2_test_count": v2_test_count,
        "v2_skipped_tests": 0,
        "v1_receipt_sha256": v1_receipt_sha256,
        "certify_full": True,
        "language_stable": False,
    }
    return {**body, "receipt_hash": canonical_hash(body)}


def _schema_path(current_base_mode: bool) -> Path:
    filename = (
        "tev-script-v2-certify-full-receipt-v2.schema.json"
        if current_base_mode
        else "tev-script-v2-certify-full-receipt.schema.json"
    )
    return ROOT / "schemas" / filename


def _validate_receipt(
    receipt: dict[str, object],
    *,
    current_base_mode: bool,
) -> None:
    try:
        schema = json.loads(
            _schema_path(current_base_mode).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
    except Exception as error:
        raise V2CertificationFailure(
            f"V2 receipt schema validation failed: {error}"
        ) from error


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json(receipt).encode("utf-8")
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def certify(
    receipt_out: Path | None,
    *,
    profile: str = "candidate",
    expected_base: str | None = None,
) -> dict[str, object]:
    if profile not in {"candidate", "stable"}:
        raise V2CertificationFailure(
            f"unsupported V2 certification profile: {profile!r}"
        )
    current_base_mode = expected_base is not None
    if not current_base_mode and profile != "candidate":
        raise V2CertificationFailure(
            "legacy V2 certification supports candidate profile only"
        )
    base = (
        CERTIFIED_BASE_SHA
        if expected_base is None
        else certification_support.require_git_sha(
            expected_base,
            "expected base",
        )
    )
    selected_receipt = (
        None
        if receipt_out is None
        else require_external_receipt_path(ROOT, receipt_out)
    )
    initial = collect_git_identity(ROOT, base)
    run_checked(
        "V2 authority",
        [
            sys.executable,
            str(ROOT / "tools" / "validate_v2_authority.py"),
            "--profile",
            profile,
        ],
        (
            f"TEV_SCRIPT_V2_AUTHORITY_PROFILE={profile}",
            "V2_NORMATIVE_SPEC=PASS",
            "V2_SCHEMAS_CONTRACTS=PASS",
            "CLI_V2=PASS",
            "V2_SOURCE_STATIC=PASS",
            "V2_PROGRAM_IR_V4=PASS",
            "TEV_SCRIPT_V2_AUTHORITY=PASS",
        ),
    )
    if current_base_mode:
        run_checked(
            "V2 stable tooling authority",
            [
                sys.executable,
                str(
                    ROOT
                    / "tools"
                    / "validate_v2_stable_tooling_authority.py"
                ),
                "--profile",
                profile,
            ],
            (
                f"TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY_PROFILE={profile}",
                "TEV_SCRIPT_V2_STABLE_TOOLING_SCHEMAS=PASS",
                "TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY=PASS",
            ),
        )
    run_checked(
        "V2 filesystem safety",
        [
            sys.executable,
            str(ROOT / "tools" / "validate_v2_filesystem_safety.py"),
        ],
        (
            "FILESYSTEM_SAFETY=PASS",
            "TOCTOU_CLOSURE=PASS",
            "ONE_MIB_PRE_ADMISSION=PASS",
            "TEV_SCRIPT_V2_FILESYSTEM_SAFETY=PASS",
        ),
    )
    test_count = _run_v2_regression()
    v1_receipt_sha256 = _run_v1_non_regression(initial)
    final = collect_git_identity(ROOT, base)
    if final != initial:
        raise V2CertificationFailure(
            "Git identity changed during V2 certification: "
            f"{initial!r} -> {final!r}"
        )
    python_version = ".".join(
        str(item) for item in sys.version_info[:3]
    )
    receipt = (
        build_receipt_v2(
            final,
            admission_profile=profile,
            python_version=python_version,
            v2_test_count=test_count,
            v1_receipt_sha256=v1_receipt_sha256,
        )
        if current_base_mode
        else build_receipt(
            final,
            python_version=python_version,
            v2_test_count=test_count,
            v1_receipt_sha256=v1_receipt_sha256,
        )
    )
    _validate_receipt(
        receipt,
        current_base_mode=current_base_mode,
    )
    if selected_receipt is not None:
        _write_receipt(selected_receipt, receipt)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Certify the exact clean TEV Script V2 candidate"
    )
    parser.add_argument(
        "--profile",
        choices=("candidate", "stable"),
        default="candidate",
    )
    parser.add_argument("--expected-base")
    parser.add_argument("--receipt-out", type=Path)
    arguments = parser.parse_args(argv)
    try:
        receipt = certify(
            arguments.receipt_out,
            profile=arguments.profile,
            expected_base=arguments.expected_base,
        )
    except Exception as error:  # noqa: BLE001
        print("CERTIFY_V2=NO")
        print(
            "TEV_SCRIPT_V2_CERTIFY_FULL_ERROR="
            + type(error).__name__
            + ":"
            + str(error)
        )
        return 1
    for witness in (
        "FILESYSTEM_SAFETY=PASS",
        "TOCTOU_CLOSURE=PASS",
        "ONE_MIB_PRE_ADMISSION=PASS",
        "V2_NORMATIVE_SPEC=PASS",
        "V2_SCHEMAS_CONTRACTS=PASS",
        "CLI_V2=PASS",
        "CERTIFY_V1=PASS",
        "FULL_REGRESSION=PASS",
    ):
        print(witness)
    if receipt["schema"] == "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2":
        print("V2_STABLE_TOOLING_AUTHORITY=PASS")
    print("TEV_SCRIPT_V2_COMMIT=" + str(receipt["commit_sha"]))
    print("TEV_SCRIPT_V2_TREE=" + str(receipt["tree_sha"]))
    print("TEV_SCRIPT_V2_RECEIPT_SCHEMA=" + str(receipt["schema"]))
    print("TEV_SCRIPT_V2_RECEIPT_SHA256=" + str(receipt["receipt_hash"]))
    print("LANGUAGE_STABLE=NO")
    print("CERTIFY_V2=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
