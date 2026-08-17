from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from typing import Callable

from .version import PACKAGE_VERSION

Builder = Callable[[Path, Path], Path]
IdentityResolver = Callable[[Path], tuple[str, str]]


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _is_hex(value: str, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(ch in "0123456789abcdef" for ch in value)
    )


def build_sbom(root: Path) -> dict[str, object]:
    root = Path(root)
    with (root / "pyproject.toml").open("rb") as stream:
        document = tomllib.load(stream)
    project = document.get("project")
    if not isinstance(project, dict):
        raise ValueError("missing [project]")
    dependencies = project.get("dependencies", [])
    if not isinstance(dependencies, list) or any(
        not isinstance(item, str) for item in dependencies
    ):
        raise ValueError("invalid dependencies")
    files: list[dict[str, object]] = []
    for path in sorted(
        (root / "tev_script").rglob("*.py"),
        key=lambda value: value.as_posix(),
    ):
        if "__pycache__" in path.parts or not path.is_file():
            continue
        data = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
                "size": len(data),
            }
        )
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_SBOM_V1",
        "package_name": str(project.get("name", "")),
        "package_version": str(project.get("version", "")),
        "dependencies": sorted(dependencies),
        "files": files,
    }
    return {
        **body,
        "sbom_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


def build_provenance(
    root: Path,
    *,
    source_commit: str,
    source_tree: str,
    normative_set_sha256: str,
    version_identity_sha256: str,
) -> dict[str, object]:
    if not _is_hex(source_commit, 40):
        raise ValueError("invalid source commit")
    if not _is_hex(source_tree, 40):
        raise ValueError("invalid source tree")
    if not _is_hex(normative_set_sha256, 64):
        raise ValueError("invalid normative set hash")
    if not _is_hex(version_identity_sha256, 64):
        raise ValueError("invalid version identity hash")
    sbom = build_sbom(Path(root))
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_PROVENANCE_V1",
        "source_commit": source_commit,
        "source_tree": source_tree,
        "package_version": PACKAGE_VERSION,
        "normative_set_sha256": normative_set_sha256,
        "version_identity_sha256": version_identity_sha256,
        "sbom_sha256": sbom["sbom_sha256"],
    }
    return {
        **body,
        "provenance_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


def compare_artifacts(path_a: Path, path_b: Path) -> dict[str, object]:
    sha_a = _sha256(path_a)
    sha_b = _sha256(path_b)
    return {
        "schema": "TEV_SCRIPT_ARTIFACT_REPRODUCIBILITY_V1",
        "status": "PASS" if sha_a == sha_b else "FAIL",
        "sha256_a": sha_a,
        "sha256_b": sha_b,
        "size_a": Path(path_a).stat().st_size,
        "size_b": Path(path_b).stat().st_size,
    }


def _default_builder(root: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_INDEX": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "SOURCE_DATE_EPOCH": "1786380000",
        }
    )
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        (
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(destination),
        ),
        cwd=root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise RuntimeError("wheel build failed")
    wheels = sorted(destination.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("expected one wheel")
    return wheels[0]


def _default_git_identity(root: Path) -> tuple[str, str]:
    def run(*arguments: str) -> str:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise RuntimeError("git identity unavailable")
        return completed.stdout.strip()

    return run("rev-parse", "HEAD"), run("rev-parse", "HEAD^{tree}")


def validate_reproducible_release(
    root: Path,
    *,
    builder: Builder | None = None,
) -> dict[str, object]:
    root = Path(root)
    build = _default_builder if builder is None else builder
    try:
        sbom = build_sbom(root)
        if sbom["package_version"] != PACKAGE_VERSION:
            raise ValueError("SBOM package version mismatch")
        with tempfile.TemporaryDirectory(
            prefix="tevscript-platform-release-"
        ) as temporary:
            temp = Path(temporary)
            artifact_a = build(root, temp / "a")
            artifact_b = build(root, temp / "b")
            comparison = compare_artifacts(artifact_a, artifact_b)
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_RELEASE_EVIDENCE_V1",
            "status": comparison["status"],
            "package_version": PACKAGE_VERSION,
            "wheel_sha256": (
                comparison["sha256_a"] if comparison["status"] == "PASS" else ""
            ),
            "artifact_reproducibility": comparison,
            "sbom_sha256": sbom["sbom_sha256"],
            "runtime_dependency_count": len(sbom["dependencies"]),
        }
        return {
            **body,
            "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
        }
    except (
        OSError,
        UnicodeError,
        ValueError,
        RuntimeError,
        tomllib.TOMLDecodeError,
    ) as error:
        body = {
            "schema": "TEV_SCRIPT_PLATFORM_RELEASE_EVIDENCE_V1",
            "status": "FAIL",
            "package_version": PACKAGE_VERSION,
            "error": str(error),
        }
        return {
            **body,
            "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
        }


def validate_platform_release(
    root: Path,
    *,
    builder: Builder | None = None,
    identity_resolver: IdentityResolver | None = None,
) -> dict[str, object]:
    from .platform_spec import validate_normative_index
    from .platform_versioning import validate_current_version_identity

    root = Path(root)
    reproduction = validate_reproducible_release(root, builder=builder)
    if reproduction.get("status") != "PASS":
        return {
            "schema": "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V1",
            "status": "FAIL",
            "artifact_reproducibility": reproduction,
        }
    version_receipt = validate_current_version_identity(root)
    normative_receipt = validate_normative_index(root)
    if (
        version_receipt.get("status") != "PASS"
        or normative_receipt.get("status") != "PASS"
    ):
        return {
            "schema": "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V1",
            "status": "FAIL",
            "artifact_reproducibility": reproduction,
            "version_identity": version_receipt,
            "normative_spec": normative_receipt,
        }
    resolver = _default_git_identity if identity_resolver is None else identity_resolver
    source_commit, source_tree = resolver(root)
    version_identity_sha256 = hashlib.sha256(
        _canonical_json_bytes(version_receipt)
    ).hexdigest()
    provenance = build_provenance(
        root,
        source_commit=source_commit,
        source_tree=source_tree,
        normative_set_sha256=str(normative_receipt["normative_set_sha256"]),
        version_identity_sha256=version_identity_sha256,
    )
    body = {
        "schema": "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V1",
        "status": "PASS",
        "package_version": PACKAGE_VERSION,
        "source_commit": source_commit,
        "source_tree": source_tree,
        "wheel_sha256": reproduction["wheel_sha256"],
        "sbom_sha256": reproduction["sbom_sha256"],
        "normative_set_sha256": normative_receipt["normative_set_sha256"],
        "version_identity_sha256": version_identity_sha256,
        "provenance_sha256": provenance["provenance_sha256"],
        "runtime_dependency_count": reproduction["runtime_dependency_count"],
    }
    return {
        **body,
        "receipt_sha256": hashlib.sha256(_canonical_json_bytes(body)).hexdigest(),
    }


__all__ = [
    "build_provenance",
    "build_sbom",
    "compare_artifacts",
    "validate_platform_release",
    "validate_reproducible_release",
]
