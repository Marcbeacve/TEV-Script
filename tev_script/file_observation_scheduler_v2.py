from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

from .diagnostics import TevScriptError
from .file_observation_acquisition_v2 import (
    FileReadAcquiredCallV2,
    MAX_FILE_READ_CALLS_V2,
)

MAX_FILE_READ_WORKERS_V2 = 64
FILE_READ_ASSEMBLY_POLICY_V2 = "canonical_request_order_v1"


@dataclass(frozen=True, slots=True)
class BoundedThreadFileReadAcquisitionStrategyV2:
    worker_count: int = 4

    def __post_init__(self) -> None:
        if isinstance(self.worker_count, bool) or not isinstance(self.worker_count, int) or not 1 <= self.worker_count <= MAX_FILE_READ_WORKERS_V2:
            raise TevScriptError(
                "TEVS_FILE_READ_ACQUISITION_WORKERS",
                f"worker_count must be 1..{MAX_FILE_READ_WORKERS_V2}",
            )

    def descriptor(self) -> dict[str, Any]:
        payload = {
            "schema": "TEV_SCRIPT_FILE_READ_ACQUISITION_SCHEDULER_V2_R1",
            "strategy": "bounded_thread_pool_v1",
            "worker_count": self.worker_count,
            "worker_count_is_semantic": False,
            "assembly_policy": FILE_READ_ASSEMBLY_POLICY_V2,
            "evidence_assembly_order": "request_call_index",
            "runtime_io": False,
        }
        payload["descriptor_hash"] = _hash(payload)
        return payload

    def run(
        self,
        calls: Sequence[tuple[int, Mapping[str, Any]]],
        acquire_call: Callable[[int, Mapping[str, Any]], FileReadAcquiredCallV2],
    ) -> Sequence[FileReadAcquiredCallV2]:
        call_tuple = tuple(calls)
        if not 1 <= len(call_tuple) <= MAX_FILE_READ_CALLS_V2:
            raise TevScriptError(
                "TEVS_FILE_READ_ACQUISITION_BOUND",
                f"scheduler requires 1..{MAX_FILE_READ_CALLS_V2} file.read calls",
            )
        expected_indexes = tuple(range(len(call_tuple)))
        observed_indexes = tuple(index for index, _call in call_tuple)
        if observed_indexes != expected_indexes:
            raise TevScriptError(
                "TEVS_FILE_READ_ACQUISITION_ORDER",
                "scheduler input must be in canonical request call-index order",
            )
        if self.worker_count == 1 or len(call_tuple) == 1:
            return tuple(acquire_call(index, call) for index, call in call_tuple)

        workers = min(self.worker_count, len(call_tuple))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="tev-file-read-v2") as executor:
            futures = tuple(executor.submit(acquire_call, index, call) for index, call in call_tuple)
            completed: list[FileReadAcquiredCallV2] = []
            try:
                # Observe results in request order. Completion timing has no authority
                # over evidence order or which diagnostic is surfaced first.
                for future in futures:
                    completed.append(future.result())
            except Exception:
                for future in futures[len(completed) + 1:]:
                    future.cancel()
                raise
        return tuple(completed)


def _hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
