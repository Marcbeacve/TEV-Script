from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re
from typing import Any, Iterable, Mapping

from .canonical import canonical_hash, canonical_json
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping

MACHINE_SCHEMA_V0 = "TEV_SCRIPT_MACHINE_FIELD_V0"
MACHINE_PROFILE_SCHEMA_V0 = "TEV_SCRIPT_MACHINE_PROFILE_V0"
MACHINE_CAPABILITY_PROFILE_SCHEMA_V0 = "TEV_SCRIPT_MACHINE_CAPABILITY_PROFILE_V0"
NUMERIC_MODEL_PROFILE_SCHEMA_V0 = "TEV_SCRIPT_NUMERIC_MODEL_PROFILE_V0"
MEMORY_SPACE_PROFILE_SCHEMA_V0 = "TEV_SCRIPT_MEMORY_SPACE_PROFILE_V0"
EXECUTABLE_FORMAT_PROFILE_SCHEMA_V0 = "TEV_SCRIPT_EXECUTABLE_FORMAT_PROFILE_V0"
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")


class MachineSemanticsError(ValueError):
    pass


def _stable(value: str, what: str) -> str:
    text = str(value)
    if _STABLE.fullmatch(text) is None:
        raise MachineSemanticsError(f"{what} must be a stable id")
    return text


def _hash64(value: str, what: str) -> str:
    text = str(value)
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise MachineSemanticsError(what)
    return text


def _hashes(values: Iterable[str], what: str) -> tuple[str, ...]:
    return tuple(sorted(set(_hash64(value, what) for value in values)))


def _fraction_object(value: Fraction) -> dict[str, list[str]]:
    return {"$rat": [str(value.numerator), str(value.denominator)]}


@dataclass(frozen=True, slots=True)
class NumericModelV0:
    model_id: str
    semantics_hash: str
    exact: bool
    properties: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", _stable(self.model_id, "model_id"))
        object.__setattr__(self, "semantics_hash", _hash64(self.semantics_hash, "numeric semantics hash"))
        if not isinstance(self.exact, bool):
            raise MachineSemanticsError("numeric model exact must be bool")
        properties = {} if self.properties is None else dict(self.properties)
        canonical_json(properties)
        object.__setattr__(self, "properties", properties)

    def profile_object(self) -> dict[str, object]:
        return {
            "schema": NUMERIC_MODEL_PROFILE_SCHEMA_V0,
            "semantics_hash": self.semantics_hash,
            "exact": self.exact,
            "properties": dict(self.properties or {}),
        }

    @property
    def numeric_model_hash(self) -> str:
        return canonical_hash(self.profile_object())

    def to_object(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "numeric_model_hash": self.numeric_model_hash,
            **{key: value for key, value in self.profile_object().items() if key != "schema"},
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class ExecutableFormatV0:
    format_id: str
    semantics_hash: str
    properties: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "format_id", _stable(self.format_id, "format_id"))
        object.__setattr__(self, "semantics_hash", _hash64(self.semantics_hash, "format semantics hash"))
        properties = {} if self.properties is None else dict(self.properties)
        canonical_json(properties)
        object.__setattr__(self, "properties", properties)

    def profile_object(self) -> dict[str, object]:
        return {
            "schema": EXECUTABLE_FORMAT_PROFILE_SCHEMA_V0,
            "semantics_hash": self.semantics_hash,
            "properties": dict(self.properties or {}),
        }

    @property
    def format_hash(self) -> str:
        return canonical_hash(self.profile_object())

    def to_object(self) -> dict[str, object]:
        return {
            "format_id": self.format_id,
            "format_hash": self.format_hash,
            **{key: value for key, value in self.profile_object().items() if key != "schema"},
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class MemorySpaceV0:
    space_id: str
    addressability: str
    capacity_bytes: Fraction | int | None = None
    properties: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "space_id", _stable(self.space_id, "space_id"))
        object.__setattr__(self, "addressability", _stable(self.addressability, "addressability"))
        if self.capacity_bytes is not None:
            capacity = self.capacity_bytes if isinstance(self.capacity_bytes, Fraction) else Fraction(self.capacity_bytes)
            if capacity < 0:
                raise MachineSemanticsError("capacity_bytes must be non-negative")
            object.__setattr__(self, "capacity_bytes", capacity)
        properties = {} if self.properties is None else dict(self.properties)
        canonical_json(properties)
        object.__setattr__(self, "properties", properties)

    def profile_object(self) -> dict[str, object]:
        return {
            "schema": MEMORY_SPACE_PROFILE_SCHEMA_V0,
            "addressability": self.addressability,
            "capacity_bytes": None if self.capacity_bytes is None else _fraction_object(self.capacity_bytes),
            "properties": dict(self.properties or {}),
        }

    @property
    def memory_space_hash(self) -> str:
        return canonical_hash(self.profile_object())

    def to_object(self) -> dict[str, object]:
        return {
            "space_id": self.space_id,
            "memory_space_hash": self.memory_space_hash,
            **{key: value for key, value in self.profile_object().items() if key != "schema"},
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class MachineCapabilityV0:
    capability_id: str
    semantic_hash: str
    capability_class: str
    numeric_model_hashes: tuple[str, ...] = ()
    properties: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_id", _stable(self.capability_id, "capability_id"))
        object.__setattr__(self, "semantic_hash", _hash64(self.semantic_hash, "semantic_hash"))
        object.__setattr__(self, "capability_class", _stable(self.capability_class, "capability_class"))
        object.__setattr__(self, "numeric_model_hashes", _hashes(self.numeric_model_hashes, "numeric model hash"))
        properties = {} if self.properties is None else dict(self.properties)
        canonical_json(properties)
        object.__setattr__(self, "properties", properties)

    def profile_object(self) -> dict[str, object]:
        return {
            "schema": MACHINE_CAPABILITY_PROFILE_SCHEMA_V0,
            "semantic_hash": self.semantic_hash,
            "numeric_model_hashes": list(self.numeric_model_hashes),
            "properties": dict(self.properties or {}),
        }

    @property
    def capability_profile_hash(self) -> str:
        return canonical_hash(self.profile_object())

    def to_object(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "capability_class": self.capability_class,
            "capability_profile_hash": self.capability_profile_hash,
            **{key: value for key, value in self.profile_object().items() if key != "schema"},
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())


@dataclass(frozen=True, slots=True)
class MachineFieldV0:
    machine_id: str
    capabilities: tuple[MachineCapabilityV0, ...] = ()
    numeric_models: tuple[NumericModelV0, ...] = ()
    memory_spaces: tuple[MemorySpaceV0, ...] = ()
    executable_formats: tuple[ExecutableFormatV0, ...] = ()
    topology_hash: str = ""
    properties: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_id", _stable(self.machine_id, "machine_id"))
        numeric_models = tuple(sorted(self.numeric_models, key=lambda item: (item.model_id, item.record_hash)))
        if len({item.model_id for item in numeric_models}) != len(numeric_models):
            raise MachineSemanticsError("duplicate numeric model id")
        known_numeric = {item.numeric_model_hash for item in numeric_models}

        capabilities = tuple(sorted(self.capabilities, key=lambda item: (item.capability_id, item.record_hash)))
        if len({item.capability_id for item in capabilities}) != len(capabilities):
            raise MachineSemanticsError("duplicate machine capability id")
        for capability in capabilities:
            missing = set(capability.numeric_model_hashes) - known_numeric
            if missing:
                raise MachineSemanticsError(
                    "machine capability references undefined numeric semantics: " + ",".join(sorted(missing))
                )

        memory_spaces = tuple(sorted(self.memory_spaces, key=lambda item: (item.space_id, item.record_hash)))
        if len({item.space_id for item in memory_spaces}) != len(memory_spaces):
            raise MachineSemanticsError("duplicate memory space id")

        formats = tuple(sorted(self.executable_formats, key=lambda item: (item.format_id, item.record_hash)))
        if len({item.format_id for item in formats}) != len(formats):
            raise MachineSemanticsError("duplicate executable format id")

        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "numeric_models", numeric_models)
        object.__setattr__(self, "memory_spaces", memory_spaces)
        object.__setattr__(self, "executable_formats", formats)
        object.__setattr__(self, "topology_hash", "" if not self.topology_hash else _hash64(self.topology_hash, "topology_hash"))
        properties = {} if self.properties is None else dict(self.properties)
        canonical_json(properties)
        object.__setattr__(self, "properties", properties)

    @property
    def capability_semantic_hashes(self) -> tuple[str, ...]:
        return tuple(sorted(set(item.semantic_hash for item in self.capabilities)))

    @property
    def numeric_model_hashes(self) -> tuple[str, ...]:
        return tuple(sorted(set(item.numeric_model_hash for item in self.numeric_models)))

    @property
    def executable_format_hashes(self) -> tuple[str, ...]:
        return tuple(sorted(set(item.format_hash for item in self.executable_formats)))

    @property
    def memory_space_hashes(self) -> tuple[str, ...]:
        return tuple(sorted(set(item.memory_space_hash for item in self.memory_spaces)))

    def supports_semantic_capability(self, semantic_hash: str) -> bool:
        return _hash64(semantic_hash, "semantic capability hash") in self.capability_semantic_hashes

    def supports_numeric_model(self, numeric_model_hash: str) -> bool:
        return _hash64(numeric_model_hash, "numeric_model_hash") in self.numeric_model_hashes

    def supports_executable_format(self, format_hash: str) -> bool:
        return _hash64(format_hash, "format_hash") in self.executable_format_hashes

    def profile_object(self) -> dict[str, object]:
        def unique_profiles(items: Iterable[Any]) -> list[dict[str, object]]:
            rows = {canonical_json(item.profile_object()): item.profile_object() for item in items}
            return [rows[key] for key in sorted(rows)]

        return {
            "schema": MACHINE_PROFILE_SCHEMA_V0,
            "capabilities": unique_profiles(self.capabilities),
            "numeric_models": unique_profiles(self.numeric_models),
            "memory_spaces": unique_profiles(self.memory_spaces),
            "executable_formats": unique_profiles(self.executable_formats),
            "topology_hash": self.topology_hash,
            "properties": dict(self.properties or {}),
        }

    @property
    def machine_profile_hash(self) -> str:
        return canonical_hash(self.profile_object())

    @property
    def machine_hash(self) -> str:
        return self.machine_profile_hash

    def to_object(self) -> dict[str, object]:
        return {
            "schema": MACHINE_SCHEMA_V0,
            "machine_profile_hash": self.machine_profile_hash,
            "machine_id": self.machine_id,
            "capabilities": [item.to_object() for item in self.capabilities],
            "numeric_models": [item.to_object() for item in self.numeric_models],
            "memory_spaces": [item.to_object() for item in self.memory_spaces],
            "executable_formats": [item.to_object() for item in self.executable_formats],
            "topology_hash": self.topology_hash,
            "properties": dict(self.properties or {}),
        }

    @property
    def record_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.machine.v0", self.to_object())


@dataclass(frozen=True, slots=True)
class MachineRequirementV0:
    required_capability_semantic_hashes: tuple[str, ...] = ()
    required_numeric_model_hashes: tuple[str, ...] = ()
    required_executable_format_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_capability_semantic_hashes", _hashes(self.required_capability_semantic_hashes, "required capability semantic hash"))
        object.__setattr__(self, "required_numeric_model_hashes", _hashes(self.required_numeric_model_hashes, "required numeric model hash"))
        object.__setattr__(self, "required_executable_format_hashes", _hashes(self.required_executable_format_hashes, "required executable format hash"))

    @property
    def required_numeric_model_ids(self) -> tuple[str, ...]:
        return self.required_numeric_model_hashes

    @property
    def required_executable_formats(self) -> tuple[str, ...]:
        return self.required_executable_format_hashes

    def to_object(self) -> dict[str, object]:
        return {
            "required_capability_semantic_hashes": list(self.required_capability_semantic_hashes),
            "required_numeric_model_hashes": list(self.required_numeric_model_hashes),
            "required_executable_format_hashes": list(self.required_executable_format_hashes),
        }


@dataclass(frozen=True, slots=True)
class MachineCompatibilityV0:
    compatible: bool
    machine_hash: str
    missing_capability_semantic_hashes: tuple[str, ...] = ()
    missing_numeric_model_hashes: tuple[str, ...] = ()
    missing_executable_format_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "machine_hash", _hash64(self.machine_hash, "machine_hash"))
        object.__setattr__(self, "missing_capability_semantic_hashes", _hashes(self.missing_capability_semantic_hashes, "missing capability hash"))
        object.__setattr__(self, "missing_numeric_model_hashes", _hashes(self.missing_numeric_model_hashes, "missing numeric model hash"))
        object.__setattr__(self, "missing_executable_format_hashes", _hashes(self.missing_executable_format_hashes, "missing executable format hash"))
        expected = not (
            self.missing_capability_semantic_hashes
            or self.missing_numeric_model_hashes
            or self.missing_executable_format_hashes
        )
        if self.compatible != expected:
            raise MachineSemanticsError("machine compatibility flag inconsistent")

    @property
    def missing_numeric_model_ids(self) -> tuple[str, ...]:
        return self.missing_numeric_model_hashes

    @property
    def missing_executable_formats(self) -> tuple[str, ...]:
        return self.missing_executable_format_hashes

    def to_object(self) -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_MACHINE_COMPATIBILITY_V0",
            "compatible": self.compatible,
            "machine_hash": self.machine_hash,
            "missing_capability_semantic_hashes": list(self.missing_capability_semantic_hashes),
            "missing_numeric_model_hashes": list(self.missing_numeric_model_hashes),
            "missing_executable_format_hashes": list(self.missing_executable_format_hashes),
        }

    @property
    def compatibility_hash(self) -> str:
        return canonical_hash(self.to_object())


def evaluate_machine_compatibility(machine: MachineFieldV0, requirement: MachineRequirementV0) -> MachineCompatibilityV0:
    missing_caps = tuple(sorted(set(requirement.required_capability_semantic_hashes) - set(machine.capability_semantic_hashes)))
    missing_numeric = tuple(sorted(set(requirement.required_numeric_model_hashes) - set(machine.numeric_model_hashes)))
    missing_formats = tuple(sorted(set(requirement.required_executable_format_hashes) - set(machine.executable_format_hashes)))
    return MachineCompatibilityV0(
        not (missing_caps or missing_numeric or missing_formats),
        machine.machine_hash,
        missing_caps,
        missing_numeric,
        missing_formats,
    )


__all__ = [
    "MACHINE_SCHEMA_V0",
    "MACHINE_PROFILE_SCHEMA_V0",
    "MACHINE_CAPABILITY_PROFILE_SCHEMA_V0",
    "NUMERIC_MODEL_PROFILE_SCHEMA_V0",
    "MEMORY_SPACE_PROFILE_SCHEMA_V0",
    "EXECUTABLE_FORMAT_PROFILE_SCHEMA_V0",
    "MachineSemanticsError",
    "MachineCapabilityV0",
    "NumericModelV0",
    "ExecutableFormatV0",
    "MemorySpaceV0",
    "MachineFieldV0",
    "MachineRequirementV0",
    "MachineCompatibilityV0",
    "evaluate_machine_compatibility",
]
