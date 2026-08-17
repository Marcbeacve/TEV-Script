from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .version import CURRENT_LANGUAGE_VERSION

INDEX_SCHEMA = "TEV_SCRIPT_3_1_NORMATIVE_INDEX_V1"
INDEX_PATH = Path("spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def _safe_relative_path(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError("normative path must be a non-empty string")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"unsafe normative path: {raw}")
    return path.as_posix()


def load_normative_index(root: Path, index_path: Path | None = None) -> dict[str, Any]:
    root = Path(root)
    path = root / (INDEX_PATH if index_path is None else index_path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("normative index must be a JSON object")
    return value


def validate_normative_index(root: Path, index_path: Path | None = None) -> dict[str, object]:
    root = Path(root)
    try:
        index = load_normative_index(root, index_path)
        if index.get("schema") != INDEX_SCHEMA:
            raise ValueError("normative index schema mismatch")
        if index.get("language_version") != CURRENT_LANGUAGE_VERSION:
            raise ValueError("normative language version mismatch")
        if index.get("hash_algorithm") != "SHA-256":
            raise ValueError("normative hash algorithm mismatch")
        raw_entries = index.get("entries")
        if not isinstance(raw_entries, list) or not raw_entries:
            raise ValueError("normative index entries must be a non-empty list")

        seen: set[str] = set()
        files: list[dict[str, str]] = []
        mismatched: list[dict[str, str]] = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                raise ValueError("normative entry must be an object")
            path = _safe_relative_path(raw.get("path"))
            role = raw.get("role")
            expected_blob = raw.get("git_blob_sha1")
            if not isinstance(role, str) or not role:
                raise ValueError(f"missing normative role: {path}")
            if not isinstance(expected_blob, str) or len(expected_blob) != 40:
                raise ValueError(f"invalid git blob identity: {path}")
            if path in seen:
                raise ValueError(f"duplicate normative path: {path}")
            seen.add(path)
            data = (root / Path(path)).read_bytes()
            observed_blob = _git_blob_sha1(data)
            sha256 = hashlib.sha256(data).hexdigest()
            files.append({"path": path, "role": role, "sha256": sha256})
            if observed_blob != expected_blob:
                mismatched.append(
                    {
                        "path": path,
                        "expected_git_blob_sha1": expected_blob,
                        "observed_git_blob_sha1": observed_blob,
                    }
                )

        files.sort(key=lambda item: item["path"])
        mismatched.sort(key=lambda item: item["path"])
        normative_set_sha256 = hashlib.sha256(_canonical_json_bytes(files)).hexdigest()
        return {
            "schema": "TEV_SCRIPT_3_1_NORMATIVE_VALIDATION_V1",
            "status": "PASS" if not mismatched else "FAIL",
            "language_version": CURRENT_LANGUAGE_VERSION,
            "files": files,
            "mismatched": mismatched,
            "normative_set_sha256": normative_set_sha256,
        }
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        return {
            "schema": "TEV_SCRIPT_3_1_NORMATIVE_VALIDATION_V1",
            "status": "FAIL",
            "language_version": CURRENT_LANGUAGE_VERSION,
            "files": [],
            "mismatched": [],
            "normative_set_sha256": "",
            "error": str(error),
        }


__all__ = [
    "INDEX_PATH",
    "INDEX_SCHEMA",
    "load_normative_index",
    "validate_normative_index",
]
