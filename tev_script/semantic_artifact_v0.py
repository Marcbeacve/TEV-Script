from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from .canonical import canonical_hash
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_machine_v0 import MachineRequirementV0

ARTIFACT_DESCRIPTOR_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_ARTIFACT_DESCRIPTOR_V0"
ARTIFACT_MANIFEST_SCHEMA_V0 = "TEV_SCRIPT_REALIZATION_ARTIFACT_MANIFEST_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class ArtifactSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise ArtifactSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise ArtifactSemanticsError(what)
    return text


def _optional_hash(value: str, what: str) -> str:
    text = str(value)
    return "" if not text else _hash64(text, what)


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


@dataclass(frozen=True, slots=True)
class ArtifactDescriptorV0:
    """Semantic role of immutable bytes in one Realization.

    Physical path/filename and adapter-local ABI aliases are absent. `format_hash`
    and numeric-model hashes bind content-addressed ABI semantics supplied by the
    target MachineField.
    """

    role_id: str
    format_hash: str
    content_hash: str
    interface_hash: str = ""
    entrypoint: bool = False
    dependency_descriptor_hashes: tuple[str, ...] = ()
    required_machine_capability_semantic_hashes: tuple[str, ...] = ()
    required_numeric_model_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "role_id", _stable(self.role_id, "artifact role_id"))
        object.__setattr__(self, "format_hash", _hash64(self.format_hash, "artifact format_hash"))
        object.__setattr__(self, "content_hash", _hash64(self.content_hash, "artifact content_hash"))
        object.__setattr__(
            self,
            "interface_hash",
            _optional_hash(self.interface_hash, "artifact interface_hash"),
        )
        if not isinstance(self.entrypoint, bool):
            raise ArtifactSemanticsError("artifact entrypoint must be bool")
        if self.entrypoint and not self.interface_hash:
            raise ArtifactSemanticsError("entrypoint artifact requires interface_hash")
        object.__setattr__(
            self,
            "dependency_descriptor_hashes",
            _hashes(self.dependency_descriptor_hashes, "artifact dependency descriptor hash"),
        )
        object.__setattr__(
            self,
            "required_machine_capability_semantic_hashes",
            _hashes(
                self.required_machine_capability_semantic_hashes,
                "artifact required machine capability semantic hash",
            ),
        )
        object.__setattr__(
            self,
            "required_numeric_model_hashes",
            _hashes(self.required_numeric_model_hashes, "artifact required numeric model hash"),
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": ARTIFACT_DESCRIPTOR_SCHEMA_V0,
            "role_id": self.role_id,
            "format_hash": self.format_hash,
            "content_hash": self.content_hash,
            "interface_hash": self.interface_hash,
            "entrypoint": self.entrypoint,
            "dependency_descriptor_hashes": list(self.dependency_descriptor_hashes),
            "required_machine_capability_semantic_hashes": list(
                self.required_machine_capability_semantic_hashes
            ),
            "required_numeric_model_hashes": list(self.required_numeric_model_hashes),
        }

    @property
    def descriptor_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ArtifactManifestV0:
    descriptors: tuple[ArtifactDescriptorV0, ...]

    def __post_init__(self) -> None:
        descriptors = tuple(sorted(self.descriptors, key=lambda item: item.descriptor_hash))
        if not descriptors:
            raise ArtifactSemanticsError("artifact manifest requires at least one descriptor")
        hashes = tuple(item.descriptor_hash for item in descriptors)
        if len(set(hashes)) != len(hashes):
            raise ArtifactSemanticsError("duplicate artifact descriptor semantics")
        known = set(hashes)
        for descriptor in descriptors:
            missing = set(descriptor.dependency_descriptor_hashes) - known
            if missing:
                raise ArtifactSemanticsError(
                    "artifact dependency outside manifest closure: " + ",".join(sorted(missing))
                )
            if descriptor.descriptor_hash in descriptor.dependency_descriptor_hashes:
                raise ArtifactSemanticsError("artifact descriptor cannot depend on itself")
        if not any(item.entrypoint for item in descriptors):
            raise ArtifactSemanticsError("artifact manifest requires at least one entrypoint")
        object.__setattr__(self, "descriptors", descriptors)

    @property
    def descriptor_hashes(self) -> tuple[str, ...]:
        return tuple(item.descriptor_hash for item in self.descriptors)

    @property
    def content_hashes(self) -> tuple[str, ...]:
        return tuple(sorted(set(item.content_hash for item in self.descriptors)))

    @property
    def entrypoint_descriptor_hashes(self) -> tuple[str, ...]:
        return tuple(item.descriptor_hash for item in self.descriptors if item.entrypoint)

    @property
    def entrypoint_format_hashes(self) -> tuple[str, ...]:
        return tuple(sorted(set(item.format_hash for item in self.descriptors if item.entrypoint)))

    @property
    def machine_requirement(self) -> MachineRequirementV0:
        capability_hashes: set[str] = set()
        numeric_hashes: set[str] = set()
        for descriptor in self.descriptors:
            capability_hashes.update(descriptor.required_machine_capability_semantic_hashes)
            numeric_hashes.update(descriptor.required_numeric_model_hashes)
        return MachineRequirementV0(
            tuple(sorted(capability_hashes)),
            tuple(sorted(numeric_hashes)),
            self.entrypoint_format_hashes,
        )

    def to_object(self) -> dict[str, object]:
        return {
            "schema": ARTIFACT_MANIFEST_SCHEMA_V0,
            "descriptors": [item.to_object() for item in self.descriptors],
            "entrypoint_descriptor_hashes": list(self.entrypoint_descriptor_hashes),
            "machine_requirement": self.machine_requirement.to_object(),
        }

    @property
    def manifest_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.artifact_manifest.v0", self.to_object())


def manifest_from_single_artifact(
    *,
    role_id: str,
    format_hash: str,
    content_hash: str,
    interface_hash: str,
    required_machine_capability_semantic_hashes: Iterable[str] = (),
    required_numeric_model_hashes: Iterable[str] = (),
) -> ArtifactManifestV0:
    return ArtifactManifestV0(
        (
            ArtifactDescriptorV0(
                role_id=role_id,
                format_hash=format_hash,
                content_hash=content_hash,
                interface_hash=interface_hash,
                entrypoint=True,
                required_machine_capability_semantic_hashes=tuple(
                    required_machine_capability_semantic_hashes
                ),
                required_numeric_model_hashes=tuple(required_numeric_model_hashes),
            ),
        )
    )


__all__ = [
    "ARTIFACT_DESCRIPTOR_SCHEMA_V0",
    "ARTIFACT_MANIFEST_SCHEMA_V0",
    "ArtifactSemanticsError",
    "ArtifactDescriptorV0",
    "ArtifactManifestV0",
    "manifest_from_single_artifact",
]
