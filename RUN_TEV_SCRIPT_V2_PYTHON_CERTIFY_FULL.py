from __future__ import annotations

import argparse
import configparser
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile

from jsonschema import Draft202012Validator

from tev_script.canonical import canonical_hash, canonical_json
from tev_script.descriptor_v2 import v2_descriptor
from tools import v2_certification_support as support

ROOT = Path(__file__).resolve().parent
REPOSITORY = "Marcbeacve/TEV-Script"
PACKAGE_NAME = "tev-script-portable-reference"
PACKAGE_VERSION = "1.0.0"
LANGUAGE_VERSION = "2.0.0"
WHEEL_FILENAME = "tev_script_portable_reference-1.0.0-py3-none-any.whl"
RECEIPT_SCHEMA = "TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL_RECEIPT_V1"
GitIdentity = support.GitIdentity
V2PythonCertificationFailure = support.V2CertificationFailure


def require_artifact_root(raw: Path) -> Path:
    return support.require_external_empty_dir(ROOT, raw)


def read_console_scripts(wheel: Path) -> dict[str, str]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            matches = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/entry_points.txt")
            ]
            if len(matches) != 1:
                raise V2PythonCertificationFailure(
                    f"wheel requires exactly one entry_points.txt, observed={matches!r}"
                )
            text = archive.read(matches[0]).decode("utf-8")
    except (OSError, UnicodeError, zipfile.BadZipFile, KeyError) as error:
        raise V2PythonCertificationFailure(
            f"cannot read wheel entry points: {error}"
        ) from error
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read_file(io.StringIO(text))
    if not parser.has_section("console_scripts"):
        raise V2PythonCertificationFailure(
            "wheel console_scripts entry point section is missing"
        )
    return {
        name: value.strip()
        for name, value in parser.items("console_scripts")
    }


def require_v2_entry_points(scripts: dict[str, str]) -> None:
    expected = {
        "tev-script-v2": "tev_script.cli_v2:main",
        "tev-script-v2-describe": "tev_script.describe_v2:main",
    }
    for name, target in expected.items():
        if scripts.get(name) != target:
            raise V2PythonCertificationFailure(
                f"V2 wheel entry point mismatch: {name} expected={target!r} "
                f"observed={scripts.get(name)!r}"
            )


def build_receipt(
    identity: GitIdentity,
    *,
    admission_profile: str,
    python_version: str,
    wheel_filename: str,
    wheel_sha256: str,
    v1_python_receipt_sha256: str,
    descriptor_hash: str,
) -> dict[str, object]:
    if admission_profile not in {"candidate", "stable"}:
        raise V2PythonCertificationFailure(
            f"unsupported V2 Python profile: {admission_profile!r}"
        )
    body: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "admission_profile": admission_profile,
        "repository": REPOSITORY,
        "commit_sha": identity.commit_sha,
        "tree_sha": identity.tree_sha,
        "base_sha": identity.base_sha,
        "branch": identity.branch,
        "dirty": False,
        "python_version": python_version,
        "package_name": PACKAGE_NAME,
        "package_version": PACKAGE_VERSION,
        "language_version": LANGUAGE_VERSION,
        "wheel_filename": wheel_filename,
        "wheel_sha256": wheel_sha256,
        "v1_python_receipt_sha256": v1_python_receipt_sha256,
        "descriptor_hash": descriptor_hash,
        "entry_points": {
            "tev-script-v2": "tev_script.cli_v2:main",
            "tev-script-v2-describe": "tev_script.describe_v2:main",
        },
        "installed_module_origin": "VENV",
        "python_v2_certify_full": True,
        "language_stable": False,
    }
    return {**body, "receipt_hash": canonical_hash(body)}


def _single_marker(stdout: str, prefix: str) -> str:
    values = [
        line[len(prefix) :]
        for line in stdout.splitlines()
        if line.startswith(prefix)
    ]
    if len(values) != 1:
        raise V2PythonCertificationFailure(
            f"expected one marker {prefix!r}, observed={values!r}"
        )
    return values[0]


def _run(
    arguments: list[str],
    *,
    cwd: Path = ROOT,
    timeout: int = 3600,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            arguments,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise V2PythonCertificationFailure(
            f"command timed out: {arguments!r}; "
            f"stdout={support.bounded(error.stdout)}; "
            f"stderr={support.bounded(error.stderr)}"
        ) from error
    if completed.returncode != 0:
        raise V2PythonCertificationFailure(
            f"command failed exit={completed.returncode}: {arguments!r}; "
            f"stdout={support.bounded(completed.stdout)}; "
            f"stderr={support.bounded(completed.stderr)}"
        )
    return completed


def _parse_v1_python_receipt(
    stdout: str,
) -> tuple[dict[str, object], str]:
    payload = _single_marker(
        stdout,
        "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT=",
    )
    expected_hash = _single_marker(
        stdout,
        "TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL_RECEIPT_SHA256=",
    )
    observed_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if observed_hash != expected_hash:
        raise V2PythonCertificationFailure(
            "V1 Python receipt hash mismatch: "
            f"expected={expected_hash} observed={observed_hash}"
        )
    try:
        receipt = json.loads(payload)
    except json.JSONDecodeError as error:
        raise V2PythonCertificationFailure(
            f"invalid V1 Python receipt JSON: {error}"
        ) from error
    if not isinstance(receipt, dict):
        raise V2PythonCertificationFailure(
            "V1 Python receipt root must be an object"
        )
    return receipt, expected_hash


def require_v1_python_receipt_identity(
    receipt: dict[str, object],
    identity: GitIdentity,
) -> None:
    wheel_sha256 = receipt.get("wheel_sha256")
    if (
        receipt.get("admission_profile") != "stable"
        or receipt.get("commit") != identity.commit_sha
        or receipt.get("tree") != identity.tree_sha
        or receipt.get("package_name") != PACKAGE_NAME
        or receipt.get("package_version") != PACKAGE_VERSION
        or receipt.get("wheel_filename") != WHEEL_FILENAME
        or not isinstance(wheel_sha256, str)
        or len(wheel_sha256) != 64
        or any(char not in "0123456789abcdef" for char in wheel_sha256)
    ):
        raise V2PythonCertificationFailure(
            "V1 Python receipt identity/package mismatch"
        )


def require_descriptor_identity(
    installed_descriptor_hash: str,
    checkout_descriptor_hash: object,
) -> None:
    for value in (installed_descriptor_hash, checkout_descriptor_hash):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise V2PythonCertificationFailure(
                "V2 descriptor identity is not a lowercase SHA-256"
            )
    if installed_descriptor_hash != checkout_descriptor_hash:
        raise V2PythonCertificationFailure(
            "V2 descriptor identity mismatch between wheel and checkout"
        )


def _venv_python(root: Path) -> Path:
    candidate = root / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if not candidate.is_file():
        raise V2PythonCertificationFailure(
            f"isolated Python executable missing: {candidate}"
        )
    return candidate


def _installed_descriptor_hash(wheel: Path, profile: str) -> str:
    with tempfile.TemporaryDirectory(prefix="tev_v2_wheel_") as raw:
        environment = Path(raw) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = _venv_python(environment)
        _run(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(wheel),
            ],
            cwd=environment,
        )
        code = """
import json, sys
from pathlib import Path
import tev_script
from tev_script.canonical import canonical_hash
from tev_script.descriptor_v2 import v2_descriptor
module = Path(tev_script.__file__).resolve()
prefix = Path(sys.prefix).resolve()
if not module.is_relative_to(prefix):
    raise SystemExit('module_not_from_venv:' + str(module))
descriptor = v2_descriptor()
body = dict(descriptor)
observed = body.pop('descriptor_hash')
if observed != canonical_hash(body):
    raise SystemExit('descriptor_hash_mismatch')
if descriptor.get('language_version') != '2.0.0':
    raise SystemExit('language_version_mismatch')
if descriptor.get('release_profile') != sys.argv[1]:
    raise SystemExit('release_profile_mismatch:' + repr(descriptor.get('release_profile')))
print(json.dumps({'descriptor_hash': observed, 'module': str(module)}, sort_keys=True, separators=(',', ':')))
"""
        completed = _run(
            [str(python), "-I", "-c", code, profile],
            cwd=environment,
        )
        try:
            result = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as error:
            raise V2PythonCertificationFailure(
                f"invalid isolated V2 descriptor witness: {completed.stdout!r}"
            ) from error
        descriptor_hash = result.get("descriptor_hash")
        if not isinstance(descriptor_hash, str) or len(descriptor_hash) != 64:
            raise V2PythonCertificationFailure(
                "isolated descriptor hash is invalid"
            )
        return descriptor_hash


def _validate_receipt(receipt: dict[str, object]) -> None:
    schema_path = (
        ROOT
        / "schemas"
        / "tev-script-v2-python-certify-full-receipt.schema.json"
    )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
    except Exception as error:
        raise V2PythonCertificationFailure(
            f"V2 Python receipt schema validation failed: {error}"
        ) from error


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    selected = support.require_external_output_path(ROOT, path)
    selected.parent.mkdir(parents=True, exist_ok=True)
    selected.write_text(
        canonical_json(receipt) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def certify(
    *,
    admission_profile: str,
    expected_base: str,
    artifact_out_dir: Path,
    receipt_out: Path | None = None,
) -> dict[str, object]:
    if admission_profile not in {"candidate", "stable"}:
        raise V2PythonCertificationFailure(
            f"unsupported V2 Python profile: {admission_profile!r}"
        )
    base = support.require_git_sha(expected_base, "expected base")
    initial = support.collect_git_identity(ROOT, base)
    artifact_root = require_artifact_root(artifact_out_dir)

    completed = _run(
        [
            sys.executable,
            str(ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py"),
            "--profile",
            "stable",
            "--artifact-out-dir",
            str(artifact_root),
        ]
    )
    lines = set(completed.stdout.splitlines())
    if (
        "PYTHON_CERTIFY_FULL=PASS" not in lines
        or "LANGUAGE_STABLE=NO" not in lines
    ):
        raise V2PythonCertificationFailure(
            "V1 Python certification witnesses are incomplete"
        )
    v1_receipt, v1_receipt_hash = _parse_v1_python_receipt(
        completed.stdout
    )
    require_v1_python_receipt_identity(v1_receipt, initial)
    wheel = artifact_root / WHEEL_FILENAME
    if not wheel.is_file():
        raise V2PythonCertificationFailure(
            f"V2 reference wheel is missing: {wheel}"
        )
    wheel_hash = support.sha256_file(wheel)
    if wheel_hash != v1_receipt.get("wheel_sha256"):
        raise V2PythonCertificationFailure(
            "V1/V2 wheel SHA-256 mismatch"
        )
    scripts = read_console_scripts(wheel)
    require_v2_entry_points(scripts)
    installed_descriptor_hash = _installed_descriptor_hash(
        wheel,
        admission_profile,
    )
    checkout_descriptor = v2_descriptor()
    if checkout_descriptor.get("release_profile") != admission_profile:
        raise V2PythonCertificationFailure(
            "V2 checkout descriptor release profile mismatch"
        )
    require_descriptor_identity(
        installed_descriptor_hash,
        checkout_descriptor.get("descriptor_hash"),
    )

    final = support.collect_git_identity(ROOT, base)
    if final != initial:
        raise V2PythonCertificationFailure(
            "Git identity changed during V2 Python certification: "
            f"{initial!r} -> {final!r}"
        )
    receipt = build_receipt(
        final,
        admission_profile=admission_profile,
        python_version=".".join(
            str(item) for item in sys.version_info[:3]
        ),
        wheel_filename=WHEEL_FILENAME,
        wheel_sha256=wheel_hash,
        v1_python_receipt_sha256=v1_receipt_hash,
        descriptor_hash=installed_descriptor_hash,
    )
    _validate_receipt(receipt)
    if receipt_out is not None:
        _write_receipt(receipt_out, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Certify the TEV Script V2 Python wheel surface"
    )
    parser.add_argument(
        "--profile",
        choices=("candidate", "stable"),
        default="candidate",
    )
    parser.add_argument("--expected-base", required=True)
    parser.add_argument(
        "--artifact-out-dir",
        type=Path,
        required=True,
    )
    parser.add_argument("--receipt-out", type=Path)
    args = parser.parse_args(argv)
    try:
        receipt = certify(
            admission_profile=args.profile,
            expected_base=args.expected_base,
            artifact_out_dir=args.artifact_out_dir,
            receipt_out=args.receipt_out,
        )
    except Exception as error:  # noqa: BLE001
        print("PYTHON_V2_CERTIFY_FULL=NO")
        print(
            "TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL_ERROR="
            + type(error).__name__
            + ":"
            + str(error)
        )
        print("LANGUAGE_STABLE=NO")
        return 1
    print("V2_PYTHON_PACKAGE_VERSION=1.0.0")
    print("V2_LANGUAGE_VERSION=2.0.0")
    print("V2_PYTHON_ENTRY_POINTS=PASS")
    print("V2_PYTHON_INSTALLED_ORIGIN=VENV")
    print("V2_PYTHON_WHEEL_SHA256=" + str(receipt["wheel_sha256"]))
    print(
        "TEV_SCRIPT_V2_PYTHON_RECEIPT_SHA256="
        + str(receipt["receipt_hash"])
    )
    print("PYTHON_V2_CERTIFY_FULL=PASS")
    print("LANGUAGE_STABLE=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
