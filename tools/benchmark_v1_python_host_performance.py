from __future__ import annotations

import argparse
import gc
import json
import platform
import statistics
import time
from typing import Callable

from tev_script.python_host_v1 import PythonRuntimeHostV1, build_python_program_v1
from tev_script.python_host_v1_optimized import (
    OptimizedPythonRuntimeHostV1,
    clear_optimized_runtime_template_cache,
    optimized_runtime_template_cache_stats,
)

COUNTER = b'''script Counter version "1.0.0";
entity E {
    state count: Int = 0;
    on inc { count = count + 1; }
}
'''

SENSOR = b'''script Sensor version "1.0.0";
capability world.read() -> Int observation;
entity E {
    state value: Int = 0;
    on update { value = world.read(); }
}
'''


class DirectCounter:
    __slots__ = ("count",)

    def __init__(self) -> None:
        self.count = 0

    def invoke(self) -> None:
        self.count += 1


class DirectSensor:
    __slots__ = ("value",)

    def __init__(self) -> None:
        self.value = 0

    @staticmethod
    def read() -> int:
        return 7

    def invoke(self) -> None:
        self.value = self.read()


def _median(values: list[int]) -> int:
    return int(statistics.median(values))


def _bench(
    factory: Callable[[], object],
    invoke: Callable[[object], None],
    *,
    events: int,
    rounds: int,
    warmup: int,
) -> tuple[int, list[int]]:
    samples: list[int] = []
    for _ in range(rounds):
        warm = factory()
        for _ in range(warmup):
            invoke(warm)
        subject = factory()
        gc.disable()
        try:
            started = time.perf_counter_ns()
            for _ in range(events):
                invoke(subject)
            samples.append(time.perf_counter_ns() - started)
        finally:
            gc.enable()
    return _median(samples), samples


def _startup(
    factory: Callable[[], object],
    *,
    rounds: int = 101,
    before_each: Callable[[], None] | None = None,
) -> tuple[int, list[int]]:
    samples: list[int] = []
    for _ in range(rounds):
        if before_each is not None:
            before_each()
        started = time.perf_counter_ns()
        factory()
        samples.append(time.perf_counter_ns() - started)
    return _median(samples), samples


def _warm_startup(
    factory: Callable[[], object],
    *,
    rounds: int = 101,
) -> tuple[int, list[int]]:
    clear_optimized_runtime_template_cache()
    factory()  # seed exactly one sealed template before measuring reuse
    return _startup(factory, rounds=rounds)


def _row(
    name: str,
    *,
    events: int,
    rounds: int,
    warmup: int,
    direct_factory: Callable[[], object],
    direct_invoke: Callable[[object], None],
    reference_factory: Callable[[], object],
    reference_invoke: Callable[[object], None],
    optimized_factory: Callable[[], object],
    optimized_invoke: Callable[[object], None],
) -> dict[str, object]:
    clear_optimized_runtime_template_cache()
    direct_ns, direct_samples = _bench(
        direct_factory,
        direct_invoke,
        events=events,
        rounds=rounds,
        warmup=warmup,
    )
    reference_ns, reference_samples = _bench(
        reference_factory,
        reference_invoke,
        events=events,
        rounds=rounds,
        warmup=warmup,
    )
    optimized_ns, optimized_samples = _bench(
        optimized_factory,
        optimized_invoke,
        events=events,
        rounds=rounds,
        warmup=warmup,
    )

    reference_startup, reference_startup_samples = _startup(reference_factory)
    optimized_cold_startup, optimized_cold_samples = _startup(
        optimized_factory,
        before_each=clear_optimized_runtime_template_cache,
    )
    optimized_warm_startup, optimized_warm_samples = _warm_startup(optimized_factory)
    cache_stats = optimized_runtime_template_cache_stats()

    return {
        "name": name,
        "events": events,
        "direct_ns_per_event": direct_ns / events,
        "reference_ns_per_event": reference_ns / events,
        "optimized_ns_per_event": optimized_ns / events,
        "reference_vs_direct": reference_ns / direct_ns,
        "optimized_vs_direct": optimized_ns / direct_ns,
        "optimized_speedup_vs_reference": reference_ns / optimized_ns,
        "reference_startup_us": reference_startup / 1e3,
        "optimized_cold_startup_us": optimized_cold_startup / 1e3,
        "optimized_warm_startup_us": optimized_warm_startup / 1e3,
        "optimized_cold_startup_vs_reference": optimized_cold_startup / reference_startup,
        "optimized_warm_startup_vs_reference": optimized_warm_startup / reference_startup,
        "direct_samples_ms": [round(value / 1e6, 3) for value in direct_samples],
        "reference_samples_ms": [round(value / 1e6, 3) for value in reference_samples],
        "optimized_samples_ms": [round(value / 1e6, 3) for value in optimized_samples],
        "reference_startup_samples_us": [round(value / 1e3, 3) for value in reference_startup_samples],
        "optimized_cold_startup_samples_us": [round(value / 1e3, 3) for value in optimized_cold_samples],
        "optimized_warm_startup_samples_us": [round(value / 1e3, 3) for value in optimized_warm_samples],
        "optimized_template_cache_after_warm_campaign": cache_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="TEV Script V1 Python host performance")
    parser.add_argument("--events", type=int, default=200_000)
    parser.add_argument("--capability-events", type=int, default=100_000)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=5_000)
    args = parser.parse_args()

    counter = build_python_program_v1({"counter.tevs": COUNTER})
    sensor = build_python_program_v1({"sensor.tevs": SENSOR})

    counter_row = _row(
        "host_counter",
        events=args.events,
        rounds=args.rounds,
        warmup=args.warmup,
        direct_factory=DirectCounter,
        direct_invoke=lambda subject: subject.invoke(),
        reference_factory=lambda: PythonRuntimeHostV1(counter),
        reference_invoke=lambda subject: subject.invoke("E", "inc"),
        optimized_factory=lambda: OptimizedPythonRuntimeHostV1(counter),
        optimized_invoke=lambda subject: subject.invoke("E", "inc"),
    )
    sensor_row = _row(
        "host_capability_int",
        events=args.capability_events,
        rounds=args.rounds,
        warmup=min(args.warmup, 2_000),
        direct_factory=DirectSensor,
        direct_invoke=lambda subject: subject.invoke(),
        reference_factory=lambda: PythonRuntimeHostV1(sensor, {"world.read": lambda: 7}),
        reference_invoke=lambda subject: subject.invoke("E", "update"),
        optimized_factory=lambda: OptimizedPythonRuntimeHostV1(sensor, {"world.read": lambda: 7}),
        optimized_invoke=lambda subject: subject.invoke("E", "update"),
    )

    direct = DirectCounter()
    reference = PythonRuntimeHostV1(counter)
    optimized = OptimizedPythonRuntimeHostV1(counter)
    for _ in range(args.events):
        direct.invoke()
        reference.invoke("E", "inc")
        optimized.invoke("E", "inc")
    if not (
        direct.count
        == reference.state("E")["count"]
        == optimized.state("E")["count"]
        == args.events
    ):
        raise RuntimeError("host counter semantic mismatch")

    reference_sensor = PythonRuntimeHostV1(sensor, {"world.read": lambda: 7})
    optimized_sensor = OptimizedPythonRuntimeHostV1(sensor, {"world.read": lambda: 7})
    reference_sensor.invoke("E", "update")
    optimized_sensor.invoke("E", "update")
    if reference_sensor.state("E") != optimized_sensor.state("E"):
        raise RuntimeError("host capability semantic mismatch")

    result = {
        "schema": "TEV_SCRIPT_V1_PYTHON_HOST_PERFORMANCE_V2",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "same_final_state": True,
        "startup_semantics": {
            "reference": "full_reference_host_construction",
            "optimized_cold": "empty_execution_template_cache",
            "optimized_warm": "same_exact_canonical_artifact_template_reused",
        },
        "workloads": [counter_row, sensor_row],
        "counter_ir_semantic_hash": counter.ir_semantic_hash,
        "sensor_ir_semantic_hash": sensor.ir_semantic_hash,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
