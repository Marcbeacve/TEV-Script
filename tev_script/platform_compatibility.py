from __future__ import annotations

import importlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .version import CURRENT_LANGUAGE_VERSION, CURRENT_PROFILE, PACKAGE_VERSION

MATRIX_PATH = Path("spec/TEV_SCRIPT_VERSION_MATRIX.json")
MATRIX_SCHEMA = "TEV_SCRIPT_VERSION_MATRIX_V1"
REQUIRED_DOMAINS = {
    "language",
    "source_profile",
    "linked_program",
    "program_ir",
    "runtime_abi",
    "checkpoint",
    "package",
}
CURRENT_DOMAINS = {
    "language",
    "source_profile",
    "program_ir",
    "runtime_abi",
    "checkpoint",
    "package",
}
PROFILE_CURRENT_DOMAINS = {
    "source_profile",
    "program_ir",
    "runtime_abi",
    "checkpoint",
}
VALID_STATUSES = {"current", "compatible", "historical"}


def load_version_matrix(root: Path) -> dict[str, Any]:
    value = json.loads((Path(root) / MATRIX_PATH).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("version matrix must be a JSON object")
    return value


def _row_key(row: dict[str, Any]) -> tuple[str, str]:
    version = row.get("version")
    profile = row.get("profile", "")
    if not isinstance(version, str) or not version:
        raise ValueError("matrix row requires version")
    if not isinstance(profile, str):
        raise ValueError("matrix profile must be a string")
    return version, profile


def _authority_path(root: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError("missing authority")
    path = PurePosixPath(raw)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        raise ValueError(f"unsafe authority path: {raw}")
    resolved = root / Path(path.as_posix())
    if not resolved.is_file():
        raise ValueError(f"authority path missing: {raw}")
    return resolved


def _resolve_entrypoint(raw: object) -> None:
    if not isinstance(raw, str) or not raw:
        raise ValueError("entrypoint must be text")
    module_name, separator, attribute = raw.partition(":")
    if not module_name:
        raise ValueError(f"entrypoint unavailable: {raw}")
    try:
        value: object = importlib.import_module(module_name)
        if separator:
            if not attribute:
                raise AttributeError("empty attribute")
            for part in attribute.split("."):
                if not part:
                    raise AttributeError("empty attribute component")
                value = getattr(value, part)
    except (ImportError, AttributeError) as error:
        raise ValueError(f"entrypoint unavailable: {raw}") from error


def validate_version_matrix(root: Path) -> dict[str, object]:
    try:
        root = Path(root)
        matrix = load_version_matrix(root)
        if matrix.get("schema") != MATRIX_SCHEMA:
            raise ValueError("version matrix schema mismatch")
        if matrix.get("current_language") != CURRENT_LANGUAGE_VERSION:
            raise ValueError("current language mismatch")
        domains = matrix.get("domains")
        if not isinstance(domains, dict):
            raise ValueError("version matrix domains missing")
        missing = sorted(REQUIRED_DOMAINS - set(domains))
        if missing:
            raise ValueError("missing version domains: " + ",".join(missing))

        current_profiles: set[str] = set()
        current_counts: dict[str, int] = {}
        current_rows: dict[str, dict[str, Any]] = {}
        row_count = 0
        authorities: set[str] = set()
        entrypoint_count = 0

        for domain in sorted(REQUIRED_DOMAINS):
            rows = domains[domain]
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"empty version domain: {domain}")
            seen: set[tuple[str, str]] = set()
            current = 0
            for raw in rows:
                if not isinstance(raw, dict):
                    raise ValueError(f"invalid row in domain: {domain}")
                key = _row_key(raw)
                if key in seen:
                    raise ValueError(
                        f"duplicate version row: {domain}:{key[0]}:{key[1]}"
                    )
                seen.add(key)
                status = raw.get("status")
                if status not in VALID_STATUSES:
                    raise ValueError(f"invalid status in domain: {domain}")
                authority = raw.get("authority")
                _authority_path(root, authority)
                authorities.add(str(authority))
                if "entrypoint" in raw:
                    _resolve_entrypoint(raw["entrypoint"])
                    entrypoint_count += 1
                if status == "current":
                    current += 1
                    current_rows[domain] = dict(raw)
                    if key[1]:
                        current_profiles.add(key[1])
                row_count += 1
            current_counts[domain] = current

        for domain in CURRENT_DOMAINS:
            if current_counts[domain] != 1:
                raise ValueError(
                    f"expected exactly one current row in domain: {domain}"
                )

        if current_rows["language"].get("version") != CURRENT_LANGUAGE_VERSION:
            raise ValueError("current language row mismatch")
        if current_rows["package"].get("version") != PACKAGE_VERSION:
            raise ValueError("current package mismatch")
        for domain in PROFILE_CURRENT_DOMAINS:
            if current_rows[domain].get("profile") != CURRENT_PROFILE:
                raise ValueError(f"current profile mismatch in domain: {domain}")

        return {
            "schema": "TEV_SCRIPT_VERSION_MATRIX_VALIDATION_V2",
            "status": "PASS",
            "current_language": CURRENT_LANGUAGE_VERSION,
            "current_package": PACKAGE_VERSION,
            "current_profiles": sorted(current_profiles),
            "row_count": row_count,
            "authority_count": len(authorities),
            "entrypoint_count": entrypoint_count,
            "current_counts": current_counts,
        }
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return {
            "schema": "TEV_SCRIPT_VERSION_MATRIX_VALIDATION_V2",
            "status": "FAIL",
            "current_language": CURRENT_LANGUAGE_VERSION,
            "current_package": PACKAGE_VERSION,
            "current_profiles": [],
            "row_count": 0,
            "authority_count": 0,
            "entrypoint_count": 0,
            "error": str(error),
        }


def resolve_runtime_route(
    root: Path,
    domain: str,
    version: str,
    profile: str | None = None,
) -> dict[str, Any]:
    matrix = load_version_matrix(Path(root))
    domains = matrix.get("domains")
    if not isinstance(domains, dict) or domain not in domains:
        raise ValueError(f"unknown version domain: {domain}")
    wanted_profile = "" if profile is None else profile
    matches = [
        dict(row)
        for row in domains[domain]
        if isinstance(row, dict)
        and row.get("version") == version
        and str(row.get("profile", "")) == wanted_profile
    ]
    if len(matches) != 1:
        raise ValueError(
            f"unresolved version route: {domain}:{version}:{wanted_profile}"
        )
    return matches[0]


__all__ = [
    "MATRIX_PATH",
    "MATRIX_SCHEMA",
    "REQUIRED_DOMAINS",
    "load_version_matrix",
    "resolve_runtime_route",
    "validate_version_matrix",
]
