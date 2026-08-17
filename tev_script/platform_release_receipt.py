from __future__ import annotations

import hashlib
import json
from typing import Mapping

from .version import PACKAGE_VERSION

_ALLOWED_FIELDS = frozenset(
    {
        "schema",
        "status",
        "package_version",
        "error",
        "version_identity",
        "normative_spec",
        "conformance",
        "artifact_reproducibility",
        "source_commit",
        "source_tree",
        "wheel_sha256",
        "sbom_sha256",
        "normative_set_sha256",
        "version_identity_sha256",
        "conformance_sha256",
        "build_environment_descriptor_sha256",
        "provenance_sha256",
        "runtime_dependency_count",
        "receipt_sha256",
    }
)
_PASS_FIELDS = frozenset(
    {
        "schema",
        "status",
        "package_version",
        "source_commit",
        "source_tree",
        "wheel_sha256",
        "sbom_sha256",
        "normative_set_sha256",
        "version_identity_sha256",
        "conformance_sha256",
        "build_environment_descriptor_sha256",
        "provenance_sha256",
        "runtime_dependency_count",
        "receipt_sha256",
    }
)
_CHILD_FIELDS = (
    "version_identity",
    "normative_spec",
    "conformance",
    "artifact_reproducibility",
)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _is_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def verify_platform_release_receipt(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    receipt = dict(value)
    if set(receipt) - _ALLOWED_FIELDS:
        return False
    observed_hash = receipt.pop("receipt_sha256", None)
    if not _is_hex(observed_hash, 64):
        return False
    if hashlib.sha256(_canonical_json_bytes(receipt)).hexdigest() != observed_hash:
        return False
    if receipt.get("schema") != "TEV_SCRIPT_PLATFORM_RELEASE_RECEIPT_V2":
        return False
    if receipt.get("package_version") != PACKAGE_VERSION:
        return False
    status = receipt.get("status")
    if status not in {"PASS", "HOLD", "FAIL"}:
        return False

    if status == "PASS":
        if set(value) != _PASS_FIELDS:
            return False
        if not _is_hex(receipt.get("source_commit"), 40):
            return False
        if not _is_hex(receipt.get("source_tree"), 40):
            return False
        for name in (
            "wheel_sha256",
            "sbom_sha256",
            "normative_set_sha256",
            "version_identity_sha256",
            "conformance_sha256",
            "build_environment_descriptor_sha256",
            "provenance_sha256",
        ):
            if not _is_hex(receipt.get(name), 64):
                return False
        return receipt.get("runtime_dependency_count") == 0

    error = receipt.get("error")
    if not isinstance(error, str) or not error:
        return False
    for name in _CHILD_FIELDS:
        if name in receipt and not isinstance(receipt[name], Mapping):
            return False
    for name in (
        "source_commit",
        "source_tree",
        "wheel_sha256",
        "sbom_sha256",
        "normative_set_sha256",
        "version_identity_sha256",
        "conformance_sha256",
        "build_environment_descriptor_sha256",
        "provenance_sha256",
        "runtime_dependency_count",
    ):
        if name in receipt:
            return False
    return True


__all__ = ["verify_platform_release_receipt"]
