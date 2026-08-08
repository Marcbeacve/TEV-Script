from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_SCHEMA_V1 = "TEV_SCRIPT_PROJECT_V1"
PROJECT_INPUT_SCHEMA_V1 = "TEV_SCRIPT_PROJECT_INPUT_V1"
V1_LANGUAGE_VERSION = "1.0.0"
MAX_PROJECT_BYTES = 1_000_000
MAX_PROJECT_SOURCES = 257


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
