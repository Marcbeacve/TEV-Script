from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping, Sequence

from .canonical import canonical_json
from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .json_io import parse_strict_json
from .pipeline_v1 import compile_v1_mapping_to_ir_v3, compile_v1_paths_to_ir_v3
from .runtime_checkpoint_v2 import RuntimeCheckpointV2
from .runtime_v3 import EmittedEventV3, ScriptRuntimeV3

CapabilityV1 = Callable[..., Any]


@dataclass(frozen=True, slots=True, order=True)
class PythonCapabilityContractV1:
    capability_id: str
    parameters: tuple[str, ...]
    return_type: str
    kind: str


@dataclass(frozen=True, slots=True)
class PythonProgramArtifactV1:
    """Immutable Python-host view of one validated canonical IR V3 program.

    Production execution is intentionally IR-only. Source compilation is kept
    in the explicit build helpers below and is never performed by
    PythonRuntimeHostV1.
    """

    canonical_ir_json: str
    program_id: str
    source_semantic_hash: str
    ir_semantic_hash: str
    required_capabilities: tuple[PythonCapabilityContractV1, ...]

    @classmethod
    def from_ir(cls, ir: Mapping[str, Any]) -> "PythonProgramArtifactV1":
        value = dict(ir)
        validate_program_ir_v3(value)
        canonical = canonical_json(value)
        return cls(
            canonical_ir_json=canonical,
            program_id=str(value["program_id"]),
            source_semantic_hash=str(value["source_semantic_hash"]),
            ir_semantic_hash=str(value["semantic_hash"]),
            required_capabilities=_collect_capabilities(value),
        )

    @classmethod
    def parse(cls, text: str) -> "PythonProgramArtifactV1":
        parsed = parse_strict_json(text)
        if not isinstance(parsed, dict):
            raise TevScriptError(
                "TEVS_PYTHON_V1_ARTIFACT_SHAPE",
                "Python production artifact must be a JSON object",
            )
        canonical = canonical_json(parsed)
        # In-memory canonical JSON has no terminator. Repository artifact
        # writers persist exactly one final LF; both spellings represent the
        # same canonical document and no other whitespace is accepted.
        if text not in {canonical, canonical + "\n"}:
            raise TevScriptError(
                "TEVS_PYTHON_V1_ARTIFACT_CANONICAL",
                "Python production artifact must use canonical IR V3 JSON with at most one final LF",
            )
        return cls.from_ir(parsed)

    def ir(self) -> dict[str, Any]:
        parsed = parse_strict_json(self.canonical_ir_json)
        if not isinstance(parsed, dict):
            raise AssertionError("validated IR V3 artifact stopped being an object")
        return parsed


def build_python_program_v1(
    sources: Mapping[str, bytes],
) -> PythonProgramArtifactV1:
    """Reference build-time source -> IR V3 path for the Python host."""

    compilation = compile_v1_mapping_to_ir_v3(sources)
    return PythonProgramArtifactV1.from_ir(compilation.target.ir)


def build_python_program_v1_paths(
    paths: Sequence[str | Path],
) -> PythonProgramArtifactV1:
    """Reference build-time path set -> IR V3 path for the Python host."""

    compilation = compile_v1_paths_to_ir_v3(paths)
    return PythonProgramArtifactV1.from_ir(compilation.target.ir)


class PythonRuntimeHostV1:
    """Least-authority production host for precompiled TEV Script IR V3.

    The host has no source compiler entry point and receives all physical
    authority through an explicit capability map. By default it rejects both
    missing and unused capability bindings before execution.

    One host instance is one serialized TEV execution domain. Concurrent or
    reentrant state/runtime access fails closed instead of introducing an
    implicit scheduling semantic outside the TEV event machine.
    """

    def __init__(
        self,
        artifact: PythonProgramArtifactV1,
        capabilities: Mapping[str, CapabilityV1] | None = None,
        *,
        reject_unused_capabilities: bool = True,
    ) -> None:
        self._artifact = artifact
        self._capabilities = _validate_bindings(
            artifact,
            capabilities or {},
            reject_unused=reject_unused_capabilities,
        )
        self._runtime = ScriptRuntimeV3(
            artifact.ir(),
            self._capabilities,
            expected_source_semantic_hash=artifact.source_semantic_hash,
        )
        self._access_lock = Lock()

    @property
    def artifact(self) -> PythonProgramArtifactV1:
        return self._artifact

    @property
    def required_capabilities(self) -> tuple[PythonCapabilityContractV1, ...]:
        return self._artifact.required_capabilities

    def invoke(
        self,
        entity_id: str,
        event_id: str,
        *arguments: Any,
    ) -> tuple[EmittedEventV3, ...]:
        self._acquire_access("invoke")
        try:
            return self._runtime.invoke(entity_id, event_id, *arguments)
        finally:
            self._access_lock.release()

    def state(self, entity_id: str) -> dict[str, Any]:
        self._acquire_access("state")
        try:
            return self._runtime.state(entity_id)
        finally:
            self._access_lock.release()

    def canonical_state(self, entity_id: str) -> dict[str, Any]:
        self._acquire_access("canonical_state")
        try:
            return self._runtime.canonical_state(entity_id)
        finally:
            self._access_lock.release()

    def capture_checkpoint(self) -> RuntimeCheckpointV2:
        self._acquire_access("capture_checkpoint")
        try:
            return RuntimeCheckpointV2.capture(self._runtime)
        finally:
            self._access_lock.release()

    def capture_checkpoint_json(self) -> str:
        return self.capture_checkpoint().to_canonical_json()

    def restore_checkpoint(
        self,
        checkpoint: RuntimeCheckpointV2 | str,
    ) -> None:
        selected = (
            RuntimeCheckpointV2.parse(checkpoint)
            if isinstance(checkpoint, str)
            else checkpoint
        )
        self._acquire_access("restore_checkpoint")
        try:
            self._runtime = selected.restore_exact(
                self._artifact.ir(),
                self._capabilities,
            )
        finally:
            self._access_lock.release()

    def _acquire_access(self, operation: str) -> None:
        if not self._access_lock.acquire(blocking=False):
            raise TevScriptError(
                "TEVS_PYTHON_V1_HOST_BUSY",
                f"PythonRuntimeHostV1 rejects concurrent or reentrant {operation!r} access; serialize one host instance explicitly",
            )


def _collect_capabilities(
    ir: Mapping[str, Any],
) -> tuple[PythonCapabilityContractV1, ...]:
    contracts: dict[str, PythonCapabilityContractV1] = {}
    for raw_entity in ir["entities"]:
        for raw_contract in raw_entity["capabilities"]:
            contract = PythonCapabilityContractV1(
                capability_id=str(raw_contract["capability_id"]),
                parameters=tuple(str(item) for item in raw_contract["parameters"]),
                return_type=str(raw_contract["return_type"]),
                kind=str(raw_contract["kind"]),
            )
            previous = contracts.get(contract.capability_id)
            if previous is not None and previous != contract:
                raise TevScriptError(
                    "TEVS_PYTHON_V1_CAPABILITY_CONTRACT_CONFLICT",
                    f"conflicting runtime capability contracts for {contract.capability_id!r}",
                )
            contracts[contract.capability_id] = contract
    return tuple(contracts[key] for key in sorted(contracts))


def _validate_bindings(
    artifact: PythonProgramArtifactV1,
    capabilities: Mapping[str, CapabilityV1],
    *,
    reject_unused: bool,
) -> dict[str, CapabilityV1]:
    bindings = dict(capabilities)
    for capability_id, binding in bindings.items():
        if not isinstance(capability_id, str) or not capability_id:
            raise TevScriptError(
                "TEVS_PYTHON_V1_CAPABILITY_BINDING_ID",
                "capability binding ids must be non-empty strings",
            )
        if not callable(binding):
            raise TevScriptError(
                "TEVS_PYTHON_V1_CAPABILITY_BINDING_CALLABLE",
                f"capability {capability_id!r} is not callable",
            )

    required = {item.capability_id for item in artifact.required_capabilities}
    observed = set(bindings)
    missing = sorted(required - observed)
    if missing:
        raise TevScriptError(
            "TEVS_PYTHON_V1_CAPABILITY_MISSING",
            f"missing required capabilities: {missing}",
        )
    unused = sorted(observed - required)
    if reject_unused and unused:
        raise TevScriptError(
            "TEVS_PYTHON_V1_CAPABILITY_UNUSED",
            f"unused capability bindings rejected by least-authority policy: {unused}",
        )
    return {key: bindings[key] for key in sorted(bindings)}
