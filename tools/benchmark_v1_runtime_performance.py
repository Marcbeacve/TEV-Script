from __future__ import annotations

import argparse
import gc
import json
from fractions import Fraction
from pathlib import Path
import platform
import statistics
import time
from typing import Callable

from tev_script.python_host_v1 import build_python_program_v1
from tev_script.runtime_v3 import ScriptRuntimeV3
from tev_script.runtime_v3_optimized import OptimizedScriptRuntimeV3

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads(
    (ROOT / "conformance" / "ir-v3-validator-cases.json").read_text(encoding="utf-8")
)["valid_program"]

COUNTER_SOURCE = b'''script Counter version "1.0.0";
entity E {
    state x: Int = 0;
    on inc {
        x = x + 1;
    }
}
'''

BRANCH_SOURCE = b'''script BranchCounter version "1.0.0";
entity E {
    state x: Int = 0;
    on inc(flag: Bool) {
        if flag {
            x = x + 1;
        }
    }
}
'''

CAPABILITY_SOURCE = b'''script CapabilityCounter version "1.0.0";
capability world.read() -> Int observation;
capability sink.write(Int) -> Unit effect;
entity E {
    state x: Int = 0;
    on pulse {
        x = world.read();
        call sink.write(x);
    }
}
'''


class DirectCounter:
    __slots__ = ("x",)

    def __init__(self) -> None:
        self.x = 0

    def invoke(self) -> None:
        self.x = self.x + 1


class DirectBranchCounter:
    __slots__ = ("x",)

    def __init__(self) -> None:
        self.x = 0

    def invoke(self) -> None:
        if True:
            self.x = self.x + 1


class DirectAlgebraic:
    __slots__ = ("count", "kind", "opt", "pair", "result")

    def __init__(self) -> None:
        self.count = 0
        self.kind = "A"
        self.opt: tuple[str, int | None] = ("None", None)
        self.pair: tuple[int, Fraction] = (1, Fraction(2, 1))
        self.result: tuple[str, int | str] = ("Ok", 0)

    def invoke(self) -> None:
        pair = (2, Fraction(3, 1))
        self.pair = pair
        self.count = pair[0]
        opt: tuple[str, int | None] = ("Some", 7)
        self.opt = opt
        flag = opt[0] == "Some"
        if not flag:  # pragma: no cover - mirrors TEST_VARIANT result
            raise AssertionError("unexpected Option variant")
        payload = opt[1]
        assert isinstance(payload, int)
        self.count = payload
        self.kind = "B"
        self.result = ("Err", "bad")


class CapabilityHost:
    __slots__ = ("last",)

    def __init__(self) -> None:
        self.last = 0

    def read(self) -> int:
        return 7

    def write(self, value: int) -> None:
        self.last = value


class DirectCapability:
    __slots__ = ("host", "x")

    def __init__(self) -> None:
        self.host = CapabilityHost()
        self.x = 0

    def invoke(self) -> None:
        self.x = self.host.read()
        self.host.write(self.x)


class TevCapability:
    __slots__ = ("host", "runtime")

    def __init__(self, runtime_type: type, ir: dict) -> None:
        self.host = CapabilityHost()
        self.runtime = runtime_type(
            ir,
            {
                "world.read": self.host.read,
                "sink.write": self.host.write,
            },
        )

    def invoke(self) -> None:
        self.runtime.invoke("E", "pulse")


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
            start = time.perf_counter_ns()
            for _ in range(events):
                invoke(subject)
            samples.append(time.perf_counter_ns() - start)
        finally:
            gc.enable()
    return _median(samples), samples


def _startup(factory: Callable[[], object], *, rounds: int = 101) -> tuple[int, list[int]]:
    samples: list[int] = []
    for _ in range(rounds):
        start = time.perf_counter_ns()
        factory()
        samples.append(time.perf_counter_ns() - start)
    return _median(samples), samples


def _result_row(
    *,
    name: str,
    events: int,
    direct_factory: Callable[[], object],
    direct_invoke: Callable[[object], None],
    reference_factory: Callable[[], object],
    reference_invoke: Callable[[object], None],
    optimized_factory: Callable[[], object],
    optimized_invoke: Callable[[object], None],
    rounds: int,
    warmup: int,
) -> dict[str, object]:
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
    optimized_startup, optimized_startup_samples = _startup(optimized_factory)
    return {
        "name": name,
        "events": events,
        "direct_ms": direct_ns / 1e6,
        "reference_ms": reference_ns / 1e6,
        "optimized_ms": optimized_ns / 1e6,
        "reference_vs_direct": reference_ns / direct_ns,
        "optimized_vs_direct": optimized_ns / direct_ns,
        "optimized_speedup_vs_reference": reference_ns / optimized_ns,
        "direct_ns_per_event": direct_ns / events,
        "reference_ns_per_event": reference_ns / events,
        "optimized_ns_per_event": optimized_ns / events,
        "direct_events_per_second": 1e9 / (direct_ns / events),
        "reference_events_per_second": 1e9 / (reference_ns / events),
        "optimized_events_per_second": 1e9 / (optimized_ns / events),
        "reference_startup_us": reference_startup / 1e3,
        "optimized_startup_us": optimized_startup / 1e3,
        "optimized_startup_vs_reference": optimized_startup / reference_startup,
        "reference_startup_samples_us": [round(value / 1e3, 3) for value in reference_startup_samples],
        "optimized_startup_samples_us": [round(value / 1e3, 3) for value in optimized_startup_samples],
        "direct_samples_ms": [round(value / 1e6, 3) for value in direct_samples],
        "reference_samples_ms": [round(value / 1e6, 3) for value in reference_samples],
        "optimized_samples_ms": [round(value / 1e6, 3) for value in optimized_samples],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="TEV Script V1 runtime performance comparison")
    parser.add_argument("--events", type=int, default=200_000)
    parser.add_argument("--rich-events", type=int, default=50_000)
    parser.add_argument("--capability-events", type=int, default=100_000)
    parser.add_argument("--rounds", type=int, default=7)
    parser.add_argument("--warmup", type=int, default=5_000)
    args = parser.parse_args()

    compile_start = time.perf_counter_ns()
    counter_artifact = build_python_program_v1({"Counter.tevs": COUNTER_SOURCE})
    branch_artifact = build_python_program_v1({"BranchCounter.tevs": BRANCH_SOURCE})
    capability_artifact = build_python_program_v1({"CapabilityCounter.tevs": CAPABILITY_SOURCE})
    compile_ns = time.perf_counter_ns() - compile_start

    counter_ir = counter_artifact.ir()
    branch_ir = branch_artifact.ir()
    capability_ir = capability_artifact.ir()

    workloads = [
        _result_row(
            name="counter",
            events=args.events,
            direct_factory=DirectCounter,
            direct_invoke=lambda subject: subject.invoke(),
            reference_factory=lambda: ScriptRuntimeV3(counter_ir),
            reference_invoke=lambda subject: subject.invoke("E", "inc"),
            optimized_factory=lambda: OptimizedScriptRuntimeV3(counter_ir),
            optimized_invoke=lambda subject: subject.invoke("E", "inc"),
            rounds=args.rounds,
            warmup=args.warmup,
        ),
        _result_row(
            name="branch_true",
            events=args.events,
            direct_factory=DirectBranchCounter,
            direct_invoke=lambda subject: subject.invoke(),
            reference_factory=lambda: ScriptRuntimeV3(branch_ir),
            reference_invoke=lambda subject: subject.invoke("E", "inc", True),
            optimized_factory=lambda: OptimizedScriptRuntimeV3(branch_ir),
            optimized_invoke=lambda subject: subject.invoke("E", "inc", True),
            rounds=args.rounds,
            warmup=args.warmup,
        ),
        _result_row(
            name="algebraic_start",
            events=args.rich_events,
            direct_factory=DirectAlgebraic,
            direct_invoke=lambda subject: subject.invoke(),
            reference_factory=lambda: ScriptRuntimeV3(BASE),
            reference_invoke=lambda subject: subject.invoke("E", "start"),
            optimized_factory=lambda: OptimizedScriptRuntimeV3(BASE),
            optimized_invoke=lambda subject: subject.invoke("E", "start"),
            rounds=args.rounds,
            warmup=min(args.warmup, 1_000),
        ),
        _result_row(
            name="capability_int",
            events=args.capability_events,
            direct_factory=DirectCapability,
            direct_invoke=lambda subject: subject.invoke(),
            reference_factory=lambda: TevCapability(ScriptRuntimeV3, capability_ir),
            reference_invoke=lambda subject: subject.invoke(),
            optimized_factory=lambda: TevCapability(OptimizedScriptRuntimeV3, capability_ir),
            optimized_invoke=lambda subject: subject.invoke(),
            rounds=args.rounds,
            warmup=min(args.warmup, 2_000),
        ),
    ]

    # Fresh semantic checks are deliberately outside timing.
    direct_counter = DirectCounter()
    reference_counter = ScriptRuntimeV3(counter_ir)
    optimized_counter = OptimizedScriptRuntimeV3(counter_ir)
    for _ in range(args.events):
        direct_counter.invoke()
        reference_counter.invoke("E", "inc")
        optimized_counter.invoke("E", "inc")
    if not (
        direct_counter.x
        == reference_counter.state("E")["x"]
        == optimized_counter.state("E")["x"]
        == args.events
    ):
        raise RuntimeError("counter semantic mismatch")

    reference_rich = ScriptRuntimeV3(BASE)
    optimized_rich = OptimizedScriptRuntimeV3(BASE)
    reference_rich.invoke("E", "start")
    optimized_rich.invoke("E", "start")
    if reference_rich.canonical_state("E") != optimized_rich.canonical_state("E"):
        raise RuntimeError("algebraic semantic mismatch")

    reference_capability = TevCapability(ScriptRuntimeV3, capability_ir)
    optimized_capability = TevCapability(OptimizedScriptRuntimeV3, capability_ir)
    reference_capability.invoke()
    optimized_capability.invoke()
    if (
        reference_capability.runtime.state("E")["x"] != 7
        or optimized_capability.runtime.state("E")["x"] != 7
        or reference_capability.host.last != 7
        or optimized_capability.host.last != 7
    ):
        raise RuntimeError("capability semantic mismatch")

    result = {
        "schema": "TEV_SCRIPT_V1_RUNTIME_PERFORMANCE_V2",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "rounds": args.rounds,
        "warmup": args.warmup,
        "compile_three_programs_ms": compile_ns / 1e6,
        "same_final_state": True,
        "workloads": workloads,
        "counter_ir_semantic_hash": counter_artifact.ir_semantic_hash,
        "counter_source_semantic_hash": counter_artifact.source_semantic_hash,
        "branch_ir_semantic_hash": branch_artifact.ir_semantic_hash,
        "capability_ir_semantic_hash": capability_artifact.ir_semantic_hash,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
