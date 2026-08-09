from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from threading import Lock
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .json_io import parse_strict_json
from .python_host_v1 import (
    CapabilityV1,
    PythonCapabilityContractV1,
    PythonProgramArtifactV1,
    _validate_bindings,
)
from .runtime_checkpoint_v2 import RuntimeCheckpointV2
from .runtime_v3 import EmittedEventV3
from .runtime_v3_optimized import OptimizedScriptRuntimeV3


@lru_cache(maxsize=64)
def _sealed_runtime_template(
    canonical_ir_json: str,
    source_semantic_hash: str,
) -> OptimizedScriptRuntimeV3:
    """Validate/compile one exact canonical artifact once per process.

    The cache key contains the complete canonical IR bytes plus the expected
    source hash; it never relies on a hash collision for identity. The cached
    runtime is private and never executed. Every host receives a deep copy with
    independent state and capability bindings.
    """

    parsed = parse_strict_json(canonical_ir_json)
    if not isinstance(parsed, dict):
        raise AssertionError("validated Python artifact stopped being an object")
    return OptimizedScriptRuntimeV3(
        parsed,
        {},
        expected_source_semantic_hash=source_semantic_hash,
    )


def _fresh_runtime(
    artifact: PythonProgramArtifactV1,
    capabilities: Mapping[str, CapabilityV1],
) -> OptimizedScriptRuntimeV3:
    runtime = deepcopy(
        _sealed_runtime_template(
            artifact.canonical_ir_json,
            artifact.source_semantic_hash,
        )
    )
    runtime.capabilities = dict(capabilities)
    return runtime


def clear_optimized_runtime_template_cache() -> None:
    _sealed_runtime_template.cache_clear()


def optimized_runtime_template_cache_stats() -> dict[str, int | None]:
    info = _sealed_runtime_template.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }


class OptimizedPythonRuntimeHostV1:
    """Opt-in least-authority Python host backed by the V1 execution plan.

    This class intentionally does not replace ``PythonRuntimeHostV1``. It uses
    the same immutable IR artifact, capability preflight, non-reentrant access
    rule and Runtime Checkpoint V2 contract while the optimized runtime remains
    under performance-polish admission.
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
        self._runtime = _fresh_runtime(artifact, self._capabilities)
        self._access_lock = Lock()

    @property
    def artifact(self) -> PythonProgramArtifactV1:
        return self._artifact

    @property
    def required_capabilities(self) -> tuple[PythonCapabilityContractV1, ...]:
        return self._artifact.required_capabilities

    @property
    def runtime_profile(self) -> str:
        return "optimized_execution_plan_v1"

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
            return RuntimeCheckpointV2.capture(self._runtime)  # type: ignore[arg-type]
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
            # RuntimeCheckpointV2 remains the certified reference restorer. It
            # validates exact program/source identity and yields semantic state.
            restored_reference = selected.restore_exact(
                self._artifact.ir(),
                self._capabilities,
            )
            optimized = _fresh_runtime(self._artifact, self._capabilities)
            for entity_id in sorted(restored_reference.entities):
                optimized.entities[entity_id].state.clear()
                optimized.entities[entity_id].state.update(
                    deepcopy(restored_reference.entities[entity_id].state)
                )
            self._runtime = optimized
        finally:
            self._access_lock.release()

    def _acquire_access(self, operation: str) -> None:
        if not self._access_lock.acquire(blocking=False):
            raise TevScriptError(
                "TEVS_PYTHON_V1_HOST_BUSY",
                "OptimizedPythonRuntimeHostV1 rejects concurrent or reentrant "
                f"{operation!r} access; serialize one host instance explicitly",
            )


__all__ = [
    "OptimizedPythonRuntimeHostV1",
    "clear_optimized_runtime_template_cache",
    "optimized_runtime_template_cache_stats",
]
