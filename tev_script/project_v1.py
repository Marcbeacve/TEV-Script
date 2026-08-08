from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .diagnostics import TevScriptError
from .json_io import load_strict_json

PROJECT_SCHEMA_V1 = "TEV_SCRIPT_PROJECT_V1"
PROJECT_INPUT_SCHEMA_V1 = "TEV_SCRIPT_PROJECT_INPUT_V1"
V1_LANGUAGE_VERSION = "1.0.0"
MAX_PROJECT_BYTES = 1_000_000
MAX_PROJECT_SOURCES = 257
_PORTABLE_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True, slots=True)
class ProjectSourceV1:
    relative_path: str
    path: Path
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class ProjectManifestV1:
    manifest_path: Path
    base_directory: Path
    default_target: str
    sources: tuple[ProjectSourceV1, ...]
    normalized: dict[str, object]
    canonical_json: str
    manifest_hash: str
    project_input_hash: str

    @property
    def source_paths(self) -> tuple[Path, ...]:
        return tuple(item.path for item in self.sources)

    @property
    def relative_sources(self) -> tuple[str, ...]:
        return tuple(item.relative_path for item in self.sources)

    def input_witness(self) -> dict[str, object]:
        return {
            "schema": PROJECT_INPUT_SCHEMA_V1,
            "manifest_hash": self.manifest_hash,
            "sources": [
                {
                    "path": item.relative_path,
                    "sha256": item.sha256,
                    "bytes": item.byte_count,
                }
                for item in self.sources
            ],
            "project_input_hash": self.project_input_hash,
        }


def load_v1_project(path: str | Path) -> ProjectManifestV1:
    manifest = Path(path)
    try:
        manifest = manifest.resolve(strict=True)
    except OSError as exc:
        raise TevScriptError(
            "TEVS_V1_PROJECT_MANIFEST_MISSING",
            f"project manifest cannot be resolved: {path}",
        ) from exc
    if not manifest.is_file():
        raise TevScriptError(
            "TEVS_V1_PROJECT_MANIFEST_FILE",
            f"project manifest is not a file: {manifest}",
        )
    try:
        manifest_bytes = manifest.read_bytes()
    except OSError as exc:
        raise TevScriptError(
            "TEVS_V1_PROJECT_MANIFEST_IO",
            f"cannot read project manifest: {manifest}",
        ) from exc
    if len(manifest_bytes) > MAX_PROJECT_BYTES:
        raise TevScriptError(
            "TEVS_V1_PROJECT_MANIFEST_BUDGET",
            f"project manifest exceeds {MAX_PROJECT_BYTES} bytes",
        )

    raw = load_strict_json(manifest)
    if not isinstance(raw, dict):
        raise TevScriptError(
            "TEVS_V1_PROJECT_SHAPE",
            "project manifest root must be an object",
        )
    expected_fields = {"schema", "language_version", "default_target", "sources"}
    if set(raw) != expected_fields:
        raise TevScriptError(
            "TEVS_V1_PROJECT_FIELDS",
            f"project manifest field set mismatch: expected {sorted(expected_fields)}, got {sorted(raw)}",
        )
    if raw["schema"] != PROJECT_SCHEMA_V1:
        raise TevScriptError(
            "TEVS_V1_PROJECT_SCHEMA",
            f"expected {PROJECT_SCHEMA_V1}",
        )
    if raw["language_version"] != V1_LANGUAGE_VERSION:
        raise TevScriptError(
            "TEVS_V1_PROJECT_VERSION",
            f"expected language version {V1_LANGUAGE_VERSION}",
        )
    default_target = raw["default_target"]
    if default_target not in {"auto", "irv2", "irv3"}:
        raise TevScriptError(
            "TEVS_V1_PROJECT_TARGET",
            "default_target must be auto, irv2, or irv3",
        )
    raw_sources = raw["sources"]
    if not isinstance(raw_sources, list):
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCES",
            "sources must be an array",
        )
    if not 1 <= len(raw_sources) <= MAX_PROJECT_SOURCES:
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_COUNT",
            f"sources must contain 1..{MAX_PROJECT_SOURCES} entries",
        )

    base = manifest.parent.resolve()
    relative_seen: set[str] = set()
    resolved_seen: set[Path] = set()
    sources: list[ProjectSourceV1] = []
    for index, raw_source in enumerate(raw_sources):
        if not isinstance(raw_source, str):
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_PATH",
                f"sources[{index}] must be text",
            )
        relative = _validate_relative_source(raw_source, index)
        if relative in relative_seen:
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_DUPLICATE",
                f"duplicate source path {relative!r}",
            )
        relative_seen.add(relative)

        selected = base.joinpath(*PurePosixPath(relative).parts)
        try:
            resolved = selected.resolve(strict=True)
        except OSError as exc:
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_MISSING",
                f"project source cannot be resolved: {relative}",
            ) from exc
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_ESCAPE",
                f"project source resolves outside project directory: {relative}",
            ) from exc
        if not resolved.is_file():
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_FILE",
                f"project source is not a file: {relative}",
            )
        if resolved in resolved_seen:
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_ALIAS",
                f"multiple source paths resolve to the same file: {relative}",
            )
        resolved_seen.add(resolved)
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            raise TevScriptError(
                "TEVS_V1_PROJECT_SOURCE_IO",
                f"cannot read project source: {relative}",
            ) from exc
        sources.append(
            ProjectSourceV1(
                relative_path=relative,
                path=resolved,
                sha256=hashlib.sha256(data).hexdigest(),
                byte_count=len(data),
            )
        )

    # File-list presentation order is not semantic. Normalize by portable
    # manifest-relative path so project receipts are reproducible.
    sources.sort(key=lambda item: item.relative_path)
    normalized: dict[str, object] = {
        "schema": PROJECT_SCHEMA_V1,
        "language_version": V1_LANGUAGE_VERSION,
        "default_target": str(default_target),
        "sources": [item.relative_path for item in sources],
    }
    normalized_json = canonical_json(normalized)
    manifest_hash = canonical_hash(normalized)
    project_input_body: dict[str, object] = {
        "schema": PROJECT_INPUT_SCHEMA_V1,
        "manifest_hash": manifest_hash,
        "sources": [
            {
                "path": item.relative_path,
                "sha256": item.sha256,
                "bytes": item.byte_count,
            }
            for item in sources
        ],
    }
    project_input_hash = canonical_hash(project_input_body)
    return ProjectManifestV1(
        manifest_path=manifest,
        base_directory=base,
        default_target=str(default_target),
        sources=tuple(sources),
        normalized=normalized,
        canonical_json=normalized_json,
        manifest_hash=manifest_hash,
        project_input_hash=project_input_hash,
    )


def verify_v1_project_inputs(
    manifest: ProjectManifestV1,
    witness: Mapping[str, object] | None = None,
) -> None:
    current = load_v1_project(manifest.manifest_path)
    if current.manifest_hash != manifest.manifest_hash:
        raise TevScriptError(
            "TEVS_V1_PROJECT_MANIFEST_CHANGED",
            "project manifest changed after it was loaded",
        )
    if current.project_input_hash != manifest.project_input_hash:
        raise TevScriptError(
            "TEVS_V1_PROJECT_INPUT_CHANGED",
            "project source inputs changed after the project was loaded",
        )
    if witness is not None and canonical_json(dict(witness)) != canonical_json(manifest.input_witness()):
        raise TevScriptError(
            "TEVS_V1_PROJECT_INPUT_WITNESS",
            "project input witness does not match the loaded project",
        )


def _validate_relative_source(value: str, index: int) -> str:
    if not value or len(value) > 1024:
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_PATH",
            f"sources[{index}] path length is outside 1..1024",
        )
    if "\\" in value:
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_SEPARATOR",
            f"sources[{index}] must use '/' path separators",
        )
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_ABSOLUTE",
            f"sources[{index}] must be a relative portable path",
        )
    pure = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_TRAVERSAL",
            f"sources[{index}] cannot contain empty, '.' or '..' segments",
        )
    if any(not _PORTABLE_SEGMENT.fullmatch(part) for part in pure.parts):
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_PORTABLE",
            f"sources[{index}] contains a non-portable path segment",
        )
    if pure.suffix != ".tevs":
        raise TevScriptError(
            "TEVS_V1_PROJECT_SOURCE_EXTENSION",
            f"sources[{index}] must end in .tevs",
        )
    return pure.as_posix()
