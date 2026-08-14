from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Sequence

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator  # noqa: E402

from tev_script.canonical import canonical_hash, canonical_json  # noqa: E402
from tev_script.descriptor_v2 import V2_CERTIFIED_BASE_SHA as CERTIFIED_BASE_SHA  # noqa: E402


REPOSITORY = "Marcbeacve/TEV-Script"
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_TEST_COUNT = re.compile(r"Ran ([0-9]+) tests? in ")


class V2CertificationFailure(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GitIdentity:
    branch: str
    commit_sha: str
    tree_sha: str
    base_sha: str


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise V2CertificationFailure(
            f"git {' '.join(arguments)} failed exit={completed.returncode}; "
            f"stdout={_bounded(completed.stdout)}; stderr={_bounded(completed.stderr)}"
        )
    return completed.stdout.strip()


def collect_git_identity(root: Path) -> GitIdentity:
    dirty = _git(root, "status", "--porcelain")
    if dirty:
        raise V2CertificationFailure("dirty worktree is not certifiable: " + _bounded(dirty))
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if not branch.startswith("agent/"):
        raise V2CertificationFailure(f"V2 certification requires an agent/ branch, observed={branch!r}")
    commit_sha = _git(root, "rev-parse", "--verify", "HEAD")
    tree_sha = _git(root, "rev-parse", "--verify", "HEAD^{tree}")
    observed_origin_main = _git(root, "rev-parse", "--verify", "origin/main")
    if observed_origin_main != CERTIFIED_BASE_SHA:
        raise V2CertificationFailure(
            "origin/main drift from pinned V2 base: "
            f"expected={CERTIFIED_BASE_SHA} observed={observed_origin_main}"
        )
    base_sha = CERTIFIED_BASE_SHA
    for label, value in (("HEAD", commit_sha), ("tree", tree_sha), ("base", base_sha)):
        if _GIT_SHA.fullmatch(value) is None:
            raise V2CertificationFailure(f"invalid {label} Git identity: {value!r}")
    _git(root, "merge-base", "--is-ancestor", CERTIFIED_BASE_SHA, "HEAD")
    return GitIdentity(branch, commit_sha, tree_sha, base_sha)


def require_external_receipt_path(root: Path, raw: Path) -> Path:
    root_resolved = root.resolve()
    selected = raw.resolve()
    try:
        selected.relative_to(root_resolved)
    except ValueError:
        return selected
    raise V2CertificationFailure("V2 certification receipt must be written outside the repository")


def v2_test_modules(root: Path) -> tuple[str, ...]:
    try:
        matrix = json.loads(
            (root / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2CertificationFailure(f"cannot load V2 test inventory: {error}") from error
    paths = matrix.get("governed_paths", {}).get("tests")
    if not isinstance(paths, list) or not paths:
        raise V2CertificationFailure("V2 test inventory is empty")
    modules: list[str] = []
    for relative in paths:
        if relative == "tests/test_v2_certify_full.py":
            continue
        if not isinstance(relative, str) or not relative.startswith("tests/") or not relative.endswith(".py"):
            raise V2CertificationFailure(f"invalid V2 test path: {relative!r}")
        if not (root / relative).is_file():
            raise V2CertificationFailure(f"missing V2 test path: {relative}")
        modules.append(relative[:-3].replace("/", "."))
    if len(modules) != len(set(modules)):
        raise V2CertificationFailure("V2 test inventory contains duplicate modules")
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
            f"{label} timed out after {timeout}s; stdout={_bounded(error.stdout)}; stderr={_bounded(error.stderr)}"
        ) from error
    combined = completed.stdout + "\n" + completed.stderr
    if completed.returncode != 0:
        raise V2CertificationFailure(
            f"{label} failed exit={completed.returncode}; stdout={_bounded(completed.stdout)}; stderr={_bounded(completed.stderr)}"
        )
    for witness in required_witnesses:
        if witness not in combined:
            raise V2CertificationFailure(
                f"{label} missing required witness {witness!r}; stdout={_bounded(completed.stdout)}; stderr={_bounded(completed.stderr)}"
            )
    return completed


def _run_v2_regression() -> int:
    modules = v2_test_modules(ROOT)
    completed = run_checked(
        "V2 governed regression",
        [sys.executable, "-m", "unittest", "-v", *modules],
        ("OK",),
    )
    combined = completed.stdout + "\n" + completed.stderr
    if "skipped=" in combined.lower() or "skipped '" in combined.lower():
        raise V2CertificationFailure("V2 governed regression contains a skip")
    matches = _TEST_COUNT.findall(combined)
    if len(matches) != 1 or int(matches[0]) <= 0:
        raise V2CertificationFailure("V2 governed regression test count is missing or ambiguous")
    return int(matches[0])


def _run_v1_non_regression() -> str:
    with tempfile.TemporaryDirectory(prefix="tev_v2_v1_cert_") as raw:
        receipt = Path(raw) / "v1-certify-full.json"
        run_checked(
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
            raise V2CertificationFailure(f"cannot load fresh V1 receipt: {error}") from error
        return canonical_hash(parsed)


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
        "gates": {
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
        },
        "v2_test_count": v2_test_count,
        "v2_skipped_tests": 0,
        "v1_receipt_sha256": v1_receipt_sha256,
    }
    return {**body, "receipt_hash": canonical_hash(body)}


def _validate_receipt(receipt: dict[str, object]) -> None:
    try:
        schema = json.loads(
            (ROOT / "schemas" / "tev-script-v2-certify-full-receipt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
    except Exception as error:
        raise V2CertificationFailure(f"V2 receipt schema validation failed: {error}") from error


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


def certify(receipt_out: Path | None) -> dict[str, object]:
    selected_receipt = None if receipt_out is None else require_external_receipt_path(ROOT, receipt_out)
    initial = collect_git_identity(ROOT)
    run_checked(
        "V2 authority",
        [sys.executable, str(ROOT / "tools" / "validate_v2_authority.py")],
        (
            "V2_NORMATIVE_SPEC=PASS",
            "V2_SCHEMAS_CONTRACTS=PASS",
            "CLI_V2=PASS",
            "V2_SOURCE_STATIC=PASS",
            "V2_PROGRAM_IR_V4=PASS",
            "TEV_SCRIPT_V2_AUTHORITY=PASS",
        ),
    )
    run_checked(
        "V2 filesystem safety",
        [sys.executable, str(ROOT / "tools" / "validate_v2_filesystem_safety.py")],
        (
            "FILESYSTEM_SAFETY=PASS",
            "TOCTOU_CLOSURE=PASS",
            "ONE_MIB_PRE_ADMISSION=PASS",
            "TEV_SCRIPT_V2_FILESYSTEM_SAFETY=PASS",
        ),
    )
    test_count = _run_v2_regression()
    v1_receipt_sha256 = _run_v1_non_regression()
    final = collect_git_identity(ROOT)
    if final != initial:
        raise V2CertificationFailure(f"Git identity changed during V2 certification: {initial!r} -> {final!r}")
    python_version = ".".join(str(item) for item in sys.version_info[:3])
    receipt = build_receipt(
        final,
        python_version=python_version,
        v2_test_count=test_count,
        v1_receipt_sha256=v1_receipt_sha256,
    )
    _validate_receipt(receipt)
    if selected_receipt is not None:
        _write_receipt(selected_receipt, receipt)
    return receipt


def _bounded(value: str | bytes | None) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value
    return text[-12000:].replace("\r", "\\r").replace("\n", "\\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Certify the exact clean TEV Script V2 candidate")
    parser.add_argument("--receipt-out", type=Path)
    arguments = parser.parse_args(argv)
    try:
        receipt = certify(arguments.receipt_out)
    except Exception as error:  # noqa: BLE001
        print("CERTIFY_V2=NO")
        print("TEV_SCRIPT_V2_CERTIFY_FULL_ERROR=" + type(error).__name__ + ":" + str(error))
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
    print("TEV_SCRIPT_V2_COMMIT=" + str(receipt["commit_sha"]))
    print("TEV_SCRIPT_V2_TREE=" + str(receipt["tree_sha"]))
    print("TEV_SCRIPT_V2_RECEIPT_SHA256=" + str(receipt["receipt_hash"]))
    print("LANGUAGE_STABLE=NO")
    print("CERTIFY_V2=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
