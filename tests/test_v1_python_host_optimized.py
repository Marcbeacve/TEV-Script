from __future__ import annotations

import unittest

from tev_script.diagnostics import TevScriptError
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


class V1OptimizedPythonHostTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_optimized_runtime_template_cache()

    def test_repeated_counter_matches_reference_host(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        reference = PythonRuntimeHostV1(artifact)
        optimized = OptimizedPythonRuntimeHostV1(artifact)

        for _ in range(10_000):
            self.assertEqual(reference.invoke("E", "inc"), optimized.invoke("E", "inc"))

        self.assertEqual(reference.state("E"), optimized.state("E"))
        self.assertEqual(reference.canonical_state("E"), optimized.canonical_state("E"))
        self.assertEqual(optimized.runtime_profile, "optimized_execution_plan_v1")

    def test_sealed_template_cache_reuses_analysis_without_sharing_state(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        before = optimized_runtime_template_cache_stats()
        self.assertEqual(before["hits"], 0)
        self.assertEqual(before["misses"], 0)
        self.assertEqual(before["currsize"], 0)

        first = OptimizedPythonRuntimeHostV1(artifact)
        after_first = optimized_runtime_template_cache_stats()
        self.assertEqual(after_first["misses"], 1)
        self.assertEqual(after_first["hits"], 0)
        self.assertEqual(after_first["currsize"], 1)

        second = OptimizedPythonRuntimeHostV1(artifact)
        after_second = optimized_runtime_template_cache_stats()
        self.assertEqual(after_second["misses"], 1)
        self.assertGreaterEqual(int(after_second["hits"] or 0), 1)
        self.assertEqual(after_second["currsize"], 1)

        for _ in range(7):
            first.invoke("E", "inc")
        self.assertEqual(first.state("E")["count"], 7)
        self.assertEqual(second.state("E")["count"], 0)

        second.invoke("E", "inc")
        self.assertEqual(first.state("E")["count"], 7)
        self.assertEqual(second.state("E")["count"], 1)

    def test_sealed_template_does_not_share_capability_bindings(self) -> None:
        artifact = build_python_program_v1({"sensor.tevs": SENSOR})
        first = OptimizedPythonRuntimeHostV1(artifact, {"world.read": lambda: 7})
        second = OptimizedPythonRuntimeHostV1(artifact, {"world.read": lambda: 11})

        first.invoke("E", "update")
        second.invoke("E", "update")
        self.assertEqual(first.state("E")["value"], 7)
        self.assertEqual(second.state("E")["value"], 11)

        stats = optimized_runtime_template_cache_stats()
        self.assertEqual(stats["misses"], 1)
        self.assertGreaterEqual(int(stats["hits"] or 0), 1)

    def test_checkpoint_capture_and_restore_match_reference_host(self) -> None:
        artifact = build_python_program_v1({"counter.tevs": COUNTER})
        reference = PythonRuntimeHostV1(artifact)
        optimized = OptimizedPythonRuntimeHostV1(artifact)

        for _ in range(17):
            reference.invoke("E", "inc")
            optimized.invoke("E", "inc")

        reference_checkpoint = reference.capture_checkpoint_json()
        optimized_checkpoint = optimized.capture_checkpoint_json()
        self.assertEqual(reference_checkpoint, optimized_checkpoint)

        for _ in range(3):
            reference.invoke("E", "inc")
            optimized.invoke("E", "inc")
        self.assertEqual(reference.state("E")["count"], 20)
        self.assertEqual(optimized.state("E")["count"], 20)

        reference.restore_checkpoint(reference_checkpoint)
        optimized.restore_checkpoint(optimized_checkpoint)
        self.assertEqual(reference.state("E"), optimized.state("E"))
        self.assertEqual(optimized.state("E")["count"], 17)

        reference.invoke("E", "inc")
        optimized.invoke("E", "inc")
        self.assertEqual(reference.state("E"), optimized.state("E"))

    def test_least_authority_preflight_matches_reference_host(self) -> None:
        artifact = build_python_program_v1({"sensor.tevs": SENSOR})

        with self.assertRaises(TevScriptError) as reference_missing:
            PythonRuntimeHostV1(artifact)
        with self.assertRaises(TevScriptError) as optimized_missing:
            OptimizedPythonRuntimeHostV1(artifact)
        self.assertEqual(
            reference_missing.exception.diagnostic.code,
            optimized_missing.exception.diagnostic.code,
        )

        reference = PythonRuntimeHostV1(artifact, {"world.read": lambda: 7})
        optimized = OptimizedPythonRuntimeHostV1(artifact, {"world.read": lambda: 7})
        reference.invoke("E", "update")
        optimized.invoke("E", "update")
        self.assertEqual(reference.state("E"), optimized.state("E"))

        with self.assertRaises(TevScriptError) as optimized_unused:
            OptimizedPythonRuntimeHostV1(
                artifact,
                {"world.read": lambda: 7, "extra": lambda: 1},
            )
        self.assertEqual(
            optimized_unused.exception.diagnostic.code,
            "TEVS_PYTHON_V1_CAPABILITY_UNUSED",
        )

    def test_capability_cannot_reenter_optimized_host(self) -> None:
        artifact = build_python_program_v1({"sensor.tevs": SENSOR})
        holder: dict[str, OptimizedPythonRuntimeHostV1] = {}

        def reentrant_read() -> int:
            holder["host"].state("E")
            return 7

        host = OptimizedPythonRuntimeHostV1(
            artifact,
            {"world.read": reentrant_read},
        )
        holder["host"] = host

        with self.assertRaises(TevScriptError) as busy:
            host.invoke("E", "update")
        self.assertEqual(busy.exception.diagnostic.code, "TEVS_PYTHON_V1_HOST_BUSY")
        self.assertEqual(host.state("E")["value"], 0)


if __name__ == "__main__":
    unittest.main()
